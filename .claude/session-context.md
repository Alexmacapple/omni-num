# Contexte de session — omni-num
> Dernière sauvegarde : 2026-05-05 19:35
> Reprendre en lisant ce fichier puis `todo.md`

## INVARIANTS

- Répertoire de travail : `/Users/alex/Claude/projets-heberges/omni-num`
- Branche : `main`
- Remote : `git@github.com:Alexmacapple/omni-num.git`
- Dernier commit poussé de référence : `b41fbfa docs: Prépare la phase qualité 18 sur 20`
- Dernier commit technique testé : `beca4b6 Stabilise routage Omni et tests E2E`
- PRD actif : `PRD/PRD-MIGRATION-001-FORK-OMNISTUDIO.md` v1.8, Phase 10 qualité dépôt 18/20
- Plan court terme : `todo.md`
- Stack : Keycloak `8082` + OmniVoice `8070` + OmniStudio `7870` + Funnel public `/omni`
- Préférence utilisateur : français, pragmatique, exécuter plutôt que proposer, commits/push uniquement quand demandé explicitement

## ETAT

### Terminé

- [x] Correction routage `/omni` sans `root_path="/omni"` par défaut + middleware préfixe public
- [x] Garde-fous ops renforcés : assets prefix, smoke test prod, monitor public JSON
- [x] Bases SQLite runtime retirées du suivi Git et ignorées
- [x] Deux E2E a11y utiles gardés : `tests/e2e/test_a11y_modals.py`, `tests/e2e/test_a11y_tabs.py`
- [x] Tests validés localement : `583 passed / 162 skipped / 0 failed`
- [x] E2E authentifiés ciblés : `48 passed / 4 skipped`
- [x] Commit technique `beca4b6` poussé sur `origin/main`
- [x] Commit documentaire `b41fbfa` poussé sur `origin/main`
- [x] Évaluation dépôt : `16/20`
- [x] Objectif suivant planifié : `18/20`
- [x] Correction documentaire : HEAD réel `b41fbfa` distingué du commit technique testé `beca4b6`
- [x] Definition of Done Phase 10 explicitée : `0 failed`, commandes en code `0`, skips justifiés, aucune régression fonctionnelle couverte
- [x] Feature flag Codex `goals` activé au bon niveau TOML : `[features] goals = true`, vérifié par `codex features list`
- [x] CI GitHub Actions créée localement : `.github/workflows/ci.yml`
- [x] Smoke statique CI créé : `scripts/ci-static-smoke.sh`
- [x] Hygiène Git : `.code-audit-results/` et `omnistudio/frontend/out/js/e2e-tests/_results/` retirés du suivi avec `git rm --cached`, fichiers conservés localement
- [x] E2E authentifiés reproductibles : `scripts/setup-e2e-user.sh`, défaut `omni-e2e`, skips documentés dans `RUNBOOK-OPS.md`
- [x] Coverage ciblée : `core/subtitle_client.py` 94 %, `routers/auth_routes.py` 89 %, `routers/export.py` 89 %, `routers/voices.py` 85 % ; coverage global local `84 %`

### En cours

- [~] Modifications documentaires non commitées : `CLAUDE.md`, `AGENTS.md`, `PRD/PRD-MIGRATION-001-FORK-OMNISTUDIO.md`, `todo.md`, `.claude/session-context.md`, `lessons.md`
- [~] Changement global non repo : `~/.codex/config.toml`

### A faire

- [x] Créer CI GitHub Actions reproductible
- [x] Nettoyer artefacts suivis (`.code-audit-results/`, résultats générés à trier)
- [x] Rendre E2E authentifiés reproductibles avec compte `omni-e2e`
- [x] Coverage cible 82-85 % atteint localement (`84 %`)
- [ ] Refactor progressif des modules volumineux (`tab-voices.js`, `routers/voices.py`, `omnivoice_client.py`)
- [ ] Ajouter scan secrets/patterns dangereux et toolchain frontend versionné

### Definition of Done Phase 10

- [ ] Toutes les commandes de validation sortent en code `0`, sans traceback ni erreur CLI non justifiée
- [ ] Suite complète verte : `python -m pytest tests` avec `0 failed`
- [ ] Skips E2E restants justifiés et documentés
- [ ] Aucune régression fonctionnelle observée sur les parcours couverts : routage `/omni`, assets, auth, voix, génération, export, sous-titres
- [ ] Smoke statique CI prévu sans services externes ; `scripts/monitor.sh`, `WARN_AS_ERROR=1 ./scripts/test-smoke.sh` et `scripts/verify-assets-prefix.sh` verts sur stack locale démarrée
- [x] Coverage global ≥ 82 %, cible 85 % (`84 %` local)
- [ ] Aucun artefact runtime/audit inutile dans `git ls-files`

### Bloqué

- [ ] Aucun blocage technique connu. Le skip de renommage voix custom est documenté tant que la fixture voix custom `omni-e2e` n'est pas automatisée.

## DECISIONS

1. **Vise 18/20 avant 20/20** - 18/20 atteignable par CI, hygiène Git, E2E, coverage et petits refactors ; 20/20 demanderait une industrialisation plus lourde.
2. **CI et hygiène avant refactor** - Meilleur ratio risque/gain ; évite de refactorer sans filet.
3. **E2E a11y conservés** - Ils ont détecté de vraies régressions modales/tabs et passent en authentifié.
4. **FastAPI sans `root_path="/omni"` par défaut** - Funnel strippe généralement le préfixe ; le middleware tolère aussi les proxys qui ne strippent pas.

## ARTEFACTS

### Modifiés cette passation

- `CLAUDE.md` : état courant, commandes réelles, lien PRD v1.8/todo/passation
- `AGENTS.md` : état courant 2026-05-05, objectif 18/20
- `README.md` : commandes `scripts/*`, qualité mesurée, PRD v1.8
- `documentation/md/RUNBOOK-OPS.md` : commandes `scripts/*`, port 7870, E2E `omni-e2e`
- `PRD/PRD-MIGRATION-001-FORK-OMNISTUDIO.md` : v1.8, Phase 10, critères #31-#36, risque #21
- `todo.md` : plan court terme 18/20
- `.claude/session-context.md` : cette passation
- `lessons.md` : leçon Codex feature flags sous `[features]`
- `tests/test_endpoints.py`, `tests/test_subtitles.py`, `tests/test_voice_ownership.py` : coverage ciblée export/voices/subtitles/auth
- `omnistudio/routers/clean.py` : `/api/clean` ne requiert plus LLMClient quand aucune étape n'est en attente
- `~/.codex/config.toml` : activation effective de `goals` sous `[features]` (hors dépôt)

### À ne pas committer par accident

- Secrets locaux : `.env`, `CLAUDE.local.md`, `~/Claude/keycloak/.env`
- Runtime : `omnistudio/data/*.db*`, `data/*.db*`, `voice/`, `export/`, `logs/`
- Cache modèle : `data/models/`

## ERREURS CORRIGEES

1. **Docs pointaient vers `./start.sh`, `./stop.sh`, `./test-smoke.sh`**
   - Mauvais : commandes racine inexistantes
   - Correct : `./scripts/start.sh`, `./scripts/stop.sh`, `WARN_AS_ERROR=1 ./scripts/test-smoke.sh`
   - Pourquoi : les scripts réels sont dans `scripts/`
2. **Passation obsolète du 2026-04-20**
   - Mauvais : contexte parlait de commits locaux non poussés et d ancien état RGAA
   - Correct : contexte 2026-05-05 avec HEAD `b41fbfa`, commit technique testé `beca4b6`, tests verts, objectif 18/20
3. **README sur-promettait coverage ≥ 85 %**
   - Mauvais : assertion non alignée avec mesure actuelle
   - Correct : coverage mesuré 84 %, cible Phase 10 82-85 % atteinte localement
4. **Flag Codex `goals` au mauvais niveau TOML**
   - Mauvais : `goals = true` au niveau racine de `~/.codex/config.toml`
   - Correct : `[features]` puis `goals = true`
   - Vérification : `codex features list | rg '^goals\s'` retourne `true`

## SUITE

1. Redémarrer Codex TUI si `/goal` reste inconnu, car la session ouverte peut avoir chargé l'ancienne config.
2. Vérifier docs : `git diff --check` puis relire `todo.md` et PRD Phase 10.
3. Si Alex demande commit/push : committer les docs avec un message du type `docs: Clarifie la Definition of Done Phase 10`.
4. Prochaine vraie tâche : pousser la branche, observer la CI distante, puis décider si un petit refactor ou un scan sécurité est nécessaire avant réévaluation.
