/**
 * tab-export.js — Onglet 6 : Export ZIP (SSE).
 */
import { fetchSSE } from './api-client.js';
import { escapeHtml } from './dom-utils.js';
import { eventBus } from './app.js';
import { authenticatedUrl, createAudioPlayer } from './audio-player.js';

const DOM = {
    normalize: () => document.getElementById('export-normalize'),
    stereo: () => document.getElementById('export-stereo'),
    rate: () => document.getElementById('export-rate'),
    format: () => document.getElementById('export-format'),
    unique: () => document.getElementById('export-unique'),
    silenceGroup: () => document.getElementById('export-silence-group'),
    silence: () => document.getElementById('export-silence'),
    silenceValue: () => document.getElementById('export-silence-value'),
    subtitles: () => document.getElementById('export-subtitles'),
    subtitleFormatGroup: () => document.getElementById('export-subtitle-format-group'),
    subtitleFormat: () => document.getElementById('export-subtitle-format'),
    exportBtn: () => document.getElementById('export-btn'),
    progress: () => document.getElementById('export-progress'),
    progressBar: () => document.getElementById('export-progress-bar'),
    progressText: () => document.getElementById('export-progress-text'),
    result: () => document.getElementById('export-result'),
    resultText: () => document.getElementById('export-result-text'),
    downloadLink: () => document.getElementById('export-download-link'),
    downloadDesc: () => document.getElementById('export-download-desc'),
    downloadDetail: () => document.getElementById('export-download-detail'),
    uniquePlayer: () => document.getElementById('export-unique-player'),
    status: () => document.getElementById('export-status'),
};

// PRD-018 : suivi état vide
let _hasGeneratedFiles = false;

function updateExportEmptyState() {
    const emptyState = document.getElementById('export-empty-state');
    const exportBtn = DOM.exportBtn();
    if (emptyState) emptyState.hidden = _hasGeneratedFiles;
    if (exportBtn) exportBtn.disabled = !_hasGeneratedFiles;
}

function init() {
    DOM.exportBtn().addEventListener('click', onExport);
    DOM.unique().addEventListener('change', () => {
        DOM.silenceGroup().hidden = !DOM.unique().checked;
    });
    DOM.subtitles().addEventListener('change', () => {
        DOM.subtitleFormatGroup().hidden = !DOM.subtitles().checked;
    });
    DOM.silence().addEventListener('input', () => {
        const v = DOM.silence().value + 's';
        DOM.silenceValue().textContent = v;
        DOM.silence().setAttribute('aria-valuetext', v);
        const output = document.querySelector('#export-silence').closest('.fr-range')?.querySelector('.fr-range__output');
        if (output) output.textContent = v;
    });

    // PRD-018 : écouter la fin de génération
    eventBus.on('generation-complete', () => {
        _hasGeneratedFiles = true;
        updateExportEmptyState();
    });

    eventBus.on('tab-activated:tab-export', updateExportEmptyState);

    eventBus.on('session-reset', () => {
        DOM.progress().hidden = true;
        DOM.result().hidden = true;
        DOM.exportBtn().disabled = false;
        const status = DOM.status();
        if (status) status.innerHTML = '';
        // PRD-018 : réafficher état vide
        _hasGeneratedFiles = false;
        updateExportEmptyState();
    });
}

async function onExport() {
    DOM.exportBtn().disabled = true;
    DOM.progress().hidden = false;
    DOM.progressBar().value = 0;
    DOM.progressBar().setAttribute('aria-busy', 'true');
    DOM.progressText().textContent = 'Démarrage...';
    DOM.result().hidden = true;

    const bitDepth = parseInt(document.querySelector('input[name="export-depth"]:checked').value);

    let sseCompleted = false;

    await fetchSSE('/api/export', {
        normalize: DOM.normalize().checked,
        stereo: DOM.stereo().checked,
        sample_rate: parseInt(DOM.rate().value),
        bit_depth: bitDepth,
        output_format: DOM.format().value,
        make_unique: DOM.unique().checked,
        silence_duration: parseFloat(DOM.silence().value),
        include_subtitles: DOM.subtitles().checked,
        subtitle_format: DOM.subtitleFormat().value
    }, {
        onProgress(data) {
            DOM.progressBar().value = data.progress || 0;
            DOM.progressText().textContent = data.message || '';
        },
        onDone(data) {
            sseCompleted = true;
            DOM.progress().hidden = true;
            DOM.progressBar().removeAttribute('aria-busy');
            DOM.exportBtn().disabled = false;
            DOM.result().hidden = false;
            const sizeMo = data.size_kb >= 1024
                ? (data.size_kb / 1024).toFixed(1) + ' Mo'
                : data.size_kb + ' Ko';
            DOM.resultText().textContent = `Export terminé — ${data.files_count} fichiers (${sizeMo})`;
            DOM.downloadLink().href = authenticatedUrl(data.export_path);
            DOM.downloadLink().textContent = `Pack audio OmniStudio — ${data.files_count} fichiers`;
            DOM.downloadDesc().textContent = `Fichiers audio post-traités, script de paroles et traçabilité technique.`;
            DOM.downloadDetail().innerHTML = `<span class="fr-icon-download-line" aria-hidden="true"></span> ZIP — ${sizeMo} — ${data.files_count} fichiers`;

            const playerContainer = DOM.uniquePlayer();
            playerContainer.innerHTML = '';
            if (data.unique_audio_url) {
                playerContainer.appendChild(createAudioPlayer(data.unique_audio_url, 'Narration complète'));
            }
            if (data.global_subtitle_url) {
                const srtLink = document.createElement('a');
                srtLink.href = authenticatedUrl(data.global_subtitle_url);
                srtLink.download = 'narration-complete.srt';
                srtLink.className = 'fr-link fr-link--download fr-mt-1w';
                srtLink.innerHTML = '<span class="fr-icon-download-line" aria-hidden="true"></span><span class="fr-link__detail">SRT</span>Sous-titres — narration complète';
                playerContainer.appendChild(srtLink);
            }

            if (data.skipped?.length > 0) {
                DOM.status().innerHTML = `<p class="fr-alert fr-alert--warning fr-alert--sm"><span class="fr-alert__title">Étapes ignorées : ${escapeHtml(data.skipped.join(', '))}</span></p>`;
            }
        },
        onError(data) {
            sseCompleted = true;
            DOM.progress().hidden = true;
            DOM.progressBar().removeAttribute('aria-busy');
            DOM.exportBtn().disabled = false;
            DOM.status().innerHTML = `<p class="fr-alert fr-alert--error fr-alert--sm"><span class="fr-alert__title">${escapeHtml(data.message)}</span></p>`;
        },
        onAbort() {
            sseCompleted = true;
            DOM.progress().hidden = true;
            DOM.progressBar().removeAttribute('aria-busy');
            DOM.exportBtn().disabled = false;
            DOM.status().innerHTML = '<p class="fr-alert fr-alert--warning fr-alert--sm"><span class="fr-alert__title">Export interrompu.</span></p>';
        }
    });

    // Filet de securite : debloquer si le flux SSE s'est termine sans callback
    if (!sseCompleted) {
        DOM.progress().hidden = true;
        DOM.progressBar().removeAttribute('aria-busy');
        DOM.exportBtn().disabled = false;
    }
}

export default { init };
