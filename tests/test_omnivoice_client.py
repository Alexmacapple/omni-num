"""Tests pour core/omnivoice_client.py -- client API OmniVoice."""

import io
import os
import zipfile
from unittest.mock import MagicMock, patch

import pytest

from core.omnivoice_client import OmniVoiceClient


# ---------------------------------------------------------------------------
# TestInit
# ---------------------------------------------------------------------------
class TestInit:
    def test_url_par_defaut(self):
        client = OmniVoiceClient()
        assert client.base_url == "http://localhost:8070"

    def test_url_custom(self):
        client = OmniVoiceClient(base_url="http://example.com:9000/")
        assert client.base_url == "http://example.com:9000"

    def test_timeouts_differencies(self):
        """PRD-008 : timeouts differencies par categorie."""
        client = OmniVoiceClient()
        assert client.timeout_admin == 10.0
        assert client.timeout_preview == 90.0
        assert client.timeout_generate == 120.0
        assert client.timeout_batch == 600.0


# ---------------------------------------------------------------------------
# TestHealthCheck
# ---------------------------------------------------------------------------
class TestHealthCheck:
    @patch("httpx.get")
    def test_succes(self, mock_get):
        mock_get.return_value = MagicMock(status_code=200)
        client = OmniVoiceClient()
        assert client.health_check() is True
        mock_get.assert_called_once_with("http://localhost:8070/", timeout=5.0)

    @patch("httpx.get")
    def test_connexion_refusee(self, mock_get):
        import httpx
        mock_get.side_effect = httpx.ConnectError("Connection refused")
        client = OmniVoiceClient()
        assert client.health_check() is False

    @patch("httpx.get")
    def test_erreur_serveur(self, mock_get):
        mock_get.return_value = MagicMock(status_code=500)
        client = OmniVoiceClient()
        assert client.health_check() is False


# ---------------------------------------------------------------------------
# TestGetVoices
# ---------------------------------------------------------------------------
class TestGetVoices:
    @patch("httpx.get")
    def test_succes(self, mock_get):
        mock_get.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value={"voices": [{"name": "Lea"}, {"name": "Jean"}]}),
        )
        client = OmniVoiceClient()
        voices = client.get_voices()
        assert len(voices) == 2
        assert voices[0]["name"] == "Lea"

    @patch("httpx.get")
    def test_vide(self, mock_get):
        mock_get.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value={"voices": []}),
        )
        client = OmniVoiceClient()
        assert client.get_voices() == []

    @patch("httpx.get")
    def test_erreur(self, mock_get):
        mock_get.side_effect = Exception("network error")
        client = OmniVoiceClient()
        # get_voices doit attraper l'exception et logger, pas retourner [] silencieusement
        with patch("logging.exception") as mock_log:
            result = client.get_voices()
            assert result == []
            mock_log.assert_called()  # Verifier que l'erreur est loggee


# ---------------------------------------------------------------------------
# TestDeleteCustomVoice
# ---------------------------------------------------------------------------
class TestDeleteCustomVoice:
    @patch("httpx.delete")
    def test_succes(self, mock_delete):
        mock_delete.return_value = MagicMock(status_code=200)
        client = OmniVoiceClient()
        assert client.delete_custom_voice("narrateur-v1") is True

    @patch("httpx.delete")
    def test_inexistante(self, mock_delete):
        mock_delete.return_value = MagicMock(status_code=404)
        client = OmniVoiceClient()
        assert client.delete_custom_voice("voix-fantome") is False


# ---------------------------------------------------------------------------
# TestPreloadModels
# ---------------------------------------------------------------------------
class TestPreloadModels:
    @patch("httpx.post")
    def test_succes(self, mock_post):
        mock_post.return_value = MagicMock(status_code=200)
        client = OmniVoiceClient()
        assert client.preload_models() is True

    @patch("httpx.post")
    def test_echec(self, mock_post):
        mock_post.return_value = MagicMock(status_code=500)
        client = OmniVoiceClient()
        assert client.preload_models() is False


# ---------------------------------------------------------------------------
# TestEstimateDuration
# ---------------------------------------------------------------------------
class TestEstimateDuration:
    @patch("httpx.post")
    def test_succes(self, mock_post):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value={"tokens": [1] * 100}),
        )
        client = OmniVoiceClient()
        duration = client.estimate_duration(["Bonjour le monde"])
        assert duration == pytest.approx(5.0)

    @patch("httpx.post")
    def test_erreur(self, mock_post):
        mock_post.side_effect = Exception("timeout")
        client = OmniVoiceClient()
        # estimate_duration doit attraper l'exception ET logger
        with patch("logging.exception") as mock_log:
            result = client.estimate_duration(["texte"])
            assert result == 0.0
            mock_log.assert_called()  # Verifier que l'erreur est loggee


# ---------------------------------------------------------------------------
# TestPreset
# ---------------------------------------------------------------------------
class TestPreset:
    @patch("httpx.post")
    def test_genere_wav(self, mock_post, tmp_path):
        mock_post.return_value = MagicMock(
            status_code=200,
            content=b"RIFF" + b"\x00" * 40,
        )
        client = OmniVoiceClient()
        result = client.preset(
            text="Bonjour",
            voice="Lea",
            output_dir=str(tmp_path),
        )
        assert result is not None
        assert os.path.isfile(result)
        assert result.endswith(".wav")

    @patch("httpx.post")
    def test_echec(self, mock_post, tmp_path):
        mock_post.return_value = MagicMock(status_code=500)
        client = OmniVoiceClient()
        result = client.preset(
            text="Bonjour",
            voice="Lea",
            output_dir=str(tmp_path),
        )
        assert result is None


# ---------------------------------------------------------------------------
# TestPresetInstruct
# ---------------------------------------------------------------------------
class TestPresetInstruct:
    @patch("httpx.post")
    def test_succes(self, mock_post, tmp_path):
        mock_post.return_value = MagicMock(
            status_code=200,
            content=b"RIFF" + b"\x00" * 40,
        )
        client = OmniVoiceClient()
        result = client.preset_instruct(
            text="Bonjour",
            voice="Lea",
            instruct="voix chaleureuse",
            output_dir=str(tmp_path),
        )
        assert result is not None
        assert os.path.isfile(result)

    @patch("httpx.post")
    def test_echec(self, mock_post, tmp_path):
        mock_post.return_value = MagicMock(status_code=500)
        client = OmniVoiceClient()
        result = client.preset_instruct(
            text="Bonjour",
            voice="Lea",
            instruct="voix chaleureuse",
            output_dir=str(tmp_path),
        )
        assert result is None


# ---------------------------------------------------------------------------
# TestDesign
# ---------------------------------------------------------------------------
class TestDesign:
    @patch("httpx.post")
    def test_succes(self, mock_post, tmp_path):
        mock_post.return_value = MagicMock(
            status_code=200,
            content=b"RIFF" + b"\x00" * 40,
        )
        client = OmniVoiceClient()
        result = client.design(
            text="Bonjour",
            voice_instruct="voix masculine grave",
            output_dir=str(tmp_path),
        )
        assert result is not None
        assert os.path.isfile(result)

    @patch("httpx.post")
    def test_echec(self, mock_post, tmp_path):
        mock_post.return_value = MagicMock(status_code=500)
        client = OmniVoiceClient()
        result = client.design(
            text="Bonjour",
            voice_instruct="voix masculine grave",
            output_dir=str(tmp_path),
        )
        assert result is None


# ---------------------------------------------------------------------------
# TestBatchPreset
# ---------------------------------------------------------------------------
class TestBatchPreset:
    @patch("httpx.post")
    def test_succes(self, mock_post, tmp_path):
        # Creer un vrai ZIP en memoire avec 3 WAV
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("001.wav", b"RIFF" + b"\x00" * 40)
            zf.writestr("002.wav", b"RIFF" + b"\x00" * 40)
            zf.writestr("003.wav", b"RIFF" + b"\x00" * 40)
        zip_bytes = buf.getvalue()

        mock_post.return_value = MagicMock(
            status_code=200,
            content=zip_bytes,
        )
        client = OmniVoiceClient()
        result = client.batch_preset(
            texts=["Un", "Deux", "Trois"],
            voice="Lea",
            output_dir=str(tmp_path),
        )
        assert len(result) == 3
        for path in result:
            assert os.path.isfile(path)

    @patch("httpx.post")
    def test_erreur(self, mock_post, tmp_path):
        mock_post.return_value = MagicMock(status_code=500)
        client = OmniVoiceClient()
        result = client.batch_preset(
            texts=["Un", "Deux"],
            voice="Lea",
            output_dir=str(tmp_path),
        )
        assert result == []


# ---------------------------------------------------------------------------
# TestSaveCustomVoice
# ---------------------------------------------------------------------------
class TestSaveCustomVoice:
    @patch("httpx.post")
    def test_design_succes(self, mock_post):
        mock_post.return_value = MagicMock(
            status_code=201,
            text="Voice saved",
        )
        client = OmniVoiceClient()
        result = client.save_custom_voice(
            name="narrateur-v1",
            source="design",
            voice_instruct="voix masculine grave",
        )
        assert result["ok"] is True
        assert "Voice saved" in result["detail"]

    @patch("httpx.post")
    def test_clone_succes(self, mock_post, tmp_path):
        mock_post.return_value = MagicMock(
            status_code=200,
            text="Cloned",
        )
        # Creer un faux fichier audio pour le clonage
        audio_file = tmp_path / "reference.wav"
        audio_file.write_bytes(b"RIFF" + b"\x00" * 40)

        client = OmniVoiceClient()
        result = client.save_custom_voice(
            name="narrateur-clone",
            source="clone",
            audio_path=str(audio_file),
            transcription="Bonjour le monde",
        )
        assert result["ok"] is True

    @patch("httpx.post")
    def test_echec_http(self, mock_post):
        mock_post.return_value = MagicMock(
            status_code=400,
            text="Bad Request",
        )
        client = OmniVoiceClient()
        result = client.save_custom_voice(
            name="test",
            source="design",
            voice_instruct="test",
        )
        assert result["ok"] is False
        assert "HTTP 400" in result["detail"]

    @patch("httpx.post")
    def test_exception(self, mock_post):
        mock_post.side_effect = Exception("connection lost")
        client = OmniVoiceClient()
        # save_custom_voice doit attraper l'exception ET logger
        with patch("logging.exception") as mock_log:
            result = client.save_custom_voice(
                name="test",
                source="design",
                voice_instruct="test",
            )
            assert result["ok"] is False
            assert "connection lost" in result["detail"]
            mock_log.assert_called()  # Verifier que l'erreur est loggee
