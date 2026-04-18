# Enrichissements OmniStudio — tags, SRT, accents, paramètres avancés

Cette doc regroupe les 5 capacités d'OmniVoice exploitées par omnistudio mais absentes de voxstudio. Référence : PRD-MIGRATION-001 v1.5 (décisions 11 à 17), annexes H à K.

---

## 1. Tags émotionnels non-verbaux (13 marqueurs)

OmniVoice supporte 13 marqueurs à insérer dans le texte pour générer des expressions non-verbales (rire, soupir, surprise, question). Ces marqueurs sont rendus en **sons**, pas en texte prononcé.

### Liste complète

| Tag | Effet sonore | Langue |
|-----|--------------|--------|
| `[laughter]` | Rire | Universel |
| `[sigh]` | Soupir | Universel |
| `[confirmation-en]` | « Mm-hmm » (accord) | Anglais |
| `[question-en]` | Intonation interrogative anglaise | Anglais |
| `[question-ah]` | « Ah ? » (question) | FR, EN |
| `[question-oh]` | « Oh ? » (question) | FR, EN |
| `[question-ei]` | « Ei ? » (question) | Italien, FR |
| `[question-yi]` | « Yi ? » (question) | Chinois |
| `[surprise-ah]` | « Ah ! » (surprise positive) | FR, EN |
| `[surprise-oh]` | « Oh ! » (surprise) | FR, EN |
| `[surprise-wa]` | « Wa ! » (surprise enthousiaste) | Japonais, CN |
| `[surprise-yo]` | « Yo ! » (surprise familière) | Multilingue |
| `[dissatisfaction-hnn]` | « Hnn » (mécontentement) | Universel |

### Utilisation dans OmniStudio

#### Palette UI (onglet 3 et onglet 2)

Au-dessus du textarea (formulaire de création de voix ou nettoyage de texte), une palette DSFR de 13 boutons `fr-btn fr-btn--secondary fr-btn--sm`. Au clic, le tag s'insère **à la position actuelle du curseur** (pas à la fin), avec gestion des espaces automatique.

La liste est récupérée dynamiquement au boot via `GET /api/voices/tags` (proxy vers OmniVoice `GET /tags`) — si OmniVoice enrichit la liste, l'UI suit sans modification.

#### Exemple

Texte d'étape : `Tu m'as bien eu ! [laughter] Mais j'ai gagné quand même. [sigh]`

Après génération : l'audio contient un rire après « Tu m'as bien eu ! » et un soupir après « Mais j'ai gagné quand même. ».

### Tests

`test_tags_emotionnels.py` — 25 tests vérifient l'insertion au curseur, le placement, la génération audio différente vs texte brut.

---

## 2. Sous-titres SRT automatiques (4 formats)

OmniStudio utilise `faster-whisper` (CTranslate2 + modèle `deepdml/faster-whisper-large-v3-turbo-ct2`) pour générer des sous-titres après chaque export audio. Cochable dans l'onglet 6 Export.

### Pipeline

1. Option `include_subtitles` cochée dans l'onglet 6
2. Pour chaque WAV exporté, appel `SubtitleClient.transcribe()` avec la langue de l'étape (ou `"auto"`)
3. Production de 6 fichiers par étape
4. Inclusion dans le ZIP final sous `subtitles/`

### Formats générés

| Format | Extension | Max lignes | Max durée | Max chars/ligne | Usage |
|--------|-----------|------------|-----------|-----------------|-------|
| Standard | `.srt` | 3 | 8 s | 42 | Vidéo broadcast, YouTube |
| Mot par mot | `_word.srt` | 1 | 2 s | (1 mot) | Karaoke, lecture active, e-learning |
| Shorts | `_shorts.srt` | 1 | 3 s | 30 | TikTok, Reels, YouTube Shorts |
| Multilignes | `_multiline.srt` | 2 | 6 s | 38 | Cinéma, Netflix |
| TXT brut | `.txt` | — | — | — | Indexation, LLM |
| JSON timestamps | `.json` | — | — | — | Intégration programmatique |

### Chunking (décision 16 PRD v1.5)

Les sous-titres Whisper sont découpés en chunks respectant les contraintes standards ci-dessus. Fonction `SubtitleClient.chunk_subtitles(segments, format)`.

Exemple : un audio de 10 min produit ~600 sous-titres avec Whisper (1-2 s granularité). La fonction de chunking regroupe/découpe pour respecter les max lignes et max durée par format.

### Structure du ZIP enrichi

```
export-2026-04-18-143000.zip
├── audio/
│   ├── 001_intro.wav
│   ├── 002_section1.wav
│   └── ...
├── subtitles/
│   ├── 001_intro.srt
│   ├── 001_intro_word.srt
│   ├── 001_intro_shorts.srt
│   ├── 001_intro_multiline.srt
│   ├── 001_intro.txt
│   ├── 001_intro.json
│   └── ...
└── manifest.json
```

### Langues supportées

Whisper couvre **~99 langues** (sous-ensemble des 646 d'OmniVoice). Si la langue d'une étape n'est pas supportée, les sous-titres sont **silencieusement omis** pour cette étape (log info, pas d'erreur bloquante). Mentionné dans le `manifest.json` du ZIP.

### Dépendance

- `faster-whisper` (~500 Mo package)
- Modèle `deepdml/faster-whisper-large-v3-turbo-ct2` (~800 Mo, téléchargé au premier boot dans `data/models/`)
- Total : ~1,3 Go supplémentaire sur disque (gitignored)

### Tests

`test_subtitles.py` — 25 tests incluant un audio 10 min FR avec vérification des 4 formats + cas limite langue non supportée.

---

## 3. Voice Design étendu — 6 catégories (accents et dialectes)

Contrairement aux 4 catégories standards (Genre, Âge, Hauteur, Style), omnistudio expose 2 catégories conditionnelles selon la langue choisie.

### English Accent (10 variantes, activées si `language=en`)

American, Australian, British, Chinese (accent anglais chinois), Canadian, Indian, Korean, Portuguese, Russian, Japanese.

Info-bulle DSFR : *« Only effective for English speech »*

### Chinese Dialect (12 variantes, activées si `language=zh`)

Mapping UI (anglais) → caractères chinois envoyés à OmniVoice :

| Dialect UI | Caractères chinois |
|------------|--------------------|
| Henan | 河南话 |
| Shaanxi | 陕西话 |
| Sichuan | 四川话 |
| Guizhou | 贵州话 |
| Yunnan | 云南话 |
| Guilin | 桂林话 |
| Jinan | 济南话 |
| Shijiazhuang | 石家庄话 |
| Gansu | 甘肃话 |
| Ningxia | 宁夏话 |
| Qingdao | 青岛话 |
| Northeast | 东北话 |

Info-bulle DSFR : *« Only effective for Chinese speech »*

### UX

Les deux selects apparaissent/disparaissent dynamiquement via `disabled` + `aria-hidden="true"` selon la langue. Lecteurs d'écran correctement pilotés.

### Tests

`test_accents_dialects.py` — 30 tests (22 valeurs × activation conditionnelle).

---

## 4. Paramètres avancés de synthèse (11 paramètres)

Panneau `fr-accordion` fermé par défaut dans l'onglet 5 Génération et onglet 3 preview Voice Design. *« Paramètres avancés (facultatif). Réservé aux utilisateurs avancés. »*

### Liste

| Paramètre | Plage | Défaut | Description UI |
|-----------|-------|--------|----------------|
| `num_step` | 4-64 | 32 | Étapes de diffusion : plus élevé = meilleure qualité, plus lent |
| `guidance_scale` | 0-4 | 2.0 | Force du guidage CFG (0 = libre, 4 = strict) |
| `duration` | 0.1-600 s | — | Durée fixe en secondes (prioritaire sur `speed`, utile pour sync vidéo) |
| `denoise` | bool | `true` | Token de débruitage (audio plus propre) |
| `t_shift` | 0-1 | 0.1 | Décalage scheduling de bruit |
| `position_temperature` | 0-20 | 5.0 | Température position (0 = déterministe) |
| `class_temperature` | 0-5 | 0.0 | Température sampling (0 = déterministe) |
| `layer_penalty_factor` | 0-20 | 5.0 | Pénalité couches profondes |
| `postprocess_output` | bool | `true` | Suppression des silences longs |
| `audio_chunk_duration` | 1-60 s | 15.0 | Durée cible par segment (textes longs) |
| `audio_chunk_threshold` | 5-120 s | 30.0 | Seuil déclenchement chunking auto |

### Validation

Limites imposées côté backend via Pydantic `Field(ge=..., le=...)`. Un paramètre hors plage retourne 422 avec message explicite.

### Cas d'usage

- **Synchronisation vidéo** : `duration=12.5` force un audio d'exactement 12,5 s (la vitesse est adaptée automatiquement)
- **Déterminisme** : `position_temperature=0.0, class_temperature=0.0` pour audio reproductible
- **Qualité max** : `num_step=64, guidance_scale=3.5` pour rendus finaux (plus lent)

### Tests

`test_advanced_params.py` — 30 tests (11 paramètres × limites hautes/basses/hors plage).

---

## 5. Auto-détection de langue

Entrée `"Auto"` en tête des selects de langue (onglets 4 Assignation, 5 Génération). OmniVoice détecte via `langdetect`.

### UX

- Valeur par défaut des selects : `fr` (pas `Auto`) pour ne pas surprendre l'utilisateur
- Info-bulle : *« Détection automatique de la langue à partir du texte »*
- Fallback OmniVoice : si `langdetect` absent → français par défaut

### Limites

- Fonctionne mal sur textes courts (< 20 caractères) ou très mixtes
- Pour contenus multilingues par étape, préférer l'assignation explicite par étape
- Multi-voix via `[voice:X]` : la langue est portée par la voix, pas le segment

### Tests

`test_auto_language.py` — 10 tests (détection FR, EN, ZH, mixte, fallback).

---

## 6. Voix aléatoire (POST /auto)

Bouton dans l'onglet 5 : *« Générer avec une voix aléatoire (prototype rapide) »*.

- Au clic : `POST /api/generate/random` → OmniVoice `POST /auto`
- Génération instantanée sans voix sélectionnée
- Audio ajouté temporairement à la liste (mais **pas** sauvegardé comme voix custom)
- Toast DSFR : *« Voix aléatoire générée. Pour la conserver, cliquez sur "Ajouter à la bibliothèque". »*

### Cas d'usage

- Prototypage rapide, brainstorming sonore
- Prévisualisation avant de choisir une voix définitive
- Test d'un texte avant de le finaliser

### Tests

`test_voice_auto.py` — 8 tests (3 générations différentes, non-déterminisme vérifié).

---

## 7. Préchargement du modèle OmniVoice

Au démarrage (`start.sh`), après que OmniVoice soit up sur 8070, appel `POST /models/preload` avant de lancer omnistudio. Le modèle OmniVoice (~1,2 Go VRAM) est chargé **avant** la première requête utilisateur → pas de latence de cold start (~30 s évités).

Configurable via `OMNISTUDIO_PRELOAD_MODEL=true` (défaut) / `false` (dev rapide).

### Tests

`test_models_preload.py` — 5 tests (vérification que la première requête preset retourne en < 3 s après boot).

---

## Résumé des 25 routes OmniVoice exploitées

| Route | Usage omnistudio |
|-------|------------------|
| `GET /` | Health check |
| `GET /health` | Sonde |
| `GET /languages` | Shortlist 10 langues |
| `GET /languages/all` | Recherche 646 langues |
| **`GET /tags`** | Palette émotionnelle (§ 1) |
| `GET /design/attributes` | Selects Guidé (§ 3) |
| `POST /transcribe` | Aide clone (Whisper intégré OmniVoice) |
| **`POST /auto`** | Voix aléatoire (§ 6) |
| `POST /design` | Via `/voices/custom` source=design |
| `POST /preset` | Génération standard |
| `POST /preset/instruct` | Instruct émotionnel |
| `POST /clone` | Clone vocal |
| `GET /voices` | Bibliothèque (filtré owner côté omnistudio) |
| `POST /voices/custom` | Création Design + Clone |
| `GET /voices/custom/{name}` | Détails |
| `DELETE /voices/custom/{name}` | Check owner |
| `POST /voices/reload` | Après seed |
| `POST /batch/auto` | Random batch (optionnel) |
| `POST /batch/design` | Design batch direct |
| `POST /batch/clone` | Clone batch direct |
| `POST /batch/preset` | Génération batch principal |
| `POST /tokenizer/encode` | Estimation durée |
| `GET /models/status` | Monitoring |
| `GET /generation/status` | État génération |
| **`POST /models/preload`** | Préchargement start.sh (§ 7) |

**25/25 routes exploitées** (gras = nouveau vs voxstudio).

---

## Références

- PRD v1.5 : `PRD/PRD-MIGRATION-001-FORK-OMNISTUDIO.md`
- Annexe H (13 tags), I (dialectes chinois), J (paramètres avancés), K (formats SRT), M (parser multi-voix)
- Écosystème Colab : `OmniVoice/google-colab/app.py`, `subtitle.py`, `hf_mirror.py`
