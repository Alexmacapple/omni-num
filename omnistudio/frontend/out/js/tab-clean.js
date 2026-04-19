/**
 * tab-clean.js — Onglet 2 : Preparation / Nettoyage LLM (SSE).
 */
import { escapeHtml, sanitizeHtml } from './dom-utils.js';
import { apiGet, apiPost, fetchSSE } from './api-client.js';
import { eventBus } from './app.js';

const DOM = {
    glossary: () => document.getElementById('clean-glossary'),
    jsonFile: () => document.getElementById('clean-json'),
    cleanBtn: () => document.getElementById('clean-btn'),
    validateBtn: () => document.getElementById('clean-validate-btn'),
    resumeContainer: () => document.getElementById('clean-resume'),
    resumeBtn: () => document.getElementById('clean-resume-btn'),
    progress: () => document.getElementById('clean-progress'),
    progressBar: () => document.getElementById('clean-progress-bar'),
    progressText: () => document.getElementById('clean-progress-text'),
    status: () => document.getElementById('clean-status'),
    tableContainer: () => document.getElementById('clean-table-container'),
    tableBody: () => document.querySelector('#clean-table tbody'),
    diffAccordion: () => document.getElementById('clean-diff-accordion'),
    diffContent: () => document.getElementById('clean-diff-content'),
    nextBtn: () => document.getElementById('clean-next-btn'),
    addId: () => document.getElementById('clean-add-id'),
    addText: () => document.getElementById('clean-add-text'),
    addBtn: () => document.getElementById('clean-add-btn'),
    deleteAllBtn: () => document.getElementById('clean-delete-all-btn'),
};

let stepsData = [];

export function init() {
    const cleanBtn = DOM.cleanBtn();
    const resumeBtn = DOM.resumeBtn();
    const validateBtn = DOM.validateBtn();
    const nextBtn = DOM.nextBtn();
    const tableBody = DOM.tableBody();

    if (cleanBtn) cleanBtn.addEventListener('click', onClean);
    if (resumeBtn) resumeBtn.addEventListener('click', onClean);
    if (validateBtn) validateBtn.addEventListener('click', onValidateAll);
    if (nextBtn) nextBtn.addEventListener('click', () => eventBus.emit('navigate', 'tab-voices'));

    const addBtn = DOM.addBtn();
    if (addBtn) addBtn.addEventListener('click', onAddStep);
    const deleteAllBtn = DOM.deleteAllBtn();
    if (deleteAllBtn) deleteAllBtn.addEventListener('click', onDeleteAll);
    if (tableBody) {
        tableBody.addEventListener('click', onTableAction);
        tableBody.addEventListener('change', onTableChange);
        tableBody.addEventListener('input', onTextareaEdit);
    }

    // Pagination du tableau
    const paginationList = document.getElementById('clean-pagination-list');
    if (paginationList) {
        paginationList.addEventListener('click', (e) => {
            const btn = e.target.closest('button[data-page]');
            if (!btn || btn.disabled) return;
            const page = parseInt(btn.dataset.page, 10);
            if (!isNaN(page) && page > 0) {
                _cleanCurrentPage = page;
                renderTable(_cleanAllSteps);
            }
        });
    }

    eventBus.on('tab-activated:tab-clean', loadSteps);
    eventBus.on('tab-deactivated:tab-clean', autoSaveEdits);

    eventBus.on('session-reset', () => {
        stepsData = [];
        DOM.tableContainer().hidden = true;
        if (DOM.tableBody()) DOM.tableBody().innerHTML = '';
        DOM.progress().hidden = true;
        DOM.resumeContainer().hidden = true;
        DOM.nextBtn().disabled = true;
        const status = DOM.status();
        if (status) status.innerHTML = '';
        // PRD-018 : réafficher état vide
        const emptyState = document.getElementById('clean-empty-state');
        if (emptyState) emptyState.hidden = false;
    });
}

async function autoSaveEdits() {
    const edits = collectEdits();
    if (Object.keys(edits).length === 0) return;
    try {
        for (const [stepId, text] of Object.entries(edits)) {
            await apiPost(`/api/clean/accept/${stepId}`, { text_tts: text });
            const step = stepsData.find(s => String(s.step_id) === String(stepId));
            if (step) step.text_tts = text;
        }
    } catch {
        // Ignore — les editions restent dans le DOM
    }
}

async function loadSteps() {
    try {
        const result = await apiGet('/api/steps');
        if (result.error || !result.data) return;
        stepsData = result.data.steps || [];
        renderTable(stepsData);
        updateTableVisibility();

    } catch (err) {
        const status = DOM.status();
        if (status) status.innerHTML = `<p class="fr-alert fr-alert--error fr-alert--sm"><span class="fr-alert__title">${escapeHtml(err.message)}</span></p>`;
    }
}

function updateTableVisibility() {
    const hasSteps = stepsData.length > 0;
    DOM.tableContainer().hidden = !hasSteps;
    // PRD-018 : état vide
    const emptyState = document.getElementById('clean-empty-state');
    if (emptyState) emptyState.hidden = hasSteps;
    const validateBtn = DOM.validateBtn();
    if (validateBtn) validateBtn.disabled = !hasSteps;
    const deleteAllBtn = DOM.deleteAllBtn();
    if (deleteAllBtn) deleteAllBtn.disabled = !hasSteps;
    const nextBtn = DOM.nextBtn();
    if (nextBtn) nextBtn.disabled = !hasSteps;
}

function statusOption(value, label, current) {
    return `<option value="${value}"${current === value ? ' selected' : ''}>${label}</option>`;
}

// Pagination du tableau : 25 lignes/page par défaut. Au-delà, on pagine pour
// éviter un scroll infini quand un scénario dépasse ~100 segments.
const CLEAN_ITEMS_PER_PAGE = 25;
let _cleanCurrentPage = 1;
let _cleanAllSteps = [];

function renderCleanPagination(totalPages, totalItems, pageStart, pageEnd) {
    const nav = document.getElementById('clean-pagination');
    const list = document.getElementById('clean-pagination-list');
    const summary = document.getElementById('clean-pagination-summary');
    if (!nav || !list || !summary) return;
    if (totalPages <= 1) { nav.hidden = true; return; }
    nav.hidden = false;
    summary.textContent = `Segments ${pageStart}-${pageEnd} sur ${totalItems}`;
    const pages = [];
    const current = _cleanCurrentPage;
    pages.push(`<li><button class="fr-pagination__link fr-pagination__link--prev fr-pagination__link--lg-label" data-page="${current - 1}" ${current === 1 ? 'disabled' : ''}>Précédent</button></li>`);
    for (let p = 1; p <= totalPages; p++) {
        const active = p === current;
        pages.push(`<li><button class="fr-pagination__link" data-page="${p}" aria-current="${active ? 'page' : 'false'}" ${active ? 'aria-disabled="true"' : ''}>${p}</button></li>`);
    }
    pages.push(`<li><button class="fr-pagination__link fr-pagination__link--next fr-pagination__link--lg-label" data-page="${current + 1}" ${current === totalPages ? 'disabled' : ''}>Suivant</button></li>`);
    list.innerHTML = pages.join('');
}

function renderTable(steps) {
    const tbody = DOM.tableBody();
    if (!tbody) return;
    _cleanAllSteps = steps;
    const total = steps.length;
    const totalPages = Math.max(1, Math.ceil(total / CLEAN_ITEMS_PER_PAGE));
    if (_cleanCurrentPage > totalPages) _cleanCurrentPage = totalPages;
    const start = (_cleanCurrentPage - 1) * CLEAN_ITEMS_PER_PAGE;
    const end = Math.min(start + CLEAN_ITEMS_PER_PAGE, total);
    const pageSteps = steps.slice(start, end);
    renderCleanPagination(totalPages, total, start + 1, end);
    tbody.innerHTML = pageSteps.map(s => {
        const status = s.cleaning_status || 'pending';

        return `<tr data-step-id="${escapeHtml(String(s.step_id))}">
            <td data-label="ID">${escapeHtml(String(s.step_id))}</td>
            <td data-label="Texte original"><div class="ov-text-cell">${escapeHtml(s.text_original)}</div></td>
            <td data-label="Texte TTS">
                <textarea class="fr-input fr-input--sm ov-tts-edit"
                          data-step-id="${escapeHtml(String(s.step_id))}"
                          title="Texte TTS étape ${escapeHtml(String(s.step_id))}"
                          rows="2">${escapeHtml(s.text_tts || '')}</textarea>
            </td>
            <td data-label="Statut">
                <select class="fr-select fr-select--sm ov-status-select" data-action="status" data-step-id="${escapeHtml(String(s.step_id))}" title="Statut étape ${escapeHtml(String(s.step_id))}">
                    ${statusOption('pending', 'En attente', status)}
                    ${statusOption('cleaned', 'Nettoyé', status)}
                    ${statusOption('validated', 'Validé', status)}
                </select>
            </td>
            <td>
                <div class="fr-btns-group fr-btns-group--sm fr-btns-group--inline">
                    <button class="fr-btn fr-btn--tertiary-no-outline fr-btn--sm fr-icon-refresh-line"
                            title="Nettoyer l'étape ${escapeHtml(String(s.step_id))} avec l'IA" data-action="clean-single" data-step-id="${s.step_id}" type="button">
                        <span class="fr-sr-only">Nettoyer étape ${escapeHtml(String(s.step_id))}</span>
                    </button>
                    <button class="fr-btn fr-btn--tertiary-no-outline fr-btn--sm fr-icon-eye-line"
                            title="Voir le diff de l'étape ${escapeHtml(String(s.step_id))}" data-action="diff" data-step-id="${s.step_id}" type="button">
                        <span class="fr-sr-only">Voir le diff étape ${escapeHtml(String(s.step_id))}</span>
                    </button>
                    <button class="fr-btn fr-btn--tertiary-no-outline fr-btn--sm fr-icon-check-line"
                            title="Accepter l'étape ${escapeHtml(String(s.step_id))}" data-action="accept" data-step-id="${s.step_id}" type="button">
                        <span class="fr-sr-only">Accepter étape ${escapeHtml(String(s.step_id))}</span>
                    </button>
                    <button class="fr-btn fr-btn--tertiary-no-outline fr-btn--sm fr-icon-delete-line"
                            title="Supprimer l'étape ${escapeHtml(String(s.step_id))}" data-action="delete" data-step-id="${s.step_id}" type="button">
                        <span class="fr-sr-only">Supprimer étape ${escapeHtml(String(s.step_id))}</span>
                    </button>
                </div>
            </td>
        </tr>`;
    }).join('');
}

async function onTableAction(e) {
    const btn = e.target.closest('button[data-action]');
    if (!btn) return;

    const action = btn.dataset.action;
    const stepId = btn.dataset.stepId;

    if (action === 'clean-single') {
        await cleanSingle(stepId, btn);
    } else if (action === 'diff') {
        await showDiff(stepId);
    } else if (action === 'accept') {
        await acceptStep(stepId);
    } else if (action === 'delete') {
        await deleteStep(stepId);
    }
}

async function onTableChange(e) {
    const select = e.target.closest('select[data-action="status"]');
    if (!select) return;
    const stepId = select.dataset.stepId;
    const newStatus = select.value;
    await updateStepStatus(stepId, newStatus);
}

function onTextareaEdit(e) {
    const textarea = e.target.closest('.ov-tts-edit');
    if (!textarea) return;
    const stepId = textarea.dataset.stepId;
    const select = document.querySelector(`select[data-step-id="${stepId}"]`);
    if (select && select.value !== 'pending') {
        select.value = 'pending';
    }
}

async function onAddStep() {
    const idInput = DOM.addId();
    const textInput = DOM.addText();
    const stepId = idInput?.value.trim();
    const text = textInput?.value.trim();

    if (!stepId || !text) {
        const status = DOM.status();
        if (status) status.innerHTML = '<p class="fr-alert fr-alert--warning fr-alert--sm"><span class="fr-alert__title">ID et texte requis.</span></p>';
        return;
    }

    if (stepsData.some(s => String(s.step_id) === stepId)) {
        const status = DOM.status();
        if (status) status.innerHTML = `<p class="fr-alert fr-alert--warning fr-alert--sm"><span class="fr-alert__title">L'ID ${escapeHtml(stepId)} existe déjà.</span></p>`;
        return;
    }

    try {
        await apiPost('/api/steps/add', { step_id: stepId, text_original: text });
        stepsData.push({ step_id: stepId, text_original: text, text_tts: '', cleaning_status: 'pending' });
        renderTable(stepsData);
        updateTableVisibility();
        if (idInput) idInput.value = '';
        if (textInput) textInput.value = '';
    } catch (err) {
        const status = DOM.status();
        if (status) status.innerHTML = `<p class="fr-alert fr-alert--error fr-alert--sm"><span class="fr-alert__title">${escapeHtml(err.message)}</span></p>`;
    }
}

async function onDeleteAll() {
    if (!confirm(`Supprimer les ${stepsData.length} segments ? Cette action est irréversible.`)) return;
    try {
        await apiPost('/api/clean/delete-all');
        stepsData = [];
        renderTable(stepsData);
        updateTableVisibility();
        const status = DOM.status();
        if (status) status.innerHTML = '<p class="fr-alert fr-alert--info fr-alert--sm"><span class="fr-alert__title">Tous les segments ont été supprimés.</span></p>';
    } catch (err) {
        const status = DOM.status();
        if (status) status.innerHTML = `<p class="fr-alert fr-alert--error fr-alert--sm"><span class="fr-alert__title">${escapeHtml(err.message)}</span></p>`;
    }
}

async function cleanSingle(stepId, btn) {
    btn.disabled = true;
    btn.classList.add('ov-spin');
    try {
        const result = await apiPost(`/api/clean/single/${stepId}`, {});
        if (result.error) throw new Error(result.error.message || 'Erreur nettoyage');
        const d = result.data;
        const textarea = document.querySelector(`.ov-tts-edit[data-step-id="${stepId}"]`);
        if (textarea) textarea.value = d.text_tts;
        const select = document.querySelector(`select[data-step-id="${stepId}"]`);
        if (select) select.value = 'cleaned';
        const step = stepsData.find(s => String(s.step_id) === String(stepId));
        if (step) {
            step.text_tts = d.text_tts;
            step.cleaning_status = 'cleaned';
        }
        const status = DOM.status();
        const label = d.fallback ? '(fallback)' : '(LLM)';
        if (status) status.innerHTML = `<p class="fr-alert fr-alert--success fr-alert--sm"><span class="fr-alert__title">Étape ${escapeHtml(stepId)} nettoyée ${label}</span></p>`;
    } catch (err) {
        const status = DOM.status();
        if (status) status.innerHTML = `<p class="fr-alert fr-alert--error fr-alert--sm"><span class="fr-alert__title">${escapeHtml(err.message)}</span></p>`;
    } finally {
        btn.disabled = false;
        btn.classList.remove('ov-spin');
    }
}

async function deleteStep(stepId) {
    if (!confirm(`Supprimer l'étape ${stepId} ?`)) return;
    try {
        await apiPost(`/api/clean/delete/${stepId}`);
        stepsData = stepsData.filter(s => String(s.step_id) !== String(stepId));
        renderTable(stepsData);
        updateTableVisibility();
        const status = DOM.status();
        if (status) status.innerHTML = `<p class="fr-alert fr-alert--info fr-alert--sm"><span class="fr-alert__title">Étape ${escapeHtml(stepId)} supprimée.</span></p>`;
    } catch (err) {
        const status = DOM.status();
        if (status) status.innerHTML = `<p class="fr-alert fr-alert--error fr-alert--sm"><span class="fr-alert__title">${escapeHtml(err.message)}</span></p>`;
    }
}

async function updateStepStatus(stepId, newStatus) {
    try {
        await apiPost(`/api/clean/status/${stepId}`, { status: newStatus });
        const step = stepsData.find(s => String(s.step_id) === String(stepId));
        if (step) step.cleaning_status = newStatus;
        checkAllValidated();
    } catch (err) {
        const status = DOM.status();
        if (status) status.innerHTML = `<p class="fr-alert fr-alert--error fr-alert--sm"><span class="fr-alert__title">${escapeHtml(err.message)}</span></p>`;
    }
}

async function showDiff(stepId) {
    try {
        const result = await apiGet(`/api/clean/diff/${stepId}`);
        if (result.error) return;
        const diffContent = DOM.diffContent();
        if (diffContent) diffContent.innerHTML = sanitizeHtml(result.data.diff_html);
        const accordion = DOM.diffAccordion();
        if (accordion) {
            accordion.hidden = false;
            const btn = accordion.querySelector('.fr-accordion__btn');
            if (btn && btn.getAttribute('aria-expanded') === 'false') btn.click();
        }
    } catch (err) {
        const status = DOM.status();
        if (status) status.innerHTML = `<p class="fr-alert fr-alert--error fr-alert--sm"><span class="fr-alert__title">${escapeHtml(err.message)}</span></p>`;
    }
}

async function acceptStep(stepId) {
    const textarea = document.querySelector(`.ov-tts-edit[data-step-id="${stepId}"]`);
    const textTts = textarea?.value || '';

    try {
        await apiPost(`/api/clean/accept/${stepId}`, { text_tts: textTts });
        const select = document.querySelector(`select[data-step-id="${stepId}"]`);
        if (select) select.value = 'validated';
        const step = stepsData.find(s => String(s.step_id) === String(stepId));
        if (step) {
            step.cleaning_status = 'validated';
            step.text_tts = textTts;
        }
        checkAllValidated();
    } catch (err) {
        const status = DOM.status();
        if (status) status.innerHTML = `<p class="fr-alert fr-alert--error fr-alert--sm"><span class="fr-alert__title">${escapeHtml(err.message)}</span></p>`;
    }
}

function parseGlossary(text) {
    const glossary = {};
    if (!text) return glossary;
    for (const line of text.split('\n')) {
        const trimmed = line.trim();
        if (trimmed.includes('=')) {
            const [key, ...rest] = trimmed.split('=');
            glossary[key.trim()] = rest.join('=').trim();
        }
    }
    return glossary;
}

async function onClean() {
    const cleanBtn = DOM.cleanBtn();
    const resumeContainer = DOM.resumeContainer();
    const progress = DOM.progress();
    const progressBar = DOM.progressBar();
    const progressText = DOM.progressText();

    if (cleanBtn) cleanBtn.disabled = true;
    if (resumeContainer) resumeContainer.hidden = true;
    if (progress) progress.hidden = false;
    if (progressBar) { progressBar.value = 0; progressBar.setAttribute('aria-busy', 'true'); }
    if (progressText) progressText.textContent = 'Démarrage...';

    const glossary = parseGlossary(DOM.glossary()?.value || '');

    let correctionsJson = null;
    const jsonFileInput = DOM.jsonFile();
    if (jsonFileInput?.files[0]) {
        try {
            const text = await jsonFileInput.files[0].text();
            correctionsJson = JSON.parse(text);
        } catch { /* ignore */ }
    }

    const body = { glossary };
    if (correctionsJson) body.corrections_json = correctionsJson;

    await fetchSSE('/api/clean', body, {
        onProgress(data) {
            if (progressBar) progressBar.value = data.progress || 0;
            if (progressText) progressText.textContent = data.message || '';

            if (data.step_id && data.text_tts) {
                const textarea = document.querySelector(`.ov-tts-edit[data-step-id="${data.step_id}"]`);
                if (textarea && document.activeElement !== textarea) {
                    textarea.value = data.text_tts;
                }
                const statusSelect = document.querySelector(`select[data-step-id="${data.step_id}"]`);
                if (statusSelect) statusSelect.value = 'cleaned';
                const step = stepsData.find(s => String(s.step_id) === String(data.step_id));
                if (step) {
                    step.text_tts = data.text_tts;
                    step.cleaning_status = 'cleaned';
                }
            }
        },
        onDone(data) {
            if (progress) progress.hidden = true;
            if (progressBar) progressBar.removeAttribute('aria-busy');
            if (cleanBtn) cleanBtn.disabled = false;
            const validateBtn = DOM.validateBtn();
            if (validateBtn) validateBtn.disabled = false;
            const msg = data.fallback > 0
                ? `${data.cleaned} textes nettoyés (${data.fallback} en mode fallback)`
                : `${data.cleaned} textes nettoyés`;
            const status = DOM.status();
            if (status) status.innerHTML = `<p class="fr-alert fr-alert--success fr-alert--sm"><span class="fr-alert__title">${msg}</span></p>`;
        },
        onError(data) {
            if (progress) progress.hidden = true;
            if (progressBar) progressBar.removeAttribute('aria-busy');
            if (cleanBtn) cleanBtn.disabled = false;
            if (resumeContainer) resumeContainer.hidden = false;
            const status = DOM.status();
            if (status) status.innerHTML = `<p class="fr-alert fr-alert--error fr-alert--sm"><span class="fr-alert__title">${escapeHtml(data?.message || 'Erreur')}</span></p>`;
        },
        onAbort() {
            if (progress) progress.hidden = true;
            if (progressBar) progressBar.removeAttribute('aria-busy');
            if (cleanBtn) cleanBtn.disabled = false;
            if (resumeContainer) resumeContainer.hidden = false;
            const status = DOM.status();
            if (status) status.innerHTML = '<p class="fr-alert fr-alert--warning fr-alert--sm"><span class="fr-alert__title">Nettoyage interrompu.</span></p>';
        },
    });
}

function collectEdits() {
    const edits = {};
    document.querySelectorAll('.ov-tts-edit').forEach(textarea => {
        const stepId = textarea.dataset.stepId;
        const step = stepsData.find(s => String(s.step_id) === String(stepId));
        if (step && textarea.value !== (step.text_tts || '')) {
            edits[stepId] = textarea.value;
        }
    });
    return edits;
}

async function onValidateAll() {
    try {
        const edits = collectEdits();
        await apiPost('/api/clean/validate', { edits });
        const status = DOM.status();
        if (status) status.innerHTML = '<p class="fr-alert fr-alert--success fr-alert--sm"><span class="fr-alert__title">Tous les textes sont validés.</span></p>';
        const nextBtn = DOM.nextBtn();
        if (nextBtn) nextBtn.disabled = false;

        document.querySelectorAll('#clean-table select.ov-status-select').forEach(select => {
            select.value = 'validated';
        });
    } catch (err) {
        const status = DOM.status();
        if (status) status.innerHTML = `<p class="fr-alert fr-alert--error fr-alert--sm"><span class="fr-alert__title">${escapeHtml(err.message)}</span></p>`;
    }
}

function checkAllValidated() {
    const allValidated = stepsData.every(s => s.cleaning_status === 'validated');
    if (allValidated) {
        const nextBtn = DOM.nextBtn();
        if (nextBtn) nextBtn.disabled = false;
    }
}

export default { init };
