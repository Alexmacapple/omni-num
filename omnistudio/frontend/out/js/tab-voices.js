/**
 * tab-voices.js — Onglet 3 : Voix (bibliotheque, design, clone).
 */
import { escapeHtml, escapeAttr } from './dom-utils.js';
import { apiGet, apiPost, apiDelete, uploadFile, checkTtsStatus } from './api-client.js';
import { eventBus } from './app.js';
import { authenticatedUrl } from './audio-player.js';
import { showError } from './toast.js';

const RESERVED_NAMES = new Set([
    'vivian', 'serena', 'uncle-fu', 'uncle_fu', 'dylan', 'eric',
    'ryan', 'aiden', 'ono-anna', 'ono_anna', 'sohee',
]);

const DOM = {
    testSegment: () => document.getElementById('voice-test-segment'),
    testText: () => document.getElementById('voice-test-text'),
    voiceCount: () => document.getElementById('voice-count'),
    voiceList: () => document.getElementById('voice-list'),
    refreshBtn: () => document.getElementById('voice-refresh-btn'),
    // Design
    designTemplates: () => document.getElementById('design-templates'),
    designGenerateBtn: () => document.getElementById('design-generate-btn'),
    designUseDirectBtn: () => document.getElementById('design-use-direct-btn'),
    designInstructGroup: () => document.getElementById('design-instruct-group'),
    designInstruct: () => document.getElementById('design-instruct'),
    designListenSection: () => document.getElementById('design-listen-section'),
    designListenBtn: () => null, // Supprimé : l'audio est généré automatiquement
    designRegenBtn: () => document.getElementById('design-regen-btn'),
    designAudioPlayer: () => document.getElementById('design-audio-player'),
    designCurrentAudio: () => document.getElementById('design-current-audio'),
    designLockSection: () => document.getElementById('design-lock-section'),
    designLockName: () => document.getElementById('design-lock-name'),
    designLockBtn: () => document.getElementById('design-lock-btn'),
    designLockResult: () => document.getElementById('design-lock-result'),
    designLockMsg: () => document.getElementById('design-lock-msg'),
    designLockedPlayer: () => document.getElementById('design-locked-player'),
    designStabilitySection: () => document.getElementById('design-stability-section'),
    designStabilityBtn: () => document.getElementById('design-stability-btn'),
    designStabilityResults: () => document.getElementById('design-stability-results'),
    designStabilityIndicator: () => document.getElementById('design-stability-indicator'),
    designStatus: () => document.getElementById('design-status'),
    // Clone
    cloneAudio: () => document.getElementById('clone-audio'),
    cloneTranscription: () => document.getElementById('clone-transcription'),
    cloneName: () => document.getElementById('clone-name'),
    cloneBtn: () => document.getElementById('clone-btn'),
    cloneResult: () => document.getElementById('clone-result'),
    cloneResultMsg: () => document.getElementById('clone-result-msg'),
    cloneAudioPlayer: () => document.getElementById('clone-audio-player'),
    cloneStatus: () => document.getElementById('clone-status'),
    // Enregistrement + apercu
    recordBtn: () => document.getElementById('clone-record-btn'),
    recordStatus: () => document.getElementById('clone-record-status'),
    previewContainer: () => document.getElementById('clone-preview'),
    previewPlayer: () => document.getElementById('clone-preview-player'),
    audioInfo: () => document.getElementById('clone-audio-info'),
    // Navigation + présélection
    nextBtn: () => document.getElementById('voices-next-btn'),
    selectionSummary: () => document.getElementById('voices-selection-summary'),
};

let selectedVoices = new Set();

// --- Enregistrement micro ---

const MAX_RECORD_SECONDS = 30;

const rec = {
    stream: null,
    mediaRecorder: null,
    chunks: [],   // Blob chunks émis par MediaRecorder (WebM/Opus typique)
    mimeType: '',
    startTime: 0,
    timer: null,
    blob: null,   // WAV final (reconverti depuis le blob MediaRecorder)
};

function writeWavString(view, offset, str) {
    for (let i = 0; i < str.length; i++) {
        view.setUint8(offset + i, str.charCodeAt(i));
    }
}

function encodeWav(samples, sampleRate) {
    const buffer = new ArrayBuffer(44 + samples.length * 2);
    const view = new DataView(buffer);
    writeWavString(view, 0, 'RIFF');
    view.setUint32(4, 36 + samples.length * 2, true);
    writeWavString(view, 8, 'WAVE');
    writeWavString(view, 12, 'fmt ');
    view.setUint32(16, 16, true);
    view.setUint16(20, 1, true);
    view.setUint16(22, 1, true);
    view.setUint32(24, sampleRate, true);
    view.setUint32(28, sampleRate * 2, true);
    view.setUint16(32, 2, true);
    view.setUint16(34, 16, true);
    writeWavString(view, 36, 'data');
    view.setUint32(40, samples.length * 2, true);
    let offset = 44;
    for (let i = 0; i < samples.length; i++) {
        const s = Math.max(-1, Math.min(1, samples[i]));
        view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
        offset += 2;
    }
    return new Blob([buffer], { type: 'audio/wav' });
}

function formatDuration(seconds) {
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}:${String(s).padStart(2, '0')}`;
}

function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' o';
    if (bytes < 1048576) return Math.round(bytes / 1024) + ' Ko';
    return (bytes / 1048576).toFixed(1) + ' Mo';
}

/** Choisit le meilleur mimeType disponible pour MediaRecorder (codec audio).
 *  Ordre de préférence : webm/opus (Chrome/Firefox/Edge), ogg/opus, mp4 (Safari),
 *  fallback défaut navigateur.
 */
function _pickRecorderMime() {
    const candidates = [
        'audio/webm;codecs=opus',
        'audio/webm',
        'audio/ogg;codecs=opus',
        'audio/mp4',
    ];
    if (typeof MediaRecorder === 'undefined' || !MediaRecorder.isTypeSupported) return '';
    for (const m of candidates) {
        try { if (MediaRecorder.isTypeSupported(m)) return m; } catch { /* ignore */ }
    }
    return '';
}

async function onStartRecording() {
    const recordBtn = DOM.recordBtn();
    const statusEl = DOM.recordStatus();

    if (typeof MediaRecorder === 'undefined') {
        if (statusEl) {
            statusEl.className = 'fr-text--sm fr-mt-1v';
            statusEl.textContent = 'Votre navigateur ne supporte pas l\'API MediaRecorder. Utilisez l\'upload d\'un fichier audio.';
        }
        return;
    }

    try {
        rec.stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (err) {
        if (statusEl) {
            statusEl.className = 'fr-text--sm fr-mt-1v';
            statusEl.textContent = err.name === 'NotAllowedError'
                ? 'Accès au microphone refusé. Vérifiez les permissions du navigateur.'
                : 'Microphone indisponible : ' + (err.message || err.name);
        }
        return;
    }

    const mimeType = _pickRecorderMime();
    try {
        rec.mediaRecorder = mimeType
            ? new MediaRecorder(rec.stream, { mimeType })
            : new MediaRecorder(rec.stream);
    } catch (err) {
        if (statusEl) {
            statusEl.className = 'fr-text--sm fr-mt-1v';
            statusEl.textContent = 'Impossible d\'initialiser l\'enregistrement : ' + (err.message || err.name);
        }
        rec.stream.getTracks().forEach(t => t.stop());
        rec.stream = null;
        return;
    }

    rec.mimeType = rec.mediaRecorder.mimeType || mimeType || 'audio/webm';
    rec.chunks = [];
    rec.blob = null;

    rec.mediaRecorder.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) rec.chunks.push(e.data);
    };
    rec.mediaRecorder.onerror = (e) => {
        console.warn('[omnistudio] MediaRecorder error:', e?.error);
    };
    // Démarrer SANS timeslice : certains navigateurs émettent un chunk size=0
    // immédiat avec timeslice, ce qui perturbe la détection « aucun son ».
    // Le blob complet est livré une fois au stop().
    try {
        rec.mediaRecorder.start();
    } catch (err) {
        console.warn('[omnistudio] MediaRecorder.start() a échoué:', err);
        if (statusEl) {
            statusEl.className = 'fr-text--sm fr-mt-1v';
            statusEl.textContent = 'Impossible de démarrer l\'enregistrement : ' + (err?.message || err?.name || 'erreur inconnue');
        }
        rec.stream.getTracks().forEach(t => t.stop());
        rec.stream = null;
        rec.mediaRecorder = null;
        return;
    }
    rec.startTime = Date.now();
    console.info('[omnistudio] Enregistrement micro démarré, mimeType=', rec.mimeType, 'state=', rec.mediaRecorder.state);

    // UI : basculer en état "enregistrement en cours"
    if (recordBtn) {
        recordBtn.setAttribute('aria-pressed', 'true');
        recordBtn.textContent = recordBtn.dataset.labelStop;
        recordBtn.classList.remove('fr-icon-mic-fill', 'fr-btn--secondary');
        recordBtn.classList.add('fr-icon-stop-fill', 'fr-btn--primary');
    }
    if (statusEl) {
        statusEl.className = 'fr-text--sm fr-mt-1v ov-recording';
        statusEl.textContent = '0:00 / 0:30';
    }

    // Effacer le fichier uploadé (une seule source à la fois)
    const fileInput = DOM.cloneAudio();
    if (fileInput) fileInput.value = '';

    rec.timer = setInterval(() => {
        const elapsed = (Date.now() - rec.startTime) / 1000;
        if (statusEl) statusEl.textContent = `${formatDuration(elapsed)} / 0:30`;
        if (elapsed >= MAX_RECORD_SECONDS) {
            onStopRecording();
        }
    }, 250);
}

async function _decodeAndEncodeWav(blob) {
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    const audioCtx = new AudioContextClass();
    try {
        const arrayBuffer = await blob.arrayBuffer();
        const audioBuffer = await audioCtx.decodeAudioData(arrayBuffer);
        const pcm = audioBuffer.getChannelData(0);
        const wavBlob = encodeWav(pcm, audioBuffer.sampleRate);
        return { wavBlob, duration: audioBuffer.duration };
    } finally {
        try { audioCtx.close(); } catch { /* ignore */ }
    }
}

async function onStopRecording() {
    if (!rec.mediaRecorder || rec.mediaRecorder.state === 'inactive') return;

    clearInterval(rec.timer);
    rec.timer = null;

    const recordBtn = DOM.recordBtn();
    const statusEl = DOM.recordStatus();

    // Attente du dernier chunk via onstop
    const sourceBlob = await new Promise((resolve) => {
        rec.mediaRecorder.onstop = () => {
            const type = rec.mimeType || rec.mediaRecorder.mimeType || 'audio/webm';
            const blob = new Blob(rec.chunks, { type });
            console.info('[omnistudio] Enregistrement micro arrêté : chunks=', rec.chunks.length, 'size=', blob.size, 'type=', type);
            resolve(blob);
        };
        try { rec.mediaRecorder.stop(); } catch (err) {
            console.warn('[omnistudio] MediaRecorder.stop() a échoué:', err);
            resolve(new Blob(rec.chunks, { type: rec.mimeType || 'audio/webm' }));
        }
    });

    // Libérer le micro
    if (rec.stream) rec.stream.getTracks().forEach(t => t.stop());
    rec.stream = null;
    rec.mediaRecorder = null;

    // UI : basculer en état "prêt à enregistrer"
    if (recordBtn) {
        recordBtn.setAttribute('aria-pressed', 'false');
        recordBtn.textContent = recordBtn.dataset.labelStart;
        recordBtn.classList.remove('fr-icon-stop-fill', 'fr-btn--primary');
        recordBtn.classList.add('fr-icon-mic-fill', 'fr-btn--secondary');
    }

    // Sécurité : si aucun chunk (micro muet, onglet background dès le start)
    if (!sourceBlob || sourceBlob.size === 0) {
        if (statusEl) {
            statusEl.className = 'fr-text--sm fr-mt-1v';
            statusEl.textContent = 'Aucun son capté. Vérifiez que le micro est autorisé dans votre navigateur et que vous parlez assez fort, puis réessayez.';
        }
        rec.blob = null;
        onCloneFormChange();
        return;
    }

    // Décodage WebM/Opus → PCM → WAV (attendu par le backend /api/voices/clone)
    let wavBlob, duration;
    try {
        ({ wavBlob, duration } = await _decodeAndEncodeWav(sourceBlob));
    } catch (err) {
        if (statusEl) {
            statusEl.className = 'fr-text--sm fr-mt-1v';
            statusEl.textContent = 'Impossible de décoder l\'enregistrement : ' + (err?.message || err?.name || 'erreur inconnue');
        }
        rec.blob = null;
        onCloneFormChange();
        return;
    }
    rec.blob = wavBlob;

    if (duration < 1) {
        if (statusEl) {
            statusEl.className = 'fr-text--sm fr-mt-1v';
            statusEl.textContent = `Enregistrement trop court (${duration.toFixed(1)} s, minimum 1 s). Recommencez et parlez plus longtemps.`;
        }
        rec.blob = null;
        onCloneFormChange();
        return;
    }
    if (duration > MAX_RECORD_SECONDS) {
        if (statusEl) {
            statusEl.className = 'fr-text--sm fr-mt-1v';
            statusEl.textContent = `Enregistrement trop long (${Math.round(duration)} s). La durée maximale est de ${MAX_RECORD_SECONDS} secondes. Veuillez recommencer.`;
        }
        rec.blob = null;
        const deleteBtn = document.getElementById('clone-record-delete');
        if (deleteBtn) deleteBtn.hidden = true;
        const container = DOM.previewContainer();
        if (container) container.hidden = true;
        onCloneFormChange();
        return;
    }

    if (statusEl) {
        statusEl.className = 'fr-text--sm fr-mt-1v';
        statusEl.textContent = `Enregistrement terminé — ${formatDuration(duration)}`;
    }

    // Afficher le bouton supprimer
    const deleteBtn = document.getElementById('clone-record-delete');
    if (deleteBtn) deleteBtn.hidden = false;

    showAudioPreview(URL.createObjectURL(rec.blob), `Enregistrement micro — ${formatDuration(duration)} — ${formatFileSize(rec.blob.size)}`);
    onCloneFormChange();
    // Auto-transcribe Whisper sur l'enregistrement micro (parité avec upload fichier)
    autoTranscribeClone(new File([rec.blob], 'recording.wav', { type: 'audio/wav' }));
}

function onDeleteRecording() {
    rec.blob = null;
    // Masquer aperçu audio
    const container = DOM.previewContainer();
    if (container) container.hidden = true;
    // Remettre le statut à zéro
    const statusEl = DOM.recordStatus();
    if (statusEl) { statusEl.className = 'fr-text--sm fr-mt-1v'; statusEl.textContent = ''; }
    // Masquer le bouton supprimer
    const deleteBtn = document.getElementById('clone-record-delete');
    if (deleteBtn) deleteBtn.hidden = true;
    // Mettre à jour le formulaire
    onCloneFormChange();
}

async function autoTranscribeClone(file) {
    const transcriptionEl = DOM.cloneTranscription();
    const hintEl = document.getElementById('clone-transcription-hint');
    if (!transcriptionEl) return;
    // Ne pas écraser une transcription déjà saisie manuellement
    if (transcriptionEl.value.trim()) return;

    const originalPlaceholder = transcriptionEl.placeholder;
    transcriptionEl.placeholder = 'Transcription automatique Whisper en cours…';
    transcriptionEl.disabled = true;
    if (hintEl) hintEl.textContent = 'Transcription Whisper en cours… (5-15 s au 1er usage)';
    try {
        const form = new FormData();
        form.append('audio', file);
        form.append('language', getSessionLanguage());
        const token = localStorage.getItem('ov_access_token') || '';
        const resp = await fetch('api/voices/transcribe', {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${token}` },
            body: form,
        });
        if (resp.ok) {
            const json = await resp.json();
            const text = json?.data?.text || '';
            if (text && !transcriptionEl.value.trim()) {
                transcriptionEl.value = text;
                transcriptionEl.dispatchEvent(new Event('input', { bubbles: true }));
                if (hintEl) hintEl.textContent = 'Transcription Whisper effectuée — relisez et corrigez si nécessaire avant de cloner.';
            } else if (hintEl) {
                hintEl.textContent = 'Whisper n\'a pas réussi à transcrire. Saisissez manuellement le texte.';
            }
        } else if (hintEl) {
            hintEl.textContent = 'Transcription automatique indisponible. Saisissez manuellement le texte.';
        }
    } catch {
        if (hintEl) hintEl.textContent = 'Transcription automatique indisponible. Saisissez manuellement le texte.';
    } finally {
        transcriptionEl.placeholder = originalPlaceholder;
        transcriptionEl.disabled = false;
    }
}

function onCloneFileChange() {
    const file = DOM.cloneAudio()?.files?.[0];
    const errorEl = document.getElementById('clone-audio-error');
    if (errorEl) {
        errorEl.textContent = '';
        errorEl.style.display = 'none';
        errorEl.removeAttribute('role');
    }
    // RGAA : retirer aria-describedby erreur, garder le hint + retirer classe erreur
    const audioInput = DOM.cloneAudio();
    if (audioInput) audioInput.setAttribute('aria-describedby', 'clone-audio-hint');
    const group = document.getElementById('clone-audio-group');
    if (group) group.classList.remove('fr-upload-group--error');

    if (file) {
        // Effacer l'enregistrement (une seule source)
        rec.blob = null;
        const statusEl = DOM.recordStatus();
        if (statusEl) { statusEl.className = 'fr-text--sm fr-mt-1v'; statusEl.textContent = ''; }

        // Verifier la duree du fichier avant upload (RGAA 11.10 : controle de saisie)
        const tempAudio = new Audio();
        tempAudio.src = URL.createObjectURL(file);
        tempAudio.onloadedmetadata = () => {
            const duration = tempAudio.duration;
            URL.revokeObjectURL(tempAudio.src);
            // On ne bloque le fichier QUE si on peut mesurer une durée finie
            // qui dépasse la limite. Les conteneurs WebM/OGG/certains MP3
            // retournent Infinity/NaN tant que seek n'a pas été déclenché —
            // dans ce cas on laisse le backend (OmniVoice 1-30 s) trancher.
            if (Number.isFinite(duration) && duration > MAX_RECORD_SECONDS) {
                if (errorEl) {
                    errorEl.textContent = `Le fichier audio dure ${Math.round(duration)} s. La durée maximale est de ${MAX_RECORD_SECONDS} secondes. Veuillez raccourcir votre fichier.`;
                    errorEl.style.display = '';
                    errorEl.setAttribute('role', 'alert');
                }
                const input = DOM.cloneAudio();
                if (input) input.setAttribute('aria-describedby', 'clone-audio-hint clone-audio-error');
                const group = document.getElementById('clone-audio-group');
                if (group) group.classList.add('fr-upload-group--error');
                const audioInput = DOM.cloneAudio();
                if (audioInput) audioInput.value = '';
                const container = DOM.previewContainer();
                if (container) container.hidden = true;
                onCloneFormChange();
                return;
            }
            const durLabel = Number.isFinite(duration) ? ` — ${Math.round(duration)} s` : '';
            showAudioPreview(URL.createObjectURL(file), `${file.name} — ${formatFileSize(file.size)}${durLabel}`);
            onCloneFormChange();
            // Auto-transcribe Whisper (parité Gradio app.py ligne 495)
            autoTranscribeClone(file);
        };
        tempAudio.onerror = () => {
            // Format métadata illisible côté navigateur : afficher quand même,
            // le backend validera (Whisper + OmniVoice).
            showAudioPreview(URL.createObjectURL(file), `${file.name} — ${formatFileSize(file.size)}`);
            onCloneFormChange();
            autoTranscribeClone(file);
        };
    } else {
        onCloneFormChange();
    }
}

function showAudioPreview(url, info) {
    const container = DOM.previewContainer();
    const player = DOM.previewPlayer();
    const infoEl = DOM.audioInfo();

    if (player) {
        player.src = url;
        player.onloadedmetadata = () => {
            const dur = Math.round(player.duration * 10) / 10;
            if (infoEl) infoEl.textContent = info + (dur ? ` — ${dur}s` : '');
        };
    }
    if (container) container.hidden = false;
    if (infoEl) infoEl.textContent = info;
}

export function init() {
    // Listener bouton Réinitialiser des paramètres avancés Design
    const designAdvResetBtn = document.getElementById('design-adv-reset-btn');
    if (designAdvResetBtn) designAdvResetBtn.addEventListener('click', resetDesignAdvanced);

    const refreshBtn = DOM.refreshBtn();
    const voiceList = DOM.voiceList();
    const designGenerateBtn = DOM.designGenerateBtn();
    // designListenBtn supprimé
    const designRegenBtn = DOM.designRegenBtn();
    const designLockName = DOM.designLockName();
    const designLockBtn = DOM.designLockBtn();
    const designStabilityBtn = DOM.designStabilityBtn();
    const cloneAudio = DOM.cloneAudio();
    const cloneName = DOM.cloneName();
    const cloneTranscription = DOM.cloneTranscription();
    const cloneBtn = DOM.cloneBtn();
    const nextBtn = DOM.nextBtn();

    // Bibliotheque
    if (refreshBtn) refreshBtn.addEventListener('click', loadVoices);
    if (voiceList) voiceList.addEventListener('click', onVoiceListAction);

    // Texte exemple Baudelaire
    const sampleTextBtn = document.getElementById('voice-sample-text-btn');
    if (sampleTextBtn) sampleTextBtn.addEventListener('click', () => {
        const seg = DOM.testSegment();
        if (seg) seg.value = '';
        const ta = DOM.testText();
        if (ta) {
            ta.value = 'Rien n\'égale en longueur les boiteuses journées,\nQuand sous les lourds flocons des neigeuses années\nL\'ennui, fruit de la morne incuriosité,\nPrend les proportions de l\'immortalité.';
            ta.dispatchEvent(new Event('input', { bubbles: true }));
        }
    });

    // Design
    if (designGenerateBtn) designGenerateBtn.addEventListener('click', onGenerateBrief);
    const designUseDirectBtn = DOM.designUseDirectBtn();
    if (designUseDirectBtn) designUseDirectBtn.addEventListener('click', onUseDirectPrompt);
    const designComposeAttrsBtn = document.getElementById('design-compose-attrs-btn');
    if (designComposeAttrsBtn) designComposeAttrsBtn.addEventListener('click', onComposeAttrs);
    const tempSlider = document.getElementById('design-temperature');
    const tempOutput = document.getElementById('design-temperature-output');
    if (tempSlider && tempOutput) {
        tempSlider.addEventListener('input', () => {
            tempOutput.textContent = tempSlider.value;
            tempSlider.setAttribute('aria-valuenow', tempSlider.value);
        });
    }

    // Tags d'ajustement rapide
    const modTags = document.getElementById('design-modifier-tags');
    if (modTags) modTags.addEventListener('click', onModifierTag);
    // designListenBtn supprimé : l'audio est généré automatiquement
    if (designRegenBtn) designRegenBtn.addEventListener('click', () => onExplore(false));
    if (designLockName) designLockName.addEventListener('input', onLockNameInput);
    if (designLockBtn) designLockBtn.addEventListener('click', onLock);
    if (designStabilityBtn) designStabilityBtn.addEventListener('click', onStabilityTest);

    // Clone
    if (cloneAudio) cloneAudio.addEventListener('change', onCloneFileChange);
    if (cloneName) cloneName.addEventListener('input', onCloneFormChange);
    if (cloneTranscription) cloneTranscription.addEventListener('input', onCloneFormChange);
    if (cloneBtn) cloneBtn.addEventListener('click', onClone);
    const recordBtn = DOM.recordBtn();
    if (recordBtn) recordBtn.addEventListener('click', () => {
        const isRecording = recordBtn.getAttribute('aria-pressed') === 'true';
        if (isRecording) {
            onStopRecording();
        } else {
            onStartRecording();
        }
    });
    const recordDeleteBtn = document.getElementById('clone-record-delete');
    if (recordDeleteBtn) recordDeleteBtn.addEventListener('click', onDeleteRecording);

    // Afficher les hints de validation au chargement
    onCloneFormChange();

    // Persistance langue de session : sélecteur Design → localStorage
    const designLangSel = document.getElementById('design-language');
    if (designLangSel) {
        // Initialise la valeur depuis la session si elle existe et que 'fr' est encore par défaut
        const stored = getSessionLanguage();
        if (stored && designLangSel.value && !designLangSel.dataset.userSet) {
            designLangSel.value = stored;
        }
        designLangSel.addEventListener('change', () => {
            setSessionLanguage(designLangSel.value);
            designLangSel.dataset.userSet = '1';
            // Si un sélecteur Clone existe, le synchroniser
            const cloneLang = document.getElementById('clone-language');
            if (cloneLang) cloneLang.value = designLangSel.value;
        });
    }
    const cloneLangSel = document.getElementById('clone-language');
    if (cloneLangSel) {
        cloneLangSel.value = getSessionLanguage();
        cloneLangSel.addEventListener('change', () => {
            setSessionLanguage(cloneLangSel.value);
            if (designLangSel) designLangSel.value = cloneLangSel.value;
        });
    }

    // Bascule entre les 3 parcours (Attributs / IA / Profil)
    initDesignModeRadios();

    // Navigation
    if (nextBtn) nextBtn.addEventListener('click', onContinueToAssign);

    // Segment selector
    const testSegment = DOM.testSegment();
    if (testSegment) testSegment.addEventListener('change', onSegmentSelect);

    // Charger les templates dans l'onglet Créer
    loadTemplates();

    // Charger les voix et segments quand on entre dans l'onglet
    eventBus.on('tab-activated:tab-voices', async () => {
        await loadSegments();
        await loadVoices();
    });

    eventBus.on('session-reset', () => {
        selectedVoices = new Set();
        const select = DOM.testSegment();
        if (select) select.innerHTML = '<option value="" selected>— Texte libre —</option>';
        const testText = DOM.testText();
        if (testText) testText.value = '';
        const summary = DOM.selectionSummary();
        if (summary) summary.textContent = '';
        DOM.nextBtn().disabled = true;
    });
}

// --- Segments pour test voix ---

async function loadSegments() {
    const select = DOM.testSegment();
    if (!select) return;
    try {
        const result = await apiGet('/api/steps');
        if (result.error || !result.data.steps.length) return;
        const steps = result.data.steps;
        select.innerHTML = '<option value="">— Texte libre —</option>' +
            steps.map(s => {
                const text = s.text_tts || s.text_original;
                const label = text.length > 80 ? text.substring(0, 80) + '…' : text;
                return `<option value="${escapeAttr(text)}">${escapeHtml(s.step_id)} — ${escapeHtml(label)}</option>`;
            }).join('');
        // Pré-sélectionner le premier segment
        if (steps.length > 0) {
            select.selectedIndex = 1;
            onSegmentSelect();
        }
    } catch { /* silencieux */ }
}

function onSegmentSelect() {
    const select = DOM.testSegment();
    const textarea = DOM.testText();
    if (!select || !textarea) return;
    if (select.value) {
        textarea.value = select.value;
    }
}

// --- Bibliotheque ---

async function loadVoices() {
    try {
        const result = await apiGet('/api/voices');
        if (result.error) return;
        const voices = [...result.data.voices].sort((a, b) => a.name.localeCompare(b.name, 'fr', { sensitivity: 'base' }));
        const voiceList = DOM.voiceList();
        if (voiceList) voiceList.innerHTML = voices.map(renderVoiceCard).join('');
        const voiceCount = DOM.voiceCount();
        if (voiceCount) voiceCount.textContent = `${voices.length} voix disponibles pour l'assignation`;
        // PRD-018 : état vide si OmniVoice down
        const emptyState = document.getElementById('voices-empty-state');
        if (emptyState) emptyState.hidden = voices.length > 0;
        if (voiceCount) voiceCount.hidden = voices.length === 0;

        const nextBtn = DOM.nextBtn();
        if (nextBtn) nextBtn.disabled = voices.length === 0;

        updateSelectionSummary();
    } catch {
        const voiceCount = DOM.voiceCount();
        if (voiceCount) voiceCount.textContent = 'Erreur de chargement des voix';
    }
}

function toggleVoiceSelection(voiceName) {
    if (selectedVoices.has(voiceName)) {
        selectedVoices.delete(voiceName);
    } else {
        selectedVoices.add(voiceName);
    }

    // Mettre à jour la carte visuellement
    const card = document.querySelector(`[data-voice-name="${CSS.escape(voiceName)}"].fr-card`);
    if (card) {
        const selected = selectedVoices.has(voiceName);
        if (selected) {
            card.setAttribute('data-selected', 'true');
        } else {
            card.removeAttribute('data-selected');
        }
        const btn = card.querySelector('[data-action="toggle-select"]');
        if (btn) {
            btn.setAttribute('aria-pressed', String(selected));
            btn.textContent = selected ? 'Sélectionnée' : 'Sélectionner';
            if (selected) {
                btn.classList.remove('fr-btn--secondary');
            } else {
                btn.classList.add('fr-btn--secondary');
            }
        }
        // NC-2 RGAA 7.1 : feedback accessible pour les lecteurs d'ecran
        let liveRegion = document.getElementById('ov-voice-selection-live');
        if (!liveRegion) {
            liveRegion = document.createElement('div');
            liveRegion.id = 'ov-voice-selection-live';
            liveRegion.setAttribute('role', 'status');
            liveRegion.setAttribute('aria-live', 'polite');
            liveRegion.className = 'fr-sr-only';
            document.body.appendChild(liveRegion);
        }
        liveRegion.textContent = selected
            ? `Voix ${voiceName} sélectionnée`
            : `Voix ${voiceName} désélectionnée`;
    }

    updateSelectionSummary();
}

function updateSelectionSummary() {
    const summary = DOM.selectionSummary();
    if (!summary) return;
    const count = selectedVoices.size;
    if (count === 0) {
        summary.hidden = true;
        return;
    }
    const names = [...selectedVoices].join(', ');
    summary.textContent = count === 1
        ? `Voix sélectionnée : ${names} (sera pré-assignée à tous les segments)`
        : `${count} voix sélectionnées : ${names} (disponibles dans l'assignation)`;
    summary.hidden = false;
}

async function onContinueToAssign() {
    if (selectedVoices.size > 0) {
        const voiceList = [...selectedVoices];
        const voice = voiceList[0];
        try {
            await apiPost('/api/assign/apply-all', {
                voice, language: getSessionLanguage(), speed: 1.0, instruction: '',
                selected_voices: voiceList,
            });
        } catch {
            // Echec non-bloquant
        }
    }
    eventBus.emit('navigate', 'tab-assign');
}

function renderVoiceCard(voice) {
    const badgeClass = voice.type === 'native' ? 'fr-badge--blue-ecume'
        : 'fr-badge--green-emeraude';
    const badgeLabel = voice.type === 'native' ? 'Native' : 'Personnalisée';

    const desc = voice.description || '';
    const shortDesc = desc.length > 60 ? desc.substring(0, 60) + '…' : desc;

    const isSelected = selectedVoices.has(voice.name);

    const vn = escapeHtml(voice.name);
    const va = escapeAttr(voice.name);
    let actionItems = `
                            <li><button type="button" class="fr-btn fr-btn--sm" data-action="preview" data-voice-name="${va}" title="Écouter la voix ${va}">Écouter ${vn}</button></li>
                            <li><button type="button" class="fr-btn fr-btn--secondary fr-btn--sm" data-action="toggle-select" data-voice-name="${va}" aria-pressed="${isSelected}">${isSelected ? 'Sélectionnée' : 'Sélectionner'}</button></li>`;
    if (voice.type === 'custom') {
        actionItems += `
                            <li><button type="button" class="fr-btn fr-btn--tertiary-no-outline fr-btn--sm" data-action="rename" data-voice-name="${va}">Renommer</button></li>
                            <li><button type="button" class="fr-btn fr-btn--tertiary-no-outline fr-btn--sm" data-action="delete" data-voice-name="${va}">Supprimer</button></li>`;
    }

    return `<div class="fr-col-12 fr-col-sm-6 fr-col-md-4 fr-col-lg-3">
        <div class="fr-card fr-card--sm fr-card--grey" data-voice-name="${escapeAttr(voice.name)}" ${isSelected ? 'data-selected="true"' : ''}>
            <div class="fr-card__body">
                <div class="fr-card__content">
                    <h4 class="fr-card__title">${escapeHtml(voice.name)}</h4>
                    <p class="fr-card__desc">${escapeHtml(shortDesc) || ''}</p>
                    <div class="fr-card__start">
                        <p class="fr-card__detail fr-icon-mic-fill"><span class="fr-badge fr-badge--sm fr-badge--no-icon ${badgeClass}">${badgeLabel}</span></p>
                    </div>
                </div>
                <div class="fr-card__footer">
                    <ul class="fr-btns-group fr-btns-group--inline fr-btns-group--sm">
                        ${actionItems}
                    </ul>
                    <div class="ov-card-status" data-status-zone></div>
                </div>
            </div>
        </div>
    </div>`;
}

async function onVoiceListAction(e) {
    const btn = e.target.closest('[data-action]');
    if (!btn) return;

    const action = btn.dataset.action;
    if (action === 'preview') {
        await previewVoice(btn.dataset.voiceName, btn);
    } else if (action === 'rename') {
        await renameVoice(btn.dataset.voiceName);
    } else if (action === 'delete') {
        await deleteVoice(btn.dataset.voiceName);
    } else if (action === 'toggle-select') {
        toggleVoiceSelection(btn.dataset.voiceName);
    }
}

async function previewVoice(voiceName, btn) {
    const testText = DOM.testText();
    if (!testText?.value) return;

    const card = document.querySelector(`[data-voice-name="${CSS.escape(voiceName)}"].fr-card`);
    const footer = card?.querySelector('.fr-card__footer');
    const statusZone = footer?.querySelector('[data-status-zone]');

    // Retirer un player precedent s'il existe
    const oldAudio = footer?.querySelector('.ov-card-audio');
    if (oldAudio) { oldAudio.pause(); oldAudio.remove(); }

    // Verifier si le moteur TTS est occupe
    const tts = await checkTtsStatus();
    if (tts?.busy) {
        if (statusZone) {
            statusZone.className = 'ov-card-status ov-card-status--warning';
            statusZone.textContent =
                `Moteur TTS occupé (${tts.elapsed_seconds}s). Patientez…`;
        }
        return;
    }

    // État chargement
    const originalLabel = btn.textContent;
    btn.classList.add('ov-preview-loading');
    btn.disabled = true;
    btn.textContent = 'Génération…';
    if (statusZone) {
        statusZone.className = 'ov-card-status ov-card-status--loading';
        statusZone.textContent = 'Synthèse en cours (5-15s)…';
    }

    try {
        const result = await apiPost('/api/voices/preview', {
            voice: voiceName, text: testText.value, language: getSessionLanguage(),
        });
        if (result.error) throw new Error(result.error.message || 'Erreur de synthèse');

        if (footer && result.data?.audio_url) {
            const audio = document.createElement('audio');
            audio.className = 'ov-card-audio';
            audio.controls = true;
            audio.title = `Aperçu voix ${voiceName}`;
            audio.addEventListener('error', () => {
                if (statusZone) {
                    statusZone.className = 'ov-card-status ov-card-status--error';
                    statusZone.textContent = 'Fichier audio introuvable ou session expirée.';
                }
            }, { once: true });
            audio.src = authenticatedUrl(result.data.audio_url);
            footer.appendChild(audio);
            audio.play().catch(() => {
                if (statusZone) {
                    statusZone.className = 'ov-card-status ov-card-status--warning';
                    statusZone.textContent = 'Lecture automatique bloquée. Utilisez le player ci-dessous.';
                }
            });
        }
        if (statusZone) {
            statusZone.className = 'ov-card-status';
            statusZone.textContent = '';
        }
    } catch (err) {
        if (statusZone) {
            statusZone.className = 'ov-card-status ov-card-status--error';
            statusZone.textContent = err.message || 'Échec de la prévisualisation';
        }
    } finally {
        btn.classList.remove('ov-preview-loading');
        btn.disabled = false;
        btn.textContent = originalLabel;
    }
}

/** Ouvre la modale DSFR de renommage et retourne le nouveau nom saisi,
 *  ou null si l'utilisateur annule / ferme la modale. Validation inline
 *  (pas d'alert() qui casse le flow), patterne identique à l'ancien prompt().
 */
function promptNewVoiceName(currentName) {
    const modal = document.getElementById('rename-voice-modal');
    const input = document.getElementById('rename-modal-input');
    const errorEl = document.getElementById('rename-modal-error');
    const inputGroup = document.getElementById('rename-modal-input-group');
    const cancelBtn = document.getElementById('rename-modal-cancel');
    const currentLabel = document.getElementById('rename-modal-current');
    const form = modal?.querySelector('form');
    if (!modal || !input || !form) return Promise.resolve(null);

    if (currentLabel) currentLabel.textContent = currentName;
    input.value = currentName;
    errorEl.hidden = true;
    errorEl.textContent = '';
    inputGroup.classList.remove('fr-input-group--error');

    return new Promise((resolve) => {
        const cleanup = () => {
            form.removeEventListener('submit', onSubmit);
            cancelBtn.removeEventListener('click', onCancel);
            modal.removeEventListener('close', onClose);
        };
        const onSubmit = (e) => {
            e.preventDefault();
            const trimmed = input.value.trim().toLowerCase();
            if (!/^[a-z0-9][a-z0-9-]{1,48}[a-z0-9]$/.test(trimmed)) {
                errorEl.textContent = 'Nom invalide : 3 à 50 caractères — minuscules, chiffres et tirets uniquement.';
                errorEl.hidden = false;
                inputGroup.classList.add('fr-input-group--error');
                input.focus();
                return;
            }
            if (trimmed === currentName) {
                modal.close();
                cleanup();
                resolve(null);
                return;
            }
            modal.close();
            cleanup();
            resolve(trimmed);
        };
        const onCancel = () => {
            modal.close();
            cleanup();
            resolve(null);
        };
        const onClose = () => {
            cleanup();
            resolve(null);
        };
        form.addEventListener('submit', onSubmit);
        cancelBtn.addEventListener('click', onCancel);
        modal.addEventListener('close', onClose, { once: true });
        if (typeof modal.showModal === 'function') modal.showModal();
        else modal.setAttribute('open', '');
        setTimeout(() => input.focus(), 50);
    });
}

async function renameVoice(voiceName) {
    const newName = await promptNewVoiceName(voiceName);
    if (!newName) return;
    try {
        const result = await apiPost(`/api/voices/${encodeURIComponent(voiceName)}/rename`, { new_name: newName });
        if (result.error) {
            showError(result.error.message || 'Erreur lors du renommage.');
            return;
        }
        if (selectedVoices.has(voiceName)) {
            selectedVoices.delete(voiceName);
            selectedVoices.add(newName);
        }
        await loadVoices();
    } catch (err) {
        showError(err.message || 'Erreur lors du renommage.');
    }
}

async function deleteVoice(voiceName) {
    if (!confirm(`Supprimer la voix "${voiceName}" ?`)) return;
    try {
        await apiDelete(`/api/voices/${encodeURIComponent(voiceName)}`);
        selectedVoices.delete(voiceName);
        await loadVoices();
    } catch (err) {
        showError(err.message || 'Impossible de supprimer la voix.');
    }
}

function useTemplate(voice) {
    const instruct = DOM.designInstruct();
    if (instruct) instruct.value = voice.voice_instruct;
    const group = DOM.designInstructGroup();
    if (group) {
        group.hidden = false;
        // Scroll vers la description pour feedback visuel
        group.scrollIntoView({ behavior: 'smooth', block: 'center' });
        // Flash le champ pour attirer l'attention
        instruct.focus();
    }
    resetModifierTags();
    showQuickAdjust();
    const listen = DOM.designListenSection();
    if (listen) listen.hidden = false;
    updateDesignStepper(2);
    // Si on est deja sur l'onglet design, pas besoin de changer
    const subTab = document.getElementById('sub-tab-design');
    if (subTab && subTab.getAttribute('aria-selected') !== 'true') {
        subTab.click();
    }
}

// --- Templates (presets onglet Creer) ---

async function loadTemplates() {
    const container = DOM.designTemplates();
    if (!container) return;
    try {
        const result = await apiGet('/api/voices/templates');
        if (result.error || !result.data?.templates) return;
        container.innerHTML = result.data.templates.map(t =>
            `<button class="fr-btn fr-btn--tertiary fr-btn--sm" type="button"
                     data-action="use-template"
                     data-instruct="${escapeAttr(t.voice_instruct)}"
                     title="${escapeAttr(t.description)}">${escapeHtml(t.name)}</button>`
        ).join('');
        container.addEventListener('click', (e) => {
            const btn = e.target.closest('[data-action="use-template"]');
            if (!btn) return;
            useTemplate({ voice_instruct: btn.dataset.instruct });
        });
    } catch { /* templates optionnels */ }
}

// --- Design ---

function updateDesignStepper(step) {
    const title = document.getElementById('design-stepper-title');
    const state = document.getElementById('design-stepper-state');
    const details = document.getElementById('design-stepper-details');
    const steps = document.querySelector('#design-stepper .fr-stepper__steps');
    // 3 étapes : Choisir un parcours · Décrire la voix · Écouter et enregistrer.
    // Le step 2 (rétrocompat : ancien nom) pointe désormais sur « Écouter ».
    const normalized = step >= 2 ? 3 : step;
    if (normalized === 1) {
        if (title) title.firstChild.textContent = 'Choisir un parcours ';
        if (state) state.textContent = 'Étape 1 sur 3';
        if (details) details.textContent = 'Trois parcours disponibles. Une seule option suffit ; vous pourrez réessayer avec un autre parcours.';
        if (steps) steps.setAttribute('data-fr-current-step', '1');
    } else if (normalized === 2) {
        if (title) title.firstChild.textContent = 'Décrire la voix ';
        if (state) state.textContent = 'Étape 2 sur 3';
        if (details) details.textContent = 'Renseignez les attributs ou la description correspondant au parcours sélectionné, puis générez.';
        if (steps) steps.setAttribute('data-fr-current-step', '2');
    } else {
        if (title) title.firstChild.textContent = 'Écouter et enregistrer ';
        if (state) state.textContent = 'Étape 3 sur 3';
        if (details) details.textContent = 'Régénérez l\'audio si besoin, puis enregistrez la voix dans votre bibliothèque.';
        if (steps) steps.setAttribute('data-fr-current-step', '3');
    }
}

/** Bascule l'affichage des 3 parcours (Attributs / IA / Profil) selon le radio sélectionné. */
function initDesignModeRadios() {
    const radios = document.querySelectorAll('input[name="design-mode"]');
    const contents = document.querySelectorAll('.design-mode-content');
    const apply = (mode) => {
        contents.forEach((el) => { el.hidden = (el.dataset.mode !== mode); });
        // Le choix d'un parcours fait passer au step 2 (décrire).
        updateDesignStepper(2);
    };
    radios.forEach((r) => {
        r.addEventListener('change', () => { if (r.checked) apply(r.value); });
    });
    // État initial (aligné sur le radio checked par défaut : attrs)
    const checked = document.querySelector('input[name="design-mode"]:checked');
    if (checked) {
        contents.forEach((el) => { el.hidden = (el.dataset.mode !== checked.value); });
    }
}

// --- Ajustements rapides (tags modificateurs) ---

// Ajustements rapides — uniquement les items whitelist OmniVoice pour éviter
// que de la prose FR dans l'instruct fasse basculer le modèle vers l'anglais.
// Chaque modifier ajoute directement un item EN valide (même catégorie que
// pitch ou style), remplaçant celui déjà présent si besoin via exclusion
// mutuelle (data-excludes).
const MODIFIERS = {
    'tres-grave': ', very low pitch',
    grave:        ', low pitch',
    aigu:         ', high pitch',
    'tres-aigu':  ', very high pitch',
    chuchote:     ', whisper',
};

const MODIFIER_KEYWORDS = {
    'tres-grave': 'very low pitch',
    grave:        'low pitch',
    aigu:         'high pitch',
    'tres-aigu':  'very high pitch',
    chuchote:     'whisper',
};

const activeModifiers = new Set();

function onModifierTag(e) {
    const btn = e.target.closest('[data-modifier]');
    if (!btn) return;
    const mod = btn.dataset.modifier;
    const instruct = DOM.designInstruct();
    if (!instruct || !instruct.value.trim()) return;

    const keyword = MODIFIER_KEYWORDS[mod];
    const promptLower = instruct.value.toLowerCase();

    if (activeModifiers.has(mod)) {
        // Retirer le modificateur
        instruct.value = instruct.value.replace(MODIFIERS[mod], '');
        activeModifiers.delete(mod);
        btn.setAttribute('aria-pressed', 'false');
        btn.classList.remove('fr-tag--dismiss');
    } else {
        // Vérifier si le mot-clé existe déjà dans le prompt
        if (promptLower.includes(keyword)) {
            return; // Déjà présent, ne rien faire
        }
        // Désactiver les exclusions mutuelles (CSV : "a,b,c")
        const excludesAttr = btn.dataset.excludes || '';
        const excludesList = excludesAttr.split(',').map(s => s.trim()).filter(Boolean);
        for (const excluded of excludesList) {
            if (!activeModifiers.has(excluded)) continue;
            const exBtn = document.querySelector(`[data-modifier="${excluded}"]`);
            if (!exBtn) continue;
            instruct.value = instruct.value.replace(MODIFIERS[excluded], '');
            activeModifiers.delete(excluded);
            exBtn.setAttribute('aria-pressed', 'false');
            exBtn.classList.remove('fr-tag--dismiss');
        }
        // Ajouter le modificateur
        instruct.value = instruct.value.trimEnd() + MODIFIERS[mod];
        activeModifiers.add(mod);
        btn.setAttribute('aria-pressed', 'true');
        btn.classList.add('fr-tag--dismiss');
    }
}

function resetModifierTags() {
    activeModifiers.clear();
    document.querySelectorAll('#design-modifier-tags [data-modifier]').forEach(btn => {
        btn.setAttribute('aria-pressed', 'false');
        btn.classList.remove('fr-tag--dismiss');
    });
}

function showQuickAdjust() {
    const el = document.getElementById('design-quick-adjust');
    if (el) el.hidden = false;
    // Griser les tags dont le mot-clé est déjà dans le prompt
    const instruct = DOM.designInstruct();
    if (!instruct) return;
    const promptLower = instruct.value.toLowerCase();
    document.querySelectorAll('#design-modifier-tags [data-modifier]').forEach(btn => {
        const keyword = MODIFIER_KEYWORDS[btn.dataset.modifier];
        if (promptLower.includes(keyword) && !activeModifiers.has(btn.dataset.modifier)) {
            btn.disabled = true;
            btn.title = 'Déjà présent dans le prompt';
        } else {
            btn.disabled = false;
            btn.title = '';
        }
    });
}

/** Langue de session lue depuis localStorage (défaut 'fr'). Partagée entre Clone, Assign, Generate. */
export function getSessionLanguage() {
    try {
        return localStorage.getItem('ov_language') || 'fr';
    } catch {
        return 'fr';
    }
}

/** Persiste la langue de session. */
function setSessionLanguage(lang) {
    try {
        if (lang) localStorage.setItem('ov_language', lang);
    } catch { /* quota / private mode : on ignore */ }
}

/** Langue cible de synthèse Design. Lit le dropdown, fallback session. */
function getDesignLanguage() {
    const val = document.getElementById('design-language')?.value;
    return val || getSessionLanguage();
}

/** Affiche les attributs whitelist OmniVoice + leur traduction FR lisible. */
function showNormalizedInstruct(normalized, instructFr) {
    const box = document.getElementById('design-instruct-normalized');
    const val = document.getElementById('design-instruct-normalized-value');
    if (!box || !val) return;
    if (normalized && normalized.trim()) {
        const frText = (instructFr && instructFr.trim()) ? ` — ${instructFr}` : '';
        val.textContent = normalized + frText;
        box.hidden = false;
    } else {
        val.textContent = '(aucun attribut reconnu — la voix sera générée avec les défauts OmniVoice)';
        box.hidden = false;
    }
}

/** Génération SRT Whisper après synthèse. */
function getDesignWantSubtitles() {
    return !!document.getElementById('design-want-subtitles')?.checked;
}

/** 12 paramètres avancés OmniVoice /design. Retourne null si tous défauts. */
function getDesignAdvanced() {
    const num = (id) => {
        const el = document.getElementById(id);
        if (!el || el.value === '' || el.value == null) return null;
        const v = parseFloat(el.value);
        return isNaN(v) ? null : v;
    };
    const bool = (id) => {
        const el = document.getElementById(id);
        return el ? !!el.checked : null;
    };
    const out = {
        num_step: num('design-adv-num-step'),
        speed: num('design-adv-speed'),
        guidance_scale: num('design-adv-guidance'),
        duration: num('design-adv-duration'),
        t_shift: num('design-adv-t-shift'),
        position_temperature: num('design-adv-pos-temp'),
        class_temperature: num('design-adv-class-temp'),
        layer_penalty_factor: num('design-adv-layer-penalty'),
        audio_chunk_duration: num('design-adv-chunk-dur'),
        audio_chunk_threshold: num('design-adv-chunk-thr'),
        denoise: bool('design-adv-denoise'),
        postprocess_output: bool('design-adv-postprocess'),
    };
    const allDefault =
        out.num_step === 32 && out.speed === 1.0 && out.guidance_scale === 2.0 &&
        out.duration === null && out.t_shift === 0.1 &&
        out.position_temperature === 5.0 && out.class_temperature === 0.0 &&
        out.layer_penalty_factor === 5.0 && out.audio_chunk_duration === 15.0 &&
        out.audio_chunk_threshold === 30.0 && out.denoise === true &&
        out.postprocess_output === true;
    return allDefault ? null : out;
}

function resetDesignAdvanced() {
    const defaults = {
        'design-adv-num-step': '32', 'design-adv-speed': '1.0',
        'design-adv-guidance': '2.0', 'design-adv-duration': '',
        'design-adv-t-shift': '0.1', 'design-adv-pos-temp': '5.0',
        'design-adv-class-temp': '0.0', 'design-adv-layer-penalty': '5.0',
        'design-adv-chunk-dur': '15.0', 'design-adv-chunk-thr': '30.0',
    };
    for (const [id, v] of Object.entries(defaults)) {
        const el = document.getElementById(id);
        if (el) el.value = v;
    }
    ['design-adv-denoise', 'design-adv-postprocess'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.checked = true;
    });
}

function getBrief() {
    return {
        contexte: document.getElementById('design-context')?.value || '',
        emotion: document.getElementById('design-emotion')?.value || '',
        genre: document.querySelector('input[name="design-gender"]:checked')?.value || '',
        age: document.querySelector('input[name="design-age"]:checked')?.value || '',
        // Décision 12 — 4 catégories OmniVoice supplémentaires (items whitelist EN)
        pitch: document.getElementById('design-pitch')?.value || '',
        style: document.querySelector('input[name="design-style"]:checked')?.value || '',
        english_accent: document.getElementById('design-english-accent')?.value || '',
        chinese_dialect: document.getElementById('design-chinese-dialect')?.value || '',
        extra: document.getElementById('design-extra')?.value || '',
    };
}

/** Compose un voice_instruct whitelist OmniVoice à partir des 6 dropdowns (sans IA).
 *  Ordre : gender, age, pitch, style, accent/dialect. 1 item max par catégorie.
 *  Les valeurs vides sont ignorées. Retourne une string « female, middle-aged, … ».
 */
function composeInstructFromAttrs() {
    const genderRaw = document.querySelector('input[name="design-gender"]:checked')?.value || '';
    const ageRaw = document.querySelector('input[name="design-age"]:checked')?.value || '';
    const pitchRaw = document.getElementById('design-pitch')?.value || '';
    const styleRaw = document.querySelector('input[name="design-style"]:checked')?.value || '';
    const accent = document.getElementById('design-english-accent')?.value || '';
    const dialect = document.getElementById('design-chinese-dialect')?.value || '';

    const GENDER = { 'masculin': 'male', 'feminin': 'female' };
    const AGE = { 'jeune': 'young adult', 'mature': 'middle-aged', 'age': 'elderly' };
    const PITCH = {
        'very low': 'very low pitch', 'low': 'low pitch',
        'moderate': 'moderate pitch', 'high': 'high pitch', 'very high': 'very high pitch'
    };

    const items = [];
    if (GENDER[genderRaw]) items.push(GENDER[genderRaw]);
    if (AGE[ageRaw]) items.push(AGE[ageRaw]);
    if (PITCH[pitchRaw]) items.push(PITCH[pitchRaw]);
    if (styleRaw === 'whisper') items.push('whisper');
    // Accent et dialecte sont exclusifs (l'un ou l'autre selon la langue cible)
    if (accent) items.push(accent.toLowerCase());
    else if (dialect) items.push(dialect.toLowerCase());
    return items.join(', ');
}

async function onComposeAttrs() {
    const btn = document.getElementById('design-compose-attrs-btn');
    const status = DOM.designStatus();
    const composed = composeInstructFromAttrs();
    if (!composed) {
        if (status) status.innerHTML = `<p class="fr-alert fr-alert--warning fr-alert--sm"><span class="fr-alert__title">Sélectionnez au moins un attribut (Genre, Âge, Hauteur, Style, Accent ou Dialecte).</span></p>`;
        return;
    }
    const instruct = DOM.designInstruct();
    if (instruct) instruct.value = composed;
    const group = DOM.designInstructGroup();
    if (group) group.hidden = false;
    if (btn) btn.disabled = true;
    showLoading(status, 'Génération audio en cours (5-15s)...');
    try {
        const result = await apiPost('/api/voices/explore', {
            voice_instruct: composed,
            test_text: DOM.testText()?.value || '',
            regenerate_instruct: false,
            language: getDesignLanguage(),
            want_subtitles: getDesignWantSubtitles(),
            advanced: getDesignAdvanced(),
        });
        if (result.error) throw new Error(result.error.message);
        if (result.data.audio_url) showDesignAudio(result.data.audio_url, result.data.srt_url);
        showNormalizedInstruct(result.data.normalized_instruct, result.data.instruct_fr);
        const lockSection = DOM.designLockSection();
        if (lockSection) lockSection.hidden = false;
        const listen = DOM.designListenSection();
        if (listen) listen.hidden = false;
        updateDesignStepper(2);
        if (status) status.innerHTML = '';
        await loadVoices();
    } catch (err) {
        if (status) status.innerHTML = `<p class="fr-alert fr-alert--error fr-alert--sm"><span class="fr-alert__title">${escapeHtml(err.message)}</span></p>`;
    } finally {
        if (btn) btn.disabled = false;
    }
}

async function onUseDirectPrompt() {
    const extra = document.getElementById('design-extra')?.value?.trim();
    if (!extra) {
        const status = DOM.designStatus();
        if (status) status.innerHTML = '<p class="fr-alert fr-alert--warning fr-alert--sm"><span class="fr-alert__title">Saisissez une description avant de l\'utiliser comme prompt vocal.</span></p>';
        return;
    }

    // Injecter directement dans le champ prompt vocal
    const instruct = DOM.designInstruct();
    if (instruct) instruct.value = extra;
    const group = DOM.designInstructGroup();
    if (group) {
        group.hidden = false;
        group.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
    resetModifierTags();
    showQuickAdjust();
    const listen = DOM.designListenSection();
    if (listen) listen.hidden = false;
    const lockSection = DOM.designLockSection();
    if (lockSection) lockSection.hidden = false;
    updateDesignStepper(2);

    // Remplir l'accordéon transparence (mode direct)
    const brief = getBrief();
    const aiGenre = document.getElementById('ai-param-genre');
    const aiAge = document.getElementById('ai-param-age');
    const aiContexte = document.getElementById('ai-param-contexte');
    const aiEmotion = document.getElementById('ai-param-emotion');
    const aiExtra = document.getElementById('ai-param-extra');
    if (aiGenre) aiGenre.textContent = brief.genre || '(non spécifié)';
    if (aiAge) aiAge.textContent = brief.age || '(non spécifié)';
    if (aiContexte) aiContexte.textContent = brief.contexte || '(non spécifié)';
    if (aiEmotion) aiEmotion.textContent = brief.emotion || '(non spécifié)';
    if (aiExtra) aiExtra.textContent = extra;
    const aiDetails = document.getElementById('design-ai-details');
    if (aiDetails) aiDetails.hidden = false;
    const footer = document.getElementById('ai-details-footer');
    if (footer) footer.textContent = 'Votre description a été utilisée directement comme prompt vocal (sans passage par Albert).';

    // Générer l'audio directement avec le prompt
    const status = DOM.designStatus();
    const btn = DOM.designUseDirectBtn();
    if (btn) btn.disabled = true;
    showLoading(status, 'Génération audio en cours (5-15s)...');

    try {
        const testText = DOM.testText()?.value || '';
        const result = await apiPost('/api/voices/explore', {
            voice_instruct: extra,
            test_text: testText,
            regenerate_instruct: false,
            language: getDesignLanguage(),
            want_subtitles: getDesignWantSubtitles(),
            advanced: getDesignAdvanced(),
        });
        if (result.error) throw new Error(result.error.message);

        if (result.data.audio_url) {
            showDesignAudio(result.data.audio_url, result.data.srt_url);
        }
        showNormalizedInstruct(result.data.normalized_instruct, result.data.instruct_fr);
        if (status) status.innerHTML = '';
    } catch (err) {
        if (status) status.innerHTML = `<p class="fr-alert fr-alert--error fr-alert--sm"><span class="fr-alert__title">${escapeHtml(err.message)}</span></p>`;
    } finally {
        if (btn) btn.disabled = false;
    }
}

async function onGenerateBrief() {
    const btn = DOM.designGenerateBtn();
    const status = DOM.designStatus();
    if (btn) btn.disabled = true;
    showLoading(status, 'Génération de la description IA en cours...');

    try {
        const tempSlider = document.getElementById('design-temperature');
        const result = await apiPost('/api/voices/design-flow', {
            brief: getBrief(),
            test_text: DOM.testText()?.value || '',
            temperature: tempSlider ? parseFloat(tempSlider.value) : 0.5,
            language: getDesignLanguage(),
            want_subtitles: getDesignWantSubtitles(),
            advanced: getDesignAdvanced(),
        });
        if (result.error) throw new Error(result.error.message);

        const instruct = DOM.designInstruct();
        if (instruct) instruct.value = result.data.voice_instruct;
        const group = DOM.designInstructGroup();
        if (group) group.hidden = false;
        resetModifierTags();
        showQuickAdjust();
        const listen = DOM.designListenSection();
        if (listen) listen.hidden = false;
        updateDesignStepper(2);

        if (result.data.audio_url) {
            showDesignAudio(result.data.audio_url, result.data.srt_url);
        }
        showNormalizedInstruct(result.data.normalized_instruct, result.data.instruct_fr);

        // Remplir l'accordéon transparence IA
        const brief = getBrief();
        const aiGenre = document.getElementById('ai-param-genre');
        const aiAge = document.getElementById('ai-param-age');
        const aiContexte = document.getElementById('ai-param-contexte');
        const aiEmotion = document.getElementById('ai-param-emotion');
        const aiExtra = document.getElementById('ai-param-extra');
        if (aiGenre) aiGenre.textContent = brief.genre || '(non spécifié)';
        if (aiAge) aiAge.textContent = brief.age || '(non spécifié)';
        if (aiContexte) aiContexte.textContent = brief.contexte || '(non spécifié)';
        if (aiEmotion) aiEmotion.textContent = brief.emotion || '(non spécifié)';
        if (aiExtra) aiExtra.textContent = brief.extra || '(aucune)';
        const aiDetails = document.getElementById('design-ai-details');
        if (aiDetails) aiDetails.hidden = false;
        const footer = document.getElementById('ai-details-footer');
        if (footer) footer.textContent = 'Ces paramètres ont été envoyés à Albert (LLM) qui a produit le prompt vocal ci-dessus.';

        const lockSection = DOM.designLockSection();
        if (lockSection) lockSection.hidden = false;
        if (status) status.innerHTML = '';

        await loadVoices();
    } catch (err) {
        if (status) status.innerHTML = `<p class="fr-alert fr-alert--error fr-alert--sm"><span class="fr-alert__title">${escapeHtml(err.message)}</span></p>`;
    } finally {
        if (btn) btn.disabled = false;
    }
}

async function onExplore(regenerateInstruct) {
    const regenBtn = DOM.designRegenBtn();
    const status = DOM.designStatus();
    if (regenBtn) regenBtn.disabled = true;
    showLoading(status, 'Génération audio en cours (5-15s)...');

    try {
        const result = await apiPost('/api/voices/explore', {
            voice_instruct: DOM.designInstruct()?.value || '',
            test_text: DOM.testText()?.value || '',
            regenerate_instruct: regenerateInstruct,
            language: getDesignLanguage(),
            want_subtitles: getDesignWantSubtitles(),
            advanced: getDesignAdvanced(),
        });
        if (result.error) throw new Error(result.error.message);

        if (result.data.voice_instruct) {
            const instruct = DOM.designInstruct();
            if (instruct) instruct.value = result.data.voice_instruct;
        }
        if (result.data.audio_url) {
            showDesignAudio(result.data.audio_url, result.data.srt_url);
        }
        showNormalizedInstruct(result.data.normalized_instruct, result.data.instruct_fr);

        const lockSection = DOM.designLockSection();
        if (lockSection) lockSection.hidden = false;
        if (status) status.innerHTML = '';

        await loadVoices();
    } catch (err) {
        if (status) status.innerHTML = `<p class="fr-alert fr-alert--error fr-alert--sm"><span class="fr-alert__title">${escapeHtml(err.message)}</span></p>`;
    } finally {
        if (regenBtn) regenBtn.disabled = false;
    }
}

function showDesignAudio(url, srtUrl) {
    const player = DOM.designAudioPlayer();
    const container = DOM.designCurrentAudio();
    const authUrl = authenticatedUrl(url);
    if (player) {
        player.src = authUrl;
        if (container) container.hidden = false;
        player.play();
    }
    // Lien download WAV (reflète la dernière exploration)
    const dl = document.getElementById('design-download-link');
    if (dl && authUrl) {
        dl.href = authUrl;
        dl.hidden = false;
        // Nom de fichier suggéré depuis l'URL (ex: design_242.wav)
        const filename = (url || '').split('/').pop().split('?')[0] || 'voix-exploration.wav';
        dl.setAttribute('download', filename);
    }
    // Lien download SRT si want_subtitles était coché et que le backend l'a généré
    const srtDl = document.getElementById('design-srt-download');
    if (srtDl) {
        if (srtUrl) {
            srtDl.href = authenticatedUrl(srtUrl);
            srtDl.hidden = false;
            const srtFilename = (srtUrl || '').split('/').pop().split('?')[0] || 'voix-exploration.srt';
            srtDl.setAttribute('download', srtFilename);
        } else {
            srtDl.hidden = true;
        }
    }
    // Après la première génération, le bouton devient "Régénérer"
    const regenBtn = DOM.designRegenBtn();
    if (regenBtn) regenBtn.textContent = 'Régénérer l\'audio';
    // Scroller vers le player audio
    if (container) container.scrollIntoView({ behavior: 'smooth', block: 'center' });
}

function onLockNameInput() {
    const nameEl = DOM.designLockName();
    const lockBtn = DOM.designLockBtn();
    const errorEl = document.getElementById('design-lock-name-error');
    const groupEl = document.getElementById('design-lock-name-group');
    if (!nameEl || !lockBtn) return;

    const name = nameEl.value;
    let error = '';

    if (name.length === 0) {
        error = '';
    } else if (name.length < 3) {
        error = `Le nom doit contenir au moins 3 caractères (${name.length} saisi${name.length > 1 ? 's' : ''}).`;
    } else if (name.length > 50) {
        error = 'Le nom ne doit pas dépasser 50 caractères.';
    } else if (/[A-Z]/.test(name)) {
        error = 'Le nom ne doit contenir que des minuscules.';
    } else if (/[àâäéèêëïîôùûüç]/.test(name)) {
        error = 'Le nom ne doit pas contenir de caractères accentués.';
    } else if (/[^a-z0-9-]/.test(name)) {
        error = 'Caractères autorisés : minuscules (a-z), chiffres (0-9) et tirets (-).';
    } else if (RESERVED_NAMES.has(name)) {
        error = `Le nom « ${name} » est réservé (voix native du système).`;
    }

    const valid = !error && name.length >= 3;
    lockBtn.disabled = !valid;

    if (errorEl) {
        errorEl.textContent = error;
        errorEl.hidden = !error;
    }
    if (groupEl) {
        if (error) {
            groupEl.classList.add('fr-input-group--error');
            nameEl.classList.add('fr-input--error');
            nameEl.setAttribute('aria-invalid', 'true');
        } else {
            groupEl.classList.remove('fr-input-group--error');
            nameEl.classList.remove('fr-input--error');
            nameEl.removeAttribute('aria-invalid');
            if (valid) {
                groupEl.classList.add('fr-input-group--valid');
                nameEl.classList.add('fr-input--valid');
            } else {
                groupEl.classList.remove('fr-input-group--valid');
                nameEl.classList.remove('fr-input--valid');
            }
        }
    }
}

async function onLock() {
    const lockBtn = DOM.designLockBtn();
    const status = DOM.designStatus();
    if (lockBtn) lockBtn.disabled = true;
    showLoading(status, 'Enregistrement et test en cours...');

    try {
        const result = await apiPost('/api/voices/lock', {
            name: DOM.designLockName()?.value || '',
            voice_instruct: DOM.designInstruct()?.value || '',
            description: document.getElementById('design-lock-desc')?.value || '',
            test_text: DOM.testText()?.value || '',
        });
        if (result.error) throw new Error(result.error.message);

        const lockResult = DOM.designLockResult();
        const lockMsg = DOM.designLockMsg();
        const lockedPlayer = DOM.designLockedPlayer();
        if (lockResult) lockResult.hidden = false;
        if (lockMsg) lockMsg.textContent = `Voix « ${result.data.name} » enregistrée avec succès dans votre bibliothèque.`;
        if (lockedPlayer) lockedPlayer.src = authenticatedUrl(result.data.audio_url);

        const stabilitySection = DOM.designStabilitySection();
        if (stabilitySection) stabilitySection.hidden = false;
        if (status) status.innerHTML = '';

        await loadVoices();
    } catch (err) {
        if (status) status.innerHTML = `<p class="fr-alert fr-alert--error fr-alert--sm"><span class="fr-alert__title">${escapeHtml(err.message)}</span></p>`;
    } finally {
        if (lockBtn) lockBtn.disabled = false;
    }
}

async function onStabilityTest() {
    const stabilityBtn = DOM.designStabilityBtn();
    const status = DOM.designStatus();
    if (stabilityBtn) stabilityBtn.disabled = true;

    const name = DOM.designLockName()?.value || '';
    const text = DOM.testText()?.value || '';

    try {
        const urls = [];
        for (let i = 0; i < 3; i++) {
            const result = await apiPost('/api/voices/preview', {
                voice: name, text, language: getSessionLanguage(),
            });
            if (result.error) throw new Error(result.error.message);
            urls.push(result.data.audio_url);
        }

        const results = DOM.designStabilityResults();
        if (results) {
            results.hidden = false;
            results.innerHTML = urls.map((u, i) => `
                <div class="fr-col-4">
                    <p class="fr-text--sm fr-text--bold">Génération ${i + 1}</p>
                    <audio src="${authenticatedUrl(u)}" controls class="ov-audio-player" title="Test de stabilité ${i + 1}">
                                            </audio>
                </div>
            `).join('');
        }

        const indicator = DOM.designStabilityIndicator();
        if (indicator) {
            indicator.hidden = false;
            indicator.innerHTML = '<span class="fr-badge fr-badge--success fr-badge--sm">Stabilité : 3/3 cohérents</span>';
        }
    } catch (err) {
        if (status) status.innerHTML = `<p class="fr-alert fr-alert--error fr-alert--sm"><span class="fr-alert__title">${escapeHtml(err.message)}</span></p>`;
    } finally {
        if (stabilityBtn) stabilityBtn.disabled = false;
    }
}

// --- Clone ---

/** Met à jour le stepper du parcours Clone (1 → 2 → 3) selon l'état rempli. */
function updateCloneStepper(hasAudio, hasTranscription, hasName) {
    const title = document.getElementById('clone-stepper-title');
    const state = document.getElementById('clone-stepper-state');
    const details = document.getElementById('clone-stepper-details');
    const steps = document.getElementById('clone-stepper-steps');
    if (!title || !state || !details || !steps) return;
    let step = 1;
    if (hasAudio && hasTranscription && hasName) step = 3;
    else if (hasAudio) step = 2;
    if (step === 1) {
        title.textContent = '1. Fournir un audio de référence';
        state.textContent = 'Étape 1 sur 3';
        details.textContent = 'Téléversez un fichier audio ou enregistrez votre voix (1 à 30 s).';
    } else if (step === 2) {
        title.textContent = '2. Vérifier la transcription et nommer la voix';
        state.textContent = 'Étape 2 sur 3';
        details.textContent = 'Whisper a rempli la transcription automatiquement ; relisez-la et donnez un nom à la voix.';
    } else {
        title.textContent = '3. Lancer le clonage';
        state.textContent = 'Étape 3 sur 3';
        details.textContent = 'Tous les champs sont prêts. Cliquez « Créer le clone » pour lancer la synthèse.';
    }
    steps.setAttribute('data-fr-current-step', String(step));
}

function onCloneFormChange() {
    const hasFile = (DOM.cloneAudio()?.files?.length || 0) > 0;
    const hasRecording = rec.blob !== null;
    const hasAudio = hasFile || hasRecording;
    const nameValue = DOM.cloneName()?.value || '';
    const hasName = /^[a-z0-9-]{3,50}$/.test(nameValue);
    const hasTranscription = (DOM.cloneTranscription()?.value || '').trim().length > 0;
    const ready = hasAudio && hasName && hasTranscription;
    const cloneBtn = DOM.cloneBtn();
    if (cloneBtn) cloneBtn.disabled = !ready;
    updateCloneStepper(hasAudio, hasTranscription, hasName);

    // Feedback de validation
    const hint = document.getElementById('clone-validation-hint');
    if (hint) {
        if (ready) {
            hint.textContent = '';
        } else {
            const missing = [];
            if (!hasAudio) missing.push('audio (fichier ou enregistrement)');
            if (!hasName) {
                if (nameValue.length === 0) missing.push('nom de la voix');
                else missing.push('nom invalide (3-50 car., minuscules, chiffres, tirets)');
            }
            if (!hasTranscription) missing.push('transcription exacte');
            hint.textContent = 'Requis : ' + missing.join(' · ');
        }
    }
}

async function onClone() {
    const cloneBtn = DOM.cloneBtn();
    const status = DOM.cloneStatus();
    if (cloneBtn) cloneBtn.disabled = true;
    showLoading(status, 'Clonage en cours (peut prendre 10-30s)...');

    const formData = new FormData();
    const audioFile = DOM.cloneAudio()?.files?.[0];
    if (audioFile) {
        formData.append('audio', audioFile);
    } else if (rec.blob) {
        formData.append('audio', rec.blob, 'recording.wav');
    }
    formData.append('transcription', DOM.cloneTranscription().value);
    formData.append('name', DOM.cloneName().value);
    // Le paramètre model est accepté par le backend (compat VoxQwen) mais
    // OmniVoice a un seul modèle — toujours « 1.7B » pour compat arrière.
    formData.append('model', document.getElementById('clone-model-hidden')?.value || '1.7B');
    formData.append('description', document.getElementById('clone-desc')?.value || '');
    formData.append('test_text', DOM.testText()?.value || '');
    formData.append('language', document.getElementById('clone-language')?.value || getSessionLanguage());
    formData.append('preprocess_prompt', document.getElementById('clone-preprocess-prompt')?.checked ? 'true' : 'false');
    formData.append('want_subtitles', document.getElementById('clone-want-subtitles')?.checked ? 'true' : 'false');

    try {
        const result = await uploadFile('/api/voices/clone', formData);
        if (result.error) throw new Error(result.error.message);

        const cloneResult = DOM.cloneResult();
        const cloneResultMsg = DOM.cloneResultMsg();
        const cloneAudioPlayer = DOM.cloneAudioPlayer();
        const authUrl = authenticatedUrl(result.data.audio_url);
        if (cloneResult) cloneResult.hidden = false;
        if (cloneResultMsg) cloneResultMsg.textContent = `Voix « ${result.data.name} » clonée et enregistrée dans votre bibliothèque.`;
        if (cloneAudioPlayer) cloneAudioPlayer.src = authUrl;
        // Lien download WAV du clone
        const dl = document.getElementById('clone-download-link');
        if (dl && authUrl) {
            dl.href = authUrl;
            dl.hidden = false;
            dl.setAttribute('download', `${result.data.name || 'voix-clone'}.wav`);
        }
        // Lien download SRT si généré
        const srtDl = document.getElementById('clone-srt-download');
        if (srtDl) {
            if (result.data.srt_url) {
                srtDl.href = authenticatedUrl(result.data.srt_url);
                srtDl.hidden = false;
                srtDl.setAttribute('download', `${result.data.name || 'voix-clone'}.srt`);
            } else {
                srtDl.hidden = true;
            }
        }
        if (status) status.innerHTML = '';

        await loadVoices();
    } catch (err) {
        if (status) status.innerHTML = `<p class="fr-alert fr-alert--error fr-alert--sm"><span class="fr-alert__title">${escapeHtml(err.message)}</span></p>`;
    } finally {
        if (cloneBtn) cloneBtn.disabled = false;
    }
}

// --- Helpers ---

function showLoading(container, message) {
    if (!container) return;
    container.innerHTML = `<div class="fr-callout fr-callout--sm fr-icon-time-line">
        <p class="fr-callout__text"><span class="fr-icon-refresh-line ov-spin fr-mr-1w" aria-hidden="true"></span>${escapeHtml(message)}</p>
    </div>`;
}

export default { init };
