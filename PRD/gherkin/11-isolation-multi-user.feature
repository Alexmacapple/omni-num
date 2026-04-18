# language: fr
Fonctionnalité: Isolation multi-utilisateur des voix custom
  En tant qu'utilisateur d'OmniStudio
  Je veux que mes voix custom restent privées
  Afin de ne pas exposer mes données biométriques vocales à d'autres utilisateurs

  Contexte:
    Étant donné que le realm Keycloak "harmonia" contient au moins 2 utilisateurs "alex" et "bob"
    Et que les 6 voix système sont versionnées avec "system: true"

  Scénario: Alex ne voit pas les voix de Bob
    Étant donné qu'Alex est connecté
    Et que Bob a créé une voix "VoixDeBob"
    Quand Alex ouvre l'onglet 3 « Voix »
    Alors Alex voit "MaVoixAlex" et les 6 voix système
    Mais Alex ne voit pas "VoixDeBob"

  Scénario: Alex ne peut pas supprimer une voix de Bob
    Étant donné qu'Alex est connecté
    Et que Bob possède une voix "VoixDeBob"
    Quand Alex envoie DELETE /api/voices/VoixDeBob
    Alors l'API retourne 403 Forbidden

  Scénario: Personne ne peut supprimer une voix système
    Étant donné qu'Alex est connecté
    Quand Alex envoie DELETE /api/voices/Marianne
    Alors l'API retourne 403 Forbidden
    Et le message d'erreur mentionne "voix système non modifiable"

  Scénario: La création injecte automatiquement l'owner
    Étant donné qu'Alex est connecté avec le sub JWT "alex-sub-123"
    Quand Alex envoie POST /api/voices/custom source=design instruct="female, young adult"
    Alors la voix est créée avec owner="alex-sub-123" et system=false

  Scénario: Export scope uniquement mes voix
    Étant donné qu'Alex possède 2 voix custom
    Et que Bob possède 3 voix custom
    Et que 6 voix système existent
    Quand Alex envoie POST /api/voices/export
    Alors le ZIP contient 8 voix (2 perso + 6 système)
    Mais le ZIP ne contient aucune voix de Bob

  Scénario: Import réécrit l'owner
    Étant donné qu'Alex importe un ZIP contenant une voix "VoixX" avec owner="bob-sub"
    Quand Alex envoie POST /api/voices/import
    Alors la voix "VoixX" est créée côté Alex avec owner="alex-sub" (réécrit)
