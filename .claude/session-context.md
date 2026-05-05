# Contexte de session — omni-num
> Dernière sauvegarde : 2026-05-05 18:25
> Reprendre en lisant ce fichier puis `todo.md`

## INVARIANTS

- Répertoire de travail : `/Users/alex/Claude/projets-heberges/omni-num`
- Branche : `main`
- Remote : `git@github.com:Alexmacapple/omni-num.git`
- Dernier commit poussé de référence : `beca4b6 Stabilise routage Omni et tests E2E`
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
- [x] Tests validés : `548 passed / 163 skipped / 0 failed`
- [x] E2E authentifiés ciblés : `48 passed / 4 skipped`
- [x] Commit `beca4b6` poussé sur `origin/main`
- [x] Évaluation dépôt : `16/20`
- [x] Objectif suivant planifié : `18/20`

### En cours

- [~] Mise à jour documentaire de passation : `CLAUDE.md`, `AGENTS.md`, `README.md`, `RUNBOOK-OPS.md`, PRD v1.8, `todo.md`, `.claude/session-context.md`
- [~] Relance stack après mise à jour docs

### A faire

- [ ] Créer CI GitHub Actions reproductible
- [ ] Nettoyer artefacts suivis (`.code-audit-results/`, résultats générés à trier)
- [ ] Rendre E2E authentifiés reproductibles avec compte `omni-e2e`
- [ ] Monter coverage de 78 % vers 82-85 % sur les zones critiques
- [ ] Refactor progressif des modules volumineux (`tab-voices.js`, `routers/voices.py`, `omnivoice_client.py`)
- [ ] Ajouter scan secrets/patterns dangereux et toolchain frontend versionné

### Bloqué

- [ ] Aucun blocage technique connu. Les E2E complets restent partiellement skipés sans fixture voix custom pour `omni-e2e`.

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
   - Correct : contexte 2026-05-05 avec commit `beca4b6`, tests verts, objectif 18/20
3. **README sur-promettait coverage ≥ 85 %**
   - Mauvais : assertion non alignée avec mesure actuelle
   - Correct : coverage mesuré 78 %, cible Phase 10 82-85 %

## SUITE

1. Vérifier docs : `git diff --check` puis relire `todo.md` et PRD Phase 10.
2. Relancer : `./scripts/stop.sh` puis `./scripts/start.sh`.
3. Vérifier : `./scripts/monitor.sh`, `WARN_AS_ERROR=1 ./scripts/test-smoke.sh`, `./scripts/verify-assets-prefix.sh`.
4. Si Alex demande commit/push : committer les docs avec un message du type `docs: Prépare la phase qualité 18 sur 20`.
5. Prochaine vraie tâche : CI GitHub Actions reproductible.
