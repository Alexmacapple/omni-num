# language: fr
Fonctionnalité: Multi-voix par étape via tag [voice:X]
  En tant qu'utilisateur d'OmniStudio
  Je veux pouvoir utiliser plusieurs voix dans une même étape
  Afin de produire des dialogues avec alternance de locuteurs

  Contexte:
    Étant donné que les 6 voix système sont disponibles

  Scénario: Étape avec 3 segments via 2 tags
    Étant donné qu'Alex a importé une étape « Hello. [voice:Jean] Hi. [voice:Paul] Bye. »
    Et que la voix par défaut de l'étape est "Marianne"
    Quand Alex passe dans l'onglet 5 Génération
    Alors 3 segments sont générés : Marianne → Jean → Paul
    Et l'audio final concatène les 3 segments dans l'ordre

  Scénario: Tag avec voix inexistante
    Étant donné qu'Alex a importé « Hello [voice:ZeusPersonne] World »
    Quand Alex envoie POST /api/assign
    Alors l'API retourne 422 Unprocessable Entity
    Et la réponse liste les voix disponibles

  Scénario: Sécurité — tag avec tentative XSS
    Étant donné qu'Alex a importé « [voice:Jean<script>alert(1)</script>] Texte »
    Quand le parser analyse le texte
    Alors le tag est invalide (regex rejette < >)
    Et le texte "[voice:Jean<script>...]" est conservé littéralement (non interprété)
    Et la voix utilisée est celle par défaut de l'étape

  Scénario: Tag fait référence à voix d'un autre utilisateur
    Étant donné qu'Alex a importé « Hello [voice:VoixDeBob] World »
    Et que VoixDeBob appartient à Bob
    Quand Alex envoie POST /api/assign
    Alors l'API retourne 422
    Et le message explique que VoixDeBob est inaccessible

  Scénario: Auto-segmentation désactivée (v1.0)
    Étant donné qu'Alex a importé « — Bonjour. — Bonjour à vous. » (tirets cadratins)
    Quand le parser analyse le texte
    Alors aucune segmentation automatique n'est faite
    Et un seul segment avec la voix par défaut est produit
    Et le texte original est préservé tel quel
