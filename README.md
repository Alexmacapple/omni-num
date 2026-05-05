# omni-num — OmniStudio

Studio de production audio batch branché sur **OmniVoice** (k2-fsa, 646 langues). SPA DSFR accessible RGAA, hébergée sur Mac Studio, exposée en 5G via Tailscale Funnel path-based.

Fork de [voice-num/voxstudio](https://github.com/Alexmacapple/voice-num) avec **zéro dette technique identifiée** et **25/25 routes OmniVoice** exploitées (tags émotionnels, sous-titres SRT, accents/dialectes, paramètres avancés, multi-voix par étape).

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

- Services opérationnels : Keycloak, OmniVoice, OmniStudio et Funnel `/omni` validés par `scripts/monitor.sh`.
- Smoke test production : `scripts/test-smoke.sh` vert, assets minifiés servis en HTTP 200.
- Tests automatisés : **548 passed / 163 skipped / 0 failed**.
- Couverture Python mesurée : **78 %** ; cible Phase 10 : **82-85 %** avec focus `routers/export.py`, `routers/voices.py`, `core/subtitle_client.py`, `routers/auth_routes.py`.
- Évaluation dépôt 2026-05-05 : **16/20** ; cible PRD v1.8 : **18/20**.

---

**Version** : v1.0 en exploitation locale/publique Funnel
**PRD de référence** : v1.8
**Licence** : MIT (alignée avec voice-num)
