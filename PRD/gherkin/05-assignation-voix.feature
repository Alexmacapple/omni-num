# language: fr
# PRD de rattachement : PRD-MIGRATION-004-ASSIGN-GENERATE-EXPORT (onglet 4)

Fonctionnalité: Assignation des voix aux étapes du scénario
  En tant que producteur de contenu
  Je veux attribuer une voix, une langue et une vitesse à chaque étape
  Afin de personnaliser la lecture de chaque partie du scénario

  Contexte:
    Soit un producteur sur l'onglet Assignation
    Et 30 étapes validées avec textes TTS
    Et 3 voix disponibles (Lea native, narrateur-dynamique custom, Paul native)

  Scénario: Assignation d'une voix native avec instruction émotionnelle  # ◆
    Quand il sélectionne la voix Lea pour l'étape 1
    Et il saisit l'instruction "Ton chaleureux et rassurant"
    Et il choisit la langue "fr" et la vitesse 1.0
    Alors l'étape 1 est assignée avec voix=Lea, instruction, langue=fr, vitesse=1.0

  Scénario: Assignation d'une voix custom sans instruction  # ◆
    Quand il sélectionne la voix "narrateur-dynamique" (custom) pour l'étape 2
    Alors le champ instruction est désactivé (grisé)
    Et l'assignation se fait sans instruction émotionnelle

  Scénario: Application d'une voix à toutes les étapes  # ◆
    Quand il sélectionne Paul et clique sur "Appliquer à toutes les étapes"
    Alors les 30 étapes sont assignées à Paul
    Et les paramètres (langue, vitesse) sont copiés uniformément

  Scénario: Pré-écoute d'une étape assignée  # ◆
    Soit l'étape 5 assignée à Lea avec instruction "Ton énergique"
    Quand il clique sur "Écouter" pour l'étape 5
    Alors un WAV est généré via /preset/instruct
    Et un lecteur audio accessible permet l'écoute

  Scénario: Ajustement de la vitesse pour une étape spécifique  # ◆
    Quand il déplace le curseur de vitesse à 0.8 pour l'étape 10
    Alors le speed_factor de l'étape 10 passe à 0.8
    Et la pré-écoute reflète la nouvelle vitesse

  Scénario: Continuation vers la génération  # ◆
    Soit toutes les étapes assignées à au moins une voix
    Quand il clique sur "Confirmer et continuer"
    Alors les assignations sont sauvegardées dans LangGraph
    Et l'onglet Génération s'active avec un récapitulatif

  Scénario: Changement de langue pour une production multilingue  # ◇
    Quand il sélectionne la langue "en" pour les étapes 20 à 25
    Alors le language_override de ces étapes passe à "en"
    Et la synthèse vocale utilisera le modèle anglais de k2-fsa OmniVoice
