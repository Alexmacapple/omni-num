# PRD-MIGRATION-001 : Fork OmniStudio depuis VoxStudio

**Version** : 1.5
**Statut** : Validé (prêt pour Phase 0)
**Priorité** : P1 (projet de création)
**Date** : 2026-04-18
**Auteur** : Alex + Claude
**Source** : Décision produit — étendre l'écosystème à OmniVoice (k2-fsa, 646 langues) en parallèle de VoxQwen
**Prérequis** : voice-num/voxstudio stable en prod (35 PRD DONE), OmniVoice v0.1.2 fonctionnel sur port 8070
**Revues effectuées** :
- connu-inconnu (matrice Rumsfeld) : 3 bloquants critiques identifiés
- avocat-du-diable : 7 préoccupations (3 Critique, 2 Haute, 2 Moyenne) — recoupent les 3 bloquants
- **codex-rescue (3e avis indépendant)** : 5 points nouveaux dont 4 non couverts par les 2 précédentes revues

Les 3 bloquants critiques + 5 points Codex sont tous résolus dans cette v1.5.

---

## Contexte

VoxStudio est une SPA DSFR de production audio batch branchée sur VoxQwen (100/100 Lighthouse, RGAA conforme, 85 % couverture tests, 349 unitaires + 25 E2E + 81 Gherkin).

OmniVoice offre : 1 modèle ~2,45 Go, 646 langues, 13 marqueurs non-verbaux, Voice Design par 6 catégories, Voice Clone avec Whisper intégré, paramètres avancés du moteur de diffusion.

Ce PRD ouvre `omni-num`, une SPA jumelle de VoxStudio branchée sur OmniVoice qui exploite pleinement les capacités OmniVoice non présentes dans VoxQwen. Le résultat n'est pas un simple clone mais une évolution : tags émotionnels, 22 accents et dialectes, sous-titres SRT automatiques, paramètres avancés pour power users.

**Principe directeur** : **zéro dette identifiée héritée de voxstudio** + **exploitation complète des 25 routes OmniVoice** + **architecture validée par stub avant code complet** (Phase 0bis).

### Ce qui existe

- `voice-num/voxstudio/` : front DSFR + API workflow LangGraph, port 7860, 43 endpoints, 349+25+81 tests, 16 scripts ops, 9 docs
- `voice-num/VoxQwen/` : API TTS Qwen3-TTS, port 8060, 39 routes, **4 voix custom existantes** (alexandra, frederique, stephanie, vieux)
- `voice-num/OmniVoice/` : API TTS k2-fsa, port 8070, **25 routes**, 646 langues
- Écosystème OmniVoice : notebook Colab + `google-colab/app.py` (31 Ko, Gradio) + `google-colab/subtitle.py` (26 Ko, faster-whisper)
- Keycloak (realm `harmonia`, port 8082), Tailscale Funnel

### Ce qui est absent

- Aucun projet ne consomme OmniVoice
- Bibliothèque vide, pas de voix préréglées
- Pas de mapping FR → EN pour Voice Design
- Pas d'exposition HTTPS publique d'OmniVoice
- voice-num porte 3 dettes techniques documentées
- Les 13 tags émotionnels et les 22 accents/dialectes d'OmniVoice ne sont exploités nulle part
- Pas de pipeline sous-titres SRT accessibles dans l'écosystème

---

## Problème

Offrir un second site de production audio strictement supérieur à VoxStudio sur 10 axes : parcours 6 onglets identique + 3 dettes corrigées + 7 enrichissements OmniVoice. Contraintes :

- VoxStudio en prod ne doit pas être touché
- Le site doit passer en 5G via port 443
- Méthode : **TDD strict** — docs d'abord, tests rouges avant code
- **Architecture validée par stub FastAPI avant code applicatif** (Phase 0bis)
- Parité tests voxstudio (349 + 25 + 81) + nouveaux tests pour les 10 capacités ajoutées
- Couverture 25/25 routes OmniVoice

---

## Écarts OmniVoice vs VoxQwen — opportunités d'enrichissement

| Écart | VoxQwen | OmniVoice | Action omnistudio |
|-------|---------|-----------|-------------------|
| Voix préréglées | 9 natives (Vivian, Serena...) | Aucune | Pré-générer **6 voix système versionnées** |
| Voice Design | Accepte le français | Anglais uniquement | UI Guidé + Expert, **6 catégories** |
| Voice Clone | Clone direct | Sans `ref_text` → Whisper (~60 s) | Bouton « transcrire » via `POST /transcribe` |
| Tags émotionnels | Non supportés | **13 tags** | **Palette de boutons DSFR insérant au curseur** |
| Voix aléatoire | Non | `POST /auto` | Bouton « voix aléatoire » en onglet 5 |
| Paramètres avancés | model 1.7B/0.6B | 11 paramètres de diffusion | **Mode « paramètres avancés » collapsed** |
| Stockage voix | `prompt.pt` | `reference.wav` | Adapter format ZIP |
| Langues | 10 | **646** + `"Auto"` | Shortlist 10 + recherche + **auto-détection** |
| Accents | Non | **10 accents anglais, 12 dialectes chinois** | Selects conditionnels |
| Sous-titres | Non | Whisper intégré + faster-whisper dans Colab | **Export SRT automatique** (4 formats + chunking) |

---

## Décisions validées (17 choix)

### 1 à 3 — voir annexe G (inchangé)

- **1. Keycloak** : nouveau client `omnistudio`
- **2. Exposition 5G** : Funnel path-based sur 443, préfixe `/omni`
- **3. Dépôt** : `github.com/Alexmacapple/omni-num`

### 4. Catalogue voix système — versionné dans le dépôt (v1.4)

Les 6 voix (Marianne, Léa, Sophie, Jean, Paul, Thomas) sont générées une seule fois puis les 6 paires `{meta.json, reference.wav}` sont commitées dans `omni-num/data/voices-system/` (~18 Mo). Seed = `cp` déterministe. Reproductibilité garantie.

### 5. UI Voice Design (deux modes)

Onglets DSFR `fr-tabs` : Guidé + Expert. Wording annexe B.

### 6. Emplacement d'OmniVoice + migration voix voice-num (v1.4)

OmniVoice déplacé dans `omni-num/OmniVoice/`. 4 voix voice-num (alexandra, frederique, stephanie, vieux) recréées manuellement après Phase 8 (~15 min).

### 7. Isolation voix par owner (traite PRD-032)

Voir v1.2 (annexe G).

### 8. Assignation multi-voix par étape — tag explicite uniquement (v1.4)

**Parser explicite uniquement** `[voice:X]`. Auto-segmentation reportée à PRD-EVOLUTION-003. Cas limites couverts par 20 tests (voir Annexe M).

### 9. Anti-cascade session stale (traite PRD-034)

Voir v1.2 (annexe F).

### 10. VOICE_TEMPLATES (12) ≠ voix système (6)

12 presets de design EN vs 6 voix système versionnées.

### 11-17 — Enrichissements OmniVoice (v1.3)

- **11. Tags émotionnels** : palette 13 boutons DSFR (GET /tags)
- **12. Voice Design 6 catégories** : Genre, Age, Pitch, Style, English Accent (10), Chinese Dialect (12)
- **13. Auto-détection langue** : `"Auto"` en tête
- **14. Paramètres avancés** : accordéon 11 paramètres
- **15. Voix aléatoire** : POST /auto
- **16. Sous-titres SRT** : faster-whisper, 4 formats + chunking (max 3 lignes, max 8 s)
- **17. Préchargement modèle** : POST /models/preload dans start.sh

---

## Architecture cible

### Structure du projet

```
omni-num/
├── CLAUDE.md, AGENTS.md, README.md, RUNBOOK-DEPLOYMENT.md
├── .gitignore
├── PRD/
│   ├── PRD-MIGRATION-001-FORK-OMNISTUDIO.md
│   └── gherkin/
├── documentation/md/                      # 10 docs + ARCHITECTURE-LANGGRAPH-OMNI.md
├── omnistudio/
│   ├── server.py                          # FastAPI(root_path="/omni")
│   ├── config.py
│   ├── dependencies.py
│   ├── auth.py
│   ├── core/
│   │   ├── voxqwen_client.py, omnivoice_client.py
│   │   ├── subtitle_client.py             # faster-whisper + 4 formats SRT + chunking
│   │   ├── voice_profiles.py              # 12 templates EN
│   │   └── ...
│   ├── routers/
│   ├── frontend/out/
│   │   ├── index.html                     # <base href="/omni/"> pour assets relatifs sous Funnel
│   │   ├── css/app.css                    # ov-*
│   │   └── js/                            # 15 modules + tag-palette.js
│   └── graph/                             # State multi-voix : extension du graphe voxstudio
├── OmniVoice/                             # dépôt autonome, gitignored
├── scripts/
│   ├── start.sh, stop.sh, test-smoke.sh, build-frontend.sh
│   ├── seed-default-voices.sh             # cp versionné idempotent
│   ├── run-forever.sh
│   ├── monitor.sh                         # + check memory_pressure (macOS)
│   ├── backup-db.sh, restore-db.sh, install-cron.sh, test-supervisor.sh
│   ├── verify-assets-prefix.sh            # NOUVEAU Phase 0bis : audit assets sous /omni
│   └── batch-*.py, generate-voix.py
├── tests/                                 # 349 + 14 nouveaux fichiers + e2e
├── data/
│   ├── default_voices.json
│   ├── voices-system/                     # VERSIONNÉ : 6 voix système
│   ├── models/                            # gitignored : cache faster-whisper
│   └── omnistudio_checkpoint.db           # gitignored
└── logs/
```

### Ports et services

| Processus | Port | Rôle | Exposition 5G |
|-----------|------|------|----------------|
| Keycloak | 8082 | Auth JWT | Interne |
| OmniVoice | 8070 | API TTS k2-fsa | Interne |
| omnistudio | 7870 | Front + API workflow | Funnel 443 `/omni/` |

### Matrice de différenciation voxstudio ↔ omnistudio (10 axes)

Inchangée v1.4.

---

## Couverture des 25 routes OmniVoice

Inchangé depuis v1.3. 25/25 routes exploitées.

---

## Plan d'exécution (TDD strict, **12 phases**)

### Phase 0 — Préparation (~10 min)

1. `mv voice-num/OmniVoice omni-num/OmniVoice`
2. `mkdir -p omni-num/{omnistudio,scripts,data/voices-system,data/models,logs,documentation/md,tests,PRD/gherkin}`
3. `cd omni-num && git init && git remote add origin git@github.com:Alexmacapple/omni-num.git`
4. Créer `.gitignore` (avec exception pour `data/voices-system/`)
5. Mettre à jour `voice-num/CLAUDE.md` et `voice-num/todo.md`

### Phase 0bis — Architecture check (~2 h, **nouvelle en v1.5, résolution point Codex #1**)

**Objectif** : valider l'architecture de déploiement avant d'écrire une ligne de code applicatif. Économise 3-5 h de debug en Phase 3-4.

**Étapes** :

1. **Stub FastAPI minimal** (~30 min)
   - Créer `omnistudio/stub_server.py` : app FastAPI avec `root_path="/omni"`, une route `GET /` qui retourne `{"ok": True}`, un mount statique sur `frontend/out-stub/` avec juste un `index.html` + `css/test.css` + `js/test.js`
   - Lancer sur port 7870

2. **Audit des chemins statiques** (~30 min)
   - Script `scripts/verify-assets-prefix.sh` qui grep dans `voxstudio/frontend/out/` : chemins absolus `/css/`, `/js/`, `/dsfr/`, `/api/` dans HTML et JS
   - Inventaire : combien d'URL absolues à préfixer ? (estimation ~50-80 occurrences)
   - Décider la stratégie :
     - **Option A** : `<base href="/omni/">` dans `<head>` de `index.html` → tous les chemins relatifs résolus automatiquement
     - **Option B** : préfixe à la compilation via esbuild define (`OMNISTUDIO_PREFIX=/omni`)
     - **Option C** : chemins dynamiques en runtime (`${window.location.pathname.startsWith('/omni') ? '/omni' : ''}/api/...`)
   - **Recommandation Codex** : Option A (base href) si l'app ne fait jamais de navigation hors `/omni/`. Simple, zéro code modifié.

3. **Keycloak redirects** (~30 min)
   - Créer le client Keycloak `omnistudio` avec `redirectUris` = `http://localhost:7870/*` et `https://mac-studio-alex.tail0fc408.ts.net/omni/*`
   - Tester flux OAuth Authorization Code sur le stub avec les deux URLs
   - Vérifier que le callback `/omni/auth/callback` est bien matché

4. **Funnel path-based** (~20 min)
   - `tailscale funnel --https=443 --set-path=/omni http://localhost:7870`
   - `curl https://mac-studio-alex.tail0fc408.ts.net/omni/` depuis un autre appareil en 5G
   - Vérifier : assets statiques 200 OK, login Keycloak → callback fonctionnel

5. **Documentation** (~10 min)
   - `RUNBOOK-DEPLOYMENT.md` : stratégie assets retenue (A/B/C), commandes Funnel, troubleshooting

**Critères de sortie Phase 0bis** :

- [ ] Stub FastAPI répond sur `http://localhost:7870/` ET `https://mac-studio-alex.tail0fc408.ts.net/omni/`
- [ ] Assets statiques (CSS, JS, images) servis correctement sous `/omni/`
- [ ] Login Keycloak fonctionnel via les deux URLs
- [ ] `scripts/verify-assets-prefix.sh` inventorie les chemins à corriger
- [ ] Décision assets documentée dans `RUNBOOK-DEPLOYMENT.md`

Si un critère échoue, **ne pas passer à Phase 1**. Trouver le fix architectural avant d'écrire du code applicatif.

### Phase 1 — Documentation (~3 h 30, v1.5 + 30 min LangGraph)

Inchangé v1.3 + :

- **Nouvelle doc `documentation/md/ARCHITECTURE-LANGGRAPH-OMNI.md`** (résolution point Codex #4) : décision explicite sur le branchement OmniVoice dans LangGraph.
  - Option A : refactor du graphe voxstudio pour supporter multi-voix natif
  - Option B : extension du graphe existant, nouveau `subgraphs/multi_voice_loop.py` + adapter `generate_node.py`
  - **Recommandation** : Option B (extension) → moins invasif, réutilise 80 % du code LangGraph existant
  - Diagrammes Mermaid avant/après
  - Budget : 30 min

### Phase 2 — Tests rouges (~7 h 30, v1.5 + tests XSS)

Inchangé v1.3/v1.4 + :

- **`test_tag_explicite.py` enrichi** (résolution point Codex #3) : 20 cas limites (voir Annexe M)
  - Multilignes : `"Hello\n[voice:Jean]\nWorld"`
  - Tag orphelin en fin : `"Texte final [voice:Marianne]"`
  - Tag au tout début : `"[voice:Paul] Bonjour"`
  - Tags consécutifs : `"[voice:A][voice:B] Texte"`
  - Voix inexistante : `"[voice:ZeusPersonne] Texte"` → 422 avec message explicite
  - **Injection XSS** : `"[voice:Jean<script>alert(1)</script>]"` → nom voix rejeté (regex stricte `[a-zA-Z][a-zA-Z0-9_-]{2,49}`)
  - Échappement : `"[voice:Jean]"` littéral dans un contenu utilisateur → texte brut, pas interprété
  - 13 autres cas limites (voir Annexe M)
- **`test_assets_prefix.py`** (nouveau, ~8 tests) : vérifie qu'aucun asset JS/CSS du build ne contient un chemin absolu `/css/`, `/js/` non préfixé

### Phase 3 — Code parité + dettes (~4 h 30)

Inchangé v1.4.

### Phase 3bis — Enrichissements OmniVoice (~7 h 30)

Inchangé v1.3.

### Phase 3ter — Sous-titres SRT (~5 h, v1.5 + chunking)

Inchangé v1.3 + :

- **Spec chunking SRT** (résolution point Codex #5) : ~30 min
  - Dans `core/subtitle_client.py`, fonction `chunk_subtitles(segments, max_lines=3, max_duration_s=8)`
  - Découpe les longs sous-titres Whisper en chunks respectant les contraintes standards
  - Test `test_subtitles.py::test_chunking_long_audio` : génère un audio 10 min, vérifie aucun chunk > 8 s, aucun > 3 lignes
  - Documentation dans `TAGS-SRT-SUBTITLES.md` : limites par format (Shorts 1 ligne / 3 s, Multiline 2 lignes / 6 s, Standard 3 lignes / 8 s)

### Phase 4 — Ajustements post-code (~2 h 30)

Inchangé v1.3 + `verify-assets-prefix.sh` relancé sur le build final.

### Phase 5 — Seed catalogue (~45 min)

Inchangé v1.4.

### Phase 6 — Ops : Keycloak + Funnel + preload (~45 min)

Inchangé v1.3 + critère #29 amendé : `memory_pressure < 0.5` (résolution point Codex #2).

### Phase 7 — Commit initial et push (~15 min)

Inchangé v1.3.

### Phase 8 — Smoke test bout-en-bout (~3 h, v1.5 + tests mémoire)

Inchangé v1.3 + :

- Deux POST simultanés `/design` + `/transcribe` → vérifier pas de timeout (résolution point Codex #2)
- Test audio 10 min avec sous-titres cochés → chunks correctement découpés
- Check `monitor.sh` : `memory_pressure < 0.5` tout le long

---

## Critères de validation (30 critères)

Inchangé v1.4 + :

| # | Critère | Cible |
|---|---------|-------|
| **29** (amendé) | **memory_pressure macOS < 0.5** | Avec omnistudio + OmniVoice + faster-whisper simultanés, via `monitor.sh` |
| **30** (nouveau) | **Assets statiques sous `/omni`** | 100 % des requêtes assets JS/CSS/img retournent 200 OK via Funnel |

Les critères 1-28 restent inchangés.

---

## Traçabilité voxstudio → omnistudio (35/35 PRD)

Inchangé v1.4. + Note : PRD-EVOLUTION-003 (auto-segmentation dialogue) ajouté au backlog.

---

## Risques et mitigations (**20 risques**, v1.5 + 2)

| # | Risque | Impact | Mitigation |
|---|--------|--------|------------|
| 1 (enrichi v1.5) | Assets frontend absolus cassent sous `/omni` | Bloquant | **Phase 0bis audit exhaustif + stub test + décision `<base href>` ou build prefix** |
| 2 | redirectUris Keycloak | Login boucle | **Test en Phase 0bis localhost + Funnel avant Phase 1** |
| 3 | JWT audience mismatch | 401 | Test dédié |
| 4 | Seed échoue | Démarrage dégradé | Seed = `cp` idempotent |
| 5 | Double démarrage OmniVoice | Port 8070 pris | start.sh vérifie avant lancement |
| 6 | Funnel path-based indisponible | Plan B | **Vérifier `tailscale funnel status` en Phase 0bis** |
| 7 | Migration 4 voix voice-num | 15 min manuel | Documenté dans CLAUDE.md |
| 8 | Tests TDD explosent | Phase 2 dérape | Prioriser core + auth + ownership |
| 9 | Multi-voix complexifie LangGraph | Refactor cascade | **Décision Option B extension documentée Phase 1** |
| 10 | Anti-cascade masque bugs | Faux positifs | Seuil 3 erreurs |
| 11 | Auth hybride + ownership | Contournement | 2 tests dédiés |
| 12 | faster-whisper ~1,3 Go | Setup initial lourd | Télécharger au premier boot, progress |
| 13 | Whisper < 646 langues | Sous-titres manquants | Skip propre + log info |
| 14 | Tags mal placés | Audio bizarre | Doc claire + tests de placement |
| 15 | Paramètres avancés mal utilisés | Audio cassé | Défauts safe, info-bulles, tests limites |
| 16 | Accents/dialectes hors bonne langue | Utilisateur confus | Selects grisés + info-bulle |
| 17 | Préchargement bloque start.sh | UX démarrage dégradée | Preload en arrière-plan |
| 18 (amendé v1.5) | Charge mémoire cumulée | OOM macOS | **`memory_pressure < 0.5`, test simultanéité Phase 8** |
| **19 (nouveau v1.5)** | **Parser multi-voix : injection XSS dans nom de voix** | **Vulnérabilité sécurité** | **Regex stricte `[a-zA-Z][a-zA-Z0-9_-]{2,49}` + 20 tests cas limites** |
| **20 (nouveau v1.5)** | **Chunking SRT manquant** | **Subtitles illisibles sur audios longs** | **`chunk_subtitles()` avec contraintes max 3 lignes / max 8 s, test audio 10 min** |

---

## Estimation

| Phase | Best-case | Planifié (buffer 40 %) |
|-------|-----------|------------------------|
| 0 — Préparation | 10 min | 15 min |
| **0bis — Architecture check (nouveau)** | **2 h** | **2 h 45** |
| 1 — Documentation (+ LangGraph) | 3 h 30 | 5 h |
| 2 — Tests rouges (+ XSS + assets) | 7 h 30 | 10 h 30 |
| 3 — Code parité + dettes | 4 h 30 | 6 h |
| 3bis — Enrichissements OmniVoice | 7 h 30 | 10 h 30 |
| 3ter — Sous-titres SRT (+ chunking) | 5 h | 7 h |
| 4 — Ajustements | 2 h 30 | 3 h 30 |
| 5 — Seed catalogue | 45 min | 1 h |
| 6 — Ops Keycloak + Funnel + preload | 45 min | 1 h |
| 7 — Commit + push | 15 min | 30 min |
| 8 — Smoke test + 5G + multi-user + mémoire | 3 h | 4 h |

**Total : ~37 h best-case / ~52 h planifié** (buffer 40 %).

**Évolution** : 33 h (v1.3/v1.4 best-case) → 37 h (v1.5 best-case). +4 h pour Phase 0bis (2 h) + Phase 1 LangGraph (30 min) + Phase 2 tests XSS et assets (1 h) + Phase 3ter chunking (30 min).

**Bénéfice v1.5** : les 2 h de Phase 0bis économisent **3-5 h** de debug en Phase 3-4 (assets absolus cassés sous `/omni`). ROI positif. Les tests XSS sécurisent le parser dès les tests rouges. Chunking SRT évite une UX dégradée sur audios longs.

---

## Annexes

### A. Catalogue des 6 voix système

Inchangé v1.4.

### B. Wording UI

Inchangé v1.3.

### C. Routes OmniVoice (25/25)

Inchangé v1.3.

### D. Diff schéma `meta.json`

Inchangé v1.2.

### E. Schéma LangGraph State — multi-voix via tag explicite

Inchangé v1.4 (parser Python en Annexe M enrichi).

### F. 3 intercepteurs anti-cascade

Inchangé v1.2.

### G. Décisions 1 à 10 détaillées

Voir v1.2 pour 1-3, 5, 7, 9, 10. Décisions 4, 6, 8 amendées en v1.4.

### H. 13 tags émotionnels

Inchangé v1.3.

### I. Mapping Chinese Dialect → caractères chinois

Inchangé v1.3.

### J. Paramètres avancés

Inchangé v1.3.

### K. Formats SRT + chunking (amendé v1.5)

Inchangé v1.3 + spec chunking :

| Format | Max lignes | Max durée | Max chars/ligne |
|--------|------------|-----------|-----------------|
| Standard | 3 | 8 s | 42 |
| Word (karaoke) | 1 | 2 s | — (1 mot) |
| Shorts | 1 | 3 s | 30 |
| Multiline | 2 | 6 s | 38 |

Fonction `chunk_subtitles(segments, format) -> List[SRTBlock]` applique les contraintes et découpe les segments longs de Whisper.

### L. 4 voix voice-num à recréer manuellement

Inchangé v1.4.

### M. Spec parser multi-voix — matrice 20 cas limites (nouveau v1.5)

**Regex de validation du nom de voix** : `^[a-zA-Z][a-zA-Z0-9_-]{2,49}$`

- Commence par une lettre
- 3 à 50 caractères
- Alphanumériques + `_` et `-` uniquement
- Pas d'espaces, pas de ponctuation, pas d'entités HTML

**Comportement si tag invalide** : conserver le texte littéral tel quel (pas d'interprétation), log warning backend.

**Comportement si voix inexistante** (regex valide mais pas dans `GET /voices`) : `POST /assign` retourne 422 avec message `{"detail": "Voix 'ZeusPersonne' introuvable. Voix disponibles : Marianne, Lea, Sophie, Jean, Paul, Thomas, ..."}`.

**Matrice des 20 cas limites** couverts par `test_tag_explicite.py` :

| # | Entrée | Résultat attendu |
|---|--------|------------------|
| 1 | `"Hello world"` (pas de tag) | 1 segment avec voix par défaut |
| 2 | `"[voice:Marianne] Hello"` | 1 segment Marianne |
| 3 | `"Hello [voice:Jean] World"` | 2 segments (défaut, Jean) |
| 4 | `"[voice:A] Texte [voice:B] Suite"` | 2 segments (A, B) |
| 5 | `"[voice:A][voice:B] Texte"` | 1 segment B (A est écrasé) |
| 6 | `"Texte final [voice:Marianne]"` | 1 segment défaut + 1 segment vide Marianne → fusion : 1 segment défaut |
| 7 | `"Hello\n[voice:Jean]\nWorld"` | 2 segments (défaut "Hello\n", Jean "\nWorld") |
| 8 | `"[voice:]"` (nom vide) | Tag invalide → texte littéral |
| 9 | `"[voice:AB]"` (trop court, < 3 chars) | Tag invalide → texte littéral |
| 10 | `"[voice:" + "a"*51 + "]"` (trop long) | Tag invalide → texte littéral |
| 11 | `"[voice:Jean Doe]"` (espace) | Tag invalide → texte littéral |
| 12 | `"[voice:Jean&lt;script&gt;]"` | Tag invalide → texte littéral (sécurité XSS) |
| 13 | `"[voice:Jean<script>]"` | Tag invalide → texte littéral (regex rejette `<`) |
| 14 | `"[voice:Jean'OR 1=1]"` | Tag invalide → texte littéral (regex rejette `'`) |
| 15 | `"[voice:ZeusPersonne] Texte"` | Regex OK mais voix inexistante → 422 côté `/assign` |
| 16 | `"[voice:123Paul]"` (commence par chiffre) | Tag invalide → texte littéral |
| 17 | `"[voice:Jean-Paul]"` | Tag valide (tiret autorisé) → segment Jean-Paul |
| 18 | `"[voice:Jean_Paul]"` | Tag valide (underscore autorisé) |
| 19 | `"[VOICE:Jean]"` (majuscule du mot-clé) | Pas reconnu comme tag → texte littéral (syntaxe `[voice:X]` seulement) |
| 20 | `"\[voice:Jean\] littéral"` (échappement) | Tag invalide → texte littéral (pas de magie pour l'échappement, l'utilisateur tape vraiment `\[voice:Jean\]` qui ne matche pas) |

### N. Phase 0bis — Matrice d'audit assets (nouveau v1.5)

Liste des chemins à auditer dans `voxstudio/frontend/out/` puis `omnistudio/frontend/out/` :

| Élément HTML | Attribut | Pattern à auditer |
|--------------|----------|-------------------|
| `<link>` | `href` | `/css/`, `/dsfr/` |
| `<script>` | `src` | `/js/` |
| `<img>` | `src` | `/images/`, `/favicon` |
| `<a>` internes | `href` | `#tab1`, `/api/`, `/auth/` |
| `<form>` | `action` | `/api/`, `/auth/` |
| JS `fetch()` | 1er argument | `/api/` |
| JS `new URL()` | 1er argument | Chemins absolus |
| CSS `url()` | Propriété | `/images/`, `/fonts/` |

Script `scripts/verify-assets-prefix.sh` parcourt `frontend/out/` et liste tous les chemins absolus. La décision `<base href="/omni/">` dans le `<head>` résout automatiquement 90 % des cas. Les 10 % restants (fetch dynamiques, new URL) sont corrigés à la main.

---

## Changelog du PRD

- **v1.5 (2026-04-18)** : **Intégration des 5 points Codex (3e avis indépendant)**. (1) Nouvelle **Phase 0bis — Architecture check (2 h)** : stub FastAPI + audit assets sous `root_path="/omni"` + Keycloak redirects + Funnel path-based. Économise 3-5 h debug Phase 3-4. (2) Critère #29 amendé : `memory_pressure < 0.5` (macOS native) au lieu de RAM < 80 %. (3) Nouvelle **Annexe M** : matrice 20 cas limites parser multi-voix dont injection XSS (regex `^[a-zA-Z][a-zA-Z0-9_-]{2,49}$`). Nouveau risque **#19** sécurité parser. (4) Nouvelle doc `ARCHITECTURE-LANGGRAPH-OMNI.md` en Phase 1 : décision Option B extension graphe. (5) Spec chunking SRT en Phase 3ter : max 3 lignes / max 8 s, par format. Nouveau risque **#20** chunking. Nouveaux tests : `test_tag_explicite.py` enrichi (20 cas), `test_assets_prefix.py`. Nouveau script `verify-assets-prefix.sh`. Nouveau RUNBOOK `RUNBOOK-DEPLOYMENT.md`. 20 risques (vs 18), 30 critères (vs 29). Estimation ~33 h → **~37 h best-case / ~52 h planifié (buffer 40 %)**. ROI positif : +4 h investis économisent 3-5 h de debug et ferment un trou de sécurité XSS.
- **v1.4 (2026-04-18)** : 3 bloquants critiques résolus (voix versionnées, tag explicite, 4 voix manuelles), 4 ajustements Haute/Moyenne, statut Validé, ~33 h.
- **v1.3 (2026-04-18)** : 25/25 routes OmniVoice + 7 enrichissements Colab, ~33 h.
- **v1.2 (2026-04-18)** : Zéro dette, PRD-032/033/034 traités, ~19 h.
- **v1.1 (2026-04-18)** : TDD + multi-user, ~14 h.
- **v1.0 (2026-04-18)** : 6 décisions, ~3 h.
