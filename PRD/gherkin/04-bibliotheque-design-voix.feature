# language: fr
# PRD de rattachement : PRD-MIGRATION-003-VOIX

Fonctionnalité: Exploration et création de voix
  En tant que producteur de contenu
  Je veux explorer, créer et verrouiller des voix
  Afin de disposer d'identités vocales reproductibles pour ma production

  Contexte:
    Soit un producteur sur l'onglet Voix avec OmniVoice opérationnel

  # --- Bibliothèque ---

  Scénario: Chargement automatique de la bibliothèque au clic sur l'onglet Voix
    Quand il navigue vers l'onglet Voix
    Alors la bibliothèque affiche les voix natives (9) et custom (N)
    Et chaque carte affiche le nom, le type (Native / Personnalisée) et un bouton Écouter
    Et toutes les voix sont sélectionnables pour l'assignation

  Scénario: Rafraîchissement manuel de la bibliothèque
    Quand il clique sur "Actualiser"
    Alors la liste des voix est rechargée depuis OmniVoice
    Et le compteur "X voix disponibles" est mis à jour

  Scénario: Écoute d'une voix native
    Quand il clique sur "Écouter" à côté de la voix Lea
    Alors un audio de test est généré via /preset
    Et un lecteur audio accessible apparaît sous la carte

  Scénario: Suppression d'une voix custom non assignée
    Soit une voix custom "narrateur-projet-alpha" non utilisée
    Quand il clique sur "Supprimer"
    Et il confirme dans la boîte de dialogue
    Alors la voix est retirée de OmniVoice
    Et elle disparaît de la liste

  Scénario: Renommage d'une voix custom
    Soit une voix custom "narrateur-v1" dans la bibliothèque
    Quand il clique sur "Renommer" et saisit "narrateur-officiel"
    Alors la voix est renommée dans OmniVoice (dossier + meta.json)
    Et les assignations utilisant cette voix sont mises à jour
    Et la bibliothèque affiche le nouveau nom

  Scénario: Refus du renommage avec un nom invalide
    Quand il tente de renommer une voix avec le nom "ab"
    Alors le renommage est refusé avec un message d'erreur
    Et la voix conserve son nom original

  Scénario: Refus du renommage avec un nom déjà existant
    Soit une voix "voix-a" et une voix "voix-b"
    Quand il tente de renommer "voix-a" en "voix-b"
    Alors le renommage est refusé (erreur 409 nom existant)

  Scénario: Protection contre la suppression d'une voix assignée
    Soit une voix "narrateur-projet-alpha" assignée à 5 étapes
    Quand il tente de la supprimer
    Alors un avertissement indique que la voix est utilisée par 5 étapes
    Et la suppression est bloquée (erreur 409)

  Scénario: Sélection de voix pour pré-assignation
    Quand il clique sur la checkbox de 2 voix
    Alors un résumé affiche "2 voix sélectionnées"
    Et au passage à l'onglet Assignation la première voix est pré-assignée

  # --- Onglet Créer : parcours en 3 étapes ---

  Scénario: Affichage du parcours guidé en 3 étapes
    Quand il ouvre le sous-onglet Créer
    Alors un stepper DSFR indique "Étape 1 sur 3 — Décrire la voix"
    Et deux options sont proposées : profils prédéfinis ou composition IA

  Scénario: Création rapide via un profil prédéfini
    Quand il clique sur "Narratrice pédagogique" dans le callout prédéfini
    Alors le champ description de voix est pré-rempli et visible
    Et la page scrolle vers le champ avec focus
    Et l'étape 2 (Écouter et ajuster) devient visible
    Et il peut modifier la description avant d'écouter

  Scénario: Création personnalisée via le brief IA
    Quand il ouvre l'accordéon "Ou composer depuis zéro avec l'IA"
    Et il remplit le brief (contexte, émotion, genre, âge)
    Et il clique sur "Générer la description avec l'IA"
    Alors le LLM produit une instruction vocale de 25 à 50 mots
    Et le champ description est pré-rempli et éditable

  Scénario: Écoute et itération (Étape 2)
    Soit une description de voix rédigée (étape 1 terminée)
    Quand il clique sur "Écouter cette voix"
    Alors un audio est généré et jouable
    Et un avertissement indique que le timbre varie à chaque génération
    Et il peut "Régénérer l'audio" pour explorer des variantes

  Scénario: Enregistrement de la voix (Étape 3)
    Soit un audio satisfaisant (étape 2 terminée)
    Quand il saisit un nom valide et clique sur "Enregistrer"
    Alors la voix est sauvegardée dans OmniVoice (source=design)
    Et un test de stabilité confirme la reproductibilité
    Et la voix apparaît dans la bibliothèque comme "Personnalisée"

  Plan du Scénario: Refus des noms de voix invalides
    Quand il saisit le nom "<nom>" pour verrouiller une voix
    Alors le verrouillage est refusé avec le message "<raison>"

    Exemples:
      | nom     | raison                          |
      | ab      | Nom trop court (minimum 3)      |
      | serena  | Nom réservé par le système      |
      | vivian  | Nom réservé par le système      |

  # --- Clonage vocal ---

  Scénario: Clonage d'une voix à partir d'un fichier audio uploadé
    Soit un fichier WAV de 15 secondes et sa transcription exacte
    Quand il remplit le nom, uploade l'audio et saisit la transcription
    Et il clique sur "Créer le clone"
    Alors la voix est créée dans OmniVoice (source=clone)
    Et un test immédiat génère un audio de vérification
    Et la voix apparaît dans la bibliothèque comme "Personnalisée"

  Scénario: Clonage d'une voix à partir d'un enregistrement micro
    Quand il clique sur "Enregistrer" et parle pendant 10 secondes
    Et il clique sur "Arrêter"
    Alors un aperçu audio avec durée est affiché
    Et il peut écouter son enregistrement avant de soumettre

  Scénario: Refus d'un audio trop court pour le clonage
    Quand il enregistre un audio de 0.5 seconde
    Alors le clonage est refusé
    Et un message indique la durée minimale requise (1 seconde)
