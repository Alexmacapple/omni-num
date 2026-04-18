# language: fr
# PRD de rattachement : PRD-MIGRATION-004-ASSIGN-GENERATE-EXPORT (onglet 5)

Fonctionnalité: Génération batch de la production vocale
  En tant que producteur de contenu
  Je veux lancer la synthèse vocale de toutes les étapes
  Afin d'obtenir les fichiers audio de ma production

  Contexte:
    Soit un producteur sur l'onglet Génération
    Et 30 étapes assignées (20 à Lea, 10 à Paul)

  Scénario: Récapitulatif avant génération  # ◆
    Quand l'onglet Génération se charge
    Alors un résumé affiche : 30 étapes, 2 voix distinctes, modèle sélectionné
    Et une estimation du temps de génération apparaît

  Scénario: Test rapide sur 3 étapes échantillons  # ◆
    Quand il clique sur "Tester (3 étapes)"
    Alors 3 étapes sont sélectionnées (première, milieu, dernière)
    Et 3 WAV sont générés et proposés à l'écoute
    Et le producteur valide la qualité avant la production complète

  Scénario: Production batch avec progression SSE  # ◆
    Quand il clique sur "Produire et exporter"
    Alors les étapes sont groupées par voix/langue/vitesse
    Et les lots sans instruction passent par /batch/preset (parallèle)
    Et les étapes avec instruction passent par /preset/instruct (séquentiel)
    Et une barre de progression SSE affiche "Génération étape N (n/30)..."
    Et chaque WAV généré apparaît dans une grille audio

  Scénario: Choix du modèle de fidélité  # ◆
    Quand il sélectionne "Brouillon (0.6B)" au lieu de "Production (1.7B)"
    Alors la génération est plus rapide mais de qualité moindre
    Et le modèle utilisé est affiché dans le récapitulatif

  Scénario: Reprise après échec sur une étape  # ◇
    Soit la génération interrompue à l'étape 18 (timeout OmniVoice)
    Quand il relance la génération
    Alors seules les étapes sans WAV généré sont retraitées
    Et les 17 WAV déjà produits sont conservés

  Scénario: Pré-écoute individuelle pendant la génération  # ◆
    Soit l'étape 5 déjà générée
    Quand il clique sur le lecteur audio de l'étape 5
    Alors il écoute le WAV produit
    Et il peut décider de régénérer cette étape spécifique

  # --- Protection contre les appels concurrents ---

  Scénario: Rejet d'un second appel de génération simultané  # ◆
    Soit une génération en cours depuis 5 secondes
    Quand un second appel POST /api/generate arrive avec force=true
    Alors le verrou récent (< 30s) est conservé
    Et le second appel reçoit une erreur 409 "génération déjà en cours"
    Et la première génération continue sans interruption

  Scénario: Libération forcée d'un verrou orphelin  # ◆
    Soit un verrou de génération bloqué depuis 2 minutes (connexion perdue)
    Quand le producteur relance la génération avec force=true
    Alors le verrou ancien (> 30s) est libéré automatiquement
    Et la nouvelle génération démarre normalement

  Scénario: Garde frontend contre la double soumission  # ◆
    Soit le bouton "Produire" cliqué une première fois
    Quand un second clic survient avant la fin de la génération
    Alors le second appel est ignoré côté client (isGenerating=true)
    Et aucune requête HTTP supplémentaire n'est envoyée
