import logging
from langgraph.graph import StateGraph, START, END
from graph.state import DesignState
from core.llm_client import LLMClient
from core.omnivoice_client import OmniVoiceClient, normalize_voice_instruct

logger = logging.getLogger("omnistudio")
vox_client = OmniVoiceClient()

# Prompt classifieur : le LLM n'est plus un rédacteur, c'est un extracteur
# d'attributs vers la whitelist OmniVoice Voice Design (k2-fsa).
# Calé sur l'endpoint racine GET /design/attributes et le comportement du
# script Gradio google-colab/app.py qui compose l'instruct directement
# depuis les dropdowns, sans rédaction littéraire.
META_PROMPT_SYSTEM = """Tu es un extracteur d'attributs vers la whitelist Voice Design d'OmniVoice (k2-fsa).
Ta SEULE mission : lire le brief utilisateur (français ou anglais) et retourner les items anglais correspondants.

WHITELIST STRICTE — 6 catégories, 1 item MAXIMUM par catégorie :
- gender : male | female
- age : child | teenager | young adult | middle-aged | elderly
- pitch : very low pitch | low pitch | moderate pitch | high pitch | very high pitch
- style : whisper  (à inclure UNIQUEMENT si le brief évoque chuchoté, murmuré, susurré)
- english_accent : American accent | British accent | Australian accent | Canadian accent | Indian accent | Japanese accent | Korean accent | Portuguese accent | Russian accent | Chinese accent
  (à inclure UNIQUEMENT si l'utilisateur demande explicitement un accent anglais ET que la langue cible est l'anglais)
- chinese_dialect : Henan dialect | Shaanxi dialect | Sichuan dialect | Guizhou dialect | Yunnan dialect | Guilin dialect | Jinan dialect | Shijiazhuang dialect | Gansu dialect | Ningxia dialect | Qingdao dialect | Northeast dialect
  (exacte whitelist renvoyée par GET /design/attributes, à inclure UNIQUEMENT si la langue cible est le chinois ; Beijing et Shanghai ne sont PAS supportés)

FORMAT DE SORTIE STRICT :
- UNIQUEMENT la liste des items en minuscules, séparés par « , » (virgule-espace).
- AUCUN texte libre, AUCUN préambule, AUCUN guillemet, AUCUN markdown, AUCUNE explication.
- Si aucun attribut n'est inférable, réponds par une chaîne vide.
- Ne jamais inventer d'adjectifs (« warm », « clear », « velvety » sont INTERDITS car non whitelist).
- Ne JAMAIS spécifier un accent francophone (non supporté par le modèle).

HEURISTIQUE D'INFÉRENCE FR :
- « voix féminine/femme/madame » → female · « voix masculine/homme/monsieur » → male
- « enfant/petit/petite/gamin » → child · « adolescent/ado » → teenager · « jeune (adulte) » → young adult
- « mature/mûr/mûre/quarantaine/cinquantaine » → middle-aged · « âgé/senior/vieillard/ancien » → elderly
- « voix grave/profonde/basse/baryton/caverneuse » → low pitch · « très grave » → very low pitch
- « voix aiguë/haute » → high pitch · « très aiguë » → very high pitch
- « voix moyenne/médium » → moderate pitch
- « chuchoté/murmuré/susurré/soufflé » → whisper
- Adjectifs qualitatifs SANS mapping whitelist (chaleureux, brillant, velouté, rond, posé, engageant, rassurant, etc.) → ÊTRE IGNORÉS, ne produit aucun item.

EXEMPLES :

Brief : « Voix féminine mature chaleureuse pour narration institutionnelle »
Sortie : female, middle-aged

Brief : « Homme grave âgé, ton autoritaire et posé »
Sortie : male, elderly, low pitch

Brief : « Voix féminin française mature, timbre chaleureux et velouté, prosodie française native »
Sortie : female, middle-aged

Brief : « Jeune femme dynamique qui chuchote comme en ASMR »
Sortie : female, young adult, whisper

Brief : « British narrator, moderate pitch, calm »  (langue cible=en)
Sortie : male, moderate pitch, british accent

Brief : (vide)
Sortie :
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

# Mapping dropdowns UI français → items whitelist OmniVoice (minuscules).
# Aligné avec composeInstructFromAttrs() côté frontend (tab-voices.js) et
# design_from_attributes() (core.omnivoice_client).
_BRIEF_GENDER_TO_ITEM = {"masculin": "male", "feminin": "female", "féminin": "female"}
_BRIEF_AGE_TO_ITEM = {"jeune": "young adult", "mature": "middle-aged", "age": "elderly", "âgé": "elderly"}
_BRIEF_PITCH_TO_ITEM = {
    "very low": "very low pitch", "low": "low pitch",
    "moderate": "moderate pitch", "high": "high pitch", "very high": "very high pitch",
}


def _compose_items_from_brief(brief: dict) -> list:
    """Compose les items whitelist depuis les 6 dropdowns structurés du brief.

    Reproduit le pattern _build_instruct() du Colab google-colab/app.py :
    filtrer les valeurs vides, convertir en items whitelist, joindre par « , ».
    Ne touche pas à `brief.extra` (prose libre, traitée par le LLM ensuite).
    """
    items = []
    gender = _BRIEF_GENDER_TO_ITEM.get((brief.get("genre") or "").strip().lower())
    if gender:
        items.append(gender)
    age = _BRIEF_AGE_TO_ITEM.get((brief.get("age") or "").strip().lower())
    if age:
        items.append(age)
    pitch = _BRIEF_PITCH_TO_ITEM.get((brief.get("pitch") or "").strip().lower())
    if pitch:
        items.append(pitch)
    style = (brief.get("style") or "").strip().lower()
    if style == "whisper":
        items.append("whisper")
    accent = (brief.get("english_accent") or "").strip()
    if accent:
        items.append(accent.lower())
    dialect = (brief.get("chinese_dialect") or "").strip()
    if dialect:
        items.append(dialect.lower())
    return items


def generate_voice_instruct(state: DesignState, config: RunnableConfig):
    """Compose le voice_instruct en deux temps :
    1. Items déterministes depuis les 6 dropdowns du brief (pattern Colab).
    2. LLM classifieur UNIQUEMENT si la description libre peut apporter
       des items pour les catégories non encore remplies.
    Fusion finale : priorité aux dropdowns, LLM en complément, aucune
    hallucination possible hors whitelist grâce à normalize_voice_instruct.
    """
    thread_id = config["configurable"].get("thread_id")
    api_key = get_api_key(thread_id)

    brief = state.get("brief", {})
    dropdown_items = _compose_items_from_brief(brief)
    dropdown_categories = {_category_of_safe(i) for i in dropdown_items if _category_of_safe(i)}

    extra = (brief.get("extra") or "").strip()
    language = state.get("language") or "fr"

    llm_items: list = []
    # LLM appelé seulement si l'user a fourni une prose libre ET qu'il
    # reste des catégories non couvertes par les dropdowns.
    remaining_cats = {"gender", "age", "pitch", "special", "accent"} - dropdown_categories
    if extra and remaining_cats:
        llm = LLMClient(
            provider=state.get("llm_provider", "Albert Large 120B"),
            api_key=api_key,
            temperature=state.get("llm_temperature", 0.5),
            model_override=state.get("llm_model_override", "")
        )
        user_prompt = (
            f"Langue cible de synthèse : {language}\n"
            f"Description libre de l'utilisateur :\n{extra}\n\n"
            f"Catégories à inférer depuis cette description uniquement : "
            f"{', '.join(sorted(remaining_cats))}.\n"
            "Ignore toute catégorie hors de cette liste.\n"
            "Retourne UNIQUEMENT les items whitelist séparés par virgule, "
            "ou une ligne vide si rien n'est inférable."
        )
        try:
            raw = llm.ask(META_PROMPT_SYSTEM, user_prompt)
            cleaned = _clean_voice_instruct(raw)
            # Normalise : ne garde que les items whitelist, 1 par catégorie
            norm = normalize_voice_instruct(cleaned)
            if norm:
                llm_items = [it.strip() for it in norm.split(",") if it.strip()]
        except Exception as e:
            logger.warning("LLM classifier échoué, dropdowns seuls : %s", e)

    # Fusion : dropdowns prioritaires, LLM complète les catégories vides
    merged = list(dropdown_items)
    seen_cats = set(dropdown_categories)
    for item in llm_items:
        cat = _category_of_safe(item)
        if cat and cat not in seen_cats:
            merged.append(item)
            seen_cats.add(cat)

    instruct = ", ".join(merged)
    return {"voice_instruct": instruct, "iteration": state.get("iteration", 0) + 1}


def _category_of_safe(item: str):
    """Wrapper lazy sur core.omnivoice_client._category_of pour éviter les cycles d'import."""
    from core.omnivoice_client import _category_of
    return _category_of(item)

def synthesize_design(state: DesignState):
    """Génère un audio exploratoire via /design.

    Le voice_instruct est transmis en anglais (whitelist OmniVoice), mais
    le texte synthétisé et la langue cible viennent du state — sinon la
    voix lit toujours une phrase anglaise hardcodée, quel que soit le
    réglage de l'utilisateur.
    """
    voice_instruct = state.get("voice_instruct", "")
    if not voice_instruct:
        # Pas d'instruction vocale fournie → retour vide
        return {"wav_paths": []}

    test_text = state.get("test_text") or "Ceci est un test de timbre et de rythme pour notre nouvelle voix studio."
    language = state.get("language") or "fr"

    try:
        path = vox_client.design(test_text, voice_instruct, language=language)
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
