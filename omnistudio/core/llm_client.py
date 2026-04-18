import logging
import httpx
import time
from typing import Dict, List, Optional
from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)

PROVIDER_PRESETS = {
    "Z.AI (Coding Pro)": {
        "base_url": "https://api.z.ai/api/coding/paas/v4/",
        "model": "glm-4.7",
    },
    "Z.AI (solde rechargeable)": {
        "base_url": "https://api.z.ai/api/paas/v4/",
        "model": "glm-4.7",
    },
    "Albert Large 120B": {
        "base_url": "https://albert.api.etalab.gouv.fr/v1",
        "model": "openai/gpt-oss-120b",
    },
    "Albert Medium 24B": {
        "base_url": "https://albert.api.etalab.gouv.fr/v1",
        "model": "mistralai/Mistral-Small-3.2-24B-Instruct-2506",
    },
    "Albert Small 8B": {
        "base_url": "https://albert.api.etalab.gouv.fr/v1",
        "model": "mistralai/Ministral-3-8B-Instruct-2512",
    },
    "Albert Code 30B": {
        "base_url": "https://albert.api.etalab.gouv.fr/v1",
        "model": "Qwen/Qwen3-Coder-30B-A3B-Instruct",
    },
    "Anthropic (Claude)": {
        "base_url": "https://api.anthropic.com/v1",
        "model": "claude-sonnet-4-6",
    },
    "Google (Gemini)": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "model": "gemini-2.0-flash",
    },
    "OpenAI (Codex)": {
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4.1-mini",
    },
}

class LLMClient:
    """Client pour le meta-prompting voix et le nettoyage TTS."""
    
    def __init__(
        self,
        provider: str = "Albert Large 120B",
        api_key: str = "sk-no-key-needed",
        temperature: float = 0.7,
        model_override: str = "",
    ):
        preset = PROVIDER_PRESETS.get(provider, PROVIDER_PRESETS["Albert Large 120B"])
        model_name = model_override.strip() if model_override else preset["model"]
        self.llm = ChatOpenAI(
            model=model_name,
            base_url=preset["base_url"],
            api_key=api_key,
            temperature=temperature,
            timeout=60
        )

    def ask(self, system_prompt: str, user_prompt: str) -> str:
        """Envoie une requête au LLM avec retry sur rate limit (429)."""
        messages = [
            ("system", system_prompt),
            ("human", user_prompt),
        ]
        max_retries = 3
        for attempt in range(max_retries + 1):
            try:
                response = self.llm.invoke(messages)
                return response.content.strip()
            except Exception as e:
                error_str = str(e)
                if "429" in error_str and attempt < max_retries:
                    wait = 8 * (attempt + 1)
                    logger.warning("Rate limit atteint, attente %ds... (tentative %d/%d)", wait, attempt + 1, max_retries)
                    time.sleep(wait)
                    continue
                logger.error("Erreur LLM (%s): %s", self.llm.model_name, e)
                return "Erreur : Impossible de joindre le moteur IA."
