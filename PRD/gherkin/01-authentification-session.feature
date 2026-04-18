# language: fr
# PRD de rattachement : PRD-MIGRATION-001-ARCHITECTURE

Fonctionnalité: Authentification et gestion de session
  En tant que producteur de contenu
  Je veux me connecter à OmniStudio via Keycloak
  Afin d'accéder à mon espace de production vocale

  Scénario: Connexion réussie avec identifiants Keycloak valides  # ◆
    Soit un utilisateur enregistré dans le realm harmonia (client omnistudio)
    Quand il saisit ses identifiants sur l'écran de login DSFR
    Alors il accède au tableau de bord avec les 6 onglets
    Et un thread_id unique est généré dans localStorage

  Scénario: Refus de connexion avec identifiants invalides  # ◆
    Soit un visiteur sur la page de login
    Quand il saisit des identifiants incorrects
    Alors un message d'erreur DSFR s'affiche
    Et il reste sur l'écran de login

  Scénario: Rafraîchissement automatique du token JWT  # ◆
    Soit un producteur connecté depuis plus de 50 minutes
    Quand le timer de refresh se déclenche avant expiration
    Alors le token est renouvelé silencieusement
    Et la session continue sans interruption

  Scénario: Déconnexion forcée après échec du refresh  # ◆
    Soit un producteur dont le refresh token a expiré
    Quand le rafraîchissement échoue 3 fois consécutives
    Alors le producteur est redirigé vers l'écran de login
    Et un message explique que la session a expiré

  Scénario: Reprise de session après fermeture du navigateur  # ◇
    Soit un producteur qui avait un projet en cours (thread_id en localStorage)
    Quand il ouvre OmniStudio et se reconnecte
    Alors le système propose de reprendre la session précédente
    Et les données LangGraph sont restaurées depuis le checkpoint SQLite

  Scénario: Isolation des sessions entre Harmonia et OmniStudio  # ◆
    Soit un utilisateur connecté simultanément à Harmonia et OmniStudio
    Quand il se déconnecte de OmniStudio
    Alors sa session Harmonia reste active
    Et les refresh tokens des deux clients sont indépendants
