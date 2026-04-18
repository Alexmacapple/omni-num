# language: fr
Fonctionnalité: Tags émotionnels et accents/dialectes OmniVoice
  En tant qu'utilisateur d'OmniStudio
  Je veux enrichir mes audios avec des marqueurs non-verbaux et des accents localisés
  Afin de produire du contenu plus naturel et localisé

  Scénario: Insertion d'un tag [laughter] via la palette
    Étant donné qu'Alex est dans l'onglet 3 et tape un texte dans un textarea
    Quand Alex clique sur le bouton "[laughter]" de la palette
    Alors le tag "[laughter]" est inséré à la position du curseur
    Et des espaces sont ajoutés autour si nécessaire (pas de double espace)

  Scénario: Palette tags accessible clavier
    Étant donné qu'Alex navigue au clavier sur la palette
    Quand Alex utilise Tab + Entrée
    Alors chaque bouton de tag est focusable avec un aria-label explicite

  Scénario: Voice Design mode Guidé avec accent British
    Étant donné qu'Alex est dans l'onglet 3 Create Voice mode Guidé
    Et que Alex a sélectionné Genre=Female, Âge=Adulte, Hauteur=Moyenne, Style=Neutre
    Et que la langue sélectionnée est "en"
    Quand Alex sélectionne English Accent = British
    Alors la chaîne composée côté backend contient "british"
    Et la voix générée a un accent britannique audible

  Scénario: Accent anglais désactivé si langue française
    Étant donné qu'Alex a sélectionné language="fr"
    Quand l'UI affiche les selects Design
    Alors le select "English Accent" est disabled avec aria-hidden="true"

  Scénario: Dialecte chinois mappé vers caractères
    Étant donné qu'Alex est dans l'onglet 3, language="zh", dialect="Sichuan"
    Quand la chaîne est composée côté backend
    Alors "四川话" est envoyé à OmniVoice (pas "Sichuan Dialect")

  Scénario: Voice Design mode Expert rejette le français
    Étant donné qu'Alex est dans mode Expert
    Quand Alex tape "femme jeune avec voix aiguë" dans le champ EN
    Alors OmniVoice retourne 422
    Et un toast DSFR affiche « La description contient des mots non reconnus par OmniVoice »
