/**
 * tab-import.js — Onglet 1 : Import de fichier.
 */
import { escapeHtml, escapeAttr } from './dom-utils.js';
import { uploadFile, apiPost } from './api-client.js';
import { eventBus } from './app.js';

const DOM = {
    fileInput: () => document.getElementById('import-file'),
    excelOptions: () => document.getElementById('import-excel-options'),
    sheetSelect: () => document.getElementById('import-sheet'),
    importBtn: () => document.getElementById('import-btn'),
    status: () => document.getElementById('import-status'),
    tableContainer: () => document.getElementById('import-table-container'),
    tableBody: () => document.querySelector('#import-table tbody'),
    selectAll: () => document.getElementById('import-select-all'),
    selectionBar: () => document.getElementById('import-selection-bar'),
    selectionCount: () => document.getElementById('import-selection-count'),
    nextBtn: () => document.getElementById('import-next-btn'),
    progressBar: () => document.querySelector('.ov-upload-progress'),
    sampleBtn: () => document.getElementById('import-sample-btn'),
    sampleConfirm: () => document.getElementById('import-sample-confirm'),
    sampleConfirmBtn: () => document.getElementById('import-sample-confirm-btn'),
    sampleCancelBtn: () => document.getElementById('import-sample-cancel-btn'),
};

const SPLEEN_MD = `### Étape 1
J'ai plus de souvenirs que si j'avais mille ans.

### Étape 2
Un gros meuble à tiroirs encombré de bilans,
De vers, de billets doux, de procès, de romances,
Avec de lourds cheveux roulés dans des quittances,
Cache moins de secrets que mon triste cerveau.
C'est une pyramide, un immense caveau,
Qui contient plus de morts que la fosse commune.
- Je suis un cimetière abhorré de la lune,

### Étape 3
Où comme des remords se traînent de longs vers
Qui s'acharnent toujours sur mes morts les plus chers.
Je suis un vieux boudoir plein de roses fanées,
Où gît tout un fouillis de modes surannées,
Où les pastels plaintifs et les pâles Boucher,
Seuls, respirent l'odeur d'un flacon débouché.

### Étape 4
Rien n'égale en longueur les boiteuses journées,
Quand sous les lourds flocons des neigeuses années
L'ennui, fruit de la morne incuriosité,
Prend les proportions de l'immortalité.

### Étape 5
- Désormais tu n'es plus, ô matière vivante !
Qu'un granit entouré d'une vague épouvante,
Assoupi dans le fond d'un Saharah brumeux ;
Un vieux sphinx ignoré du monde insoucieux,
Oublié sur la carte, et dont l'humeur farouche
Ne chante qu'aux rayons du soleil qui se couche.
`;

let steps = [];

export function init() {
    const fileInput = DOM.fileInput();
    const importBtn = DOM.importBtn();
    const selectAll = DOM.selectAll();
    const nextBtn = DOM.nextBtn();
    const tableBody = DOM.tableBody();

    if (fileInput) fileInput.addEventListener('change', onFileChange);
    if (importBtn) importBtn.addEventListener('click', onImport);
    if (selectAll) selectAll.addEventListener('change', onSelectAllToggle);
    if (nextBtn) nextBtn.addEventListener('click', onContinue);
    if (tableBody) tableBody.addEventListener('change', onCheckboxChange);

    const sampleBtn = DOM.sampleBtn();
    if (sampleBtn) sampleBtn.addEventListener('click', onLoadSample);
    const sampleConfirmBtn = DOM.sampleConfirmBtn();
    if (sampleConfirmBtn) sampleConfirmBtn.addEventListener('click', () => {
        DOM.sampleConfirm().hidden = true;
        importSampleFile();
    });
    const sampleCancelBtn = DOM.sampleCancelBtn();
    if (sampleCancelBtn) sampleCancelBtn.addEventListener('click', () => {
        DOM.sampleConfirm().hidden = true;
    });

    const skipTopBtn = document.getElementById('import-skip-top-btn');
    if (skipTopBtn) skipTopBtn.addEventListener('click', () => eventBus.emit('navigate', 'tab-clean'));

    eventBus.on('session-reset', () => {
        steps = [];
        DOM.tableContainer().hidden = true;
        if (DOM.tableBody()) DOM.tableBody().innerHTML = '';
        DOM.selectionBar().hidden = true;
        DOM.nextBtn().disabled = true;
        DOM.importBtn().disabled = true;
        const fileInput = DOM.fileInput();
        if (fileInput) fileInput.value = '';
        DOM.excelOptions().hidden = true;
        const sampleConfirm = DOM.sampleConfirm();
        if (sampleConfirm) sampleConfirm.hidden = true;
        const status = DOM.status();
        if (status) status.innerHTML = '';
    });
}

function onLoadSample() {
    if (steps.length > 0) {
        DOM.sampleConfirm().hidden = false;
        DOM.sampleConfirm().scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    } else {
        importSampleFile();
    }
}

async function importSampleFile() {
    const blob = new Blob([SPLEEN_MD], { type: 'text/markdown' });
    const file = new File([blob], 'spleen.md', { type: 'text/markdown' });

    const formData = new FormData();
    formData.append('file', file);
    formData.append('sheet', 'PLAN');
    formData.append('mode', 'replace');

    DOM.importBtn().disabled = true;
    DOM.status().innerHTML = '<p class="fr-badge fr-badge--info fr-badge--no-icon">Import en cours...</p>';

    try {
        const result = await uploadFile('/api/import', formData, () => {});

        if (result.error) throw new Error(result.error.message);

        steps = result.data.steps;
        renderTable(steps);
        updateSelectionCount();
        DOM.tableContainer().hidden = false;
        DOM.selectionBar().hidden = false;
        DOM.status().innerHTML = `<p class="fr-alert fr-alert--success fr-alert--sm"><span class="fr-alert__title">${steps.length} étapes importées depuis spleen.md</span></p>`;
    } catch (err) {
        DOM.status().innerHTML = `<p class="fr-alert fr-alert--error fr-alert--sm"><span class="fr-alert__title">${escapeHtml(err.message)}</span></p>`;
    } finally {
        DOM.importBtn().disabled = false;
    }
}

function onFileChange(e) {
    const file = e.target.files[0];
    if (!file) return;

    DOM.importBtn().disabled = false;

    if (file.name.endsWith('.xlsx')) {
        DOM.excelOptions().hidden = false;
    } else {
        DOM.excelOptions().hidden = true;
    }
}

async function onImport() {
    const file = DOM.fileInput().files[0];
    if (!file) return;

    DOM.importBtn().disabled = true;
    DOM.status().innerHTML = '<p class="fr-badge fr-badge--info fr-badge--no-icon">Import en cours...</p>';

    const sheet = DOM.sheetSelect()?.value || 'PLAN';
    const mode = document.querySelector('input[name="import-mode"]:checked')?.value || 'replace';

    const formData = new FormData();
    formData.append('file', file);
    formData.append('sheet', sheet);
    formData.append('mode', mode);

    try {
        const result = await uploadFile('/api/import', formData, (pct) => {
            const bar = DOM.progressBar();
            if (bar) {
                bar.hidden = false;
                bar.querySelector('progress').value = pct;
                bar.querySelector('.ov-upload-progress__text').textContent = pct + '%';
            }
        });

        if (result.error) {
            throw new Error(result.error.message);
        }

        steps = result.data.steps;

        // Remplir le selecteur d'onglets si Excel
        if (result.data.sheets?.length > 1) {
            const select = DOM.sheetSelect();
            if (select) {
                select.innerHTML = result.data.sheets
                    .map(s => `<option value="${escapeAttr(s)}" ${s === result.data.selected_sheet ? 'selected' : ''}>${escapeHtml(s)}</option>`)
                    .join('');
                DOM.excelOptions().hidden = false;
            }
        }

        renderTable(steps);
        updateSelectionCount();

        DOM.tableContainer().hidden = false;
        DOM.selectionBar().hidden = false;
        const bar = DOM.progressBar();
        if (bar) bar.hidden = true;
        DOM.status().innerHTML = `<p class="fr-alert fr-alert--success fr-alert--sm"><span class="fr-alert__title">${steps.length} étapes importées</span></p>`;

    } catch (err) {
        DOM.status().innerHTML = `<p class="fr-alert fr-alert--error fr-alert--sm"><span class="fr-alert__title">${escapeHtml(err.message)}</span></p>`;
    } finally {
        DOM.importBtn().disabled = false;
    }
}

function renderTable(stepsData) {
    const tbody = DOM.tableBody();
    if (!tbody) return;
    tbody.innerHTML = stepsData.map(s => `
        <tr>
            <td>
                <div class="fr-checkbox-group fr-checkbox-group--sm">
                    <input type="checkbox" id="step-cb-${s.step_id}"
                           data-step-id="${s.step_id}" checked class="ov-step-checkbox">
                    <label class="fr-label" for="step-cb-${s.step_id}">
                        <span class="fr-sr-only">Sélectionner étape ${s.step_id}</span>
                    </label>
                </div>
            </td>
            <td>${escapeHtml(String(s.step_id))}</td>
            <td>${escapeHtml(s.text_original)}</td>
        </tr>
    `).join('');
}

function onCheckboxChange(e) {
    if (e.target.classList.contains('ov-step-checkbox')) {
        updateSelectionCount();
    }
}

function getSelectedIds() {
    return Array.from(document.querySelectorAll('.ov-step-checkbox:checked'))
        .map(cb => cb.dataset.stepId);
}

function updateSelectionCount() {
    const selected = getSelectedIds().length;
    const countEl = DOM.selectionCount();
    if (countEl) countEl.textContent = `${selected}/${steps.length} étapes sélectionnées`;
    const selectAll = DOM.selectAll();
    if (selectAll) {
        selectAll.checked = selected === steps.length;
        selectAll.indeterminate = selected > 0 && selected < steps.length;
    }
    // Activer/désactiver le bouton Continuer selon la sélection
    const nextBtn = DOM.nextBtn();
    if (nextBtn) nextBtn.disabled = selected === 0;
}

function onSelectAllToggle(e) {
    const checked = e.target.checked;
    document.querySelectorAll('.ov-step-checkbox').forEach(cb => { cb.checked = checked; });
    updateSelectionCount();
}

async function onContinue() {
    const selectedIds = getSelectedIds();
    if (selectedIds.length === 0) {
        DOM.status().innerHTML = '<p class="fr-alert fr-alert--warning fr-alert--sm"><span class="fr-alert__title">Sélectionnez au moins une étape.</span></p>';
        return;
    }

    try {
        await apiPost('/api/import/select', { step_ids: selectedIds });
        eventBus.emit('navigate', 'tab-clean');
    } catch (err) {
        DOM.status().innerHTML = `<p class="fr-alert fr-alert--error fr-alert--sm"><span class="fr-alert__title">${escapeHtml(err.message)}</span></p>`;
    }
}

export default { init };
