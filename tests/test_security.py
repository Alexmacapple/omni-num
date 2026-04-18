"""Tests pour core/security.py — Cle API serveur (PRD-005 simplifie)."""

from core.security import set_api_key, get_api_key, clear_api_keys


class TestApiKeyServer:
    """Tests de la cle API serveur (variable d'environnement, plus de cache)."""

    def test_get_unknown_thread_returns_fallback(self):
        result = get_api_key("session-inexistante")
        assert result == "sk-no-key-needed"

    def test_get_empty_string_returns_fallback(self):
        result = get_api_key("")
        assert result == "sk-no-key-needed"

    def test_set_is_noop(self):
        """set_api_key est un no-op depuis PRD-005."""
        set_api_key("session-42", "sk-test")
        assert get_api_key("session-42") == "sk-no-key-needed"

    def test_clear_is_noop(self):
        """clear_api_keys est un no-op depuis PRD-005."""
        clear_api_keys()  # Ne doit pas lever d'exception
