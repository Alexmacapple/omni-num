# OmniStudio — protocole agent

## Contexte

- Fork de `voice-num/voxstudio/` branché sur OmniVoice (k2-fsa, 646 langues) au lieu de VoxQwen.
- Stack : FastAPI + DSFR 1.11.2 + LangGraph + OmniVoice (port 8070) + Keycloak (client `omnistudio`, realm `harmonia`).
- Statut : projet en création (Phase 0 à 0bis). PRD-MIGRATION-001 v1.5 validé.

## Comment je travaille

- **TDD strict** : documentation d'abord (Phase 1), tests rouges (Phase 2), code pour passer au vert (Phase 3+), ajustements après.
- **Phase 0bis obligatoire** avant code applicatif : stub FastAPI `root_path="/omni"` + audit assets + Keycloak + Funnel. Critères de sortie stricts.
- Commits en français, conventionnels. Pas de `--no-verify`.
- Contenu > 30 lignes → fichier, jamais le chat.
- Suivi : PRD comme source de vérité, `todo.md` pour session, `/sauvegarde-git` inter-session.

## Playbooks

- **Démarrer le site** : `./start.sh` (lance Keycloak + OmniVoice:8070 + seed si vide + omnistudio:7870).
- **Arrêter** : `./stop.sh`.
- **Smoke test** : `./test-smoke.sh`.
- **Build prod** : `VOXSTUDIO_MINIFY=true ./scripts/build-frontend.sh`.
- **Audit assets sous `/omni`** : `./scripts/verify-assets-prefix.sh`.
- **Exposer en 5G** : `tailscale funnel --https=443 --set-path=/omni http://localhost:7870`.
- **Monitor** : `./scripts/monitor.sh` (vérifie Keycloak, OmniVoice, omnistudio, `memory_pressure < 0.5`).
- **Backup SQLite** : `./scripts/backup-db.sh` (rsync Mac Mini via Tailscale).
- **Seed voix système** : `cp -r data/voices-system/* OmniVoice/voices/custom/` puis `curl -X POST localhost:8070/voices/reload`.
- **Ajouter une voix perso** : onglet 3 → Design (Guidé ou Expert) ou Clone. Voix auto-taguées `owner=<JWT.sub>`.
- **Insérer un tag émotionnel** : cliquer un bouton de la palette, tag inséré au curseur. 13 tags : `[laughter]`, `[sigh]`, etc.
- **Multi-voix dans une étape** : insérer `[voice:Marianne] ... [voice:Jean] ...` dans le texte.
- **Recréer les 4 voix voice-num post-Phase 8** : pour `alexandra`, `frederique`, `stephanie`, `vieux` — générer 30 s via voxstudio preview, feed à `/voices/custom` source=clone (~15 min total).

## À ne pas faire

- Ne jamais écrire de code applicatif avant la fin de Phase 0bis (architecture non validée = debug en cascade).
- Ne jamais régénérer les 6 voix système — elles sont versionnées dans `data/voices-system/`, seed = `cp` uniquement.
- Ne jamais écrire des chemins absolus `/css/`, `/js/`, `/dsfr/` dans HTML/JS sans `<base href="/omni/">` ou préfixe build.
- Ne jamais accepter un nom de voix hors regex `^[a-zA-Z][a-zA-Z0-9_-]{2,49}$` (risque XSS).
- Ne jamais envoyer du français à `POST /design` d'OmniVoice (rejet 422). Compose toujours en anglais côté backend.
- Ne jamais activer l'auto-segmentation de dialogue — non supportée en v1.0, tag explicite uniquement.
- Ne jamais committer `data/models/` (faster-whisper ~800 Mo) ni `data/*.db` ni `voice/` ni `export/`.
- Ne jamais supprimer une voix `system: true` — non modifiable par design.
- Ne jamais démarrer voxstudio ET omnistudio simultanément sur le même Mac sans check `memory_pressure` (risque OOM).

## Modes d'échec connus

- (À remplir au fil des dérives observées pendant l'implémentation et l'usage.)
- Candidats probables dès les premières phases : assets absolus qui cassent sous `/omni`, redirectUris Keycloak mal configurés, contamination JWT audience `voxstudio`/`omnistudio`, cascade 409/423 si session stale mal interceptée.

## Comment demander

- Toute demande vague (« corrige ce truc », « améliore ça ») : reformuler avec au moins un chemin de fichier ou une décision PRD nommée avant d'agir.
- Avant un changement touchant `graph/` ou `routers/` : lire `documentation/md/ARCHITECTURE-LANGGRAPH-OMNI.md` — décision Option B (extension du graphe voxstudio).
- Avant d'ajouter un test : vérifier qu'il n'existe pas déjà dans `tests/` (27 fichiers adaptés + 14 nouveaux).
- Alex dit « commit et push » = faire exactement ça, rien de plus.
- Fin de session : `/sauvegarde-git` puis clôture, pas de suggestions de tâches suivantes.

## Références

| Ressource | Fichier |
|-----------|---------|
| PRD actif | `PRD/PRD-MIGRATION-001-FORK-OMNISTUDIO.md` (v1.5, 30 critères, 20 risques) |
| Architecture LangGraph | `documentation/md/ARCHITECTURE-LANGGRAPH-OMNI.md` *(à créer en Phase 1)* |
| Déploiement (Funnel, root_path) | `RUNBOOK-DEPLOYMENT.md` *(à créer en Phase 0bis)* |
| Ops (start, backup, monitor) | `documentation/md/RUNBOOK-OPS.md` *(à créer en Phase 1)* |
| Tags, SRT, accents, dialectes | `documentation/md/TAGS-SRT-SUBTITLES.md` *(à créer en Phase 1)* |
| Parser multi-voix (20 cas limites) | PRD Annexe M |
| Catalogue 6 voix système | `data/voices-system/` + `data/default_voices.json` |
| Dépôt front | `git@github.com:Alexmacapple/omni-num.git` |
| Dépôt TTS | `git@github.com:Alexmacapple/OmniVoice.git` (dossier `OmniVoice/` gitignored) |
