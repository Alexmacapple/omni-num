# Contexte de session — omni-num
> Dernière sauvegarde : 2026-04-20 18:xx
> Reprendre en lisant ce fichier

## INVARIANTS

- Répertoire de travail : /Users/alex/Claude/projets-heberges/omni-num
- Branche : main
- Remote : git@github.com:Alexmacapple/omni-num.git
- Dernier commit : 524bdae RGAA 11.7/11.9 fieldset zone test + optgroup 3 selects
- PRD : PRD/PRD-MIGRATION-001-FORK-OMNISTUDIO.md (v1.7, phases 1-8 livrées)
- Stack : FastAPI 7870 + OmniVoice 8070 + Keycloak 8082, exposition Cloudflare Tunnel omni.appmiweb.com
- Venv : OmniVoice/venv (actif via start.sh)

## ETAT

### Terminé (session 2026-04-20)

- [x] Navigation clavier onglets principaux (roving tabindex + ArrowLeft/Right/Home/End capture phase) — app.js
- [x] Sous-onglets Voix : tabindex initial + data-fr-js-tab-button='true' pour DSFR natif — index.html
- [x] Breadcrumb aria-current : tabindex='0' statique et dynamique (url-state.js)
- [x] aria-label sur toutes les zones role='status' (import, clean, design, clone, record) — index.html
- [x] CSP_DEV mode : relâche CSP pour audits a11y bookmarklets en dev (config.py + server.py + start.sh)
- [x] Ajout python-dotenv (requirements.txt) + chargement .env dans config.py et start.sh
- [x] Build out-dist (app.min.js à 17:40) — déployé et validé clavier sur omni.appmiweb.com
- [x] Commits RGAA 11.7/11.9 fieldset+optgroup (524bdae)

### À faire (bloquant ouverture publique)

- [ ] Audit RGAA 4.1.2 complet via /audit-rgaa-dsfr (est. 6 h) — taux cible >= 90%
- [ ] focus-visible cohérent sur composants custom (est. 2 h, WCAG 2.4.7)
- [ ] Déclaration d'accessibilité à publier avant ouverture publique
- [ ] Recréer 4 voix voice-num (alexandra, frederique, stephanie, vieux) via voxstudio clone (~15 min)
- [ ] git push origin main (jamais poussé, 13+ commits locaux)

## DECISIONS

1. Roving tabindex DSFR : seul l'onglet actif a tabindex='0', les autres tabindex='-1'. switchTab() gère le roving. Rejeté : forcer tous les onglets à tabindex=0 (combat DSFR, casse les flèches)
2. initTabKeyboardNav en capture phase : intercepte ArrowLeft/Right/Home/End avant que DSFR ne reçoive l'événement. stopPropagation() dans le handler.
3. Sous-onglets gérés par DSFR nativement (data-fr-js-tab-button='true') — pas de handler custom.
4. CSP_DEV flag gitignored via .env — jamais en prod.

## ARTEFACTS

### Modifiés (non encore commités)

- omnistudio/frontend/out/js/app.js (roving tabindex + initTabKeyboardNav + observeTabChanges immédiat)
- omnistudio/frontend/out/index.html (sous-onglets tabindex + aria-labels role=status)
- omnistudio/frontend/out/js/url-state.js (breadcrumb tabindex='0')
- omnistudio/config.py (CSP_DEV flag + python-dotenv)
- omnistudio/server.py (CSP_DEV middleware)
- omnistudio/requirements.txt (python-dotenv==1.1.0)
- scripts/start.sh (.env chargement + OMNISTUDIO_CSP_DEV export)

### Créés

- lessons.md (patterns ARIA onglets + sous-onglets + CSP_DEV)

### Ne PAS committer

- omnistudio/data/*.db (runtime)

## ERREURS CORRIGEES

1. MutationObserver tabindex=0 forcé sur tous onglets : combat DSFR, nav clavier cassée. Fix : roving tabindex correct.
2. observeTabChanges appelé avec setTimeout 200ms : fenêtre aveugle où ArrowRight ne switchait pas le panel. Fix : appel immédiat.
3. Sous-onglets sans data-fr-js-tab-button : DSFR ne les initialise pas, pas de nav clavier. Fix : attribut ajouté.

## SUITE

1. Committer les changements de la session (accessibilité clavier + CSP_DEV)
2. Lancer /audit-rgaa-dsfr sur omni.appmiweb.com (RGAA 4.1.2, bloquant)
3. Corriger les non-conformités détectées (focus-visible en priorité)
4. git push origin main quand audit >= 90%
5. Publier la déclaration d'accessibilité