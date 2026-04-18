# language: fr
# PRD de rattachement : PRD-MIGRATION-001 (SSE) + PRD-MIGRATION-002 (sauvegarde incrémentale)

Fonctionnalité: Résilience face aux interruptions
  En tant que producteur de contenu
  Je veux que mon travail survive aux coupures
  Afin de ne jamais perdre ma progression

  Scénario: Sauvegarde incrémentale pendant le nettoyage SSE  # ◆
    Soit le nettoyage en cours (étape 35 sur 42)
    Quand la connexion est coupée à l'étape 35
    Alors les 35 premières étapes sont sauvegardées (batch toutes les 5 étapes)
    Et au maximum 4 étapes sont perdues

  Scénario: Reprise de session avec le thread_id précédent  # ◇
    Soit un producteur qui a fermé son navigateur hier
    Quand il ouvre OmniStudio et choisit "Reprendre"
    Alors le thread_id précédent est restauré depuis localStorage
    Et l'état LangGraph est lu depuis le checkpoint SQLite
    Et l'onglet correspondant à sa dernière position s'active

  Scénario: OmniVoice redémarré en cours de session  # ◇
    Soit OmniVoice tombé et relancé pendant une session
    Quand le producteur tente une action TTS
    Alors le health check détecte la disponibilité
    Et l'action est exécutée normalement
    Et les voix custom sont toujours disponibles (persistées sur disque)
