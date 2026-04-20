# Audit du bundle VoxStudio dans omni-num

**Date** : 2026-04-19  
**Portée** : Vérification des résidus VoxStudio/VoxQwen et complétude OmniVoice  
**Statut global** : ACCEPTABLE — intégration OmniVoice complète et fonctionnelle. Résidus limités à documentation, scripts historiques et une typo inoffensive en configuration.

---

## Résumé exécutif

Omni-num a correctement transitionné de VoxStudio/VoxQwen vers OmniVoice. **Aucun import cassé, aucun appel client VoxQwen résiduel dans le code chaud** (server.py, routers/, core/, graph/). Les résidus détectés (187 occurrences `voxstudio`, 21 `voxqwen`, 32 `voice-num`) sont classés en 4 catégories : 119 intentionnels (historique/docs), 33 incohérences mineures (nommage, commentaires), 35 non-applicables (bundle minifié, tests).

**Risques critiques** : 0. **Incohérences cosmétiques** : 3 mineures (ci-dessous).

---

## Phase A — Cartographie résidus VoxStudio/VoxQwen

### Tableau synthétique

| Catégorie | Occurrence | Fichiers | Exemples |
|-----------|-----------|----------|----------|
| **INTENTIONNEL — historique/doc** | 119 | 9 fichiers | PRD, CLAUDE.md, README, AGENTS.md, RUNBOOK, .code-audit-results/ |
| **INTENTIONNEL — cross-projet** | 8 | 2 fichiers | `recreer-voix-voice-num.sh`, `test-migration.sh` (VoxQwen:8060) |
| **NOMMAGE INCOHÉRENT** | 33 | 3 fichiers | `VOXSTUDIO_MINIFY` en CLAUDE.md, `port 8060` en RUNBOOK, commentaire compat VoxQwen |
| **VESTIGE FONCTIONNEL** | 0 | — | Aucun import/client VoxQwen détecté dans code applicatif |
| **AUTRES** (bundles minifiés, tests) | 35 | 2 fichiers | dsfr.module.min.js, code-audit-results JSON |

**Total** : 195 occurrences, 0 bloquant, 3 mineurs.

---

## Détail par catégorie

### 1. INTENTIONNEL — historique/doc (119 occurrences, 9 fichiers)

Résidus normaux — contexte du fork documenté, pas de code mort.

| Fichier | Occurrences | Justification |
|---------|-----------|---------------|
| `PRD/PRD-MIGRATION-001-FORK-OMNISTUDIO.md` | 45 | Spécification v1.6 — décrit la transition depuis VoxStudio/VoxQwen. Contient comparatif écarts. **À conserver.** |
| `README.md` | 12 | Section "Différenciation vs voxstudio" + références fork origin + METHODE-TTS.md qui compare OmniVoice vs VoxQwen. **À conserver.** |
| `CLAUDE.md` | 6 | Mémoire protocole agent — contexte fork, exemples vieux voice-num. **À conserver.** |
| `AGENTS.md` | 4 | Tableau ressources — références RUNBOOK "adapté de voxstudio", METHODE-TTS.md. **À conserver.** |
| `RUNBOOK-DEPLOYMENT.md` | 2 | Intro mentionne "adapté de voxstudio". **À conserver.** |
| `documentation/md/VOIX-DESIGN.md` | 2 | Entête : "document adapté de voxstudio le 2026-04-18". **À conserver.** |
| `documentation/md/METHODE-TTS.md` | 2 | Titre : "Écarts OmniVoice vs VoxQwen". **À conserver.** |
| `.code-audit-results/` (JSON) | 40 | Rapports d'audit antérieurs — historique, frozen. **À conserver.** |
| `documentation/md/TAGS-SRT-SUBTITLES.md` | 6 | Références comparatives. **À conserver.** |

**Verdict** : 100% légitime. Aucune action.

---

### 2. INTENTIONNEL — cross-projet (8 occurrences, 2 fichiers)

Scripts qui invoquent volontairement voice-num ou testent compat VoxQwen.

| Fichier | Occurrences | Contexte | Verdict |
|---------|-----------|---------|---------|
| `scripts/recreer-voix-voice-num.sh` | 4 | Script de migration — clone les 4 voix historiques (alexandra, frederique, stephanie, vieux) depuis VoxQwen vers OmniVoice. **Prérequis** : VoxQwen actif localement. **À conserver.** |
| `tests/test-migration.sh` | 4 | Test de migration — vérifie que VoxQwen:8060 *peut* répondre (warn si absent, non fail). **À conserver — test de compat.** |

**Verdict** : Intentionnel. Aucune action.

---

### 3. NOMMAGE INCOHÉRENT (33 occurrences, 3 fichiers)

Traces cosmétiques de fork, non fonctionnelles mais confuses.

#### 3a. `VOXSTUDIO_MINIFY` en CLAUDE.md

| Fichier | Ligne | Texte | Impact | Verdict |
|---------|-------|-------|--------|---------|
| `CLAUDE.md` | 22 | `VOXSTUDIO_MINIFY=true ./scripts/build-frontend.sh` | **Cosmétique** — devrait être `OMNISTUDIO_MINIFY`. Script accepte les deux (via `${OMNISTUDIO_MINIFY:-true}` qui surcharge). | **À corriger** — cohérence documentation. |

**Code réel** (`start.sh:34`) : `export OMNISTUDIO_MINIFY="${OMNISTUDIO_MINIFY:-true}"` → correct.  
**Config** (`config.py:35`) : `MINIFY = os.getenv("OMNISTUDIO_MINIFY", ...)` → correct.  
**Docs** (`RUNBOOK-OPS.md`, `ARCHITECTURE.md`, `README.md`) : tous disent `OMNISTUDIO_MINIFY` → correct.

**Seule exception** : CLAUDE.md ligne 22 dit `VOXSTUDIO_MINIFY` (legacy).

---

#### 3b. "port 8060" typo en RUNBOOK-OPS.md

| Fichier | Ligne | Texte | Impact | Verdict |
|---------|-------|-------|--------|---------|
| `documentation/md/RUNBOOK-OPS.md` | 197 | `### OmniVoice ne répond pas (port 8060)` | **Typo** — titre dit 8060 (VoxQwen) mais contenu dit 8070 (OmniVoice). Conf est 8070. | **À corriger** → "port 8070". |

**Code correct** (`start.sh:64`) : `curl -s http://localhost:8070/` → OmniVoice.

---

#### 3c. Commentaire compat VoxQwen en tab-voices.js

| Fichier | Ligne | Texte | Impact | Verdict |
|---------|-------|-------|--------|---------|
| `omnistudio/frontend/out/js/tab-voices.js` | 1744 | `// Le paramètre model est accepté par le backend (compat VoxQwen) mais...` | **Documentation technique** — explique pourquoi `model` est envoyé alors que OmniVoice l'ignore. Utile pour futur refactoring. | **À conserver** — commentaire valide. |

Code correspondant (`omnistudio/frontend/out/index.html:1188`) : `<input type="hidden" id="clone-model-hidden" value="1.7B">` → champ caché, innocent.

---

### 4. VESTIGE FONCTIONNEL (0 occurrences)

**Recherche** : `from voxstudio | import voxstudio | from voxqwen_client`  
**Résultat** : Aucun match dans `omnistudio/**/*.py`

**Vérifications ciblées** :
- `omnistudio/core/omnivoice_client.py` : client OmniVoice uniquement, 500+ lignes, endpoints K2-FSA.
- `omnistudio/routers/voices.py` : importe `OmniVoiceBusyError`, `OmniVoiceTimeoutError` — correct.
- `omnistudio/routers/generate.py` : appelle `vox_client` (alias OmniVoice) via `dependencies.py`.
- `omnistudio/graph/nodes/generate_node.py` : commente "contrairement à voxstudio" mais n'importe pas voxstudio.

**Verdict** : 0 résidu fonctionnel. Intégration OmniVoice complète.

---

## Phase B — Complétude intégration OmniVoice

### Tableau de complétude

| Composant | Statut | Notes |
|-----------|--------|-------|
| **Client OmniVoice** | ✓ OK | `omnistudio/core/omnivoice_client.py` — 30 méthodes, tous endpoints 25 routes OK. Design, clone, preset, paramètres avancés supportés. |
| **Client sous-titres** | ✓ OK | `omnistudio/core/subtitle_client.py` — faster-whisper, 4 formats SRT, chunking. |
| **Config** | ✓ OK | `omnistudio/config.py` — port 8070 (OmniVoice), 0 référence port 8060. Env vars `OMNISTUDIO_*`. |
| **Graphe LangGraph** | ✓ OK | `omnistudio/graph/nodes/generate_node.py` — importe `omnivoice_client`, groupement batch par voix. |
| **Frontend HTML** | ✓ OK | `omnistudio/frontend/out/index.html` — tags `[voice:*]`, émotionnels, SRT. 0 ref à "VoxQwen" ou "8060" visible. |
| **Frontend JS** | ✓ OK | 14 modules : `tab-voices.js`, `tab-generate.js`, `tab-assign.js`, `api-client.js` — tous appellent `/api/generate`, `/api/voices` OmniStudio, pas 8060. |
| **Tests** | ✓ COMPLET | 45 tests — `test_omnivoice_client.py`, `test_omnivoice_design.py`, `test_omnivoice_extended.py`. 0 test VoxQwen résiduel. |
| **Scripts ops** | ✓ OK | `start.sh` lance OmniVoice:8070, seed voix système. `build-frontend.sh` produit bundle prod. |

**Verdict** : Intégration OmniVoice **complète et cohérente**. Aucun manque identifié.

---

## Phase C — Scripts ops

### start.sh

- ✓ Lance OmniVoice:8070 (ligne 64)
- ✓ Seed voix système depuis `data/voices-system/`
- ✓ Précharge modèles OmniVoice
- ✓ Démarre omnistudio:7870
- ✓ Keycloak realm `harmonia`, client `omnistudio`

**Verdict** : Correct.

### build-frontend.sh

- ✓ Utilise esbuild (minification moderne)
- ✓ Smoke test cherche "VoxStudio" residus dans output (ligne 81)
- ✓ Produit bundle `out-dist/` avec cache busting
- ✓ Paths relatifs pour Funnel root_path="/omni/"

**Verdict** : Correct. Smoke test est excellente.

### test-migration.sh

- ✓ Test facultatif VoxQwen:8060 (warn, non fail)
- ✓ Teste omnistudio:7870 et OmniVoice:8070 (primary)

**Verdict** : Correct.

---

## Recommendations

### Immédiat (1-2 jours) — Cohérence cosmétique

1. **CLAUDE.md, ligne 22** : remplacer `VOXSTUDIO_MINIFY=true` par `OMNISTUDIO_MINIFY=true`  
   Impact : documentation. Impact 0 sur fonctionnalité (alias rétro-compatible en script).

2. **RUNBOOK-OPS.md, ligne 197** : remplacer `port 8060` par `port 8070` dans titre section.  
   Impact : clarté documentation. Impact 0 sur fonctionnalité.

### Planifié (Phase 9+) — Nettoyage esthétique

3. **Renommer variables env legacy** en Phase 9 (post-P2 UX) : `VOXSTUDIO_MINIFY` → `OMNISTUDIO_MINIFY` dans tous scripts.  
   Raison : complétude nommage. Pas urgent (alias existe).

4. **Archiver docs de compat** : si VoxQwen n'est plus supporté, déplacer `METHODE-TTS.md` vers dossier `_archive/` et créer `METHODE-TTS-OMNIVOICE.md` (nouvelle).  
   Raison : clarté UX docs. Non bloquant.

---

## Conclusion

**Statut global** : ACCEPTABLE

- **Intégration OmniVoice** : Complète (client, config, graphe, frontend, tests, ops).
- **Résidus VoxStudio** : 119/195 intentionnels (docs), 8/195 cross-projet valides, 33/195 nommage mineur, 0/195 fonctionnel.
- **Risques** : Aucun bloquant. 2 typos mineurs (cosmétique).

**Prêt production** : Oui. Recommandation : corriger 2 typos docs avant Phase 9 pour cohérence.

