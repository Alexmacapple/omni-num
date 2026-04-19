/**
 * tab-assign.js — Onglet 4 : Assignation des voix aux etapes.
 */
import { apiGet, apiPost, apiDelete, checkTtsStatus } from './api-client.js';
import { eventBus } from './app.js';
import { escapeHtml, escapeAttr } from './dom-utils.js';
import { authenticatedUrl } from './audio-player.js';

const NATIVE_VOICES = new Set([
    'vivian', 'serena', 'uncle_fu', 'dylan', 'eric',
    'ryan', 'aiden', 'ono_anna', 'sohee'
]);

const DOM = {
    voiceSelect: () => document.getElementById('assign-voice'),
    langSelect: () => document.getElementById('assign-lang'),
    speedRange: () => document.getElementById('assign-speed'),
    speedValue: () => document.getElementById('assign-speed-value'),
    instruction: () => document.getElementById('assign-instruction'),
    instructionInfo: () => document.getElementById('assign-instruction-info'),
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

    applyAllBtn.addEventListener('click', onApplyAll);
    nextBtn.addEventListener('click', onContinue);
    speedRange.addEventListener('input', () => {
        const v = DOM.speedRange().value + 'x';
        DOM.speedValue().textContent = v;
        DOM.speedRange().setAttribute('aria-valuetext', v);
        const output = document.querySelector('#assign-speed').closest('.fr-range')?.querySelector('.fr-range__output');
        if (output) output.textContent = v;
    });
    DOM.voiceSelect().addEventListener('change', onVoiceChange);

    // Delegation sur le tableau
    DOM.tableBody().addEventListener('click', onTableAction);
    DOM.tableBody().addEventListener('change', onTableChange);
    DOM.tableBody().addEventListener('input', onTableInput);

    // Ajout de segment
    const addBtn = DOM.addBtn();
    if (addBtn) addBtn.addEventListener('click', onAddStep);

    eventBus.on('tab-activated:tab-assign', loadAssignData);
    eventBus.on('tab-deactivated:tab-assign', autoSave);

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
    const voice = DOM.voiceSelect().value;
    const isNative = NATIVE_VOICES.has(voice.toLowerCase());
    DOM.instruction().disabled = !isNative;
    DOM.instructionInfo().hidden = isNative;
    if (!isNative) DOM.instruction().value = '';
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

function renderTable(rows, voices) {
    DOM.tableBody().innerHTML = rows.map(r => `
        <tr data-step-id="${escapeAttr(r.step_id)}">
            <td data-label="ID">${escapeHtml(r.step_id)}</td>
            <td data-label="Texte">
                <textarea class="fr-input fr-input--sm vx-tts-edit vx-assign-text" data-step-id="${escapeAttr(r.step_id)}" rows="2" title="Texte étape ${escapeAttr(r.step_id)}">${escapeHtml(r.text_full || r.text_preview)}</textarea>
            </td>
            <td data-label="Langue">
                <select class="fr-select fr-select--sm vx-assign-lang" data-step-id="${escapeAttr(r.step_id)}" title="Langue étape ${escapeAttr(r.step_id)}">
                    ${['fr','en','zh','jp','ko'].map(l =>
                        `<option value="${l}" ${l === r.language ? 'selected' : ''}>${l}</option>`
                    ).join('')}
                </select>
            </td>
            <td data-label="Voix">
                <select class="fr-select fr-select--sm vx-assign-voice" data-step-id="${escapeAttr(r.step_id)}" title="Voix étape ${escapeAttr(r.step_id)}">
                    ${voices.map(v =>
                        `<option value="${escapeAttr(v.name)}" ${v.name === r.voice ? 'selected' : ''}>${escapeHtml(v.name)}</option>`
                    ).join('')}
                </select>
            </td>
            <td data-label="Vitesse">
                <div class="fr-range" data-fr-js-range="true">
                    <span class="fr-range__output">${r.speed}x</span>
                    <input type="range" class="vx-assign-speed" data-step-id="${escapeAttr(r.step_id)}"
                           min="0.5" max="2.0" step="0.1" value="${r.speed}"
                           title="Vitesse étape ${escapeAttr(r.step_id)}"
                           aria-valuetext="${r.speed}x">
                    <span class="fr-range__min">0.5x</span>
                    <span class="fr-range__max">2.0x</span>
                </div>
            </td>
            <td data-label="Instruction">
                <input type="text" class="fr-input fr-input--sm vx-assign-instruct" data-step-id="${escapeAttr(r.step_id)}"
                       value="${escapeAttr(r.instruction || '')}"
                       title="Instruction étape ${escapeAttr(r.step_id)}"
                       placeholder="Instruction"
                       ${(voiceTypes[r.voice] || 'custom') !== 'native' ? 'disabled' : ''}>
            </td>
            <td data-label="Actions">
                <div class="fr-btns-group fr-btns-group--sm fr-btns-group--inline">
                    <button class="fr-btn fr-btn--secondary fr-btn--sm"
                            data-action="preview" data-step-id="${escapeAttr(r.step_id)}"
                            title="Écouter un aperçu de l'étape ${escapeAttr(r.step_id)}">Écouter</button>
                    <button class="fr-btn fr-btn--secondary fr-btn--sm"
                            data-action="delete" data-step-id="${escapeAttr(r.step_id)}"
                            title="Supprimer le segment ${escapeAttr(r.step_id)}">Supprimer le segment ${escapeHtml(String(r.step_id))}</button>
                </div>
                <div class="vx-card-status" data-status-zone="${escapeAttr(r.step_id)}" aria-live="polite"></div>
                <div class="vx-audio-container" data-audio-zone="${escapeAttr(r.step_id)}" hidden>
                    <p class="fr-text--xs fr-mb-0">Audio étape ${escapeHtml(r.step_id)}</p>
                    <audio class="vx-card-audio" controls title="Audio généré pour l'étape ${escapeAttr(r.step_id)}"></audio>
                    <a class="fr-btn fr-btn--tertiary-no-outline fr-btn--sm fr-mt-1v vx-download-link"
                       data-action="download" data-step-id="${escapeAttr(r.step_id)}"
                       download="etape-${escapeAttr(r.step_id)}.wav"
                       title="Télécharger l'audio de l'étape ${escapeAttr(r.step_id)}">Télécharger</a>
                </div>
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

    const voiceEl = row.querySelector('.vx-assign-voice');
    if (!voiceEl) return;
    const voice = voiceEl.value;
    const lang = row.querySelector('.vx-assign-lang')?.value || 'fr';
    const speed = parseFloat(row.querySelector('.vx-assign-speed')?.value || '1');
    const instruction = row.querySelector('.vx-assign-instruct')?.value || '';
    const text = row.querySelector('.vx-assign-text')?.value || '';

    const statusZone = document.querySelector(`[data-status-zone="${CSS.escape(stepId)}"]`);
    const audioContainer = document.querySelector(`[data-audio-zone="${CSS.escape(stepId)}"]`);
    const audioEl = audioContainer?.querySelector('audio');

    // Verifier si le moteur TTS est occupe
    const tts = await checkTtsStatus();
    if (tts?.busy) {
        if (statusZone) {
            statusZone.className = 'vx-card-status vx-card-status--warning';
            statusZone.textContent =
                'Une synthèse est déjà en cours. Réessayez dans quelques secondes.';
        }
        return;
    }

    // État chargement
    const originalLabel = btn.textContent;
    btn.classList.add('vx-preview-loading');
    btn.disabled = true;
    btn.textContent = 'Écoute…';
    if (statusZone) {
        statusZone.className = 'vx-card-status vx-card-status--loading';
        const wordCount = text.split(/\s+/).filter(Boolean).length;
        const estimate = wordCount > 80 ? '30-60s' : wordCount > 30 ? '15-30s' : '5-15s';
        statusZone.textContent = `Synthèse en cours (${estimate})…`;
    }
    if (audioContainer) audioContainer.hidden = true;

    try {
        const result = await apiPost(`/api/assign/preview/${stepId}`, {
            voice, language: lang, speed, instruction, text,
        });
        if (result.error) throw new Error(result.error.message || 'Erreur de synthèse');

        if (result.data?.audio_url) {
            const authUrl = authenticatedUrl(result.data.audio_url);
            if (!authUrl || authUrl === '') {
                if (statusZone) {
                    statusZone.className = 'vx-card-status vx-card-status--error';
                    statusZone.textContent = 'Session non initialisée. Rechargez la page.';
                }
            } else if (audioEl) {
                audioEl.addEventListener('error', () => {
                    if (statusZone) {
                        statusZone.className = 'vx-card-status vx-card-status--error';
                        statusZone.textContent = 'Fichier audio introuvable ou session expirée.';
                    }
                }, { once: true });
                audioEl.src = authUrl;
                if (audioContainer) {
                    audioContainer.hidden = false;
                    const dlLink = audioContainer.querySelector('.vx-download-link');
                    if (dlLink) dlLink.href = authUrl;
                }
                audioEl.play().then(() => {
                    if (statusZone) {
                        statusZone.className = 'vx-card-status';
                        statusZone.textContent = '';
                    }
                }).catch(() => {
                    if (statusZone) {
                        statusZone.className = 'vx-card-status vx-card-status--warning';
                        statusZone.textContent = 'Lecture automatique bloquée. Utilisez le player ci-dessous.';
                    }
                });
            }
        } else if (statusZone) {
            statusZone.className = 'vx-card-status';
            statusZone.textContent = '';
        }
    } catch (err) {
        if (statusZone) {
            statusZone.className = 'vx-card-status vx-card-status--error';
            statusZone.textContent = err.message || 'Échec de la prévisualisation';
        }
    } finally {
        btn.classList.remove('vx-preview-loading');
        btn.disabled = false;
        btn.textContent = originalLabel;
    }
}

function onTableInput(e) {
    if (e.target.classList.contains('vx-assign-speed')) {
        const v = e.target.value + 'x';
        e.target.setAttribute('aria-valuetext', v);
        e.target.setAttribute('title', v);
        const output = e.target.closest('.fr-range')?.querySelector('.fr-range__output');
        if (output) output.textContent = v;
    }
}

function onTableChange(e) {
    if (e.target.classList.contains('vx-assign-voice')) {
        const stepId = e.target.dataset.stepId;
        const voice = e.target.value;
        const isNative = NATIVE_VOICES.has(voice.toLowerCase());
        const row = document.querySelector(`tr[data-step-id="${stepId}"]`);
        const instruct = row?.querySelector('.vx-assign-instruct');
        if (instruct) {
            instruct.disabled = !isNative;
            if (!isNative) instruct.value = '';
        }
    }
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
    const instructions = {};
    const speeds = {};
    const languages = {};

    document.querySelectorAll('#assign-table tbody tr').forEach(row => {
        const stepId = row.dataset.stepId;
        assignments[stepId] = row.querySelector('.vx-assign-voice').value;
        languages[stepId] = row.querySelector('.vx-assign-lang').value;
        speeds[stepId] = parseFloat(row.querySelector('.vx-assign-speed').value);
        const inst = row.querySelector('.vx-assign-instruct').value;
        if (inst) instructions[stepId] = inst;
    });

    return { assignments, instructions, speeds, languages };
}

async function onApplyAll() {
    const voice = DOM.voiceSelect().value;
    const lang = DOM.langSelect().value;
    const speed = parseFloat(DOM.speedRange().value);
    const instruction = DOM.instruction().value;

    try {
        const result = await apiPost('/api/assign/apply-all', {
            voice, language: lang, speed, instruction
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
