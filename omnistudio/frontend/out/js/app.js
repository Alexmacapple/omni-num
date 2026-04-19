/**
 * app.js — Point d'entree OmniStudio DSFR.
 * Initialise l'authentification, les onglets, le theme et l'event bus.
 */
import { isAuthenticated, login, logout, scheduleTokenRefresh, onAuthStateChange } from './auth.js';
import { apiGet, apiPost } from './api-client.js';
import { escapeHtml } from './dom-utils.js';
import { showError, showSuccess, showWarning } from './toast.js';
import { initUrlState } from './url-state.js';
import tabImport from './tab-import.js';
import tabClean from './tab-clean.js';
import tabVoices from './tab-voices.js';
import tabAssign from './tab-assign.js';
import tabGenerate from './tab-generate.js';
import tabExport from './tab-export.js';
import { initTagPalette, mountTagPalette } from './tag-palette.js';

// --- Mode ---
const _isMinified = !import.meta.url.includes('/js/app.js');
console.info(
    `%cOmniStudio%c ${_isMinified ? 'PRODUCTION (minifié)' : 'DÉVELOPPEMENT (sources)'}`,
    'background:#000091;color:#fff;padding:2px 6px;border-radius:3px;font-weight:bold',
    'color:inherit'
);

// --- Event Bus ---

class EventBus {
    constructor() {
        this._listeners = {};
    }
    on(event, callback) {
        if (!this._listeners[event]) this._listeners[event] = [];
        this._listeners[event].push(callback);
    }
    off(event, callback) {
        if (!this._listeners[event]) return;
        this._listeners[event] = this._listeners[event].filter(cb => cb !== callback);
    }
    emit(event, data) {
        (this._listeners[event] || []).forEach(cb => cb(data));
    }
}

export const eventBus = new EventBus();

// --- Elements DOM ---
const loginScreen = document.getElementById('vx-login-screen');
const appScreen = document.getElementById('vx-app-screen');
const loginForm = document.getElementById('vx-login-form');
const loginError = document.getElementById('vx-login-error');
const logoutBtn = document.getElementById('vx-logout-btn');
const usernameDisplay = document.getElementById('vx-username');

// --- Tab tracking ---
let currentActiveTab = null;

const TAB_IDS = ['tab-import', 'tab-clean', 'tab-voices', 'tab-assign', 'tab-generate', 'tab-export'];

const STEP_LABELS = {
    'tab-import':   'Import',
    'tab-clean':    'Preparation',
    'tab-voices':   'Voix',
    'tab-assign':   'Assignation',
    'tab-generate': 'Generation',
    'tab-export':   'Export',
};

export function getCurrentActiveTab() {
    return currentActiveTab;
}

function activateDsfrTab(tabId) {
    const btn = document.getElementById(tabId);
    if (btn) btn.click();
}

function switchTab(tabId) {
    const prev = getCurrentActiveTab();
    if (prev && prev !== tabId) {
        eventBus.emit(`tab-deactivated:${prev}`);
    }
    // Gestion directe des panels via data-vx-active / data-vx-hidden.
    // Ces attributs CSS ecrasent les classes DSFR (fr-tabs__panel--selected)
    // que le DSFR JS peut remettre sur le mauvais panel.
    TAB_IDS.forEach(tid => {
        const btn = document.getElementById(tid);
        if (!btn) return;
        // Synchroniser l'etat visuel du bouton d'onglet
        btn.setAttribute('aria-selected', tid === tabId ? 'true' : 'false');
        const panelId = btn.getAttribute('aria-controls');
        const panel = panelId ? document.getElementById(panelId) : null;
        if (panel) {
            if (tid === tabId) {
                panel.setAttribute('data-vx-active', '');
                panel.removeAttribute('data-vx-hidden');
                panel.classList.add('fr-tabs__panel--selected');
            } else {
                panel.removeAttribute('data-vx-active');
                panel.setAttribute('data-vx-hidden', '');
                panel.classList.remove('fr-tabs__panel--selected');
            }
        }
    });
    currentActiveTab = tabId;

    // Recalculer la hauteur des tabs DSFR apres le switch.
    // Le DSFR JS fixe --tabs-height en style inline basee sur le panel actif.
    // Quand on change de panel, cette hauteur est obsolete — le contenu deborde.
    const mainTabs = document.getElementById('main-tabs');
    if (mainTabs) {
        mainTabs.style.removeProperty('--tabs-height');
        // Laisser le navigateur recalculer, puis demander au DSFR de re-mesurer
        requestAnimationFrame(() => {
            const activePanel = mainTabs.querySelector('[data-vx-active]');
            if (activePanel) {
                mainTabs.style.setProperty('--tabs-height', activePanel.scrollHeight + 'px');
            }
        });
    }

    eventBus.emit(`tab-activated:${tabId}`);
    eventBus.emit('tab-activated', tabId);
}

function updateStepper(tabId) {
    const stepperEl = document.getElementById('vx-stepper');
    if (!stepperEl) return;

    const index = TAB_IDS.indexOf(tabId);
    if (index === -1) return;

    const step = index + 1;
    const total = TAB_IDS.length;
    const label = STEP_LABELS[tabId] || '';

    // Titre et etat
    const stateEl = stepperEl.querySelector('.fr-stepper__state');
    if (stateEl) stateEl.textContent = 'Etape ' + step + ' sur ' + total;

    // Texte du titre (noeud texte apres le <span>)
    const titleEl = stepperEl.querySelector('.fr-stepper__title');
    if (titleEl) {
        titleEl.childNodes.forEach(node => {
            if (node.nodeType === Node.TEXT_NODE && node.textContent.trim()) {
                node.textContent = '\n' + label + '\n';
            }
        });
    }

    // Barre de progression
    const stepsEl = stepperEl.querySelector('.fr-stepper__steps');
    if (stepsEl) stepsEl.setAttribute('data-fr-current-step', String(step));

    // Boutons prev/next
    const prevBtn = document.getElementById('vx-stepper-prev');
    const nextBtn = document.getElementById('vx-stepper-next');
    if (prevBtn) prevBtn.disabled = (step === 1);
    if (nextBtn) nextBtn.disabled = (step === total);
}

// Observer les changements d'onglet DSFR (niveau 1 uniquement)
function observeTabChanges() {
    // Ne cibler que les onglets principaux, pas les sous-onglets (sub-tab-*)
    const mainTabSet = new Set(TAB_IDS);
    const tabs = document.querySelectorAll('.fr-tabs__tab');
    if (tabs.length === 0) return;

    const observer = new MutationObserver((mutations) => {
        for (const m of mutations) {
            if (m.attributeName === 'aria-selected' &&
                m.target.getAttribute('aria-selected') === 'true') {
                const tabId = m.target.id;
                // Ignorer les sous-onglets (geres par url-state.js)
                if (!mainTabSet.has(tabId)) continue;
                if (tabId !== currentActiveTab) {
                    // Deleguer a switchTab pour gerer data-vx-hidden
                    switchTab(tabId);
                }
            }
        }
    });

    tabs.forEach(t => observer.observe(t, { attributes: true, attributeFilter: ['aria-selected'] }));

    // Fix DSFR tabindex : tous les onglets (principaux + sous-onglets) restent
    // atteignables au clavier (Tab). Le DSFR pose tabindex="-1" sur les onglets
    // inactifs (roving tabindex), on force tabindex="0" pour la conformité RGAA.
    const allTabIds = new Set([...TAB_IDS, 'sub-tab-library', 'sub-tab-design', 'sub-tab-clone']);
    tabs.forEach(t => { if (allTabIds.has(t.id)) t.setAttribute('tabindex', '0'); });
    const tabIndexObserver = new MutationObserver((mutations) => {
        for (const m of mutations) {
            if (m.attributeName === 'tabindex' && m.target.getAttribute('tabindex') === '-1') {
                if (allTabIds.has(m.target.id)) {
                    m.target.setAttribute('tabindex', '0');
                }
            }
        }
    });
    tabs.forEach(t => tabIndexObserver.observe(t, { attributes: true, attributeFilter: ['tabindex'] }));
}

// Ecouter les demandes de navigation
eventBus.on('navigate', (tabId) => {
    switchTab(tabId);
});

// --- Affichage login / app ---

let appInitialized = false;

function showLogin() {
    if (loginScreen) loginScreen.removeAttribute('hidden');
    if (appScreen) appScreen.setAttribute('hidden', '');
}

function showApp() {
    if (loginScreen) loginScreen.setAttribute('hidden', '');
    if (appScreen) appScreen.removeAttribute('hidden');

    if (!appInitialized) {
        appInitialized = true;
        tabImport.init();
        tabClean.init();
        tabVoices.init();
        tabAssign.init();
        tabGenerate.init();
        tabExport.init();

        // Palette de marqueurs émotionnels (montée à l'activation de l'onglet Préparation)
        initTagPalette();
        eventBus.on('tab-activated:tab-clean', () => {
            mountTagPalette('clean-tag-palette');
        });

        // Observer les onglets DSFR
        setTimeout(observeTabChanges, 200);

        // Stepper mobile
        const stepperPrev = document.getElementById('vx-stepper-prev');
        const stepperNext = document.getElementById('vx-stepper-next');

        if (stepperPrev) {
            stepperPrev.addEventListener('click', () => {
                const i = TAB_IDS.indexOf(currentActiveTab);
                if (i > 0) eventBus.emit('navigate', TAB_IDS[i - 1]);
            });
        }
        if (stepperNext) {
            stepperNext.addEventListener('click', () => {
                const i = TAB_IDS.indexOf(currentActiveTab);
                if (i < TAB_IDS.length - 1) eventBus.emit('navigate', TAB_IDS[i + 1]);
            });
        }

        eventBus.on('tab-activated', updateStepper);

        // Routage URL (deep linking, persistance au refresh, bouton retour)
        // Remplace le forçage de tab-import : le hash determine l'onglet initial
        setTimeout(() => initUrlState(), 250);
    }
}

// --- Login form ---

if (loginForm) {
    loginForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const username = loginForm.querySelector('#vx-username-input').value.trim();
        const password = loginForm.querySelector('#vx-password-input').value;

        if (loginError) {
            loginError.style.display = 'none';
            loginError.textContent = '';
        }

        try {
            await login(username, password);

            // Creer une session si pas de thread_id
            if (!localStorage.getItem('thread_id')) {
                const result = await apiPost('/api/session', { label: '' });
                if (result.data?.thread_id) {
                    localStorage.setItem('thread_id', result.data.thread_id);
                }
            }

            if (usernameDisplay) usernameDisplay.textContent = username;
            showApp();
        } catch (err) {
            if (loginError) {
                loginError.textContent = err.message || 'Échec de connexion';
                loginError.style.display = '';
            }
        }
    });
}

// --- Logout ---

if (logoutBtn) {
    logoutBtn.addEventListener('click', async () => {
        await logout();
        localStorage.removeItem('thread_id');
        showLogin();
    });
}

// --- Nouvelle session ---

const newSessionBtn = document.getElementById('vx-new-session-btn');
const newSessionDialog = document.getElementById('vx-new-session-dialog');
const newSessionCancel = document.getElementById('vx-new-session-cancel');
const newSessionConfirm = document.getElementById('vx-new-session-confirm');

if (newSessionBtn && newSessionDialog) {
    newSessionBtn.addEventListener('click', () => {
        if (window.__vxGenerating) {
            showWarning('Génération en cours. Attendez la fin avant de changer de session.');
            return;
        }
        newSessionDialog.showModal();
        newSessionCancel?.focus();
    });
    newSessionCancel?.addEventListener('click', () => {
        newSessionDialog.close();
    });
    newSessionConfirm?.addEventListener('click', async () => {
        newSessionConfirm.disabled = true;
        try {
            const result = await apiPost('/api/session', { label: '' });
            if (result.data?.thread_id) {
                localStorage.setItem('thread_id', result.data.thread_id);
            }
            newSessionDialog.close();
            eventBus.emit('session-reset');
            eventBus.emit('navigate', 'tab-import');
            showSuccess('Nouvelle session créée');
        } catch (err) {
            showError(err.message || 'Impossible de créer la session. Vérifiez la connexion.');
        } finally {
            newSessionConfirm.disabled = false;
        }
    });
    newSessionDialog.addEventListener('close', () => newSessionBtn.focus());
}

// --- Auth state change ---

onAuthStateChange((authenticated) => {
    if (authenticated) {
        showApp();
    } else {
        showLogin();
    }
});

// --- Force logout event ---

window.addEventListener('vx-force-logout', (e) => {
    showWarning(e.detail?.message || 'Session expirée');
    showLogin();
});

// --- État des services ---

function initStatusDialog() {
    const btn = document.getElementById('vx-status-btn');
    const dialog = document.getElementById('vx-status-dialog');
    const closeBtn = document.getElementById('vx-status-close');
    if (!btn || !dialog) return;

    btn.addEventListener('click', async () => {
        dialog.showModal();
        closeBtn?.focus();
        await checkStatus();
    });

    closeBtn?.addEventListener('click', () => dialog.close());
    dialog.addEventListener('click', (e) => {
        if (e.target === dialog) dialog.close();
    });
    dialog.addEventListener('close', () => btn.focus());
}

async function checkStatus() {
    const content = document.getElementById('vx-status-content');
    if (!content) return;

    content.setAttribute('aria-busy', 'true');
    content.innerHTML = '<p class="fr-text--sm"><span class="fr-icon-refresh-line vx-spin" aria-hidden="true"></span> Vérification en cours…</p>';

    try {
        const resp = await fetch('api/status');
        const json = await resp.json();
        const d = json.data;

        const badge = (ok, label) => ok
            ? `<span class="fr-badge fr-badge--sm fr-badge--success fr-badge--no-icon">${label || 'Actif'}</span>`
            : `<span class="fr-badge fr-badge--sm fr-badge--error fr-badge--no-icon">${label || 'Inactif'}</span>`;

        // Etat generation TTS (semaphore)
        let generationHtml = '';
        try {
            // Normaliser URL: fetch() n'honore pas <base href> pour URLs avec paramètres
            // Utiliser apiRequest() du api-client qui applique _normalizeUrl()
            const ttsResp = await fetch('api/tts/status', {
                headers: { 'Authorization': `Bearer ${localStorage.getItem('ov_access_token') || ''}` }
            });
            if (ttsResp.ok) {
                const ttsJson = await ttsResp.json();
                const gen = ttsJson.data?.generation;
                if (gen) {
                    const busyBadge = gen.busy
                        ? `<span class="fr-badge fr-badge--sm fr-badge--warning fr-badge--no-icon">En cours (${escapeHtml(String(gen.elapsed_seconds))}s) — ${escapeHtml(gen.endpoint || '')}</span>`
                        : badge(true, 'Disponible');
                    generationHtml = `<tr><th scope="row" class="fr-pl-2w">Moteur génération</th><td>${busyBadge}</td></tr>`;
                }
            }
        } catch { /* OmniVoice injoignable, deja gere */ }

        let modelsHtml = '';
        if (d.models) {
            const MODEL_LABELS = {
                voice_design_loaded: 'Design vocal (1.7B)',
                voice_clone_loaded: 'Clonage vocal',
                preset_voice_loaded: 'Voix preset (0.6B)',
                clone_1_7b_loaded: 'Clone 1.7B (qualité)',
                clone_0_6b_loaded: 'Clone 0.6B (rapide)',
            };
            modelsHtml = Object.entries(MODEL_LABELS)
                .filter(([key]) => key in d.models)
                .map(([key, label]) => {
                    const loaded = d.models[key] === true;
                    return `<tr><th scope="row" class="fr-pl-2w">${label}</th><td>${badge(loaded, loaded ? 'Chargé' : 'À la demande')}</td></tr>`;
                }).join('');
            if (d.models.custom_voices_count != null) {
                modelsHtml += `<tr><th scope="row" class="fr-pl-2w">Voix personnalisées</th><td><span class="fr-badge fr-badge--sm fr-badge--info fr-badge--no-icon">${escapeHtml(String(d.models.custom_voices_count))}</span></td></tr>`;
            }
        }

        content.innerHTML = `
            <table class="vx-status-table">
                <caption class="fr-sr-only">État des services OmniStudio</caption>
                <thead class="fr-sr-only"><tr><th scope="col">Service</th><th scope="col">État</th></tr></thead>
                <tbody>
                    <tr><th scope="row">Mode</th><td><span class="fr-badge fr-badge--sm ${_isMinified ? 'fr-badge--success' : 'fr-badge--info'} fr-badge--no-icon">${_isMinified ? 'Production' : 'Développement'}</span></td></tr>
                    <tr><th scope="row">Serveur OmniStudio</th><td>${badge(true)}</td></tr>
                    <tr><th scope="row">Moteur TTS (OmniVoice)</th><td>${badge(d.omnivoice)}</td></tr>
                    ${generationHtml}
                    ${modelsHtml}
                    <tr><th scope="row">Albert API (nettoyage LLM)</th><td>${d.albert ? badge(d.albert.ok, d.albert.ok ? escapeHtml(d.albert.model || 'Actif') : 'Injoignable') : badge(false, 'Non configuré')}</td></tr>
                    <tr><th scope="row">SoX (post-traitement)</th><td>${badge(d.audio_tools?.sox)}</td></tr>
                    <tr><th scope="row">FFmpeg</th><td>${badge(d.audio_tools?.ffmpeg)}</td></tr>
                </tbody>
            </table>
        `;
    } catch {
        content.innerHTML = '<p class="fr-alert fr-alert--error fr-alert--sm"><span class="fr-alert__title">Serveur injoignable</span></p>';
    } finally {
        content.removeAttribute('aria-busy');
    }
}

// --- Initialisation ---

document.addEventListener('DOMContentLoaded', () => {
    // Theme DSFR : gere nativement par le composant fr-display + dsfr.module.min.js
    // Persistance via localStorage cle "scheme" (geree par le DSFR)

    initStatusDialog();

    if (isAuthenticated()) {
        scheduleTokenRefresh();

        try {
            const token = localStorage.getItem('ov_access_token');
            if (token) {
                const payload = JSON.parse(atob(token.split('.')[1]));
                if (usernameDisplay) usernameDisplay.textContent = payload.preferred_username || '';
            }
        } catch {
            // Token malformed
        }

        showApp();
    } else {
        showLogin();
    }
});
