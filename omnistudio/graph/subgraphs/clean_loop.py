import logging
import re
import time
from typing import Dict, List

logger = logging.getLogger(__name__)
from langgraph.graph import StateGraph, START, END
from graph.state import CleanState
from core.llm_client import LLMClient
from core.templates import CLEANING_SYSTEM_PROMPT, CLEANING_USER_PROMPT, apply_layer_a
from jinja2 import Template
from datetime import datetime

def apply_layer_b(text: str, patterns: Dict[str, str], parentheses: Dict[str, str], majuscules: Dict[str, str]) -> str:
    """Applique corrections Layer B (patterns, parenthèses, majuscules)."""
    # Patterns regex
    for pattern, repl in (patterns or {}).items():
        try:
            text = re.sub(pattern, repl, text)
        except Exception as e:
            logger.warning("Erreur Regex %s: %s", pattern, e)
    # Parenthèses spécifiques
    for original, replacement in (parentheses or {}).items():
        text = text.replace(original, replacement)
    # Majuscules non naturelles
    for upper, normal in (majuscules or {}).items():
        text = text.replace(upper, normal)
    return text

from langchain_core.runnables import RunnableConfig
from core.security import get_api_key

def propose_corrections(state: CleanState, config: RunnableConfig) -> Dict:
    thread_id = config["configurable"].get("thread_id")
    api_key = get_api_key(thread_id)
    
    llm = LLMClient(
        provider=state.get("llm_provider", "Albert Large 120B"),
        api_key=api_key,
        temperature=state.get("llm_temperature", 0.7),
        model_override=state.get("llm_model_override", "")
    )
    glossary = state.get("domain_glossary", {})
    patterns = state.get("correction_patterns", {})
    parentheses = state.get("correction_parentheses", {})
    majuscules = state.get("correction_majuscules", {})
    
    new_steps = []
    logs = []
    llm_call_count = 0

    sys_tpl = Template(CLEANING_SYSTEM_PROMPT)
    system_prompt = sys_tpl.render(glossary=glossary)

    pending = [s for s in state["steps"] if s.get("cleaning_status") != "validated"]
    total = len(pending)

    for step in state["steps"]:
        if step.get("cleaning_status") == "validated":
            new_steps.append(step)
            continue

        # Rate limit proactif : Albert = 10 req/min → 1 req/7s
        # Note : fonction sync executee par LangGraph via asyncio.to_thread()
        # time.sleep() bloque le worker thread, pas l'event loop (PRD-035 Bug 3)
        if llm_call_count > 0 and llm_call_count % 9 == 0:
            logger.info("Pause rate limit (9 requetes envoyees)... attente 60s")
            time.sleep(60)
        elif llm_call_count > 0:
            time.sleep(1)

        llm_call_count += 1
        logger.info("Nettoyage etape %s (%d/%d)", step['step_id'], llm_call_count, total)

        # 1. Layer B : Application des corrections locales
        text = apply_layer_b(step["text_original"], patterns, parentheses, majuscules)

        # 2. LLM : Nettoyage sémantique
        user_prompt = Template(CLEANING_USER_PROMPT).render(text=text)
        proposed = llm.ask(system_prompt, user_prompt)

        if proposed.startswith("Erreur :"):
            proposed = apply_layer_a(text)

        step["text_tts"] = proposed
        step["cleaning_status"] = "cleaned"
        new_steps.append(step)

        logs.append({
            "step_id": step["step_id"],
            "llm_provider": state.get("llm_provider"),
            "temperature": state.get("llm_temperature", 0.7),
            "timestamp": datetime.now().isoformat()
        })
    
    return {
        "steps": new_steps,
        "iteration": state.get("iteration", 0) + 1,
        "cleaning_log": logs
    }

def create_clean_subgraph():
    workflow = StateGraph(CleanState)
    workflow.add_node("propose", propose_corrections)
    workflow.add_node("human_review", lambda x: x)
    workflow.add_edge(START, "propose")
    workflow.add_edge("propose", "human_review")
    
    def check_decision(state: CleanState):
        if state.get("decision") == "validated" or state.get("iteration", 0) >= 10:
            return END
        return "propose"

    workflow.add_conditional_edges("human_review", check_decision)
    return workflow.compile(interrupt_before=["human_review"])
