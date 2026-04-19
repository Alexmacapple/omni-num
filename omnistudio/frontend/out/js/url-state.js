/**
 * url-state.js — Routage URL par hash pour les onglets OmniStudio.
 *
 * Format : #<tab-name>[/<sub-tab>]
 * Exemples : #import, #clean, #voices, #voices/design, #voices/clone
 *
 * - Deep linking : ouvrir une URL avec un hash navigue vers l'onglet
 * - Persistance : F5 revient au bon onglet (et sous-onglet)
 * - Historique : bouton retour du navigateur fonctionnel
 * - Prevention des boucles : comparaison d'etat (pas de flag)
 */
import { eventBus, getCurrentActiveTab } from './app.js';

// Mapping hash <-> tab ID (niveau 1)
const HASH_TO_TAB = {
    import:   'tab-import',
    clean:    'tab-clean',
    voices:   'tab-voices',
    assign:   'tab-assign',
    generate: 'tab-generate',
    export:   'tab-export',
};

const TAB_TO_HASH = Object.fromEntries(
    Object.entries(HASH_TO_TAB).map(([h, t]) => [t, h])
);

// Mapping sous-onglets voix (niveau 2)
const SUB_HASH_TO_TAB = {
    library: 'sub-tab-library',
    design:  'sub-tab-design',
    clone:   'sub-tab-clone',
};

const SUB_TAB_TO_HASH = Object.fromEntries(
    Object.entries(SUB_HASH_TO_TAB).map(([h, t]) => [t, h])
);

const DEFAULT_HASH = 'import';
const DEFAULT_SUB_HASH = 'library';

// Labels pour le fil d'Ariane
const TAB_LABELS = {
    'tab-import':   'Import',
    'tab-clean':    'Préparation',
    'tab-voices':   'Voix',
    'tab-assign':   'Assignation',
    'tab-generate': 'Génération',
    'tab-export':   'Export',
};

const SUB_TAB_LABELS = {
    'sub-tab-library': 'Bibliothèque',
    'sub-tab-design':  'Créer',
    'sub-tab-clone':   'Cloner',
};

/** Parse le hash courant. Retourne { tab, sub } ou null. */
function parseHash(hash) {
    const raw = (hash || location.hash).replace(/^#\/?/, '').toLowerCase();
    const parts = raw.split('/');
    const tabName = parts[0];

    if (!HASH_TO_TAB[tabName]) return null;

    const subName = parts[1] || null;
    // Valider le sous-onglet uniquement pour voices
    const validSub = (tabName === 'voices' && subName && SUB_HASH_TO_TAB[subName])
        ? subName : null;

    return { tab: tabName, sub: validSub };
}

/** Construit le hash complet depuis un tab ID et optionnellement un sub-tab ID. */
function buildHash(tabId, subTabId) {
    const base = TAB_TO_HASH[tabId] || DEFAULT_HASH;
    if (tabId === 'tab-voices' && subTabId && SUB_TAB_TO_HASH[subTabId]) {
        const subHash = SUB_TAB_TO_HASH[subTabId];
        // Ne pas ajouter le sous-hash par defaut (library)
        if (subHash !== DEFAULT_SUB_HASH) {
            return base + '/' + subHash;
        }
    }
    return base;
}

/** Active un sous-onglet DSFR par clic. */
function activateSubTab(subTabId) {
    const btn = document.getElementById(subTabId);
    if (btn && btn.getAttribute('aria-selected') !== 'true') {
        btn.click();
    }
}

/** Retourne l'ID du sous-onglet voix actuellement actif. */
function getCurrentSubTab() {
    const active = document.querySelector('#panel-voices .fr-tabs__tab[aria-selected="true"]');
    return active?.id || 'sub-tab-library';
}

/**
 * Hash -> JS : lit le hash et navigue si necessaire.
 * Appele sur hashchange et au chargement initial.
 */
function syncHashToState() {
    const parsed = parseHash();
    if (!parsed) {
        // Hash invalide ou vide -> corriger silencieusement
        history.replaceState(null, '', '#' + DEFAULT_HASH);
        return;
    }

    const targetTab = HASH_TO_TAB[parsed.tab];
    // Utiliser l'etat JS (pas le DOM) pour eviter les desynchronisations
    // quand aria-selected n'est pas mis a jour (mobile stepper)
    const currentTab = getCurrentActiveTab();

    const needsTabSwitch = targetTab !== currentTab;

    // Naviguer vers l'onglet L1 si necessaire
    if (needsTabSwitch) {
        eventBus.emit('navigate', targetTab);
    }

    // Gerer le sous-onglet voix
    if (parsed.tab === 'voices') {
        const targetSub = parsed.sub ? SUB_HASH_TO_TAB[parsed.sub] : 'sub-tab-library';
        // Petit delai pour laisser le DSFR activer le panel
        const delay = needsTabSwitch ? 100 : 0;
        setTimeout(() => activateSubTab(targetSub), delay);
    }

    // Focus sur le panel pour navigation par URL
    if (needsTabSwitch) {
        const panelId = targetTab.replace('tab-', 'panel-');
        const panel = document.getElementById(panelId);
        if (panel) {
            if (!panel.hasAttribute('tabindex')) panel.setAttribute('tabindex', '-1');
            requestAnimationFrame(() => panel.focus({ preventScroll: false }));
        }
    }
}

/**
 * JS -> Hash : met a jour le hash quand la navigation JS change.
 * Appele quand un onglet L1 est active.
 */
function syncStateToHash(tabId) {
    // Pour voices, inclure le sous-onglet courant
    const subTabId = (tabId === 'tab-voices') ? getCurrentSubTab() : null;
    const newHash = '#' + buildHash(tabId, subTabId);

    // Deja a jour -> rien a faire (coupe la boucle)
    if (location.hash === newHash) return;

    // Changement d'onglet -> entree d'historique (bouton retour)
    location.hash = newHash;
}

/**
 * Sous-onglet voix change -> mettre a jour le hash.
 */
function syncSubTabToHash(subTabId) {
    if (!SUB_TAB_TO_HASH[subTabId]) return;
    // Ne pas reagir si on n'est plus sur l'onglet Voix
    // (le DSFR peut modifier aria-selected des sous-onglets en quittant le panel)
    const currentMainTab = document.querySelector(
        '#main-tabs > .fr-tabs__list .fr-tabs__tab[aria-selected="true"]'
    );
    if (currentMainTab?.id !== 'tab-voices') return;

    const newHash = '#' + buildHash('tab-voices', subTabId);
    if (location.hash !== newHash) {
        location.hash = newHash;
    }
    updateBreadcrumb('tab-voices', subTabId);
}

/**
 * Observer les changements de sous-onglets voix.
 */
function observeSubTabs() {
    const subTabs = document.querySelectorAll('#panel-voices .fr-tabs__tab');
    if (subTabs.length === 0) return;

    const observer = new MutationObserver((mutations) => {
        for (const m of mutations) {
            if (m.attributeName === 'aria-selected' &&
                m.target.getAttribute('aria-selected') === 'true') {
                syncSubTabToHash(m.target.id);
            }
        }
    });

    subTabs.forEach(t => observer.observe(t, { attributes: true, attributeFilter: ['aria-selected'] }));
}

/**
 * Met a jour le fil d'Ariane DSFR en fonction de l'onglet actif.
 */
function updateBreadcrumb(tabId, subTabId) {
    const list = document.getElementById('ov-breadcrumb-list');
    if (!list) return;

    const tabLabel = TAB_LABELS[tabId] || 'Import';
    const tabHash = TAB_TO_HASH[tabId] || DEFAULT_HASH;

    let html = `<li><a class="fr-breadcrumb__link" href="#main-content">OmniStudio</a></li>`;

    if (tabId === 'tab-voices' && subTabId && SUB_TAB_LABELS[subTabId]) {
        // 3 niveaux : OmniStudio > Voix > Sous-onglet
        html += `<li><a class="fr-breadcrumb__link" href="#panel-${tabHash}">${tabLabel}</a></li>`;
        html += `<li><a class="fr-breadcrumb__link" aria-current="page">${SUB_TAB_LABELS[subTabId]}</a></li>`;
    } else {
        // 2 niveaux : OmniStudio > Onglet
        html += `<li><a class="fr-breadcrumb__link" aria-current="page">${tabLabel}</a></li>`;
    }

    list.innerHTML = html;
}

/**
 * Initialise le routage URL.
 * A appeler une seule fois dans showApp() apres l'init des modules.
 */
export function initUrlState() {
    // Ecouter les changements de hash (saisie manuelle, retour navigateur)
    window.addEventListener('hashchange', syncHashToState);

    // Ecouter les activations d'onglets JS -> mettre a jour le hash + breadcrumb
    eventBus.on('tab-activated', (tabId) => {
        syncStateToHash(tabId);
        const subTabId = (tabId === 'tab-voices') ? getCurrentSubTab() : null;
        updateBreadcrumb(tabId, subTabId);
    });

    // Observer les sous-onglets voix
    observeSubTabs();

    // Etat initial : si un hash est present, naviguer ; sinon activer le defaut
    const parsed = parseHash();
    if (parsed) {
        syncHashToState();
        // Breadcrumb initial
        const tabId = HASH_TO_TAB[parsed.tab];
        const subTabId = parsed.sub ? SUB_HASH_TO_TAB[parsed.sub] : null;
        updateBreadcrumb(tabId, subTabId);
    } else {
        history.replaceState(null, '', '#' + DEFAULT_HASH);
        eventBus.emit('navigate', HASH_TO_TAB[DEFAULT_HASH]);
    }
}
