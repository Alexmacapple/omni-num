# language: fr
# PRD de rattachement : PRD-MIGRATION-002-IMPORT-PREPARATION (onglet 1)

Fonctionnalité: Import d'un scénario de production vocale
  En tant que producteur de contenu
  Je veux charger un fichier Excel ou Markdown
  Afin de définir les étapes de ma production vocale

  Contexte:
    Soit un producteur connecté sur l'onglet Import

  Scénario: Import d'un fichier Excel avec détection des onglets  # ◆
    Quand il sélectionne un fichier .xlsx contenant plusieurs onglets
    Alors le sélecteur d'onglet Excel apparaît avec la liste des feuilles
    Et le mode d'import (Remplacer/Ajouter) est proposé

  Scénario: Import d'un fichier Markdown sans options Excel  # ◆
    Quand il sélectionne un fichier .md
    Alors les options Excel restent masquées
    Et le bouton "Importer les étapes" devient actif

  Scénario: Aperçu des étapes après import réussi  # ◆
    Soit un fichier Excel valide sélectionné
    Quand il clique sur "Importer les étapes"
    Alors un tableau affiche chaque étape (ID, Texte Original)
    Et toutes les étapes sont cochées par défaut
    Et le compteur affiche "N/N étapes sélectionnées"

  Scénario: Sélection partielle des étapes à traiter  # ◆
    Soit un tableau de 42 étapes importées
    Quand il décoche les étapes 5, 12 et 38
    Alors le compteur affiche "39/42 étapes sélectionnées"
    Et la checkbox "Tout sélectionner" passe en état indeterminate

  Scénario: Continuation vers la préparation avec les étapes filtrées  # ◆
    Soit 30 étapes sélectionnées sur 42
    Quand il clique sur "Continuer vers la préparation"
    Alors seules les 30 étapes sélectionnées sont conservées dans LangGraph
    Et l'onglet Préparation s'active

  Scénario: Refus de continuer sans aucune étape sélectionnée  # ◆
    Soit toutes les étapes décochées
    Quand il clique sur "Continuer vers la préparation"
    Alors un message d'avertissement demande de sélectionner au moins une étape

  Scénario: Progression visible pendant l'upload d'un fichier volumineux  # ◆
    Quand il uploade un fichier Excel de 5 Mo
    Alors une barre de progression affiche le pourcentage d'upload
    Et la barre disparaît une fois l'import terminé

  Scénario: Rejet d'un fichier au format non supporté  # ◆
    Quand il tente d'uploader un fichier .pdf via manipulation du POST
    Alors le serveur rejette le fichier avant toute écriture disque
    Et un message d'erreur indique les formats acceptés (.xlsx, .md)

  Scénario: Import d'un Excel avec formules non résolues  # ◇
    Quand il importe un fichier Excel contenant des formules =CONCATENER(...)
    Alors openpyxl retourne les valeurs cachées de la dernière évaluation
    Et les cellules jamais évaluées sont ignorées silencieusement

  Scénario: Nettoyage du fichier uploadé après import  # ◆
    Quand l'import se termine (succès ou erreur)
    Alors le fichier temporaire est supprimé de data/uploads/
    Et les données sont uniquement dans le state LangGraph
