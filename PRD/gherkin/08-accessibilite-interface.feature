# language: fr
# PRD de rattachement : Transversal (PRD-001 à PRD-004)

Fonctionnalité: Accessibilité de l'interface OmniStudio
  En tant que producteur en situation de handicap visuel
  Je veux utiliser OmniStudio avec un lecteur d'écran
  Afin de produire du contenu vocal de manière autonome

  Scénario: Navigation complète au clavier  # ◆
    Soit un producteur naviguant uniquement au clavier
    Quand il parcourt les 6 onglets avec Tab et les flèches
    Alors chaque élément interactif reçoit le focus dans l'ordre visuel
    Et le focus est toujours visible (outline DSFR)

  Scénario: Annonce des mises à jour SSE par le lecteur d'écran  # ◆
    Soit le nettoyage LLM en cours
    Quand une étape est nettoyée
    Alors le message de progression est annoncé via aria-live="polite"
    Et les heartbeats ne déclenchent pas d'annonce

  Scénario: Lecteurs audio avec labels accessibles  # ◆
    Quand un audio de pré-écoute est proposé
    Alors le lecteur utilise <audio controls> natif
    Et un aria-label indique "Écoute de l'étape N, voix Lea"
    Et une légende visible complète l'information

  Scénario: Tableaux sémantiques avec en-têtes de colonnes  # ◆
    Quand le tableau des étapes est affiché
    Alors il utilise <table> avec <thead>, <th scope="col">, <caption>
    Et chaque checkbox a un label sr-only "Sélectionner étape N"

  Scénario: Diff accessible sans dépendance à la couleur seule  # ◆
    Quand le diff entre texte original et TTS est affiché
    Alors les suppressions ont text-decoration: line-through en plus de la couleur
    Et un lecteur d'écran distingue les insertions des suppressions

  Scénario: Tableaux responsives avec scroll clavier  # ◇
    Soit un écran de 320px de large
    Quand le tableau dépasse la largeur disponible
    Alors un scroll horizontal est disponible via tabindex="0"
    Et un aria-label indique "Tableau des étapes, défilable horizontalement"

  # --- Fil d'Ariane ---

  Scénario: Fil d'Ariane DSFR synchronisé avec le routage URL  # ◆
    Quand le producteur navigue vers l'onglet Préparation (#clean)
    Alors le fil d'Ariane affiche "OmniStudio > Préparation"
    Et le dernier élément porte aria-current="page"
    Et le composant utilise la structure DSFR (nav, ol, fr-breadcrumb)

  Scénario: Fil d'Ariane avec sous-onglets Voix  # ◆
    Quand le producteur navigue vers #voices/design
    Alors le fil d'Ariane affiche "OmniStudio > Voix > Créer"
    Et "OmniStudio" et "Voix" sont des liens cliquables
    Et "Créer" porte aria-current="page"

  Scénario: Journal de génération accessible  # ◆
    Soit la génération batch en cours
    Quand un événement SSE (batch_start, heartbeat, progress) arrive
    Alors le journal affiche l'horodatage et le message
    Et la zone est annoncée par le lecteur d'écran (role="log" aria-live="polite")
    Et les erreurs sont visuellement distinctes (couleur + texte)

  # --- Dark mode (composant fr-display DSFR natif) ---

  Scénario: Ouverture des paramètres d'affichage depuis le header  # ◆
    Quand il clique sur le bouton d'affichage (icône contraste) dans le header
    Alors la modale DSFR "Paramètres d'affichage" s'ouvre
    Et trois options sont proposées : Thème clair, Thème sombre, Système
    Et le composant utilise fr-display avec fr-radio-rich

  Scénario: Basculement en thème sombre via fr-display  # ◆
    Quand il sélectionne "Thème sombre" dans les paramètres d'affichage
    Alors data-fr-scheme passe à "dark" sur <html>
    Et tous les tokens DSFR (couleurs, fonds, bordures) basculent en sombre
    Et le choix est persisté dans localStorage sous la clé "scheme"

  Scénario: Persistance du thème après rechargement  # ◆
    Soit le thème sombre activé via fr-display
    Quand il recharge la page (F5)
    Alors le thème sombre est restauré sans flash blanc
    Et le script theme-init.js lit la clé DSFR "scheme" avant le rendu CSS

  Scénario: Bouton paramètres d'affichage dans le footer  # ◆
    Quand il clique sur "Paramètres d'affichage" dans le footer
    Alors la même modale fr-display s'ouvre
    Et le lien est conforme à l'obligation DSFR (fr-footer__bottom-link)
