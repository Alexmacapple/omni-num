# language: fr
# PRD de rattachement : PRD-MIGRATION-004-ASSIGN-GENERATE-EXPORT (onglet 6)

Fonctionnalité: Export de la production vocale finalisée
  En tant que producteur de contenu
  Je veux post-traiter et exporter ma production en ZIP
  Afin de la livrer ou la publier

  Contexte:
    Soit un producteur sur l'onglet Export avec 30 WAV générés

  Scénario: Post-traitement audio avec paramètres par défaut  # ◆
    Quand il clique sur "Préparer le pack ZIP" avec les paramètres par défaut
    Alors chaque WAV est normalisé (-3 dB), converti en stéréo, 48 kHz, 24 bits
    Et les fichiers sont sauvegardés dans export/{thread_id}/audio/

  Scénario: Concaténation en narration unique  # ◆
    Soit la case "Créer fichier unique" cochée avec 1.5s de silence
    Quand le pack ZIP est préparé
    Alors un fichier narration-complete.wav est créé
    Et chaque étape est séparée par 1.5 seconde de silence

  Scénario: Téléchargement du pack ZIP complet  # ◆
    Quand le post-traitement est terminé
    Alors un fichier ZIP est proposé au téléchargement
    Et il contient : audio/*.wav, narration-complete.wav, SCRIPT_PAROLES.md, EQUIVALENCES.md

  Scénario: Contenu du document EQUIVALENCES.md  # ◆
    Quand le ZIP est généré
    Alors EQUIVALENCES.md contient pour chaque étape :
      l'ID, la voix assignée, la vitesse, l'instruction éventuelle et la durée audio

  Scénario: Fallback SoX vers ffmpeg  # ◆
    Soit SoX indisponible sur le système
    Quand le post-traitement démarre
    Alors ffmpeg est utilisé en fallback
    Et les paramètres (normalisation, stéréo, rate, profondeur) sont appliqués via ffmpeg

  Scénario: Export sans post-traitement (copie brute)  # ◇
    Soit aucun outil audio disponible (ni SoX ni ffmpeg)
    Quand le pack ZIP est préparé
    Alors les WAV sont copiés tels quels (PCM 16 bits, mono, 24 kHz)
    Et un avertissement indique l'absence de post-traitement

  Plan du Scénario: Configuration du post-traitement  # ◆
    Quand il décoche "<option>"
    Alors le post-traitement "<effet>" n'est pas appliqué

    Exemples:
      | option      | effet                    |
      | Normaliser  | gain -3 dB               |
      | Stéréo      | conversion mono vers stéréo |
