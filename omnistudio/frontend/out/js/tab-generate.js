/**
 * tab-generate.js — Onglet 5 : Generation batch des audios (SSE).
 */
import { apiGet, apiPost, fetchSSE } from './api-client.js';
import { eventBus } from './app.js';
import { escapeHtml, escapeAttr } from './dom-utils.js';
import { authenticatedUrl } from './audio-player.js';

const ITEMS_PER_PAGE = 10;

const DOM = {
    summaryText: () => document.getElementById('generate-summary-text'),
    sampleBtn: () => document.getElementById('gen-sample-btn'),
    randomBtn: () => document.getElementById('gen-random-btn'),
    randomResult: () => document.getElementById('gen-random-result'),
    startBtn: () => document.getElementById('gen-start-btn'),
    resumeContainer: () => document.getElementById('gen-resume'),
    resumeBtn: () => document.getElementById('gen-resume-btn'),
    sampleResults: () => document.getElementById('gen-sample-results'),
    progress: () => document.getElementById('gen-progress'),
    progressBar: () => document.getElementById('gen-progress-bar'),
    progressText: () => document.getElementById('gen-progress-text'),
    log: () => document.getElementById('gen-log'),
    results: () => document.getElementById('gen-results'),
    resultsList: () => document.getElementById('gen-results-list'),
    pagination: () => document.getElementById('gen-pagination'),
    paginationList: () => document.querySelector('#gen-pagination .fr-pagination__list'),
    status: () => document.getElementById('gen-status'),
    nextBtn: () => document.getElementById('gen-next-btn'),
};

let generatedItems = [];
let currentPage = 1;
let isGenerating = false;

function setGenerating(value) {
    isGenerating = value;
    window.__vxGenerating = value;
}

function init() {
    DOM.sampleBtn().addEventListener('click', onSample);
    DOM.randomBtn().addEventListener('click', onRandom);
    DOM.startBtn().addEventListener('click', () => onGenerate(false));
    DOM.resumeBtn().addEventListener('click', () => onGenerate(true));
    DOM.nextBtn().addEventListener('click', () => eventBus.emit('navigate', 'tab-export'));

    // Pagination par delegation
    DOM.paginationList().addEventListener('click', onPageClick);

    eventBus.on('tab-activated:tab-generate', loadSummary);

    eventBus.on('session-reset', () => {
        generatedItems = [];
        currentPage = 1;
        clearLog();
        DOM.progress().hidden = true;
        DOM.results().hidden = true;
        DOM.pagination().hidden = true;
        DOM.resumeContainer().hidden = true;
        DOM.nextBtn().disabled = true;
        const status = DOM.status();
        if (status) status.innerHTML = '';
        DOM.summaryText().textContent = '';
        // Nettoyer les echantillons audio
        const samples = DOM.sampleResults();
        if (samples) {
            samples.querySelectorAll('audio').forEach(a => { a.pause(); a.removeAttribute('src'); a.load(); });
            samples.innerHTML = '';
            samples.hidden = true;
        }
    });
}

// --- Journal d'activite ---

function logTime() {
    const now = new Date();
    return `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}:${String(now.getSeconds()).padStart(2, '0')}`;
}

function addLogEntry(message, type = '') {
    const log = DOM.log();
    if (!log) return;
    const cls = type ? ` vx-gen-log__entry--${type}` : '';
    const entry = document.createElement('div');
    entry.className = `vx-gen-log__entry${cls}`;
    entry.innerHTML = `<span class="vx-gen-log__time">${logTime()}</span>${escapeHtml(message)}`;
    log.appendChild(entry);
    log.scrollTop = log.scrollHeight;
}

function clearLog() {
    const log = DOM.log();
    if (log) log.innerHTML = '';
}

function updateProgressBar(value, text) {
    const bar = DOM.progressBar();
    if (bar) {
        bar.value = value;
        bar.setAttribute('aria-valuetext', text);
    }
    const txt = DOM.progressText();
    if (txt) txt.textContent = text;
}

// --- Actions ---

async function loadSummary() {
    try {
        const result = await apiGet('/api/generate/summary');
        const d = result.data;
        const hasSteps = d.total_steps > 0;
        const estimate = d.total_steps > 30 ? '15-30 minutes' : d.total_steps > 10 ? '5-15 minutes' : '2-5 minutes';
        DOM.summaryText().textContent = hasSteps
            ? `${d.total_steps} étapes — ${d.voices.length} voix — ${estimate} de génération` +
              (d.has_instructions ? ' (dont instructions émotionnelles)' : '')
            : 'Aucune étape importée. Importez un fichier pour commencer.';
        DOM.sampleBtn().disabled = !hasSteps;
        DOM.startBtn().disabled = !hasSteps;
    } catch {
        DOM.summaryText().textContent = 'Erreur de chargement du récapitulatif.';
        DOM.sampleBtn().disabled = true;
        DOM.startBtn().disabled = true;
    }
}

async function onSample() {
    const btn = DOM.sampleBtn();
    const originalText = btn.textContent;

    btn.disabled = true;
    btn.setAttribute('aria-busy', 'true');
    btn.innerHTML = '<span class="vx-spin" aria-hidden="true">&#9696;</span> Échantillons en cours\u2026';

    // Recuperer les etapes pour appeler les previews une par une
    clearLog();
    DOM.sampleResults().hidden = false;
    DOM.sampleResults().innerHTML = '';
    addLogEntry('Préparation des échantillons...');

    const fidelity = document.querySelector('input[name="gen-fidelity"]:checked').value;

    try {
        // Recuperer les assignations (contient voix, langue, vitesse, instruction, texte)
        const assignResult = await apiGet('/api/assign');
        if (assignResult.error) throw new Error(assignResult.error.message || 'Erreur');
        const rows = assignResult.data?.rows || [];
        if (rows.length === 0) throw new Error('Aucune étape à générer');

        // Selectionner 3 etapes (debut, milieu, fin)
        let sampleRows;
        if (rows.length <= 3) {
            sampleRows = rows;
        } else {
            sampleRows = [rows[0], rows[Math.floor(rows.length / 2)], rows[rows.length - 1]];
        }

        addLogEntry(`${sampleRows.length} échantillons à générer (étapes ${sampleRows.map(r => r.step_id).join(', ')}) — mode ${fidelity}`);

        let generated = 0;
        for (const row of sampleRows) {
            const sid = String(row.step_id);
            addLogEntry(`Synthèse étape ${sid} — voix ${row.voice}...`);

            try {
                const result = await apiPost(`/api/assign/preview/${sid}`, {
                    voice: row.voice,
                    language: row.language,
                    speed: row.speed,
                    instruction: row.instruction || '',
                    text: row.text_full,
                });
                if (result.error) {
                    addLogEntry(`Étape ${sid} — échec : ${result.error.message}`, 'error');
                    continue;
                }
                if (result.data?.audio_url) {
                    generated++;
                    addLogEntry(`Étape ${sid} terminée (${generated}/${sampleRows.length})`, 'success');
                    const col = document.createElement('div');
                    col.className = 'fr-col-4';
                    col.innerHTML = `
                        <p class="fr-text--sm fr-text--bold">Étape ${escapeHtml(sid)}</p>
                        <audio src="${authenticatedUrl(result.data.audio_url)}" controls class="vx-audio-player" title="Échantillon étape ${escapeHtml(sid)}"></audio>`;
                    DOM.sampleResults().appendChild(col);
                }
            } catch (err) {
                addLogEntry(`Étape ${sid} — erreur : ${err.message}`, 'error');
            }
        }
        addLogEntry(`Terminé — ${generated} échantillon(s) généré(s)`, 'success');
        DOM.status().innerHTML = `<p class="fr-alert fr-alert--success fr-alert--sm"><span class="fr-alert__title">${generated} échantillon(s) généré(s)</span></p>`;
    } catch (err) {
        addLogEntry(`Erreur : ${err.message}`, 'error');
        DOM.status().innerHTML = `<p class="fr-alert fr-alert--error fr-alert--sm"><span class="fr-alert__title">${escapeHtml(err.message)}</span></p>`;
    } finally {
        btn.disabled = false;
        btn.removeAttribute('aria-busy');
        btn.textContent = originalText;
    }
}

// --- Voix aléatoire (prototype rapide) ---

async function onRandom() {
    const btn = DOM.randomBtn();
    const original = btn.textContent;
    const result = DOM.randomResult();

    btn.disabled = true;
    btn.setAttribute('aria-busy', 'true');
    btn.innerHTML = '<span class="vx-spin" aria-hidden="true">&#9696;</span> Tirage en cours\u2026';
    result.hidden = false;
    result.innerHTML = '<p class="fr-text--sm fr-text--mention-grey">Génération d\'un échantillon avec voix aléatoire…</p>';

    try {
        const text = "Bonjour, ceci est un test rapide avec une voix tirée au hasard.";
        const response = await apiPost('/api/generate/random', { text, language: 'fr' });
        if (response.error) throw new Error(response.error.message || 'Erreur');
        const voice = response.data?.voice || response.data?.filename || 'voix tirée au hasard';
        const audioUrl = response.data?.audio_url;
        const filename = response.data?.filename || '';
        if (!audioUrl) throw new Error('Aucun audio retourné');
        result.innerHTML = `
            <p class="fr-text--sm"><strong>Échantillon :</strong> ${escapeHtml(voice)}</p>
            <audio src="${authenticatedUrl(audioUrl)}" controls class="vx-audio-player" title="Échantillon voix aléatoire ${escapeHtml(voice)}"></audio>
            <div class="fr-mt-2w" id="vx-random-save-box">
                <label for="vx-random-save-name" class="fr-label fr-text--sm">Nom pour conserver cette voix</label>
                <div class="fr-input-group">
                    <input class="fr-input" type="text" id="vx-random-save-name"
                        placeholder="ex. voix-aleatoire-1" maxlength="50"
                        pattern="^[a-zA-Z][a-zA-Z0-9_-]{2,49}$"
                        aria-describedby="vx-random-save-hint">
                </div>
                <p class="fr-hint-text" id="vx-random-save-hint">
                    Lettre + 2 à 49 caractères alphanumériques, _ ou -.
                </p>
                <button class="fr-btn fr-btn--secondary" type="button" id="vx-random-save-btn"
                    data-filename="${escapeAttr(filename)}" data-text="${escapeAttr(text)}">
                    Ajouter à la bibliothèque
                </button>
                <p class="fr-mt-1w" id="vx-random-save-status" role="status" aria-live="polite"></p>
            </div>`;
        const saveBtn = document.getElementById('vx-random-save-btn');
        if (saveBtn) saveBtn.addEventListener('click', onSaveRandom);
    } catch (err) {
        result.innerHTML = `<p class="fr-alert fr-alert--error fr-alert--sm"><span class="fr-alert__title">${escapeHtml(err.message)}</span></p>`;
    } finally {
        btn.disabled = false;
        btn.removeAttribute('aria-busy');
        btn.textContent = original;
    }
}

async function onSaveRandom(e) {
    const btn = e.currentTarget;
    const nameInput = document.getElementById('vx-random-save-name');
    const status = document.getElementById('vx-random-save-status');
    const name = (nameInput?.value || '').trim();
    const filename = btn.dataset.filename || '';
    const text = btn.dataset.text || '';

    if (!/^[a-zA-Z][a-zA-Z0-9_-]{2,49}$/.test(name)) {
        if (status) status.innerHTML = '<span class="fr-text--error">Nom invalide : lettre + 2-49 caractères alphanumériques, _ ou -.</span>';
        nameInput?.focus();
        return;
    }

    btn.disabled = true;
    btn.setAttribute('aria-busy', 'true');
    if (status) status.textContent = 'Enregistrement en cours…';

    try {
        const response = await apiPost('/api/voices/save-random', {
            name, filename, transcription: text,
        });
        if (response.error) throw new Error(response.error.message || 'Erreur');
        if (status) status.innerHTML = `<span class="fr-text--success">Voix « ${escapeHtml(name)} » ajoutée à la bibliothèque.</span>`;
        btn.disabled = true;
        btn.textContent = 'Ajoutée';
    } catch (err) {
        if (status) status.innerHTML = `<span class="fr-text--error">${escapeHtml(err.message)}</span>`;
        btn.disabled = false;
    } finally {
        btn.removeAttribute('aria-busy');
    }
}

function setStartBtnLoading(loading) {
    const btn = DOM.startBtn();
    if (loading) {
        btn._originalText = btn.textContent;
        btn.disabled = true;
        btn.setAttribute('aria-busy', 'true');
        btn.innerHTML = '<span class="vx-spin" aria-hidden="true">&#9696;</span> Production en cours\u2026';
    } else {
        btn.disabled = false;
        btn.removeAttribute('aria-busy');
        btn.textContent = btn._originalText || 'Lancer la production';
    }
}

async function onGenerate(isResume = false) {
    if (isGenerating) {
        return;
    }
    setGenerating(true);
    setStartBtnLoading(true);
    DOM.resumeContainer().hidden = true;
    DOM.progress().hidden = false;
    DOM.status().innerHTML = '';
    updateProgressBar(0, isResume ? 'Reprise...' : 'Démarrage...');
    if (!isResume) {
        generatedItems = [];
        clearLog();
    }

    addLogEntry(isResume ? 'Reprise de la génération...' : 'Démarrage de la génération...');

    const fidelity = document.querySelector('input[name="gen-fidelity"]:checked').value;
    const startTime = Date.now();

    let sseCompleted = false;

    try {
    await fetchSSE('/api/generate', { fidelity, resume: isResume, force: true }, {
        onProgress(data) {
            const progress = data.progress || 0;
            const message = data.message || '';

            // Calcul du temps restant
            let displayText = message;
            if (data.index && data.total && data.index > 1) {
                const elapsed = (Date.now() - startTime) / 1000;
                const avgPerItem = elapsed / data.index;
                const remaining = Math.round(avgPerItem * (data.total - data.index));
                if (remaining > 60) {
                    displayText = `${message} (~${Math.round(remaining / 60)} min restantes)`;
                } else if (remaining > 0) {
                    displayText = `${message} (~${remaining}s restantes)`;
                }
            }

            updateProgressBar(progress, displayText);

            // Journal : distinguer batch_start et progress avec audio
            if (data.audio_url) {
                addLogEntry(`Étape ${data.step_id} terminée — voix ${data.voice}`, 'success');
                generatedItems.push({
                    step_id: data.step_id,
                    voice: data.voice,
                    audio_url: data.audio_url
                });
                renderResultsPage(currentPage);
                DOM.results().hidden = false;
            } else if (data.step_id && !data.audio_url && data.index) {
                // Etape terminee mais sans audio (echec silencieux)
                addLogEntry(`Étape ${data.step_id} — aucun audio produit`, 'error');
            } else if (message) {
                // batch_start ou autre message informatif
                addLogEntry(message);
            }
        },
        onHeartbeat(data) {
            const msg = data?.message || 'Génération en cours...';
            addLogEntry(msg);
        },
        onDone() {
            sseCompleted = true;
            setGenerating(false);
            DOM.progress().hidden = true;
            DOM.progressBar().removeAttribute('aria-busy');
            setStartBtnLoading(false);
            DOM.nextBtn().disabled = false;
            addLogEntry(`Terminé — ${generatedItems.length} fichiers audio générés`, 'success');
            DOM.status().innerHTML = `<p class="fr-alert fr-alert--success fr-alert--sm"><span class="fr-alert__title">${generatedItems.length} fichiers audio générés</span></p>`;
            // PRD-018 : signaler à l'onglet Export que des fichiers existent
            eventBus.emit('generation-complete');
        },
        onError(data) {
            sseCompleted = true;
            setGenerating(false);
            DOM.progress().hidden = true;
            DOM.progressBar().removeAttribute('aria-busy');
            setStartBtnLoading(false);
            DOM.resumeContainer().hidden = false;
            const code = data?.code || '';
            const msg = data?.message || 'Erreur inconnue';
            const isTts = code === 'TTS_BUSY' || code === 'TTS_TIMEOUT';
            const alertType = isTts ? 'warning' : 'error';
            addLogEntry(`${isTts ? 'TTS' : 'Erreur'} : ${msg}`, 'error');
            DOM.status().innerHTML = `<p class="fr-alert fr-alert--${alertType} fr-alert--sm"><span class="fr-alert__title">${escapeHtml(msg)}</span></p>`;
        },
        onAbort() {
            sseCompleted = true;
            setGenerating(false);
            DOM.progress().hidden = true;
            DOM.progressBar().removeAttribute('aria-busy');
            setStartBtnLoading(false);
            DOM.resumeContainer().hidden = false;
            addLogEntry('Génération interrompue par l\'utilisateur', 'error');
            DOM.status().innerHTML = '<p class="fr-alert fr-alert--warning fr-alert--sm"><span class="fr-alert__title">Génération interrompue.</span></p>';
        }
    });

    } catch (err) {
        setGenerating(false);
        DOM.progress().hidden = true;
        setStartBtnLoading(false);
        DOM.resumeContainer().hidden = false;
        addLogEntry(`Erreur réseau : ${err.message || 'connexion perdue'}`, 'error');
        DOM.status().innerHTML = `<p class="fr-alert fr-alert--error fr-alert--sm"><span class="fr-alert__title">${escapeHtml(err.message || 'Erreur réseau')}</span></p>`;
        return;
    }

    // Filet de securite : debloquer si le flux SSE s'est termine sans callback
    if (!sseCompleted) {
        setGenerating(false);
        DOM.progress().hidden = true;
        DOM.progressBar().removeAttribute('aria-busy');
        setStartBtnLoading(false);
        if (generatedItems.length > 0) DOM.nextBtn().disabled = false;
        DOM.resumeContainer().hidden = false;
    }
}

function renderResultsPage(page) {
    const totalPages = Math.ceil(generatedItems.length / ITEMS_PER_PAGE);
    const start = (page - 1) * ITEMS_PER_PAGE;
    const pageItems = generatedItems.slice(start, start + ITEMS_PER_PAGE);

    DOM.resultsList().innerHTML = pageItems.map(item => `
        <div class="fr-grid-row fr-grid-row--middle fr-mb-1w fr-p-1w" style="border:1px solid var(--border-default-grey)">
            <div class="fr-col-auto fr-mr-1w">
                <span class="fr-text--sm fr-text--bold">Étape ${escapeHtml(item.step_id)}</span>
                <span class="fr-text--sm fr-text--mention-grey"> — ${escapeHtml(item.voice)}</span>
            </div>
            <div class="fr-col">
                <audio src="${authenticatedUrl(item.audio_url)}" controls class="vx-audio-player" title="Audio étape ${escapeHtml(item.step_id)} — ${escapeHtml(item.voice)}">
                </audio>
            </div>
        </div>
    `).join('');

    if (totalPages > 1) {
        DOM.pagination().hidden = false;
        DOM.paginationList().innerHTML = Array.from({length: totalPages}, (_, i) => {
            const p = i + 1;
            const current = p === page ? 'aria-current="page"' : '';
            return `<li><a class="fr-pagination__link" href="#" data-page="${p}" ${current}>${p}</a></li>`;
        }).join('');
    } else {
        DOM.pagination().hidden = true;
    }
}

function onPageClick(e) {
    const link = e.target.closest('[data-page]');
    if (!link) return;
    e.preventDefault();
    currentPage = parseInt(link.dataset.page);
    renderResultsPage(currentPage);
}

export default { init };
