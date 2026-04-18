# language: fr
# PRD de rattachement : PRD-MIGRATION-002-IMPORT-PREPARATION (onglet 2)

Fonctionnalité: Préparation des textes pour la synthèse vocale
  En tant que producteur de contenu
  Je veux que l'IA nettoie et optimise mes textes pour le TTS
  Afin d'obtenir une lecture vocale fluide et naturelle

  Contexte:
    Soit un producteur sur l'onglet Préparation avec 42 étapes importées

  Scénario: Nettoyage LLM avec suivi en temps réel  # ◆
    Quand il clique sur "Lancer le nettoyage LLM"
    Alors une barre de progression SSE s'affiche
    Et chaque étape nettoyée met à jour le tableau incrémentalement
    Et un message indique "Nettoyage étape N (n/42)..."

  Scénario: Pause rate-limit avec heartbeats  # ◆
    Soit le nettoyage en cours (étape 10 sur 42)
    Quand la 9e requête LLM est envoyée
    Alors une pause de 60 secondes démarre
    Et des heartbeats SSE maintiennent la connexion toutes les 15 secondes
    Et un message indique "Pause rate-limit (60s)..."

  Scénario: Fallback sans IA quand le LLM est injoignable  # ◆
    Soit le LLM Albert injoignable
    Quand le nettoyage d'une étape échoue
    Alors le texte est corrigé par les règles structurelles (Layer A)
    Et l'événement SSE progress contient le texte fallback
    Et le compteur de fallback est incrémenté

  Scénario: Glossaire phonétique appliqué au nettoyage  # ◆
    Soit le glossaire rempli avec "DN = Démarches Numériques"
    Quand le nettoyage traite un texte contenant "DN"
    Alors le prompt LLM inclut le glossaire
    Et le texte TTS contient "Démarches Numériques" au lieu de "DN"

  Scénario: Édition manuelle d'un texte TTS dans le tableau  # ◆
    Soit le nettoyage terminé
    Quand le producteur modifie le texte TTS d'une étape dans le textarea
    Alors la modification est conservée localement
    Et le SSE ne remplace pas un textarea en cours d'édition

  Scénario: Comparaison diff entre texte original et TTS  # ◆
    Quand il clique sur "Voir le diff" pour une étape
    Alors l'accordéon de comparaison s'ouvre
    Et les suppressions sont barrées (text-decoration + couleur)
    Et les insertions sont surlignées (couleur différente)

  Scénario: Validation individuelle d'une étape  # ◆
    Quand il clique sur "Accepter" pour l'étape 3
    Alors le badge passe à "Validé" (vert)
    Et le texte TTS éventuellement modifié est sauvegardé

  Scénario: Validation globale de tous les textes  # ◆
    Soit au moins une étape avec un texte TTS
    Quand il clique sur "Valider tous les textes"
    Alors toutes les étapes passent en statut "validated"
    Et les éditions manuelles sont transmises au serveur
    Et le bouton "Continuer" devient actif
    Et le graphe LangGraph est positionné après finalize_clean

  Scénario: Suppression de tous les segments  # ◆
    Soit 42 segments importés dans le tableau
    Quand il clique sur "Supprimer tous les segments"
    Et il confirme dans la boîte de dialogue
    Alors tous les segments sont supprimés du serveur
    Et le tableau disparaît
    Et le titre "Aperçu des segments" est masqué
    Et les boutons "Valider" et "Supprimer tous" deviennent inactifs

  Scénario: Interruption SSE et reprise du nettoyage  # ◆
    Soit le nettoyage en cours (étape 25 sur 42)
    Quand la connexion réseau est coupée
    Alors le front affiche une alerte "Nettoyage interrompu"
    Et un bouton "Reprendre" apparaît
    Et les étapes déjà traitées sont conservées (sauvegarde incrémentale)

  Scénario: Reprise du nettoyage après interruption  # ◆
    Soit 25 étapes déjà nettoyées et sauvegardées
    Quand il clique sur "Reprendre le nettoyage"
    Alors seules les 17 étapes restantes (non validées) sont traitées
    Et la progression reprend à 25/42

  Scénario: Protection contre le double lancement du nettoyage  # ◆
    Soit un nettoyage SSE en cours
    Quand un second appel POST /api/clean est émis sur la même session
    Alors le serveur retourne CLEAN_IN_PROGRESS
    Et le front affiche "Un nettoyage est déjà en cours"

  Scénario: Structure accessible de l'onglet Préparation  # ◆
    Quand l'onglet Préparation se charge avec des segments
    Alors le titre principal est "Préparation des textes" (h2)
    Et la section "Ajouter un segment" est identifiée par un titre h3
    Et la section "Aperçu des segments" est identifiée par un titre h3
    Et le tableau a une légende visible décrivant son contenu
    Et les colonnes "Texte original" et "Texte TTS" ont la même largeur

  Scénario: Auto-sauvegarde en quittant l'onglet  # ◆
    Soit des textes TTS modifiés manuellement dans le tableau
    Quand le producteur navigue vers l'onglet Voix
    Alors les modifications sont sauvegardées automatiquement sur le serveur
    Et l'événement tab-deactivated déclenche la persistance
