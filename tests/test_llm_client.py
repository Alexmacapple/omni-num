"""Tests pour core/llm_client.py -- client LLM avec retry 429."""

from unittest.mock import MagicMock, patch

import pytest

from core.llm_client import LLMClient, PROVIDER_PRESETS


# ---------------------------------------------------------------------------
# TestInit
# ---------------------------------------------------------------------------
class TestInit:
    @patch("core.llm_client.ChatOpenAI")
    def test_provider_defaut(self, mock_chat_cls):
        mock_chat_cls.return_value = MagicMock()
        client = LLMClient(provider="Albert Large 120B", api_key="test-key")
        call_kwargs = mock_chat_cls.call_args[1]
        preset = PROVIDER_PRESETS["Albert Large 120B"]
        assert call_kwargs["base_url"] == preset["base_url"]
        assert call_kwargs["model"] == preset["model"]

    @patch("core.llm_client.ChatOpenAI")
    def test_model_override(self, mock_chat_cls):
        mock_chat_cls.return_value = MagicMock()
        client = LLMClient(
            provider="Albert Large 120B",
            api_key="test-key",
            model_override="custom-model",
        )
        call_kwargs = mock_chat_cls.call_args[1]
        assert call_kwargs["model"] == "custom-model"

    def test_provider_presets(self):
        """Tous les presets doivent avoir base_url et model."""
        for name, preset in PROVIDER_PRESETS.items():
            assert "base_url" in preset, f"Preset '{name}' manque base_url"
            assert "model" in preset, f"Preset '{name}' manque model"


# ---------------------------------------------------------------------------
# TestAsk
# ---------------------------------------------------------------------------
class TestAsk:
    @patch("core.llm_client.ChatOpenAI")
    def test_reponse_normale(self, mock_chat_cls):
        mock_llm = MagicMock()
        mock_chat_cls.return_value = mock_llm
        mock_llm.invoke.return_value = MagicMock(content="texte nettoye")

        client = LLMClient(provider="Albert Large 120B", api_key="test-key")
        result = client.ask("Tu es un assistant.", "Nettoie ce texte.")
        assert result == "texte nettoye"

    @patch("core.llm_client.time")
    @patch("core.llm_client.ChatOpenAI")
    def test_rate_limit_retry_succes(self, mock_chat_cls, mock_time):
        mock_llm = MagicMock()
        mock_chat_cls.return_value = mock_llm
        # Premier appel : rate limit 429, deuxieme : succes
        mock_llm.invoke.side_effect = [
            Exception("Error 429: rate limit exceeded"),
            MagicMock(content="resultat apres retry"),
        ]

        client = LLMClient(provider="Albert Large 120B", api_key="test-key")
        result = client.ask("system", "user")
        assert result == "resultat apres retry"
        mock_time.sleep.assert_called_once_with(8)

    @patch("core.llm_client.time")
    @patch("core.llm_client.ChatOpenAI")
    def test_retries_epuises(self, mock_chat_cls, mock_time):
        mock_llm = MagicMock()
        mock_chat_cls.return_value = mock_llm
        # 4 appels (initial + 3 retries) tous en 429
        mock_llm.invoke.side_effect = Exception("Error 429: rate limit")

        client = LLMClient(provider="Albert Large 120B", api_key="test-key")
        result = client.ask("system", "user")
        assert "Erreur" in result
        assert mock_time.sleep.call_count == 3

    @patch("core.llm_client.ChatOpenAI")
    def test_erreur_autre(self, mock_chat_cls):
        mock_llm = MagicMock()
        mock_chat_cls.return_value = mock_llm
        mock_llm.invoke.side_effect = Exception("Connection timeout")

        client = LLMClient(provider="Albert Large 120B", api_key="test-key")
        result = client.ask("system", "user")
        assert "Erreur" in result

    @patch("core.llm_client.ChatOpenAI")
    def test_strip_reponse(self, mock_chat_cls):
        mock_llm = MagicMock()
        mock_chat_cls.return_value = mock_llm
        mock_llm.invoke.return_value = MagicMock(content="  texte avec espaces  \n")

        client = LLMClient(provider="Albert Large 120B", api_key="test-key")
        result = client.ask("system", "user")
        assert result == "texte avec espaces"
