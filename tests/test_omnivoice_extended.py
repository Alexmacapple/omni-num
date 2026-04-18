"""Tests etendus pour core/omnivoice_client.py — erreurs reseau et timeouts.

Couvre les chemins non testes dans test_omnivoice_client.py :
- ConnectError (OmniVoice down)
- ReadTimeout -> OmniVoiceTimeoutError
- 503 -> OmniVoiceBusyError
- 504 -> OmniVoiceTimeoutError
"""
import io
import os
import zipfile
from unittest.mock import MagicMock, patch

import httpx
import pytest

from core.omnivoice_client import OmniVoiceClient, OmniVoiceBusyError, OmniVoiceTimeoutError


class TestPresetTimeout:
    """Timeouts sur /preset -> OmniVoiceTimeoutError."""

    @patch("httpx.post")
    def test_read_timeout_raises_omnivoice_timeout(self, mock_post, tmp_path):
        mock_post.side_effect = httpx.ReadTimeout("timed out")
        client = OmniVoiceClient()
        with pytest.raises(OmniVoiceTimeoutError, match="Timeout httpx"):
            client.preset("Bonjour", "Lea", output_dir=str(tmp_path))

    @patch("httpx.post")
    def test_503_raises_busy(self, mock_post, tmp_path):
        mock_post.return_value = MagicMock(status_code=503)
        client = OmniVoiceClient()
        with pytest.raises(OmniVoiceBusyError, match="occup"):
            client.preset("Bonjour", "Lea", output_dir=str(tmp_path))

    @patch("httpx.post")
    def test_504_raises_timeout(self, mock_post, tmp_path):
        mock_post.return_value = MagicMock(status_code=504)
        client = OmniVoiceClient()
        with pytest.raises(OmniVoiceTimeoutError, match="timeout"):
            client.preset("Bonjour", "Lea", output_dir=str(tmp_path))


class TestBatchPresetTimeout:
    """Timeouts sur /batch/preset -> OmniVoiceTimeoutError."""

    @patch("httpx.post")
    def test_read_timeout_raises_omnivoice_timeout(self, mock_post, tmp_path):
        mock_post.side_effect = httpx.ReadTimeout("batch timed out")
        client = OmniVoiceClient()
        with pytest.raises(OmniVoiceTimeoutError, match="Timeout httpx"):
            client.batch_preset(["Un", "Deux"], "Lea", output_dir=str(tmp_path))

    @patch("httpx.post")
    def test_503_raises_busy(self, mock_post, tmp_path):
        mock_post.return_value = MagicMock(status_code=503)
        client = OmniVoiceClient()
        with pytest.raises(OmniVoiceBusyError):
            client.batch_preset(["Un"], "Lea", output_dir=str(tmp_path))


class TestDesignTimeout:
    """Timeouts sur /design -> OmniVoiceTimeoutError."""

    @patch("httpx.post")
    def test_read_timeout_raises_omnivoice_timeout(self, mock_post, tmp_path):
        mock_post.side_effect = httpx.ReadTimeout("design timed out")
        client = OmniVoiceClient()
        with pytest.raises(OmniVoiceTimeoutError, match="Timeout httpx"):
            client.design("Bonjour", "voix grave", output_dir=str(tmp_path))

    @patch("httpx.post")
    def test_504_raises_timeout(self, mock_post, tmp_path):
        mock_post.return_value = MagicMock(status_code=504)
        client = OmniVoiceClient()
        with pytest.raises(OmniVoiceTimeoutError):
            client.design("Bonjour", "voix grave", output_dir=str(tmp_path))


class TestPresetInstructTimeout:
    """Timeouts sur /preset/instruct -> OmniVoiceTimeoutError."""

    @patch("httpx.post")
    def test_read_timeout_raises_omnivoice_timeout(self, mock_post, tmp_path):
        mock_post.side_effect = httpx.ReadTimeout("instruct timed out")
        client = OmniVoiceClient()
        with pytest.raises(OmniVoiceTimeoutError, match="Timeout httpx"):
            client.preset_instruct("Bonjour", "Lea", "voix douce", output_dir=str(tmp_path))


class TestConnectError:
    """OmniVoice down -> ConnectError geree gracieusement."""

    @patch("httpx.post")
    def test_preset_connect_error_returns_none(self, mock_post, tmp_path):
        mock_post.side_effect = httpx.ConnectError("Connection refused")
        client = OmniVoiceClient()
        result = client.preset("Bonjour", "Lea", output_dir=str(tmp_path))
        assert result is None

    @patch("httpx.post")
    def test_batch_connect_error_returns_empty(self, mock_post, tmp_path):
        mock_post.side_effect = httpx.ConnectError("Connection refused")
        client = OmniVoiceClient()
        result = client.batch_preset(["Un"], "Lea", output_dir=str(tmp_path))
        assert result == []

    @patch("httpx.post")
    def test_design_connect_error_returns_none(self, mock_post, tmp_path):
        mock_post.side_effect = httpx.ConnectError("Connection refused")
        client = OmniVoiceClient()
        result = client.design("Bonjour", "voix grave", output_dir=str(tmp_path))
        assert result is None


class TestPresetWithSpeed:
    """Preset avec parametre speed."""

    @patch("httpx.post")
    def test_speed_sent_in_data(self, mock_post, tmp_path):
        mock_post.return_value = MagicMock(status_code=200, content=b"RIFF" + b"\x00" * 40)
        client = OmniVoiceClient()
        client.preset("Bonjour", "Lea", speed=1.3, output_dir=str(tmp_path))
        call_data = mock_post.call_args[1].get("data") or mock_post.call_args[0][1] if len(mock_post.call_args[0]) > 1 else mock_post.call_args[1].get("data", {})
        assert call_data.get("speed") == 1.3

    @patch("httpx.post")
    def test_speed_1_not_sent(self, mock_post, tmp_path):
        mock_post.return_value = MagicMock(status_code=200, content=b"RIFF" + b"\x00" * 40)
        client = OmniVoiceClient()
        client.preset("Bonjour", "Lea", speed=1.0, output_dir=str(tmp_path))
        call_data = mock_post.call_args[1].get("data") or mock_post.call_args[0][1] if len(mock_post.call_args[0]) > 1 else mock_post.call_args[1].get("data", {})
        assert "speed" not in call_data


class TestCustomVoiceDetails:
    """get_custom_voice_details et reload_custom_voices."""

    @patch("httpx.get")
    def test_details_succes(self, mock_get):
        mock_get.return_value = MagicMock(status_code=200, json=MagicMock(return_value={"name": "test", "source": "design"}))
        client = OmniVoiceClient()
        result = client.get_custom_voice_details("test")
        assert result["name"] == "test"

    @patch("httpx.get")
    def test_details_not_found(self, mock_get):
        mock_get.return_value = MagicMock(status_code=404)
        client = OmniVoiceClient()
        assert client.get_custom_voice_details("inexistante") is None

    @patch("httpx.post")
    def test_reload_succes(self, mock_post):
        mock_post.return_value = MagicMock(status_code=200)
        client = OmniVoiceClient()
        assert client.reload_custom_voices() is True

    @patch("httpx.post")
    def test_reload_echec(self, mock_post):
        mock_post.side_effect = httpx.ConnectError("down")
        client = OmniVoiceClient()
        assert client.reload_custom_voices() is False


class TestGetLanguages:
    """get_languages et get_models_status."""

    @patch("httpx.get")
    def test_languages_succes(self, mock_get):
        mock_get.return_value = MagicMock(status_code=200, json=MagicMock(return_value={"languages": ["fr", "en", "es"]}))
        client = OmniVoiceClient()
        assert "es" in client.get_languages()

    @patch("httpx.get")
    def test_languages_fallback(self, mock_get):
        mock_get.side_effect = Exception("timeout")
        client = OmniVoiceClient()
        assert client.get_languages() == ["fr", "en"]

    @patch("httpx.get")
    def test_models_status_succes(self, mock_get):
        mock_get.return_value = MagicMock(status_code=200, json=MagicMock(return_value={"design": True}))
        client = OmniVoiceClient()
        assert client.get_models_status()["design"] is True

    @patch("httpx.get")
    def test_models_status_echec(self, mock_get):
        mock_get.side_effect = Exception("timeout")
        client = OmniVoiceClient()
        assert client.get_models_status() is None
