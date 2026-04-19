# Contexte de session — omni-num
> Dernière sauvegarde : 2026-04-19 13:15
> Reprendre en lisant ce fichier

## INVARIANTS

- Répertoire de travail : `/Users/alex/Claude/projets-heberges/omni-num`
- Branche : `main` (pas de remote pushé : `git ls-remote origin` vide)
- Dernier commit local : `079835e` "Phase 3ter SRT + injection owner — sous-titres faster-whisper et PRD-032"
- 8 commits locaux non pushés depuis l'init du repo
- PRD source : `PRD/PRD-MIGRATION-001-FORK-OMNISTUDIO.md` v1.5 (17 décisions, 30 critères, 20 risques, 12 phases)
- Stack runtime : FastAPI port 7870 (PID 78241, venv `voice-num/voxstudio/venv/bin/python3`),
  OmniVoice port 8070, Keycloak realm `harmonia` client `omnistudio` port 8082,
  exposition Tailscale Funnel `https://mac-studio-alex.tail0fc408.ts.net/omni/`
- Frontend assets : `<base href="/omni/">` + `_normalizeUrl()` dans api-client.js
  (sinon les fetch `/api/...` contournent base href et tapent voxstudio:7860)

## ETAT

### Terminé (sans push)

- [x] Phase 0 / 0bis / 1 / 2 / 3 / 5 (commits be733bb, b8291c5, 1cb84c4)
- [x] Phase 3bis frontend — palette 13 tags émotionnels + bouton voix aléatoire +
      option Auto-détection langue (commit b8764ad, validé in vivo agent-browser)
- [x] Phase 3ter — sous-titres SRT via faster-whisper, 4 formats, opt-in via
      `include_subtitles` + `subtitle_format` (commit 079835e)
- [x] PRD-032 — injection automatique `owner=<JWT.sub>` + `system: false` dans
      meta.json après chaque save_custom_voice (lock + clone). Helper
      `_inject_owner_in_meta()` idempotent dans voices.py
- [x] Smoke test backend post-Phase 3ter : /api/health OK, 3 nouvelles routes
      répondent en 401 (auth requise = enregistrées correctement)
- [x] Audit a11y des ajouts : accesslint statique 0 violation toutes sévérités,
      ARIA ciblé sur 5 ajouts 100% conforme (role=group, aria-label, label for,
      fieldset+legend, options descriptives)

### À faire pour finir le PRD à 100% (~5 h)

- [ ] **Décision 14** — Accordéon DSFR 11 paramètres avancés dans onglet Génération
      (0 occurrence dans index.html, voir Annexe J du PRD pour la liste)
- [ ] **Vérifier Décision 5** — Tabs Guidé/Expert dans sub-panel-design (sous-tabs
      Bibliothèque/Créer/Cloner existent, mais Guidé/Expert à confirmer)
- [ ] **Vérifier Décision 12** — UI 6 catégories Voice Design (Genre/Age/Pitch/
      Style/EnglishAccent/ChineseDialect) — 14 occurrences détectées, à valider
- [ ] **Scripts ops** : créer `scripts/start.sh`, `stop.sh`, `monitor.sh`,
      `test-smoke.sh` (absents de scripts/)
- [ ] **Décision 17** — Appel POST /api/models/preload au boot dans start.sh
      (endpoint existe dans status.py, juste pas wiré au démarrage)
- [ ] **Phase 8** — Smoke test bout-en-bout 5G + 2 utilisateurs concurrents +
      check `memory_pressure < 0.5` (critère #29)
- [ ] **Annexe L** — Recréer 4 voix voice-num (alexandra, frederique, stephanie,
      vieux) via voxstudio preview → POST /voices/custom source=clone (~15 min)
- [ ] **Phase 7 push** — `git push -u origin main` vers
      `git@github.com:Alexmacapple/omni-num.git`

### Bloqué

- (rien — tous les blocages identifiés tout au long sont levés)

## DECISIONS

1. **Phase 3bis palette tags : insertion à la position du curseur** dans le
   dernier `.vx-tts-edit` qui a eu le focus. Module `tag-palette.js` avec
   `trackFocus()` global + `insertAtCursor()`. Rejeté : tag inséré dans la cellule
   active uniquement (UX cassée si la palette est globale).
2. **Bouton « Voix aléatoire » → POST /api/generate/random** (proxy OmniVoice
   POST /auto). Texte d'échantillon par défaut : "Bonjour, ceci est un test
   rapide avec une voix tirée au hasard.". Voix retournée dans `data.filename`
   si pas de champ `voice` (route ne le surface pas encore).
3. **SubtitleClient lazy-init via singleton `_get_subtitle_client()`** dans
   export.py. Si faster-whisper non installé, log warning et continue sans SRT
   (skip propre). Modèle ~800 Mo téléchargé au premier transcribe. Rejeté :
   import au boot (impose ~1,3 Go au démarrage).
4. **Injection owner dans meta.json côté omnistudio** plutôt que patch
   d'OmniVoice. PRD-032. Setdefault sur owner (n'écrase pas), refuse de toucher
   si system: true.
5. **Critère #30 assets sous /omni validé in vivo** : palette tags, bouton
   random et fieldset SRT visibles + interactifs via agent-browser sur l'URL
   Funnel. Pas besoin de Lighthouse pour valider ce critère.

## ARTEFACTS

### Modifiés (cette session)

- `omnistudio/frontend/out/index.html` (3 ajouts : palette, bouton random,
  fieldset SRT, option Auto langue)
- `omnistudio/frontend/out/js/app.js` (import + mountTagPalette à activation
  panel-clean, rebrand vx_* → ov_*)
- `omnistudio/frontend/out/js/auth.js` (rebrand vx_access_token →
  ov_access_token + 2 autres clés)
- `omnistudio/frontend/out/js/tab-generate.js` (handler onRandom, DOM refs)
- `omnistudio/frontend/out/js/tab-export.js` (DOM refs subtitles, toggle
  show/hide format, payload include_subtitles + subtitle_format)
- `omnistudio/routers/voices.py` (helper _inject_owner_in_meta + appels après
  save_custom_voice dans /lock et /clone)
- `omnistudio/routers/export.py` (ExportRequest étend, _get_subtitle_client
  singleton, intégration boucle post-traitement → .srt à côté du WAV/MP3)
- `omnistudio/requirements.txt` (faster-whisper>=1.0.0)

### Créés (cette session)

- `omnistudio/frontend/out/js/tag-palette.js` (module palette 13 tags,
  TARGET_SELECTOR `.vx-tts-edit`, insertion à position curseur)

### Brouillons commit

- `/Users/alex/Claude/.commit-drafts/2026-04-19-001500-omni-phase3bis-frontend.txt`
- `/Users/alex/Claude/.commit-drafts/2026-04-19-130000-omni-phase3ter-srt-owner.txt`

## ERREURS CORRIGEES

1. **Serveur omnistudio ne reload pas les modifs Python** (uptime 14h depuis
   matin) — kill PID 31505 + relance. Mais `python3 server.py` direct → 
   `ModuleNotFoundError: uvicorn`. Cause : pas de venv dans omni-num/, le
   serveur précédent utilisait `voice-num/voxstudio/venv/bin/python3`. Fix
   appliqué : relance via ce venv. **Follow-up à faire** : créer un venv
   dédié à omni-num (sinon dépendance fragile à voxstudio).

2. **agent-browser refs périment après navigation/render** — après `click @e2`
   les refs `@e3, @e4` ne pointent plus aux mêmes éléments. Solution : refresh
   `snapshot -i -s "#panel-X"` après chaque action structurelle.

3. **CSP bloque le chargement axe-core depuis CDN** dans evaluate_script. Fix :
   audit ARIA manuel ciblé sur les 5 ajouts via JS pur (role, aria-label,
   label for, fieldset+legend, options) suffisant car accesslint statique
   avait déjà retourné 0 violation.

4. **Bouton voix aléatoire : `data.voice` absent** dans la réponse
   `/api/generate/random`. La route ne surface que filename + audio_url +
   message. Fix frontend : fallback `data.voice || data.filename`.

## SUITE

1. (au prochain démarrage) `git pull` — pas nécessaire, tout est local
2. Décider l'ordre : accordéon paramètres avancés (~1 h) → vérification UI
   Voice Design Guidé/Expert + 6 catégories (~30 min) → scripts ops + preload
   (~1 h 10) → smoke test multi-user (~2 h) → recréation 4 voix (~15 min) →
   push GitHub (~5 min)
3. Pour la phase 8 multi-user : préparer 2 utilisateurs Keycloak, lancer 2
   sessions concurrentes, vérifier que GET /api/voices retourne uniquement
   les voix system + les voix owner=user.sub (pas celles de l'autre user)
4. Avant push : auditer secrets dans frontend/css/ et data/ (interdiction
   commit secrets), refaire un `git status` complet (data/voices-system/
   doit être versionné, data/models/ non, data/*.db non)
5. Créer un venv dédié `omni-num/.venv` avec
   `pip install -r omnistudio/requirements.txt` pour rendre le projet
   autonome (n'oublier de mettre à jour CLAUDE.md du projet)