# language: fr
# Origine : Retours utilisateurs (session feedback)
# PRD de rattachement : voir annotations par scénario

# --- MUST : Persistance des variantes Voice Design (bug UX) ---
# PRD-003 — Le state LangGraph stocke wav_paths, mais le front Gradio ne les rechargeait pas.
# En DSFR, l'onglet Voix doit relire wav_paths depuis le state à chaque activation.

Fonctionnalité: Persistance des variantes Voice Design lors de la navigation
  En tant que producteur de contenu
  Je veux que mes variantes vocales survivent à la navigation entre onglets
  Afin de ne pas perdre mon exploration vocale

  Scénario: Les variantes Voice Design persistent quand on navigue vers un autre onglet  # ◆ MUST
    Soit 3 variantes vocales générées dans le sous-onglet Voice Design
    Quand le producteur navigue vers l'onglet Script puis revient sur l'onglet Voix
    Alors les 3 variantes sont toujours affichées avec leurs lecteurs audio
    Et la voix verrouillée (si existante) reste marquée comme telle

  Scénario: Les variantes persistent après verrouillage d'une voix  # ◆ MUST
    Soit 3 variantes générées et la variante 2 verrouillée
    Quand le producteur clique sur le sous-onglet Voice Design
    Alors les 3 variantes sont visibles
    Et la variante 2 porte le badge "Verrouillée" (vert)
    Et les variantes 1 et 3 restent écoutable pour comparaison

  Scénario: Les variantes sont rechargées depuis le state LangGraph  # ◆ MUST
    Soit des variantes générées dans une session précédente (wav_paths dans le state)
    Quand le producteur reprend sa session et ouvre l'onglet Voix
    Alors les variantes sont reconstituées depuis wav_paths
    Et les fichiers WAV sont toujours sur le disque (voice/{thread_id}/)

# --- SHOULD : Saisie directe de texte (sans upload fichier) ---
# PRD-002 — Ajouter une alternative à l'upload : textarea de saisie libre.

Fonctionnalité: Saisie directe de texte sans fichier
  En tant que producteur de contenu
  Je veux coller ou saisir un texte directement dans l'application
  Afin de ne pas créer un fichier Excel ou Markdown pour un texte court

  Scénario: Import par collage de texte brut  # ◆ SHOULD
    Soit un producteur sur l'onglet Import
    Quand il choisit le mode "Saisie directe" au lieu de "Fichier"
    Et il colle un texte de 500 mots dans le textarea
    Et il clique sur "Importer les étapes"
    Alors le texte est découpé en étapes (une par paragraphe ou par ligne non vide)
    Et le tableau des étapes s'affiche comme pour un import fichier

  Scénario: Validation du texte saisi (minimum requis)  # ◆ SHOULD
    Quand il saisit un texte de moins de 10 caractères
    Alors un message indique que le texte est trop court pour générer des étapes

# --- SHOULD : Passer le nettoyage LLM (conserver texte tel quel) ---
# PRD-002 — Le bouton "Valider tous" existe mais force le passage par l'onglet.
# Ajouter un raccourci "Utiliser les textes originaux" qui skip le nettoyage.

Fonctionnalité: Conservation du texte original sans nettoyage LLM
  En tant que producteur de contenu
  Je veux utiliser mes textes tels quels sans passer par le nettoyage IA
  Afin de garder ma formulation exacte pour la synthèse vocale

  Scénario: Skip du nettoyage avec conservation du texte original  # ◆ SHOULD
    Soit un producteur sur l'onglet Préparation avec 10 étapes importées
    Quand il clique sur "Utiliser les textes originaux"
    Alors chaque text_tts est copié depuis text_original
    Et toutes les étapes passent en statut "validated"
    Et le bouton "Continuer" devient actif
    Et aucun appel LLM n'est effectué

# --- COULD : Import Word (.docx) ---
# Non prévu dans PRD-001 à 005. Demande utilisateur récurrente.

Fonctionnalité: Import d'un fichier Word
  En tant que producteur de contenu
  Je veux charger un fichier Word (.docx)
  Afin de réutiliser mes documents existants sans conversion manuelle

  Scénario: Import d'un fichier Word avec extraction du texte  # ◇ COULD
    Soit un producteur sur l'onglet Import
    Quand il sélectionne un fichier .docx
    Alors le texte est extrait (paragraphes, sans mise en forme)
    Et les étapes sont créées comme pour un fichier Markdown

# --- COULD : Réglage de tessiture (pitch) ---
# Non prévu. k2-fsa OmniVoice ne supporte pas le pitch nativement.
# Possible en post-traitement SoX (pitch shift) mais dégrade la qualité.

Fonctionnalité: Réglage de tessiture vocale
  En tant que producteur de contenu
  Je veux ajuster la tessiture (grave/aigu) d'une voix
  Afin d'obtenir le timbre exact souhaité

  Scénario: Ajustement du pitch via post-traitement  # ◇ COULD
    Soit une étape assignée à la voix Lea
    Quand le producteur règle la tessiture à -2 demi-tons
    Alors le post-traitement applique un pitch shift au WAV généré
    Et la voix sonne plus grave sans distorsion perceptible

# --- COULD : Voix favorites (distinct du verrouillage) ---
# PRD-003 couvre le verrouillage (persistance technique).
# Les favoris = marquage UX pour retrouver rapidement ses voix préférées.

Fonctionnalité: Marquage de voix favorites
  En tant que producteur de contenu
  Je veux marquer certaines voix comme favorites
  Afin de les retrouver rapidement dans la bibliothèque

  Scénario: Ajout d'une voix aux favoris  # ◇ COULD
    Quand il clique sur l'étoile à côté de la voix "narrateur-dynamique"
    Alors la voix est marquée comme favorite
    Et elle apparaît en premier dans la liste de la bibliothèque

  Scénario: Persistance des favoris entre sessions  # ◇ COULD
    Soit 3 voix marquées comme favorites
    Quand le producteur se reconnecte
    Alors les 3 voix favorites sont toujours en tête de liste
