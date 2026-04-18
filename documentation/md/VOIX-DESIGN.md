# Voix Design — OmniStudio

Guide de création de voix personnalisées dans OmniStudio (onglet 3, section « Créer une voix par description »).

> **Origine** : document adapté de voxstudio le 2026-04-18 pour le fork omnistudio. Contrairement à VoxQwen, OmniVoice **n'accepte pas le français** pour `/design` (erreur 422). Les descriptions moteur sont donc composées en anglais côté backend, avec une UI française côté utilisateur.

---

## Les deux modes de création

OmniStudio expose deux modes dans l'onglet 3, via un composant DSFR `fr-tabs` :

### Mode Guidé (recommandé)

L'utilisateur compose sa voix en sélectionnant dans 4 selects (6 catégories si la langue est anglaise ou chinoise) :

| Catégorie | Valeurs | Condition d'activation |
|-----------|---------|------------------------|
| Genre | Homme, Femme | Toujours active |
| Âge | Enfant, Adolescent, Jeune adulte, Adulte, Senior | Toujours active |
| Hauteur | Très grave, Grave, Moyenne, Aiguë, Très aiguë | Toujours active |
| Style | Neutre, Chuchoté | Toujours active |
| Accent anglais | American, Australian, British, ... (10) | Activée si `language=en` |
| Dialecte chinois | Henan, Shaanxi, Sichuan, ... (12) | Activée si `language=zh` |

Le backend compose la chaîne EN (`female, young adult, high pitch, energetic`) et l'envoie à `POST /voices/custom` source=design. Les dialectes chinois sont mappés vers leurs caractères chinois (ex. `Sichuan Dialect` → `四川话`).

### Mode Expert

Champ texte libre en anglais. Placeholder : `female, young adult, high pitch, energetic`. Aide sous le champ avec la liste des attributs acceptés.

Erreur 422 si l'utilisateur saisit du français → toast DSFR : *« La description contient des mots non reconnus par OmniVoice. Vérifiez qu'elle est bien en anglais, ou passez en mode Guidé. »*

### Champ commun : Description libre

Texte FR libre stocké dans `meta.json` (champ `description`), affiché dans la bibliothèque pour aider à retrouver la voix. **Aucun impact** sur la génération (non envoyé à OmniVoice).

---

## Les 6 voix système (pré-générées, versionnées)

Avant la création de voix personnelles, OmniStudio fournit 6 voix pré-générées qui couvrent les cas d'usage courants (narration, dialogue, didactique). Elles sont **versionnées dans le dépôt** (`data/voices-system/`) pour garantir la reproductibilité cross-instances.

| Nom | Description UI (FR) | `instruct` envoyé à OmniVoice |
|-----|---------------------|-------------------------------|
| Marianne | Voix féminine posée, chaleureuse et nette, idéale pour la narration | `female, middle-aged, moderate pitch, warm and clear` |
| Léa | Voix féminine jeune, douce et expressive | `female, young adult, moderate pitch, gentle` |
| Sophie | Voix féminine mature, grave et affirmée | `female, elderly, low pitch, assertive` |
| Jean | Voix masculine posée, grave et rassurante | `male, middle-aged, low pitch, calm` |
| Paul | Voix masculine jeune, dynamique et claire | `male, young adult, moderate pitch, energetic` |
| Thomas | Voix masculine mature, profonde et autoritaire | `male, elderly, very low pitch, authoritative` |

Les 6 voix système sont marquées `system: true` dans `meta.json`, visibles par tous les utilisateurs, **non modifiables** et **non supprimables**.

---

## Exemples de profils personnalisés

Exemples de création pour des cas d'usage métier — adapter les `instruct` EN selon les attributs.

### 1. Narrateur institutionnel (administration française)

- **Usage** : narration principale, ton d'autorité bienveillante
- **Mode Guidé** : Homme + Adulte + Grave + Neutre (+ language=fr, sans accent spécifique)
- **Chaîne composée** : `male, middle-aged, low pitch`
- **Alternative système** : utiliser `Jean` directement (pas de création nécessaire)

### 2. Narratrice pédagogique

- **Usage** : formation en ligne, ton accompagnant
- **Mode Guidé** : Femme + Adulte + Moyenne + Neutre
- **Chaîne composée** : `female, middle-aged, moderate pitch`
- **Alternative système** : utiliser `Marianne` directement

### 3. Narrateur dynamique (démo produit tech)

- **Usage** : public jeune, contexte innovation
- **Mode Guidé** : Homme + Jeune adulte + Moyenne + Neutre
- **Chaîne composée** : `male, young adult, moderate pitch, energetic`
- **Alternative système** : utiliser `Paul` directement

### 4. Conférencière avec accent britannique

- **Usage** : content anglophone formel
- **Mode Guidé** : Femme + Adulte + Moyenne + Neutre + English Accent = British + `language=en`
- **Chaîne composée** : `female, middle-aged, moderate pitch, british accent`

### 5. Dialogue chinois (mandarin dialecte Sichuan)

- **Usage** : contenu localisé Chine du sud-ouest
- **Mode Guidé** : Homme + Adulte + Moyenne + Neutre + Chinese Dialect = Sichuan + `language=zh`
- **Chaîne composée** : `male, middle-aged, moderate pitch, 四川话`

### 6. Chuchotement (confidentialité, intimité)

- **Usage** : contenu immersif, messages personnels
- **Mode Guidé** : Femme + Jeune adulte + Moyenne + **Chuchoté**
- **Chaîne composée** : `female, young adult, moderate pitch, whisper`

---

## Non-déterminisme OmniVoice

Le décodeur audio OmniVoice introduit des variations à chaque génération. Deux appels `POST /voices/custom` avec le même `instruct` produiront deux voix au timbre légèrement différent.

**Conséquence** :

- Les 6 voix système sont générées **une seule fois** puis versionnées dans le dépôt. Chaque instance d'omnistudio lit les mêmes fichiers, donc entend les mêmes voix.
- Une voix personnelle créée via l'UI est stable **dans cette instance**, mais ne peut pas être recréée à l'identique ailleurs.

Pour une cohérence audio garantie sur un long projet (livre audio, série pédagogique), **préférer le clonage** (`POST /voices/custom` source=clone avec un échantillon audio humain + transcription), qui stocke une `reference.wav` déterministe.

---

## Routes API

| Usage | Route | Paramètre clé |
|-------|-------|---------------|
| Créer une voix via description | `POST /api/voices/custom` source=design | `instruct` (EN) |
| Créer une voix par clone | `POST /api/voices/custom` source=clone | `reference_audio` + `reference_text` |
| Lister les voix visibles | `GET /api/voices` | filtre `owner OR system` |
| Prévisualiser une voix | `POST /api/voices/preview` | `voice` + `text` |
| Attributs acceptés (pour Guidé) | `GET /api/voices/design-attributes` | proxie OmniVoice `/design/attributes` |

---

## Protocole de test qualité

Pour évaluer une nouvelle voix avant production :

1. Générer la voix via mode Guidé ou Expert
2. Utiliser la phrase de référence ci-dessous via `POST /api/voices/preview`
3. Écoute comparative avec une voix système (ex. Marianne)
4. Si validée, utiliser la voix dans l'onglet 4 (Assignation)

### Phrase de test (FR)

« Le délégué se connecte via ProConnect à Grist ADN gestion pour préparer la campagne annuelle de l'arbre de Noël. »

### Phrase de test (EN)

« The administrator connects through ProConnect to prepare the annual campaign. »

### Phrase de test (chuchoté)

« [whisper] Cette information reste strictement confidentielle. »

*Note* : les marqueurs non-verbaux (`[laughter]`, `[sigh]`, etc.) peuvent être insérés dans le texte pour générer des expressions. Voir [TAGS-SRT-SUBTITLES.md](./TAGS-SRT-SUBTITLES.md).
