# Méthode de génération des synthèses vocales ADN

Processus de production des voix off pour les étapes du plan ADN Scénarios.

---

## Phase 1 - Sélection de la voix

### Objectif

Identifier la voix préréglée qui passe le mieux en français parmi les 9 disponibles.

### Voix à tester

| Voix | Type |
|------|------|
| Vivian | Féminine |
| Serena | Féminine |
| Ono_Anna | Féminine |
| Sohee | Féminine |
| Dylan | Masculine |
| Eric | Masculine |
| Ryan | Masculine |
| Aiden | Masculine |
| Uncle_Fu | Masculine |

### Protocole

- Générer les 9 voix avec une phrase identique extraite du plan ADN
- Phrase de test : "Le délégué se connecte via Pro Connect à Grist ADN gestion pour préparer la campagne."
- Écoute comparative et sélection de la meilleure voix
- Sortie : `voice/test/test-{voix}.wav`

### Route API utilisée

```bash
POST /preset
  text: [phrase de test]
  voice: [nom de la voix]
  language: fr
```

---

## Phase 2 - Génération des étapes

### Préparation des textes

1. Extraire le texte narratif de chaque étape du plan Markdown
2. Nettoyer le contenu pour un rendu vocal naturel :
   - Retirer le formatage technique (noms de boutons entre guillemets, termes d'interface)
   - Reformuler les phrases trop longues ou complexes
   - Supprimer les abréviations et acronymes non prononcables

### Génération

- Route : `POST /preset` avec la voix sélectionnée en phase 1
- Langue : fr
- Génération séquentielle (une étape à la fois)

### Convention de nommage

```
voice/etape-01-connexion-delegue.wav
voice/etape-02-parametrage-campagne.wav
voice/etape-03-diffusion-messages.wav
...
voice/etape-38-archivage-anonymisation.wav
```

Format : `etape-{numéro sur 2 chiffres}-{description courte en kebab-case}.wav`

---

## Phase 3 - Vérification

### Contrôles

- Chaque fichier WAV est valide (format RIFF, PCM 16 bits, mono 24 kHz)
- Aucun fichier vide ou corrompu
- Cohérence de la voix sur l'ensemble des étapes

### Livrable

Liste récapitulative avec :

| Étape | Fichier | Durée | Taille |
|-------|---------|-------|--------|
| 1 | etape-01-connexion-delegue.wav | Xs | X Ko |
| ... | ... | ... | ... |

---

## Option avancée - Mode expressif

Pour un rendu plus riche (ton narrateur, émotions), utiliser la route `/preset/instruct` avec le modèle 1.7B.

```bash
POST /preset/instruct
  text: [texte de l'étape]
  voice: [voix sélectionnée]
  instruct: "Ton professionnel et pédagogique, rythme posé"
  language: fr
```

Avantage : contrôle du style et des émotions.
Inconvénient : génération plus lente (~20 secondes par étape au lieu de ~5).

---

## Nettoyage des textes (2 couches)

Le nettoyage transforme les textes sources en textes optimisés pour la synthèse vocale :

1. **Layer B (déterministe)** — Corrections automatiques via fichier JSON optionnel :
   - `patterns` : expressions régulières (sigles, abréviations)
   - `parenthèses` : suppressions de références parasites
   - `majuscules` : normalisation des mots en MAJUSCULES

2. **Layer LLM (sémantique)** — Reformulation par Albert (LLM) :
   - Transforme les listes à puces en phrases fluides
   - Développe les abréviations restantes
   - Ajuste la ponctuation pour un rythme naturel

3. **Layer A (fallback)** — Si le LLM est indisponible :
   - Nettoyage basique regex (listes, espaces, ponctuation)

---

## Résumé du processus

```
Phase 1          Phase 2              Phase 3
Sélection   -->  Génération      -->  Vérification
9 tests          N étapes            Contrôle qualité
~3 min           ~10-30 min           ~2 min
```
