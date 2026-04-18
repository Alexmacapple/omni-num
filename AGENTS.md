# AGENTS.md — omnistudio

Ce fichier complète `CLAUDE.md` (protocole agent 6 blocs) et le PRD.
**Ne pas répéter** ce qui est déjà dans `CLAUDE.md` ou dans le PRD v1.5.

## Vue d'ensemble

OmniStudio — studio de production vocale branché sur OmniVoice (k2-fsa, 646 langues).
Fork de voxstudio avec isolation multi-user, multi-voix par étape via tags explicites,
sous-titres SRT, tags émotionnels, accents/dialectes, paramètres avancés.
Auth : Keycloak JWT (realm `harmonia` partagé avec Harmonia et voxstudio, client `omnistudio`).

## Objectifs qualité (non négociables)

| Axe | Cible |
|-----|-------|
| Conformité DSFR | 100 % |
| Accessibilité WCAG 2.1 AA / RGAA | 100 % |
| Compatibilité LangGraph | 100 % (extension du graphe voxstudio, cf. ARCHITECTURE-LANGGRAPH-OMNI.md) |
| Routes FastAPI | 100 % (44+ endpoints, 10 routeurs hérités + nouveaux) |
| Couverture 25 routes OmniVoice | 100 % (cf. PRD Annexe C et TAGS-SRT-SUBTITLES.md) |
| Lighthouse (4 axes) | 100 % |
| Zéro bug | 100 % |
| Tests | 349 hérités + ~130 nouveaux, 0 FAILED |
| Mémoire cumulée | `memory_pressure < 0.5` sous charge (cf. RUNBOOK-DEPLOYMENT.md) |

## Spécificités omnistudio (vs voxstudio)

1. **FastAPI sans `root_path`** — Tailscale Funnel strippe `/omni/`, donc l'app fonctionne à la racine en interne. `<base href="/omni/">` assure la cohérence côté navigateur. Vérifié empiriquement en Phase 0bis. **Ne JAMAIS ajouter `root_path="/omni"` à `FastAPI()`**.
2. **Préfixe CSS `ov-*`** (au lieu de `vx-*`). BEM préservé : `.ov-{bloc}__{element}--{modificateur}`.
3. **`<base href="/omni/">`** dans `<head>` de `index.html`. Ne jamais le retirer ni le modifier sans relancer les tests Phase 0bis.
4. **Multi-voix par étape** via tag `[voice:X]` explicite uniquement. Regex stricte `^[a-zA-Z][a-zA-Z0-9_-]{2,49}$` (anti-XSS). Auto-segmentation **reportée** à PRD-EVOLUTION-003.
5. **Isolation voix par owner** (décision 7, PRD-032). `meta.json` contient `owner` (sub JWT) et `system` (bool). Filtrage dans `routers/voices.py`.
6. **Anti-cascade session stale** (décision 9, PRD-034). 3 intercepteurs, 16 points de trace, seuil `OMNISTUDIO_STALE_THRESHOLD_MIN=10`.
7. **Voice Design EN uniquement** (OmniVoice rejette le FR). Deux modes UI : Guidé (selects) + Expert (saisie EN libre). Mapping FR → EN côté backend via `omnivoice_client.design_from_attributes()`.
8. **Voix système versionnées** (décision 4 v1.4). Les 6 voix Marianne/Léa/Sophie/Jean/Paul/Thomas sont générées une fois puis commitées dans `data/voices-system/`. Seed = `cp`, jamais regénération.
9. **Sous-titres SRT** via `SubtitleClient` (faster-whisper ~1,3 Go, téléchargé au 1er boot dans `data/models/`). 4 formats + TXT + JSON.
10. **Paramètres avancés** (11 paramètres de diffusion) exposés via accordéon DSFR dans l'onglet 5 et onglet 3 preview. Validation Pydantic stricte.

## Credentials

- **Keycloak admin** : `~/Claude/keycloak/.env` (variable `KEYCLOAK_ADMIN_PASSWORD`). Username : `admin`.
- **Albert (OPENAI_API_KEY)** : hérité de `voice-num/gitingore/credential-alex.md`. Chargé par `start.sh`.
- **Client Keycloak omnistudio** : public, ROPC (`directAccessGrantsEnabled`), UUID `7c0cfb9b-3c88-4ec0-839f-7e76bac27ad7` dans realm harmonia.

## Ne pas toucher

- **`OmniVoice/`** : dépôt Git autonome gitignored. Modifications à faire dans le dépôt upstream GitHub.
- **`data/voices-system/`** : voix système versionnées, modifiables uniquement par régénération manuelle documentée (PRD Phase 5).
- **`data/models/`** : cache faster-whisper, gitignored.
- **Les 3 intercepteurs anti-cascade stale** : ne pas baisser le seuil sous 3 erreurs (sinon faux positifs).
- **`root_path` FastAPI** : ne jamais le configurer (casse assets via Funnel).

## Playbooks rapides

Voir `CLAUDE.md` (12 commandes exactes).

## Références

| Doc | Usage |
|-----|-------|
| `CLAUDE.md` | Protocole agent 6 blocs |
| `PRD/PRD-MIGRATION-001-FORK-OMNISTUDIO.md` v1.5 | Décisions produit + plan d'exécution |
| `RUNBOOK-DEPLOYMENT.md` | Funnel, Keycloak, assets |
| `documentation/md/ARCHITECTURE.md` | Architecture technique (hérité + différences omnistudio) |
| `documentation/md/ARCHITECTURE-LANGGRAPH-OMNI.md` | Multi-voix, schéma State, parser |
| `documentation/md/TAGS-SRT-SUBTITLES.md` | 5 enrichissements OmniVoice + routes |
| `documentation/md/VOIX-DESIGN.md` | 2 modes Guidé/Expert, catalogue |
| `documentation/md/RUNBOOK-OPS.md` | Ops quotidien (adapté de voxstudio) |
| `documentation/md/GUIDE-UTILISATEUR.md` | Parcours 6 onglets (adapté) |
| `documentation/md/METHODE-TTS.md` | Écarts OmniVoice vs VoxQwen |
