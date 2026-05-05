# omni-num — OmniStudio

Studio de production audio batch branché sur **OmniVoice** (k2-fsa, 646 langues). SPA DSFR accessible RGAA, hébergée sur Mac Studio, exposée en 5G via Tailscale Funnel path-based.

Fork de [voice-num/voxstudio](https://github.com/Alexmacapple/voice-num) devenu un studio OmniVoice à part entière : multi-utilisateur, voix système versionnées, voix custom isolées par owner JWT, sous-titres SRT, tags émotionnels, accents/dialectes et paramètres avancés.

## Statut courant (2026-05-05)

| Axe | État |
|-----|------|
| Exploitation | Locale + Funnel public `/omni` validés |
| Services | Keycloak `8082`, OmniVoice `8070`, OmniStudio `7870` |
| Tests locaux | `583 passed / 162 skipped / 0 failed` |
| Coverage Python | `84 %` global, cible Phase 10 `82-85 %` atteinte localement |
| CI | GitHub Actions ajoutée dans `.github/workflows/ci.yml` |
| Qualité dépôt | `16/20` historique ; candidat local `18/20`, CI distante à confirmer |

<!-- CAUSAL:BEGIN — sections générées par readme-causal, ne pas éditer manuellement -->
## Anamèse [IC]

VoxStudio couvrait déjà un workflow de production vocale DSFR avec import, préparation, assignation, génération et export. Ce socle ne suffisait plus dès que la cible n'était plus VoxQwen mais OmniVoice : les capacités à exposer changent de nature, avec 646 langues, 25 routes API, des tags émotionnels, des accents/dialectes, des sous-titres SRT et des paramètres de diffusion avancés. Le problème n'était donc pas seulement de changer un backend TTS, mais de préserver le parcours producteur existant tout en ajoutant des capacités que l'ancien modèle applicatif ne représentait pas.

La contrainte s'est renforcée avec l'exploitation réelle : le service doit fonctionner derrière Tailscale Funnel sous `/omni`, partager le realm Keycloak `harmonia`, rester conforme DSFR/RGAA, isoler les voix par utilisateur et éviter les cascades de sessions stale pendant les flux SSE. Ces contraintes sont visibles dans le PRD v1.8, `AGENTS.md`, `RUNBOOK-DEPLOYMENT.md` et les commits récents de stabilisation routage, E2E, RGAA et Phase 10 qualité.

## Étiologie [IC]

**Kairos** : le dépôt naît au moment où OmniVoice devient une cible exploitable dans l'écosystème existant. Le PRD v1.8 documente explicitement la décision produit : étendre l'écosystème à OmniVoice en parallèle de VoxQwen, avec une Phase 0bis pour valider l'architecture avant code applicatif. Les commits récents montrent ensuite le passage d'un fork fonctionnel à une application opérable : UX Phase 9, corrections RGAA, routage `/omni`, E2E authentifiés, puis CI et hygiène Git Phase 10.

**Nécessitation** : un simple branchement d'API aurait cassé les garanties attendues. Le fork devait conserver FastAPI + DSFR + LangGraph, mais sans `root_path="/omni"` car Funnel strippe le préfixe ; il devait ajouter `<base href="/omni/">` côté navigateur ; il devait étendre le graphe existant plutôt que le réécrire ; il devait filtrer les voix custom par `owner` JWT ; il devait conserver les voix système en données versionnées. Cette chaîne rend l'approche actuelle raisonnable : un fork contrôlé, documenté par PRD, avec garde-fous de tests et scripts ops.

## Ossature causale [IC]

Le pattern principal est un **studio web FastAPI/DSFR orchestré par LangGraph et branché sur OmniVoice**. Keycloak porte l'identité, OmniStudio porte l'expérience producteur et l'isolation applicative, OmniVoice reste le moteur TTS autonome.

- Le frontend DSFR existe pour offrir un parcours dense en 6 onglets, utilisable en production et auditable RGAA.
- Les routeurs FastAPI existent pour exposer les étapes métier sans coupler le navigateur aux détails OmniVoice.
- LangGraph existe pour garder un état de workflow résumable, compatible avec le modèle hérité de VoxStudio.
- Les clients OmniVoice et SubtitleClient existent pour exploiter les routes TTS, design, clone, tags, transcription et SRT sans les disperser dans l'UI.
- Les scripts `start.sh`, `monitor.sh`, `test-smoke.sh`, `verify-assets-prefix.sh`, `ci-static-smoke.sh` et `setup-e2e-user.sh` existent parce que l'exploitation locale/publique est une partie du produit, pas un détail de développement.

Le projet ne cherche pas à rendre OmniVoice multi-user en interne : OmniVoice reste global, l'isolation est assurée dans OmniStudio. Il ne configure pas `root_path="/omni"` dans FastAPI : la compatibilité Funnel repose sur le `<base href>` et le middleware de tolérance du préfixe.

## Résidu [IC]

La Phase 10 est atteinte localement sur les axes à fort levier : CI ajoutée, hygiène Git nettoyée, E2E reproductibles documentés, suite complète verte et coverage global à `84 %`. Le dernier verrou formel reste d'observer la CI verte sur `main` après push. Une partie des E2E reste skippée sans secret Keycloak ou sans fixture voix custom pour `omni-e2e`, ce qui est documenté plutôt que masqué.

Certaines exclusions sont assumées : l'auto-segmentation de dialogues est reportée, Voice Design reste composé en anglais côté backend parce qu'OmniVoice rejette le français sur `/design`, et les modèles Whisper sont téléchargés au premier usage dans `data/models/`. Le projet est donc exploitable aujourd'hui, avec une candidature locale crédible à `18/20` ; la clôture formelle dépend encore de la CI verte distante et de la réévaluation après push.
<!-- CAUSAL:END -->

---

## Démarrage rapide

```bash
# 1. Lancer tous les services (Keycloak + OmniVoice + omnistudio)
#    Par défaut, scripts/start.sh sert le build production minifié.
./scripts/start.sh

# 2. Ouvrir
open http://localhost:7870              # local
open https://mac-studio-alex.tail0fc408.ts.net/omni/   # public 5G

# 3. Login Keycloak (compte existant réutilisé du realm harmonia)
```

Arrêter : `./scripts/stop.sh`. Smoke test : `WARN_AS_ERROR=1 ./scripts/test-smoke.sh`.

Mode développement front : `OMNISTUDIO_MINIFY=false ./scripts/start.sh`.

Préparer le compte E2E reproductible :

```bash
E2E_PASSWORD=<mot_de_passe_policy_ok> ./scripts/setup-e2e-user.sh
E2E_USERNAME=omni-e2e E2E_PASSWORD=<mot_de_passe> .venv/bin/python -m pytest tests/e2e/ -v
```

---

## Architecture

3 processus, 1 réseau Tailscale :

| Processus | Port local | Rôle |
|-----------|-----------|------|
| Keycloak | 8082 | Auth JWT (realm `harmonia`, client `omnistudio`) |
| OmniVoice | 8070 | API TTS k2-fsa (MPS Apple Silicon) |
| omnistudio | 7870 | Front DSFR + API workflow + proxy TTS |

Exposition publique : `https://mac-studio-alex.tail0fc408.ts.net/omni/` (Funnel path-based sur 443).

---

## Parcours utilisateur (6 onglets)

1. **Import** — charger un fichier (`.xlsx`, `.md`, `.csv`, `.txt`, `.docx`, `.pdf`) et sélectionner les étapes
2. **Préparation** — nettoyage LLM + validation, insertion optionnelle de marqueurs non-verbaux (`[laughter]`, `[sigh]`, ...)
3. **Voix** — explorer les 6 voix système + créer des voix personnalisées via Design (modes Guidé/Expert) ou Clone
4. **Assignation** — attribuer voix, langue, vitesse par étape. Multi-voix possible via tag `[voice:Marianne]` dans le texte
5. **Génération** — batch TTS avec paramètres avancés optionnels (11 paramètres de diffusion)
6. **Export** — post-traitement audio + option sous-titres SRT (4 formats) dans ZIP

---

## Différenciation vs voxstudio

10 axes de supériorité (cf. PRD v1.8) :

- Isolation multi-user des voix custom (owner + system)
- Multi-voix par étape via tags `[voice:X]`
- Anti-cascade session stale (3 intercepteurs)
- 6 voix système versionnées (reproductibles cross-instances)
- Voice Design 6 catégories (+ 10 accents, 12 dialectes)
- 13 tags émotionnels non-verbaux
- Auto-détection de langue sur 646 langues
- 11 paramètres avancés de diffusion
- Voix aléatoire (POST /auto) pour prototypage rapide
- Sous-titres SRT automatiques (4 formats + TXT + JSON)

---

## Documentation

| Doc | Usage |
|-----|-------|
| [`CLAUDE.md`](./CLAUDE.md) | Protocole agent (6 blocs) |
| [`AGENTS.md`](./AGENTS.md) | Directives spécifiques omnistudio |
| [`PRD/PRD-MIGRATION-001-FORK-OMNISTUDIO.md`](./PRD/PRD-MIGRATION-001-FORK-OMNISTUDIO.md) v1.8 | PRD complet + Phase 10 qualité dépôt 18/20 |
| [`todo.md`](./todo.md) | Plan court terme pour passer le dépôt de 16/20 à 18/20 |
| [`RUNBOOK-DEPLOYMENT.md`](./RUNBOOK-DEPLOYMENT.md) | Funnel, Keycloak, `<base href>`, troubleshooting |
| [`documentation/md/RUNBOOK-KEYCLOAK-USERS.md`](./documentation/md/RUNBOOK-KEYCLOAK-USERS.md) | Comptes Keycloak, mapper audience JWT, compte E2E |
| [`documentation/md/ARCHITECTURE.md`](./documentation/md/ARCHITECTURE.md) | Architecture technique couche par couche |
| [`documentation/md/ARCHITECTURE-LANGGRAPH-OMNI.md`](./documentation/md/ARCHITECTURE-LANGGRAPH-OMNI.md) | Multi-voix, parser, schéma State |
| [`documentation/md/TAGS-SRT-SUBTITLES.md`](./documentation/md/TAGS-SRT-SUBTITLES.md) | Enrichissements OmniVoice |
| [`documentation/md/VOIX-DESIGN.md`](./documentation/md/VOIX-DESIGN.md) | Modes Guidé/Expert, catalogue |
| [`documentation/md/RUNBOOK-OPS.md`](./documentation/md/RUNBOOK-OPS.md) | Ops quotidien |
| [`documentation/md/GUIDE-UTILISATEUR.md`](./documentation/md/GUIDE-UTILISATEUR.md) | Parcours 6 onglets |
| [`documentation/md/METHODE-TTS.md`](./documentation/md/METHODE-TTS.md) | Écarts OmniVoice vs VoxQwen |

---

## Dépôts

- **omni-num** (ce dépôt) : `git@github.com:Alexmacapple/omni-num.git` — front DSFR + API workflow
- **OmniVoice** : `git@github.com:Alexmacapple/OmniVoice.git` — API TTS k2-fsa (gitignored dans `OmniVoice/`)

---

## Qualité

- CI : workflow GitHub Actions dans `.github/workflows/ci.yml`, validation distante à confirmer après push.
- Services opérationnels : Keycloak, OmniVoice, OmniStudio et Funnel `/omni` validés par `scripts/monitor.sh`.
- Smoke test production : `scripts/test-smoke.sh` vert, assets minifiés servis en HTTP 200.
- Tests automatisés locaux : **583 passed / 162 skipped / 0 failed**.
- Couverture Python mesurée : **84 %** ; cible Phase 10 **82-85 %** atteinte localement, avec `routers/export.py` à **89 %** et `routers/voices.py` à **85 %**.
- Évaluation dépôt 2026-05-05 : **16/20** historique ; cible PRD v1.8 **18/20** atteignable après push + CI verte.

Commande de validation locale complète :

```bash
OMNISTUDIO_MINIFY=false OMNISTUDIO_PRELOAD_MODEL=false \
PYTHONPATH=omnistudio .venv/bin/python -m pytest tests -q --timeout=120 \
  --cov=omnistudio --cov-report=term-missing --cov-report=xml --cov-report=html
```

---

**Version** : v1.0 en exploitation locale/publique Funnel
**PRD de référence** : v1.8
**Licence** : MIT (alignée avec voice-num)
