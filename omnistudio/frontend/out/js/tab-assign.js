/**
 * tab-assign.js — Onglet 4 : Assignation des voix aux etapes.
 */
import { apiGet, apiPost, apiDelete, checkTtsStatus } from './api-client.js';
import { eventBus } from './app.js';
import { escapeHtml, escapeAttr } from './dom-utils.js';
import { authenticatedUrl } from './audio-player.js';

const DOM = {
    voiceSelect: () => document.getElementById('assign-voice'),
    langSelect: () => document.getElementById('assign-lang'),
    speedRange: () => document.getElementById('assign-speed'),
    speedValue: () => document.getElementById('assign-speed-value'),
    applyAllBtn: () => document.getElementById('assign-apply-all-btn'),
    tableBody: () => document.querySelector('#assign-table tbody'),
    status: () => document.getElementById('assign-status'),
    nextBtn: () => document.getElementById('assign-next-btn'),
    addId: () => document.getElementById('assign-add-id'),
    addText: () => document.getElementById('assign-add-text'),
    addBtn: () => document.getElementById('assign-add-btn'),
};

let voiceTypes = {};
let assignData = [];
let voicesList = [];

function init() {
    const applyAllBtn = DOM.applyAllBtn();
    const nextBtn = DOM.nextBtn();
    const speedRange = DOM.speedRange();
    const voiceSelect = DOM.voiceSelect();
    const tableBody = DOM.tableBody();

    if (!applyAllBtn || !nextBtn || !speedRange || !voiceSelect || !tableBody) {
        console.error('[tab-assign] DOM elements missing during init');
        return;
    }

    const advResetBtn = document.getElementById('assign-adv-reset-btn');
    if (advResetBtn) advResetBtn.addEventListener('click', resetAssignAdvancedParams);

    applyAllBtn.addEventListener('click', onApplyAll);
    nextBtn.addEventListener('click', onContinue);
    speedRange.addEventListener('input', () => {
        const v = speedRange.value + 'x';
        const speedValue = DOM.speedValue();
        if (speedValue) speedValue.textContent = v;
        speedRange.setAttribute('aria-valuetext', v);
        const output = document.querySelector('#assign-speed').closest('.fr-range')?.querySelector('.fr-range__output');
        if (output) output.textContent = v;
    });
    voiceSelect.addEventListener('change', onVoiceChange);

    // Delegation sur le tableau
    tableBody.addEventListener('click', onTableAction);
    tableBody.addEventListener('change', onTableChange);
    tableBody.addEventListener('input', onTableInput);

    // Ajout de segment
    const addBtn = DOM.addBtn();
    if (addBtn) addBtn.addEventListener('click', onAddStep);

    eventBus.on('tab-activated:tab-assign', loadAssignData);
    eventBus.on('tab-deactivated:tab-assign', autoSave);

    // Fermeture du tiroir de preview audio (sticky en bas)
    const drawerClose = document.getElementById('assign-preview-drawer-close');
    const drawer = document.getElementById('assign-preview-drawer');
    if (drawerClose && drawer) {
        drawerClose.addEventListener('click', () => {
            const audio = document.getElementById('assign-preview-drawer-audio');
            if (audio) { audio.pause(); audio.src = ''; }
            drawer.hidden = true;
        });
    }

    eventBus.on('session-reset', () => {
        assignData = [];
        voicesList = [];
        if (DOM.tableBody()) DOM.tableBody().innerHTML = '';
        DOM.nextBtn().disabled = true;
        const status = DOM.status();
        if (status) status.innerHTML = '';
        // PRD-018 : réafficher état vide
        updateAssignEmptyState([]);
    });
}

function onVoiceChange() {
}

async function loadAssignData() {
    try {
        const result = await apiGet('/api/assign');
        if (result.error) throw new Error(result.error.message || 'Erreur de chargement');
        assignData = result.data.rows;
        voiceTypes = {};
        result.data.voices.forEach(v => { voiceTypes[v.name] = v.type; });

        const select = DOM.voiceSelect();
        select.innerHTML = result.data.voices
            .map(v => `<option value="${escapeAttr(v.name)}">${escapeHtml(v.name)} (${v.type})</option>`)
            .join('');

        // Pré-sélectionner la voix par défaut
        if (result.data.default_voice) {
            select.value = result.data.default_voice;
        }

        voicesList = result.data.voices;
        renderTable(assignData, voicesList);
        onVoiceChange();
        // PRD-018 : état vide
        updateAssignEmptyState(assignData);
    } catch (err) {
        DOM.status().innerHTML = `<p class="fr-alert fr-alert--error fr-alert--sm"><span class="fr-alert__title">${escapeHtml(err.message)}</span></p>`;
    }
}

// PRD-018 : gestion état vide
function updateAssignEmptyState(rows) {
    const emptyState = document.getElementById('assign-empty-state');
    const tableContainer = document.getElementById('assign-table-container');
    const nextBtn = DOM.nextBtn();
    const hasSteps = rows.length > 0;
    if (emptyState) emptyState.hidden = hasSteps;
    if (tableContainer) tableContainer.hidden = !hasSteps;
    if (nextBtn) nextBtn.disabled = !hasSteps;
}

/**
 * Paramètres avancés OmniVoice (accordion Assign — applique au preview).
 * Retourne null si toutes valeurs par défaut (évite payload inutile).
 */
function getAssignAdvancedParams() {
    const num = (id) => {
        const el = document.getElementById(id);
        if (!el || !el.value) return null;
        const v = parseFloat(el.value);
        return isNaN(v) ? null : v;
    };
    const bool = (id) => {
        const el = document.getElementById(id);
        return el ? !!el.checked : null;
    };
    const out = {
        num_step: num('assign-adv-num-step'),
        guidance_scale: num('assign-adv-guidance'),
        t_shift: num('assign-adv-t-shift'),
        denoise: bool('assign-adv-denoise'),
        postprocess_output: bool('assign-adv-postprocess'),
        preprocess_prompt: bool('assign-adv-preprocess'),
    };
    const allDefault =
        out.num_step === 32 && out.guidance_scale === 2.0 &&
        out.t_shift === 0.1 && out.denoise === true &&
        out.postprocess_output === true && out.preprocess_prompt === true;
    return allDefault ? null : out;
}

function resetAssignAdvancedParams() {
    const defaults = {
        'assign-adv-num-step': '32',
        'assign-adv-guidance': '2.0',
        'assign-adv-t-shift': '0.1',
    };
    for (const [id, v] of Object.entries(defaults)) {
        const el = document.getElementById(id);
        if (el) el.value = v;
    }
    ['assign-adv-denoise', 'assign-adv-postprocess', 'assign-adv-preprocess'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.checked = true;
    });
}

/**
 * Regroupe les voix par catégorie (système / personnelles / clonées) via <optgroup>.
 * Clarifie la distinction avec les voix voxstudio homonymes.
 */
function renderVoiceOptions(voices, selected) {
    const systemVoices = voices.filter(v => v.system);
    const cloneVoices = voices.filter(v => !v.system && v.source === 'clone');
    const designVoices = voices.filter(v => !v.system && v.source !== 'clone');

    const opt = v => `<option value="${escapeAttr(v.name)}" ${v.name === selected ? 'selected' : ''}>${escapeHtml(v.name)}</option>`;

    let html = '';
    if (systemVoices.length) {
        html += `<optgroup label="Voix système OmniStudio (partagées)">${systemVoices.map(opt).join('')}</optgroup>`;
    }
    if (designVoices.length) {
        html += `<optgroup label="Mes voix design (créées par vous)">${designVoices.map(opt).join('')}</optgroup>`;
    }
    if (cloneVoices.length) {
        html += `<optgroup label="Mes voix clonées (depuis audio)">${cloneVoices.map(opt).join('')}</optgroup>`;
    }
    return html;
}

function renderTable(rows, voices) {
    DOM.tableBody().innerHTML = rows.map(r => `
        <tr data-step-id="${escapeAttr(r.step_id)}">
            <td data-label="ID">${escapeHtml(r.step_id)}</td>
            <td data-label="Texte">
                <textarea class="fr-input fr-input--sm ov-tts-edit ov-assign-text" data-step-id="${escapeAttr(r.step_id)}" rows="2" title="Texte étape ${escapeAttr(r.step_id)}">${escapeHtml(r.text_full || r.text_preview)}</textarea>
            </td>
            <td data-label="Langue">
                <select class="fr-select fr-select--sm ov-assign-lang" data-step-id="${escapeAttr(r.step_id)}" title="Langue étape ${escapeAttr(r.step_id)}">
                    ${['fr','en','zh','jp','ko'].map(l =>
                        `<option value="${l}" ${l === r.language ? 'selected' : ''}>${l}</option>`
                    ).join('')}
                </select>
            </td>
            <td data-label="Voix">
                <select class="fr-select fr-select--sm ov-assign-voice" data-step-id="${escapeAttr(r.step_id)}" title="Voix étape ${escapeAttr(r.step_id)}">
                    ${renderVoiceOptions(voices, r.voice)}
                </select>
            </td>
            <td data-label="Vitesse">
                <div class="fr-range" data-fr-js-range="true">
                    <span class="fr-range__output">${r.speed}x</span>
                    <input type="range" class="ov-assign-speed" data-step-id="${escapeAttr(r.step_id)}"
                           min="0.5" max="2.0" step="0.1" value="${r.speed}"
                           title="Vitesse étape ${escapeAttr(r.step_id)}"
                           aria-valuetext="${r.speed}x">
                    <span class="fr-range__min">0.5x</span>
                    <span class="fr-range__max">2.0x</span>
                </div>
            </td>
            <td data-label="Actions">
                <div class="fr-btns-group fr-btns-group--sm fr-btns-group--inline">
                    <button class="fr-btn fr-btn--secondary fr-btn--sm"
                            data-action="preview" data-step-id="${escapeAttr(r.step_id)}"
                            title="Écouter un aperçu de l'étape ${escapeAttr(r.step_id)}">Écouter</button>
                    <button class="fr-btn fr-btn--tertiary fr-btn--sm fr-btn--icon-left fr-icon-delete-line ov-btn-danger"
                            data-action="delete" data-step-id="${escapeAttr(r.step_id)}"
                            title="Supprimer le segment ${escapeAttr(r.step_id)}">Supprimer</button>
                </div>
                <div class="ov-card-status" data-status-zone="${escapeAttr(r.step_id)}" aria-live="polite"></div>
            </td>
        </tr>
    `).join('');

    // Reinitialiser uniquement les composants range DSFR inseres dynamiquement.
    // NE PAS appeler dsfr.start() qui reinitialise TOUS les composants
    // (y compris les tabs, ce qui desynchronise aria-selected).
    if (window.dsfr && window.dsfr.Range) {
        document.querySelectorAll('#assign-table .fr-range').forEach(el => {
            window.dsfr.Range.create(el);
        });
    }
}

async function onTableAction(e) {
    const btn = e.target.closest('[data-action]');
    if (!btn) return;

    if (btn.dataset.action === 'delete') {
        await onDeleteStep(btn.dataset.stepId);
        return;
    }

    if (btn.dataset.action !== 'preview') return;
    const stepId = btn.dataset.stepId;
    const row = document.querySelector(`tr[data-step-id="${stepId}"]`);
    if (!row) return;

    const voiceEl = row.querySelector('.ov-assign-voice');
    if (!voiceEl) return;
    const voice = voiceEl.value;
    const lang = row.querySelector('.ov-assign-lang')?.value || 'fr';
    const speed = parseFloat(row.querySelector('.ov-assign-speed')?.value || '1');
    const text = row.querySelector('.ov-assign-text')?.value || '';

    const statusZone = document.querySelector(`[data-status-zone="${CSS.escape(stepId)}"]`);
    // Tiroir de preview audio unique (partagé par toutes les lignes du tableau).
    const audioContainer = document.getElementById('assign-preview-drawer');
    const audioEl = document.getElementById('assign-preview-drawer-audio');
    const drawerStep = document.getElementById('assign-preview-drawer-step');
    const drawerDownload = document.getElementById('assign-preview-drawer-download');
    if (drawerStep) drawerStep.textContent = stepId;
    if (drawerDownload) drawerDownload.setAttribute('download', `etape-${stepId}.wav`);

    // Note : pas de pre-check busy — OmniVoice a son propre semaphore et
    // mettra la requête en attente jusqu'à queue_timeout (5s). Si saturé
    // réellement, le backend renvoie 503 TTS_BUSY et le catch ci-dessous
    // affiche l'erreur. Le pre-check bloquait trop souvent sur busy=true
    // transitoire (preview d'un autre step encore en cours).

    // État chargement
    const originalLabel = btn.textContent;
    btn.classList.add('ov-preview-loading');
    btn.disabled = true;
    btn.textContent = 'Écoute…';
    if (statusZone) {
        statusZone.className = 'ov-card-status ov-card-status--loading';
        const wordCount = text.split(/\s+/).filter(Boolean).length;
        const estimate = wordCount > 80 ? '30-60s' : wordCount > 30 ? '15-30s' : '5-15s';
        statusZone.textContent = `Synthèse en cours (${estimate})…`;
    }
    if (audioContainer) audioContainer.hidden = true;

    try {
        const advanced = getAssignAdvancedParams();
        const payload = { voice, language: lang, speed, text };
        if (advanced) payload.advanced = advanced;
        const result = await apiPost(`/api/assign/preview/${stepId}`, payload);
        if (result.error) throw new Error(result.error.message || 'Erreur de synthèse');

        if (result.data?.audio_url) {
            const authUrl = authenticatedUrl(result.data.audio_url);
            if (!authUrl || authUrl === '') {
                if (statusZone) {
                    statusZone.className = 'ov-card-status ov-card-status--error';
                    statusZone.textContent = 'Session non initialisée. Rechargez la page.';
                }
            } else if (audioEl) {
                audioEl.addEventListener('error', () => {
                    if (statusZone) {
                        statusZone.className = 'ov-card-status ov-card-status--error';
                        statusZone.textContent = 'Fichier audio introuvable ou session expirée.';
                    }
                }, { once: true });
                audioEl.src = authUrl;
                if (audioContainer) {
                    audioContainer.hidden = false;
                    if (drawerDownload) drawerDownload.href = authUrl;
                }
                audioEl.play().then(() => {
                    if (statusZone) {
                        statusZone.className = 'ov-card-status';
                        statusZone.textContent = '';
                    }
                }).catch(() => {
                    if (statusZone) {
                        statusZone.className = 'ov-card-status ov-card-status--warning';
                        statusZone.textContent = 'Lecture automatique bloquée. Utilisez le player ci-dessous.';
                    }
                });
            }
        } else if (statusZone) {
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

function onTableInput(e) {
    if (e.target.classList.contains('ov-assign-speed')) {
        const v = e.target.value + 'x';
        e.target.setAttribute('aria-valuetext', v);
        e.target.setAttribute('title', v);
        const output = e.target.closest('.fr-range')?.querySelector('.fr-range__output');
        if (output) output.textContent = v;
    }
}

function onTableChange(e) {
}

async function onAddStep() {
    const idInput = DOM.addId();
    const textInput = DOM.addText();
    const stepId = idInput?.value.trim();
    const text = textInput?.value.trim();

    if (!stepId || !text) {
        DOM.status().innerHTML = '<p class="fr-alert fr-alert--warning fr-alert--sm"><span class="fr-alert__title">ID et texte requis.</span></p>';
        return;
    }

    if (assignData.some(r => r.step_id === stepId)) {
        DOM.status().innerHTML = `<p class="fr-alert fr-alert--warning fr-alert--sm"><span class="fr-alert__title">L'ID ${escapeHtml(stepId)} existe déjà.</span></p>`;
        return;
    }

    try {
        const result = await apiPost('/api/steps/add', { step_id: stepId, text_original: text });
        if (result.error) throw new Error(result.error.message || "Erreur lors de l'ajout");
        if (idInput) idInput.value = '';
        if (textInput) textInput.value = '';
        await loadAssignData();
        DOM.status().innerHTML = `<p class="fr-alert fr-alert--success fr-alert--sm"><span class="fr-alert__title">Étape ${escapeHtml(stepId)} ajoutée.</span></p>`;
    } catch (err) {
        DOM.status().innerHTML = `<p class="fr-alert fr-alert--error fr-alert--sm"><span class="fr-alert__title">${escapeHtml(err.message)}</span></p>`;
    }
}

async function onDeleteStep(stepId) {
    if (!confirm(`Supprimer l'étape ${stepId} ?`)) return;
    try {
        await apiPost(`/api/clean/delete/${stepId}`);
        await loadAssignData();
        DOM.status().innerHTML = `<p class="fr-alert fr-alert--info fr-alert--sm"><span class="fr-alert__title">Étape ${escapeHtml(stepId)} supprimée.</span></p>`;
    } catch (err) {
        DOM.status().innerHTML = `<p class="fr-alert fr-alert--error fr-alert--sm"><span class="fr-alert__title">${escapeHtml(err.message)}</span></p>`;
    }
}

function collectAssignments() {
    const assignments = {};
    const speeds = {};
    const languages = {};

    document.querySelectorAll('#assign-table tbody tr').forEach(row => {
        const stepId = row.dataset.stepId;
        assignments[stepId] = row.querySelector('.ov-assign-voice').value;
        languages[stepId] = row.querySelector('.ov-assign-lang').value;
        speeds[stepId] = parseFloat(row.querySelector('.ov-assign-speed').value);
    });

    return { assignments, speeds, languages };
}

async function onApplyAll() {
    const voice = DOM.voiceSelect().value;
    const lang = DOM.langSelect().value;
    const speed = parseFloat(DOM.speedRange().value);

    try {
        const result = await apiPost('/api/assign/apply-all', {
            voice, language: lang, speed
        });
        DOM.status().innerHTML = `<p class="fr-alert fr-alert--success fr-alert--sm"><span class="fr-alert__title">${escapeHtml(result.data.voice)} appliqué à ${result.data.applied} étapes</span></p>`;
        await loadAssignData();
    } catch (err) {
        DOM.status().innerHTML = `<p class="fr-alert fr-alert--error fr-alert--sm"><span class="fr-alert__title">${escapeHtml(err.message)}</span></p>`;
    }
}

async function autoSave() {
    try {
        const data = collectAssignments();
        if (Object.keys(data.assignments).length === 0) return;
        await apiPost('/api/assign', data);
    } catch { /* ignore */ }
}

async function onContinue() {
    try {
        const data = collectAssignments();
        await apiPost('/api/assign', data);
        eventBus.emit('navigate', 'tab-generate');
    } catch (err) {
        DOM.status().innerHTML = `<p class="fr-alert fr-alert--error fr-alert--sm"><span class="fr-alert__title">${escapeHtml(err.message)}</span></p>`;
    }
}

export default { init };
