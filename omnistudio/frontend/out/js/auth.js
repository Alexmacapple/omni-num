/**
 * auth.js — Authentification Keycloak (JWT, refresh, intercepteur).
 */

const STORAGE_KEYS = {
    ACCESS_TOKEN: 'vx_access_token',
    REFRESH_TOKEN: 'vx_refresh_token',
    TOKEN_EXP: 'vx_token_exp',
};

const MAX_REFRESH_FAILURES = 3;

let refreshTimer = null;
let refreshFailures = 0;
const authListeners = [];

// --- Stockage tokens ---

export function getAccessToken() {
    return localStorage.getItem(STORAGE_KEYS.ACCESS_TOKEN) || '';
}

function getRefreshToken() {
    return localStorage.getItem(STORAGE_KEYS.REFRESH_TOKEN) || '';
}

function storeTokens(accessToken, refreshToken, expiresIn) {
    localStorage.setItem(STORAGE_KEYS.ACCESS_TOKEN, accessToken);
    localStorage.setItem(STORAGE_KEYS.REFRESH_TOKEN, refreshToken);
    localStorage.setItem(STORAGE_KEYS.TOKEN_EXP, String(Math.floor(Date.now() / 1000) + expiresIn));
}

function clearTokens() {
    localStorage.removeItem(STORAGE_KEYS.ACCESS_TOKEN);
    localStorage.removeItem(STORAGE_KEYS.REFRESH_TOKEN);
    localStorage.removeItem(STORAGE_KEYS.TOKEN_EXP);
}

// --- Auth state ---

export function isAuthenticated() {
    const token = getAccessToken();
    if (!token) return false;
    const exp = parseInt(localStorage.getItem(STORAGE_KEYS.TOKEN_EXP) || '0', 10);
    return Date.now() / 1000 < exp;
}

export function onAuthStateChange(callback) {
    authListeners.push(callback);
}

function notifyAuthChange(authenticated) {
    authListeners.forEach(cb => cb(authenticated));
}

// --- Login ---

export async function login(username, password) {
    const response = await fetch('api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
    });

    const result = await response.json();
    if (result.error) {
        throw new Error(result.error.message || 'Échec de connexion');
    }

    const { access_token, refresh_token, expires_in } = result.data;
    storeTokens(access_token, refresh_token, expires_in);
    refreshFailures = 0;
    scheduleTokenRefresh();
    notifyAuthChange(true);
    return result.data;
}

// --- Logout ---

export async function logout() {
    const refreshToken = getRefreshToken();
    try {
        await fetch('api/auth/logout', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ refresh_token: refreshToken }),
        });
    } catch {
        // Best-effort
    }
    clearTokens();
    clearTimeout(refreshTimer);
    refreshTimer = null;
    notifyAuthChange(false);
}

// --- Refresh ---

export async function refreshAccessToken() {
    const refreshToken = getRefreshToken();
    if (!refreshToken) throw new Error('Pas de refresh token');

    const response = await fetch('api/auth/token/refresh', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: refreshToken }),
    });

    const result = await response.json();
    if (result.error) {
        throw new Error(result.error.message || 'Refresh échoué');
    }

    const { access_token, refresh_token, expires_in } = result.data;
    storeTokens(access_token, refresh_token, expires_in);
    return result.data;
}

// --- Planification auto-refresh ---

export function scheduleTokenRefresh() {
    const token = getAccessToken();
    if (!token) return;

    try {
        const payload = JSON.parse(atob(token.split('.')[1]));
        const expiresIn = (payload.exp * 1000) - Date.now();
        const refreshIn = Math.max(expiresIn - 60000, 10000);

        clearTimeout(refreshTimer);
        refreshTimer = setTimeout(async () => {
            try {
                await refreshAccessToken();
                refreshFailures = 0;
                scheduleTokenRefresh();
            } catch {
                refreshFailures++;
                if (refreshFailures >= MAX_REFRESH_FAILURES) {
                    forceLogout('Session expirée, veuillez vous reconnecter.');
                } else {
                    refreshTimer = setTimeout(() => scheduleTokenRefresh(), 10000);
                }
            }
        }, refreshIn);
    } catch {
        // Token malformed, ignore
    }
}

// --- Force logout ---

export function forceLogout(message) {
    clearTokens();
    clearTimeout(refreshTimer);
    refreshTimer = null;
    notifyAuthChange(false);
    // Le message sera affiche par app.js via le callback onAuthStateChange
    if (message) {
        window.dispatchEvent(new CustomEvent('vx-force-logout', { detail: { message } }));
    }
}
