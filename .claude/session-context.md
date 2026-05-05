# Contexte de session — omni-num
> Dernière sauvegarde : 2026-05-05 23:35 CEST
> Reprendre en lisant ce fichier puis `todo.md`

## INVARIANTS

- Répertoire de travail : `/Users/alex/Claude/projets-heberges/omni-num`
- Branche : `main`
- Remote : `git@github.com:Alexmacapple/omni-num.git`
- PRD actif : `PRD/PRD-MIGRATION-001-FORK-OMNISTUDIO.md` v1.8.2
- Plan court terme : `todo.md`
- Stack validée : Keycloak `8082`, OmniVoice `8070`, OmniStudio `7870`, Funnel public `/omni`
- Invariant Funnel : FastAPI doit rester sans `root_path="/omni"` ; `<base href="/omni/">` reste dans `index.html`
- Ne pas toucher : `OmniVoice/`, `data/voices-system/`, `data/models/`
- Préférence utilisateur : français, pragmatique, exécuter plutôt que proposer, commits/push quand demandé explicitement
- Dernier commit poussé avant cette sauvegarde : `9c9029b chore: Sauvegarde clôture session`
- Dernière CI confirmée verte : GitHub Actions run `25403342115`

## ETAT

### Terminé

- [x] Phase 10 qualité dépôt clôturée : **18/20 atteint**
- [x] CI GitHub Actions verte sur `main`
- [x] Suite complète locale : `590 passed / 162 skipped / 0 failed`
- [x] Coverage Python : `84 %`
- [x] Build frontend reproductible : `package.json`, `package-lock.json`, `npm ci`, `npm run build`, `esbuild` local verrouillé
- [x] Durcissements sécurité : uploads audio bornés, paramètres avancés Pydantic bornés, garde-chemins `Path.resolve().is_relative_to(...)`
- [x] `root_path` verrouillé vide dans FastAPI + smoke CI contre `root_path="/omni"` et env dynamique
- [x] Stub front nettoyé : plus de `innerHTML`, plus de logs console
- [x] Scan sécurité final ajouté : `scripts/security-smoke.sh`, branché dans `.github/workflows/ci.yml`
- [x] Docs mises à jour : `README.md`, `AGENTS.md`, `todo.md`, PRD v1.8.2
- [x] Insight Forge lancé :
  - 4 sessions Codex traitées
  - 2056 candidats extraits
  - 1 événement direct routé
  - 0 contradiction
  - 0 connaissance cristallisée à injecter dans `CLAUDE.md` / `AGENTS.md`
- [x] Premortem production réalisée en conversation : risque principal = confondre dépôt prêt et service opérable
- [x] `postmortem.md` créé avec une gate prod en 10 points pour prod contrôlée/interne

### En cours

- [~] Commit/push final de clôture : `postmortem.md` + passation

### A faire

- [ ] Après push, surveiller la CI du commit final
- [ ] Si CI verte, considérer la session close sans autre action

### Bloqué

- [ ] Aucun blocage connu

## DECISIONS

1. **Smoke sécurité ciblé plutôt que scan naïf global** - Le frontend principal contient des `innerHTML` historiques, souvent échappés ou DSFR contrôlés. Le scan bloque les secrets et les patterns critiques, mais garde le refactor `innerHTML` principal comme backlog non bloquant.
2. **18/20 sans grand refactor** - Objectif Phase 10 atteint par garde-fous reproductibles : CI, coverage, E2E documentés, build front verrouillé, smokes assets/sécurité.
3. **Refactors reportés** - `tab-voices.js`, `routers/voices.py` et `omnivoice_client.py` restent à découper progressivement, sans bloquer la clôture Phase 10.
4. **Insight Forge versionné sans cache brut** - Les synthèses `.insight-forge/logic`, `trace`, `staging`, `proposals` et README sont utiles pour la reprise. Le cache `.insight-forge/.cache/` est généré depuis les sessions et reste ignoré.
5. **Prod interne = gate d'exploitation** - Pour une prod contrôlée/interne, le blocage n'est plus prioritairement le code mais la preuve opérationnelle : stack, auth, Funnel, parcours complet, charge/mémoire, backup/restore, sécurité, accessibilité, runbook/rollback.

## ARTEFACTS

### Modifiés

- `.github/workflows/ci.yml` : ajout du step `Security smoke`
- `README.md` : statut Phase 10 clôturée, qualité 18/20, scan sécurité documenté
- `AGENTS.md` : état courant 18/20 et restes non bloquants
- `todo.md` : Phase 10 clôturée, backlog post-18/20
- `PRD/PRD-MIGRATION-001-FORK-OMNISTUDIO.md` : version 1.8.2 + changelog de clôture
- `.claude/session-context.md` : cette passation
- `.insight-forge/.gitignore` : ignore le cache brut généré
- `postmortem.md` : premortem production + gate prod en 10 points

### Créés

- `scripts/security-smoke.sh` : scan statique sécurité sans services externes
- `.insight-forge/` : base de connaissance Insight Forge initialisée
- `.insight-forge/proposals/2026-05-05T21-15-32Z.md` : proposition vide, aucune connaissance cristallisée pour l'instant
- `postmortem.md` : checklist go/no-go pour prod contrôlée/interne et prod publique large

### Mémoire hors dépôt

- `~/.claude/projects/-Users-alex-Claude/memory/feedback_security_smoke_baseline.md` : leçon sur scans sécurité ciblés
- `~/.claude/projects/-Users-alex-Claude/memory/feedback_prod_gate_operability.md` : leçon sur la distinction qualité dépôt / opérabilité prod
- `~/.claude/projects/-Users-alex-Claude/memory/MEMORY.md` : index mémoire mis à jour

## ERREURS CORRIGEES

1. **Scan `innerHTML` trop large**
   - Mauvais : bloquer tous les `innerHTML` du frontend principal d'un coup
   - Correct : bloquer le stub déjà nettoyé et traiter le frontend principal comme refactor non bloquant
   - Pourquoi : sinon la CI échoue sur dette historique connue, au lieu de protéger les invariants Phase 10

2. **Docs Phase 10 obsolètes**
   - Mauvais : `CI distante à confirmer`, `candidat local`, `583 passed`
   - Correct : CI verte, `590 passed / 162 skipped`, coverage `84 %`, PRD v1.8.2
   - Pourquoi : le dépôt doit raconter l'état réel après les commits poussés

3. **Hash de dernier commit dans docs**
   - Mauvais : figer le dernier commit dans tous les docs de statut, puis le rendre obsolète au commit suivant
   - Correct : documenter la CI verte sur `main` et les critères, sans dépendre d'un hash dans chaque section

4. **Cache Insight Forge**
   - Mauvais : committer `.insight-forge/.cache/normalized.jsonl`
   - Correct : versionner les synthèses et ignorer `.cache/`
   - Pourquoi : le cache est reconstructible et contient du matériau brut de session inutile en revue de code

5. **Confusion dépôt prêt / prod prête**
   - Mauvais : répondre seulement avec CI, tests et note dépôt
   - Correct : poser une gate d'exploitation à preuves concrètes
   - Pourquoi : la prod peut échouer sur Keycloak, Funnel, mémoire, backup ou parcours réel malgré une CI verte

## SUITE

1. Committer `postmortem.md` et la passation avec un message du type `docs: Ajoute gate prod interne`.
2. Pousser `main`.
3. Surveiller la CI GitHub Actions du commit final.
4. Si CI verte, répondre à Alex : session clôturée, `postmortem.md` poussé, Phase 10 fermée, 18/20 atteint.
5. Prochaine action utile : exécuter la gate prod en 10 points et remplir les preuves dans `postmortem.md`.