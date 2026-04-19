import logging
from langgraph.graph import StateGraph, START, END
from graph.state import DesignState
from core.llm_client import LLMClient
from core.omnivoice_client import OmniVoiceClient

logger = logging.getLogger("omnistudio")
vox_client = OmniVoiceClient()

META_PROMPT_SYSTEM = """Tu es un expert en Design Vocal pour k2-fsa OmniVoice.
Ta mission : produire une description de voix (voice_instruct) optimisée pour le moteur de synthèse.

FORMAT DE SORTIE STRICT :
- Réponds UNIQUEMENT avec la description de voix brute.
- Pas de préambule ("Voici", "Je propose"), pas d'explication, pas de guillemets, pas de markdown.
- Une ou plusieurs phrases descriptives continues, attributs séparés par des virgules ou des points.
- Longueur : 30 à 80 mots.

TEMPLATE (6 axes obligatoires) :
Voix [genre] [langue] [âge], timbre [couleur], texture [grain/proximité], ton [émotion], rythme [débit/pauses], style [contexte]

PROSODIE FRANÇAISE :
- Toujours spécifier une prosodie typiquement française : liaisons fluides, fins de phrases descendantes.
- Privilégier : accent neutre métropolitain, diction nette, fluidité naturelle.

RÈGLES :
- Formuler TOUJOURS en positif (ce qu'on veut), jamais en négatif.
- Pas de contradictions internes (ex: "grave" + "jeune énergique").
- Prioriser : intelligibilité > style > expressivité.
- TOUJOURS répondre en français sauf indication contraire.

EXEMPLES DE RÉFÉRENCE :

Exemple masculin (70 mots) :
Voix masculine française native, extrêmement fluide et naturelle. L'élocution est celle d'un locuteur s'exprimant avec une aisance totale, sans aucune rupture de rythme. La prosodie est typiquement française : plate, régulière, avec des liaisons fluides entre les mots. Les fins de phrases sont posées et descendantes. Le timbre est chaleureux, professionnel et proche du micro. L'accent est neutre, de type métropolitain.

Exemple féminin (55 mots) :
Voix féminine française mature, timbre rond et chaleureux avec des médiums enveloppants. L'élocution est fluide et posée, avec une aisance naturelle de locutrice native. La prosodie est française, régulière, avec des fins de phrases descendantes et des liaisons soignées. Le ton est bienveillant et pédagogique. Texture veloutée proche du micro, style formation institutionnelle, diction articulée.

Exemple court (30 mots) :
Voix féminine française jeune et dynamique, timbre clair et brillant, texture précise micro proche, ton engageant et confiant, rythme soutenu avec pauses courtes, style keynote tech, diction nette.
"""

import re as _re

from langchain_core.runnables import RunnableConfig
from core.security import get_api_key

_PREAMBLE_RE = _re.compile(
    r'^(?:voici|je propose|bien sûr|certainement|d\'accord|ok|here is|sure)[\s:,.\-!]*',
    _re.IGNORECASE
)

def _clean_voice_instruct(raw: str) -> str:
    """Nettoie la sortie LLM : retire préambules, guillemets, markdown."""
    text = raw.strip()
    # Retirer les guillemets englobants
    if (text.startswith('"') and text.endswith('"')) or (text.startswith('«') and text.endswith('»')):
        text = text[1:-1].strip()
    # Retirer les backticks markdown
    if text.startswith('```') and text.endswith('```'):
        text = text[3:-3].strip()
    if text.startswith('`') and text.endswith('`'):
        text = text[1:-1].strip()
    # Retirer les préambules courants
    text = _PREAMBLE_RE.sub('', text).strip()
    # Capitaliser la première lettre
    if text and text[0].islower():
        text = text[0].upper() + text[1:]
    return text

def generate_voice_instruct(state: DesignState, config: RunnableConfig):
    thread_id = config["configurable"].get("thread_id")
    api_key = get_api_key(thread_id)

    llm = LLMClient(
        provider=state.get("llm_provider", "Albert Large 120B"),
        api_key=api_key,
        temperature=state.get("llm_temperature", 0.5),
        model_override=state.get("llm_model_override", "")
    )
    brief = state.get("brief", {})
    system_prompt = META_PROMPT_SYSTEM

    gender = brief.get('genre', '')
    age = brief.get('age', '')
    contexte = brief.get('contexte', '')
    emotion = brief.get('emotion', '')
    extra = brief.get('extra', '')

    # Construire le brief en format structuré clé-valeur
    axes = []
    if gender:
        axes.append(f"- Genre : {gender}")
    if age:
        axes.append(f"- Âge : {age}")
    if contexte:
        axes.append(f"- Contexte : {contexte}")
    if emotion:
        axes.append(f"- Émotion : {emotion}")
    if extra:
        axes.append(f"- Description libre : {extra}")

    if axes and extra:
        user_prompt = (
            "Brief utilisateur :\n"
            + "\n".join(axes) + "\n\n"
            "La description libre est PRIORITAIRE en cas de contradiction avec les autres paramètres.\n"
        )
        if gender:
            user_prompt += f"Commence par 'Voix {gender}'.\n"
    elif axes:
        user_prompt = "Brief utilisateur :\n" + "\n".join(axes) + "\n"
        if gender:
            user_prompt += f"\nCommence par 'Voix {gender}'.\n"
    elif extra:
        user_prompt = f"Description libre de l'utilisateur :\n{extra}\n"
    else:
        user_prompt = "Aucun paramètre fourni. Génère une voix française neutre et professionnelle.\n"

    raw = llm.ask(system_prompt, user_prompt)

    # Point 4 : nettoyage de la sortie (strip préambules parasites)
    instruct = _clean_voice_instruct(raw)
    
    return {"voice_instruct": instruct, "iteration": state.get("iteration", 0) + 1}

def synthesize_design(state: DesignState):
    """Génère un audio exploratoire via /design."""
    voice_instruct = state.get("voice_instruct", "")
    if not voice_instruct:
        # Pas d'instruction vocale fournie → retour vide
        return {"wav_paths": []}

    try:
        # OmniVoice /design n'accepte que l'anglais (voir CLAUDE.md § À ne pas faire)
        path = vox_client.design("This is a test of timbre and rhythm for our new studio voice.", voice_instruct)
        return {"wav_paths": [path] if path else []}
    except Exception as e:
        logger.error("Erreur synthèse design: %s", e, exc_info=True)
        return {"wav_paths": []}

def create_design_subgraph():
    workflow = StateGraph(DesignState)
    workflow.add_node("generate_instruct", generate_voice_instruct)
    workflow.add_node("synthesize", synthesize_design)
    workflow.add_node("human_review", lambda x: x)
    
    workflow.add_edge(START, "generate_instruct")
    workflow.add_edge("generate_instruct", "synthesize")
    workflow.add_edge("synthesize", "human_review")
    
    def check_decision(state: DesignState):
        decision = state.get("decision")
        if decision == "lock" or state.get("iteration", 0) >= 20: return END
        return "generate_instruct" if decision == "regenerate_instruct" else "synthesize"

    workflow.add_conditional_edges("human_review", check_decision)
    return workflow.compile(interrupt_before=["human_review"])
