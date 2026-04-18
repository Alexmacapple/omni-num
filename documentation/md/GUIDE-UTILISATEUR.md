# Guide utilisateur — OmniStudio

Bienvenue sur OmniStudio, le studio de production vocale pour l'administration publique. Ce guide vous accompagne pas à pas, de la connexion jusqu'au téléchargement de vos fichiers audio.

---

## Glossaire

| Terme | Signification |
|-------|--------------|
| **TTS** | Text-to-Speech — synthèse vocale, la technologie qui transforme du texte écrit en parole |
| **LLM** | Large Language Model — modèle d'intelligence artificielle utilisé pour le nettoyage des textes |
| **DSFR** | Design System de l'État Français — la charte graphique officielle des sites publics |
| **WAV** | Format audio non compressé, haute qualité (utilisé pour les livrables) |
| **ZIP** | Archive compressée regroupant plusieurs fichiers en un seul téléchargement |
| **CSV** | Comma-Separated Values — fichier texte avec des données séparées par des virgules ou points-virgules |
| **Markdown (.md)** | Format de texte léger avec balisage simple (titres avec `#`, listes avec `-`) |
| **PDF** | Portable Document Format — format de document universel |
| **JSON** | Format de données structurées utilisé pour les fichiers de corrections |
| **kHz** | Kilohertz — unité de fréquence d'échantillonnage audio (plus élevé = meilleure qualité) |
| **Stéréo** | Son diffusé sur deux canaux (gauche et droite), plus naturel que le mono |
| **Prompt vocal** | Description technique d'une voix (ton, rythme, émotion) utilisée par le moteur TTS |

---

## Accès et connexion

### Se connecter

1. Ouvrir OmniStudio dans votre navigateur (adresse fournie par votre administrateur)
2. Saisir votre **identifiant** et votre **mot de passe** (compte Keycloak)
3. Cliquer sur **Se connecter**

Votre nom apparaît en haut à droite de l'écran. Vous êtes prêt.

### En cas d'erreur de connexion

- Vérifiez l'orthographe de votre identifiant (sensible à la casse)
- Vérifiez que le service est accessible (bouton **État des services** en bas de page)
- Contactez votre administrateur si le problème persiste

### Se déconnecter

Cliquez sur l'icône de déconnexion en haut à droite (flèche vers la droite).

---

## Vue d'ensemble

OmniStudio fonctionne en **6 étapes séquentielles**, représentées par des onglets :

| Étape | Onglet | Ce que vous faites |
|-------|--------|-------------------|
| 1 | **Import** | Charger votre fichier scénario |
| 2 | **Préparation** | Nettoyer les textes pour la synthèse vocale |
| 3 | **Voix** | Choisir, créer ou cloner des voix |
| 4 | **Assignation** | Attribuer une voix à chaque segment |
| 5 | **Génération** | Produire les fichiers audio |
| 6 | **Export** | Télécharger le pack final |

Chaque onglet se débloque progressivement. Le bouton **Continuer** en bas de chaque onglet vous guide vers l'étape suivante.

Sur mobile, un stepper avec les boutons **Précédent / Suivant** remplace les onglets.

---

## Étape 1 — Import du scénario

### Charger un fichier

1. Cliquer sur **Parcourir** ou glisser-déposer votre fichier dans la zone d'upload
2. Formats acceptés : **Excel (.xlsx)**, **CSV**, **Word (.docx)**, **PDF**, **Markdown (.md)**, **Texte brut (.txt)**
3. Le fichier est analysé automatiquement

**Pour un fichier Excel** : OmniStudio vous propose de choisir l'onglet à importer et le mode (remplacer ou ajouter aux segments existants).

### Format attendu par type de fichier

| Format | Structure attendue |
|--------|-------------------|
| **Excel (.xlsx)** | Chaque ligne = un segment. Première colonne = identifiant (optionnel), deuxième colonne = texte. La première ligne peut être un en-tête (détecté automatiquement). Plusieurs onglets possibles |
| **CSV** | Même structure que Excel, séparateur virgule ou point-virgule (détecté automatiquement). Encodage UTF-8 recommandé |
| **Word (.docx)** | Chaque paragraphe non vide = un segment. Les titres et la mise en forme sont ignorés, seul le texte brut est conservé |
| **PDF** | Le texte est extrait page par page. Chaque paragraphe détecté = un segment. Les PDF scannés (images) ne sont pas supportés |
| **Markdown (.md)** | Chaque paragraphe ou élément de liste = un segment. Les titres servent de séparateurs |
| **Texte brut (.txt)** | Chaque ligne non vide = un segment |

**Taille maximale** : 10 Mo par fichier.

### Sélectionner les segments

Après l'import, un tableau affiche tous les segments détectés avec leur texte original. Cochez les segments que vous souhaitez conserver, puis cliquez sur **Continuer vers la préparation**.

### Pas de fichier ?

Vous pouvez aussi saisir vos segments manuellement. Cliquez sur **Passer à la préparation** (lien en haut de l'onglet), puis utilisez le formulaire « Ajouter un segment » dans l'onglet Préparation.

---

## Étape 2 — Préparation des textes

L'intelligence artificielle nettoie vos textes pour une lecture optimale par la synthèse vocale : sigles développés, parenthèses supprimées, majuscules normalisées, ponctuation ajustée.

### Configurer le nettoyage (optionnel)

Avant de lancer le nettoyage, vous pouvez configurer :

- **Glossaire et phonétique** : indiquer comment prononcer certains termes. Un remplacement par ligne, format `CLÉ = VALEUR`. Exemple : `DN = Démarches Numériques`
- **Corrections JSON** : charger un fichier de corrections automatiques (patterns regex, parenthèses à supprimer, majuscules à normaliser)

### Lancer le nettoyage

1. Cliquer sur **Lancer le nettoyage LLM**
2. Une barre de progression montre l'avancement (chaque segment est traité individuellement)
3. Le traitement peut prendre quelques minutes pour un grand nombre de segments

### Vérifier et valider

Le tableau affiche pour chaque segment :
- **Texte original** : ce que vous avez importé
- **Texte TTS** : la version nettoyée par l'IA
- **Statut** : en attente, nettoyé, ou validé

Vous pouvez :
- Modifier manuellement un texte TTS en cliquant dessus
- Comparer les différences via l'accordéon **Comparaison**
- **Valider tous les textes** quand le résultat vous convient

### En cas d'interruption

Si le nettoyage s'interrompt (fermeture du navigateur, perte de connexion), les segments déjà traités sont conservés. Un bouton **Reprendre le nettoyage** apparaît pour continuer là où vous vous étiez arrêté.

### Ajouter un segment manuellement

Utilisez le formulaire en haut de l'onglet : saisissez un identifiant et un texte, puis cliquez sur **Ajouter**.

Une fois satisfait, cliquez sur **Continuer vers le design des voix**.

---

## Étape 3 — Design des voix

C'est ici que vous choisissez les voix qui liront vos textes. Trois sous-onglets sont disponibles.

### Bibliothèque

La bibliothèque affiche toutes les voix disponibles (natives et personnalisées). Chaque carte de voix indique son nom, son type (native ou custom) et permet de la sélectionner.

Sélectionnez une ou plusieurs voix, puis cliquez sur **Continuer vers l'assignation**.

### Créer (Design de voix)

Créer une voix en 3 temps :

**1. Décrire la voix**

Deux options :
- **Profils prédéfinis** : cliquez sur un bouton (Narrateur chaleureux, Présentateur dynamique, etc.) pour pré-remplir les paramètres
- **Brief IA** : configurez manuellement le contexte (Tutoriel, Podcast, Keynote...), l'émotion (Engageant, Rassurant, Neutre...), le genre, l'âge, et ajoutez une description libre

Cliquez sur **Créer le prompt vocal avec l'IA** pour générer une description technique de la voix.

**2. Écouter et ajuster**

Cliquez sur **Écouter cette voix** pour entendre un échantillon. Chaque génération produit un timbre légèrement différent — n'hésitez pas à régénérer plusieurs fois.

Vous pouvez affiner la voix avec les **ajustements rapides** (tags cliquables : grave, aigu, chaleureux, lent, rapide, etc.).

**3. Enregistrer la voix**

Quand le résultat vous plaît :
1. Donnez un **nom** à la voix (3 à 50 caractères, sans espaces)
2. Ajoutez une **description** (optionnel)
3. Cliquez sur **Verrouiller cette voix**

La voix est sauvegardée et apparaît dans la bibliothèque.

**Test de stabilité** : le bouton **Tester la stabilité** génère 3 échantillons pour vérifier que la voix produit un résultat constant.

### Cloner

Cloner une voix existante à partir d'un enregistrement audio :

1. **Charger un audio de référence** (WAV, MP3, FLAC ou OGG, 1 à 30 secondes) ou **enregistrer via le micro**
2. Saisir la **transcription exacte** de ce qui est dit dans l'audio
3. Donner un **nom** à la voix
4. Choisir le modèle (**1.7B** pour la qualité, **0.6B** pour la rapidité)
5. Cliquer sur **Créer le clone**

La voix clonée est ajoutée à la bibliothèque.

---

## Étape 4 — Assignation des voix

Chaque segment de votre scénario reçoit ici une voix, une langue et une vitesse de lecture.

### Assignation globale

En haut de l'onglet, des sélecteurs permettent de définir les paramètres par défaut :
- **Voix** : choisir parmi les voix disponibles
- **Langue** : français (défaut), anglais, chinois, japonais, coréen
- **Vitesse** : de 0.5x (très lent) à 2.0x (très rapide), par défaut 1.0x
- **Instruction émotionnelle** : disponible uniquement pour les voix natives (Serena, Vivian, Dylan...)

Cliquez sur **Appliquer à tout** pour affecter ces paramètres à tous les segments d'un coup.

### Assignation individuelle

Le tableau affiche chaque segment avec ses paramètres. Vous pouvez modifier individuellement :
- La voix (menu déroulant)
- La langue
- La vitesse (curseur)
- L'instruction émotionnelle

Cliquez sur **Continuer vers la génération** quand tout est prêt.

---

## Étape 5 — Génération des voix

C'est ici que les fichiers audio sont produits par le moteur de synthèse vocale.

### Récapitulatif

Un encadré résume le nombre de segments à générer et les paramètres choisis.

### Choix de la fidélité

- **Production (1.7B)** : meilleure qualité, plus lent (recommandé pour le livrable final)
- **Brouillon (0.6B)** : plus rapide, qualité réduite (pour tester rapidement)

### Échantillon rapide

Cliquez sur **Échantillon (3 étapes)** pour générer seulement 3 segments et vérifier le résultat avant de lancer la production complète.

### Lancer la production

1. Cliquer sur **Lancer la production**
2. La barre de progression montre l'avancement segment par segment
3. Le **journal de génération** affiche le détail en temps réel

La génération peut prendre plusieurs minutes selon le nombre de segments. Vous pouvez fermer l'onglet et revenir plus tard — la progression est conservée.

### Écouter les résultats

Les fichiers audio apparaissent dans une liste avec un lecteur intégré pour chaque segment. Vous pouvez réécouter, comparer et relancer un segment individuel si nécessaire.

### En cas d'interruption

Les fichiers déjà générés sont conservés. Un bouton **Reprendre la génération** permet de continuer là où vous vous étiez arrêté.

Cliquez sur **Continuer vers l'export** quand tous les segments sont générés.

---

## Étape 6 — Export final

Dernière étape : le post-traitement audio et le téléchargement du pack final.

### Paramètres audio

| Paramètre | Défaut | Description |
|-----------|--------|-------------|
| Normaliser le volume | Oui | Niveau sonore constant entre les fichiers |
| Convertir en stéréo | Oui | Son sur les deux canaux, plus naturel |
| Fréquence d'échantillonnage | 48 kHz (standard pro) | Aussi disponible : 24 kHz (original), 44.1 kHz (CD) |
| Profondeur de bits | 24 bits | Aussi disponible : 16 bits |

### Narration unique (optionnel)

Cochez **Créer un fichier audio unique** pour concaténer tous les segments en un seul fichier WAV. Réglez le **silence entre les étapes** (0.1 à 3.0 secondes, défaut 1.0 seconde).

### Préparer et télécharger

1. Cliquer sur **Préparer le pack ZIP**
2. La barre de progression montre le post-traitement (normalisation, conversion, concaténation)
3. Quand c'est prêt, une carte de téléchargement apparaît

Le ZIP contient :
- `audio/*.wav` — les fichiers unitaires post-traités
- `narration-complete.wav` — le fichier unique (si activé)
- `SCRIPT_PAROLES.md` — les textes finaux
- `EQUIVALENCES.md` — la traçabilité technique

---

## Fonctionnalités transversales

### Nouvelle session

Cliquez sur le bouton **Nouvelle session** (icône +) en haut à droite pour repartir de zéro. Une confirmation vous sera demandée — les données de la session en cours ne seront plus accessibles.

### Paramètres d'affichage

Cliquez sur l'icône de contraste en haut à droite (ou dans le pied de page) pour basculer entre :
- **Thème clair**
- **Thème sombre**
- **Système** (suit les préférences de votre appareil)

### État des services

En bas de page, le lien **État des services** ouvre une modale affichant la santé de chaque composant : moteur TTS, authentification, base de données, outils audio.

### Navigation au clavier

OmniStudio est accessible au clavier :

| Action | Touche |
|--------|--------|
| Aller au contenu principal | **Tab** puis **Entrée** sur « Contenu » (lien d'évitement) |
| Naviguer entre les onglets | **Flèche gauche / droite** quand un onglet est sélectionné |
| Activer un bouton | **Entrée** ou **Espace** |
| Ouvrir un accordéon | **Entrée** ou **Espace** sur le titre de l'accordéon |
| Fermer une modale | **Échap** |
| Cocher / décocher | **Espace** sur la case à cocher |

Les lecteurs d'écran sont supportés : tous les éléments interactifs ont des labels accessibles, les zones dynamiques utilisent `aria-live` pour annoncer les changements.

---

## Limites connues

| Limite | Valeur |
|--------|--------|
| Taille maximale d'un fichier importé | 10 Mo |
| Durée audio pour le clonage de voix | 1 à 30 secondes |
| Longueur du nom de voix | 3 à 50 caractères, sans espaces |
| Vitesse de lecture | 0.5x à 2.0x |
| Silence entre segments (export) | 0.1 à 3.0 secondes |
| Génération TTS | 1 segment à la fois (file d'attente automatique) |
| Nettoyage LLM | ~10 segments par minute (limitation du moteur IA) |
| Navigateurs supportés | Chrome, Firefox, Safari, Edge (versions récentes) |

---

## Questions fréquentes

### Mon nettoyage prend du temps, est-ce normal ?

Oui. Chaque segment est traité individuellement par l'IA. Pour un scénario de 50 segments, comptez 5 à 10 minutes. La barre de progression vous montre l'avancement en temps réel.

### La voix générée ne me convient pas

Chaque génération produit un timbre légèrement différent (le modèle est non-déterministe). Cliquez sur **Écouter cette voix** plusieurs fois pour comparer les résultats. Utilisez les **ajustements rapides** (grave, aigu, lent, rapide...) pour affiner.

### J'ai fermé mon navigateur en cours de génération

Pas de panique. OmniStudio conserve votre progression. Reconnectez-vous, revenez sur l'onglet Génération, et un bouton **Reprendre** apparaîtra.

### Le mot parasite en début de phrase

Le moteur TTS peut parfois ajouter un mot au début de la synthèse. Deux solutions :
- Ajoutez un mot de liaison en début de texte (« Ensuite, », « Puis, »)
- Régénérez le segment (chaque génération est différente)

### Comment ajouter un utilisateur ?

Contactez votre administrateur. Les comptes sont gérés dans Keycloak (authentification centralisée).

### L'instruction émotionnelle est grisée

L'instruction émotionnelle n'est disponible que pour les voix **natives** (Serena, Vivian, Dylan...). Les voix personnalisées et clonées utilisent le prompt vocal défini lors de leur création.
