/**
 * api-client.js — Client REST (fetch, fetchSSE, retry, intercepteur 401).
 */
import { getAccessToken, refreshAccessToken, forceLogout } from './auth.js';

// --- Configuration retry ---
const RETRY_CONFIG = { maxRetries: 2, baseDelay: 1000 };

// --- Mapping codes d'erreur ---
const ERROR_MESSAGES = {
    AUTH_REQUIRED: 'Session expirée, veuillez vous reconnecter.',
    FORBIDDEN: "Vous n'avez pas accès à cette session.",
    SESSION_NOT_FOUND: 'Session introuvable. Créez-en une nouvelle.',
    OMNIVOICE_UNAVAILABLE: 'Service TTS indisponible. Vérifiez que OmniVoice est démarré.',
    LLM_RATE_LIMITED: 'Limite de requêtes atteinte. Réessayez dans quelques minutes.',
    IMPORT_FAILED: "Échec de l'import. Vérifiez le format du fichier.",
    EXPORT_IN_PROGRESS: 'Un export est déjà en cours. Veuillez patienter.',
    TTS_BUSY: 'Le moteur de synthèse vocale est occupé. Réessayez dans quelques secondes.',
    TTS_TIMEOUT: 'La génération a dépassé le délai maximum. Essayez avec un texte plus court.',
};

function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

function getErrorMessage(code) {
    return ERROR_MESSAGES[code] || 'Une erreur est survenue. Veuillez reessayer.';
}

function getHeaders(extra = {}) {
    const headers = {
        'Authorization': `Bearer ${getAccessToken()}`,
        'X-Thread-Id': localStorage.getItem('thread_id') || '',
        ...extra,
    };
    return headers;
}

// --- Request avec retry et intercepteur 401 ---

export async function apiRequest(url, options = {}) {
    const mergedOptions = {
        ...options,
        headers: {
            ...getHeaders(),
            ...options.headers,
        },
    };

    for (let attempt = 0; attempt <= RETRY_CONFIG.maxRetries; attempt++) {
        try {
            const response = await fetch(url, mergedOptions);

            // Intercepteur 401
            if (response.status === 401) {
                try {
                    await refreshAccessToken();
                    // Rejouer avec nouveau token
                    mergedOptions.headers['Authorization'] = `Bearer ${getAccessToken()}`;
                    return fetch(url, mergedOptions);
                } catch {
                    forceLogout('Session expirée, veuillez vous reconnecter.');
                    throw new Error('AUTH_EXPIRED');
                }
            }

            // Pas de retry sur 4xx, 503 (TTS occupe) et 504 (timeout)
            const NO_RETRY = response.status === 503 || response.status === 504;
            if (response.ok || response.status < 500 || NO_RETRY) return response;

            // Retry sur 500, 502 (erreurs transitoires)
            if (attempt < RETRY_CONFIG.maxRetries) {
                await sleep(RETRY_CONFIG.baseDelay * (attempt + 1));
                continue;
            }
            return response;
        } catch (networkError) {
            if (networkError.message === 'AUTH_EXPIRED') throw networkError;
            if (attempt === RETRY_CONFIG.maxRetries) throw networkError;
            await sleep(RETRY_CONFIG.baseDelay * (attempt + 1));
        }
    }
}

// --- Helpers JSON ---

export async function apiGet(url) {
    const response = await apiRequest(url);
    return response.json();
}

export async function apiPost(url, body) {
    const response = await apiRequest(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
    });
    return response.json();
}

export async function apiDelete(url) {
    const response = await apiRequest(url, { method: 'DELETE' });
    const data = await response.json();
    if (data.error) throw new Error(data.error.message);
    return data;
}

// --- Upload multipart avec progression (XHR) ---

export function uploadFile(url, formData, onProgress) {
    return new Promise((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        xhr.open('POST', url);

        xhr.setRequestHeader('Authorization', `Bearer ${getAccessToken()}`);
        const threadId = localStorage.getItem('thread_id');
        if (threadId) xhr.setRequestHeader('X-Thread-Id', threadId);

        xhr.upload.addEventListener('progress', (e) => {
            if (e.lengthComputable && onProgress) {
                onProgress(Math.round((e.loaded / e.total) * 100));
            }
        });

        xhr.addEventListener('load', () => {
            if (xhr.status >= 200 && xhr.status < 300) {
                try {
                    resolve(JSON.parse(xhr.responseText));
                } catch {
                    reject(new Error('Reponse invalide du serveur'));
                }
            } else {
                try {
                    const err = JSON.parse(xhr.responseText);
                    reject(new Error(err.error?.message || `Erreur ${xhr.status}`));
                } catch {
                    reject(new Error(`Erreur ${xhr.status}`));
                }
            }
        });

        xhr.addEventListener('error', () => reject(new Error('Erreur reseau')));
        xhr.addEventListener('abort', () => reject(new Error('Upload annule')));

        xhr.send(formData);
    });
}

// --- SSE via fetch + ReadableStream ---

export async function fetchSSE(url, body, { onProgress, onDone, onError, onAbort, onHeartbeat }) {
    const controller = new AbortController();
    fetchSSE._currentController = controller;

    let response;
    try {
        response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${getAccessToken()}`,
                'X-Thread-Id': localStorage.getItem('thread_id') || '',
            },
            body: JSON.stringify(body),
            signal: controller.signal,
        });
    } catch (err) {
        if (err.name === 'AbortError') { onAbort?.(); return; }
        throw err;
    }

    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        onError?.(errorData.error || errorData);
        return;
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    try {
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop();

            let currentEvent = 'message';
            for (const line of lines) {
                if (line.startsWith('event: ')) {
                    currentEvent = line.slice(7).trim();
                } else if (line.startsWith('data: ')) {
                    try {
                        const data = JSON.parse(line.slice(6));
                        if (currentEvent === 'done') {
                            onDone?.(data);
                        } else if (currentEvent === 'error') {
                            onError?.(data);
                        } else if (currentEvent === 'heartbeat') {
                            onHeartbeat?.(data);
                        } else {
                            onProgress?.(data);
                        }
                    } catch {
                        // JSON invalide, ignorer
                    }
                    currentEvent = 'message';
                }
            }
        }
    } catch (err) {
        if (err.name === 'AbortError') { onAbort?.(); return; }
        throw err;
    } finally {
        fetchSSE._currentController = null;
    }
}

fetchSSE._currentController = null;

export function abortSSE() {
    if (fetchSSE._currentController) {
        fetchSSE._currentController.abort();
    }
}

/**
 * Verifie si le moteur TTS est occupe avant de lancer une generation.
 * Retourne { busy, elapsed_seconds, endpoint } ou null si injoignable.
 */
export async function checkTtsStatus() {
    try {
        const resp = await apiRequest('/api/tts/status');
        if (!resp.ok) return null;
        const json = await resp.json();
        return json.data?.generation || null;
    } catch {
        return null;
    }
}

export { getErrorMessage };
