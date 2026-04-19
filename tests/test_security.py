"""Tests pour core/security.py — Cle API serveur (PRD-005 simplifie).

get_api_key retourne OPENAI_API_KEY si défini dans l'env, sinon "sk-no-key-needed".
Les tests monkeypatchent env pour isoler du contexte d'exécution.
"""

from core.security import set_api_key, get_api_key, clear_api_keys


class TestApiKeyServer:
    """Tests de la cle API serveur (variable d'environnement, plus de cache)."""

    def test_get_unknown_thread_returns_fallback(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        result = get_api_key("session-inexistante")
        assert result == "sk-no-key-needed"

    def test_get_empty_string_returns_fallback(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        result = get_api_key("")
        assert result == "sk-no-key-needed"

    def test_set_is_noop(self, monkeypatch):
        """set_api_key est un no-op depuis PRD-005."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        set_api_key("session-42", "sk-test")
        assert get_api_key("session-42") == "sk-no-key-needed"

    def test_env_var_used_when_set(self, monkeypatch):
        """Si OPENAI_API_KEY est défini dans l'env, get_api_key le retourne."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-env")
        assert get_api_key("session-42") == "sk-test-env"

    def test_clear_is_noop(self):
        """clear_api_keys est un no-op depuis PRD-005."""
        clear_api_keys()  # Ne doit pas lever d'exception
