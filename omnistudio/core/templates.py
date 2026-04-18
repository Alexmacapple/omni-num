from jinja2 import Template
import re

# Template pour le nettoyage TTS (Layer B + LLM)
CLEANING_SYSTEM_PROMPT = """
Tu es un correcteur spécialisé pour la synthèse vocale française.

Règles :
- Corriger les fautes d'orthographe et conserver STRICTEMENT les accents (é, à, è, etc.) en encodage UTF-8.
- Développer toutes les abréviations (ex: DN → Démarches Numériques, MOA → maîtrise d'ouvrage).
- Convertir les listes à puces en phrases fluides reliées par des virgules ou des points.
- Supprimer les parenthèses : intégrer le contenu dans la phrase avec une virgule.
- Supprimer les guillemets.
- Remplacer les mots en MAJUSCULES par leur forme en casse normale.
- Chaque texte doit se terminer par un point.
- Ne jamais reformuler le sens : garder les mots de l'auteur.
- Résultat : une seule phrase ou un court paragraphe fluide et lisible à voix haute.

{% if glossary %}
Glossaire du projet et Phonétique :
{% for key, val in glossary.items() %}
- {{ key }} → {{ val }}
{% endfor %}
{% endif %}
"""

CLEANING_USER_PROMPT = "Texte à nettoyer :\n{{ text }}"

def apply_layer_a(text: str) -> str:
    """
    Nettoyage basique sans LLM (Repris de generate-voix.py).
    Garantit un résultat propre en cas d'absence d'IA.
    """
    if not text:
        return ""
        
    # 1. Remplacer les tirets de liste
    text = re.sub(r"\n\s*\d+-\s*", ". ", text)
    text = re.sub(r"\n\s*-\s*", ". ", text)
    
    # 2. Supprimer les doubles espaces
    text = re.sub(r"\s+", " ", text).strip()
    
    # 3. Parenthèses et guillemets
    text = text.replace("(", "").replace(")", "").replace('"', "")
    
    # 4. Point final
    if text and text[-1] not in ".!?":
        text += "."
        
    return text
