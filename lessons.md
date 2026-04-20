# Leçons — omni-num

## ARIA pattern onglets DSFR (2026-04-20)

**Bug :** forcer `tabindex="0"` sur tous les onglets (via MutationObserver) combat le DSFR JS et casse la navigation clavier — le DSFR ne peut plus gérer son roving tabindex.

**Fix :** appliquer le pattern ARIA correct :
- Seul l'onglet actif a `tabindex="0"`, tous les autres `tabindex="-1"`
- `switchTab()` gère le roving tabindex à chaque changement d'onglet
- `initTabKeyboardNav()` : listener `keydown` en phase CAPTURE sur la `tablist`, gère ArrowLeft/Right/Home/End, stoppe la propagation avant que DSFR ne reçoive l'événement

**Règle :** ne jamais observer `tabindex` pour forcer une valeur — ça entre en conflit avec tout composant JS qui gère lui-même son état de focus.

## Sous-onglets DSFR (2026-04-20)

Les sous-onglets gérés nativement par DSFR (ex : Bibliothèque/Créer/Cloner) nécessitent `data-fr-js-tab-button="true"` dans le HTML pour que le DSFR JS les initialise. Sans cet attribut, DSFR ignore le composant et il n'y a pas de nav clavier.

## CSP et bookmarklets d'audit a11y (2026-04-20)

La CSP strict bloque axe-core et autres bookmarklets d'audit. Solution : flag `OMNISTUDIO_CSP_DEV=true` dans `.env` (gitignored) relâche la CSP uniquement en dev — jamais en prod. Chargé via `python-dotenv` dans `config.py` et via `start.sh`.
