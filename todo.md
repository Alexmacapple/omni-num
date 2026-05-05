# TODO — Phase 10 clôturée, restes non bloquants

Source de vérité : [`PRD/PRD-MIGRATION-001-FORK-OMNISTUDIO.md`](PRD/PRD-MIGRATION-001-FORK-OMNISTUDIO.md), Phase 10 v1.8.2.

## État de départ

- Score actuel : **16/20**.
- Dernier commit poussé : `b41fbfa docs: Prépare la phase qualité 18 sur 20`.
- Dernier commit technique testé : `beca4b6 Stabilise routage Omni et tests E2E`.
- Tests : `548 passed / 163 skipped / 0 failed`.
- Coverage Python : `78 %`.
- Ops verts : `scripts/monitor.sh`, `scripts/test-smoke.sh`, `scripts/verify-assets-prefix.sh`.

## État courant après lots Phase 10

- CI GitHub Actions verte sur `main`.
- Suite complète : `590 passed / 162 skipped / 0 failed`.
- Coverage Python : `84 %` (`routers/export.py` 89 %, `routers/voices.py` 88 %).
- Build frontend reproductible : `package.json`, `package-lock.json`, `npm ci`, `npm run build`, `esbuild` local verrouillé.
- Garde-fous ajoutés : `root_path` forcé vide, uploads audio bornés, garde-chemins `Path.resolve().is_relative_to(...)`, paramètres avancés bornés, stub front sans `innerHTML` ni logs console.
- Scan sécurité final : `scripts/security-smoke.sh`, branché dans la CI.
- Statut qualité : **16/20** historique ; **18/20 atteint** en Phase 10.

## Lots Phase 10

1. [x] Créer la CI GitHub Actions :
   - install Python 3.12 ;
   - installer `omnistudio/requirements.txt`, `tests/requirements-test.txt`, `tests/e2e/requirements.txt` ;
   - lancer `python -m pytest tests -q --timeout=120` ;
   - lancer `scripts/verify-assets-prefix.sh` ;
   - ajouter/lancer un smoke statique CI sans services externes ;
   - publier le coverage.
2. [x] Nettoyer l'hygiène Git :
   - retirer du suivi `.code-audit-results/` si non nécessaire ;
   - vérifier les screenshots/résultats générés ;
   - compléter `.gitignore`.
3. [x] Rendre les E2E authentifiés reproductibles :
   - documenter `omni-e2e` ;
   - ajouter un script de préparation sans secret en dur ;
   - créer une voix custom fixture ou justifier les skips.
4. [x] Coverage ciblée :
   - `routers/export.py` ;
   - `routers/voices.py` ;
   - `core/subtitle_client.py` ;
   - `routers/auth_routes.py`.
5. [ ] Refactor progressif (non bloquant, post-18/20) :
   - extraire des helpers depuis `tab-voices.js` ;
   - extraire services/helpers depuis `routers/voices.py` ;
   - isoler les branches testables de `core/omnivoice_client.py`.
6. [x] Sécurité et dépendances :
   - [x] ajouter scan secrets/patterns dangereux ;
   - [x] déclarer le build frontend (`esbuild`) dans un toolchain versionné.
   - [x] préparer GitHub Actions au runtime Node 24.

## Critères de sortie

- CI verte sur `main`.
- Toutes les commandes de validation sortent en code `0`, sans traceback ni erreur CLI non justifiée.
- Suite complète verte : `python -m pytest tests` avec `0 failed` ; les tests skippés sont justifiés et documentés.
- Aucune régression fonctionnelle observée sur les parcours couverts : routage `/omni`, assets, auth, voix, génération, export, sous-titres.
- `scripts/monitor.sh`, `WARN_AS_ERROR=1 ./scripts/test-smoke.sh` et `scripts/verify-assets-prefix.sh` verts sur stack locale démarrée.
- Coverage global ≥ 82 %, cible 85 % (`84 %` local atteint).
- Skips E2E justifiés et documentés.
- Aucun artefact runtime/audit inutile dans `git ls-files`.
- Réévaluation dépôt : **18/20 atteint**.

## Restes non bloquants

- Refactor progressif de `omnistudio/frontend/out/js/tab-voices.js`.
- Extraction de services/helpers depuis `omnistudio/routers/voices.py`.
- Isolation de branches testables dans `omnistudio/core/omnivoice_client.py`.
- Audit RGAA approfondi avant exposition publique plus large que le Funnel interne.
- Réduction progressive des usages historiques de `innerHTML` dans le frontend principal, en conservant les cas DSFR contrôlés ou échappés.
