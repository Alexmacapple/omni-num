# language: fr
Fonctionnalité: Sous-titres SRT automatiques
  En tant qu'utilisateur d'OmniStudio
  Je veux générer des sous-titres en même temps que mon audio
  Afin de livrer du contenu vidéo accessible RGAA

  Scénario: Export avec sous-titres cochés
    Étant donné qu'Alex a généré 3 étapes d'audio
    Quand Alex coche « Inclure les sous-titres SRT » et envoie POST /api/export
    Alors le ZIP contient le dossier "subtitles/"
    Et chaque étape a 6 fichiers : .srt, _word.srt, _shorts.srt, _multiline.srt, .txt, .json

  Scénario: Export sans sous-titres
    Étant donné qu'Alex a généré 3 étapes d'audio
    Quand Alex décoche « Inclure les sous-titres » et envoie POST /api/export
    Alors le ZIP ne contient PAS de dossier "subtitles/"

  Scénario: Chunking d'un audio de 10 minutes
    Étant donné qu'Alex a généré un audio de 600 secondes en français
    Quand les sous-titres standards sont générés
    Alors aucun chunk ne dépasse 8 secondes de durée
    Et aucun chunk ne dépasse 3 lignes
    Et aucune ligne ne dépasse 42 caractères

  Scénario: Langue non supportée par Whisper
    Étant donné qu'Alex a généré un audio en haoussa (langue hors des ~99 supportées par Whisper)
    Quand l'export avec sous-titres est lancé
    Alors les sous-titres pour cette étape sont omis (skip propre)
    Et le manifest.json mentionne l'étape comme "subtitles: skipped (language not supported)"
    Et l'export ne retourne PAS une erreur

  Scénario: Format Shorts vertical
    Étant donné qu'Alex a généré un audio de 30 secondes
    Quand les sous-titres au format Shorts sont générés
    Alors chaque chunk contient 1 ligne max
    Et chaque chunk dure max 3 secondes
    Et chaque ligne fait max 30 caractères
