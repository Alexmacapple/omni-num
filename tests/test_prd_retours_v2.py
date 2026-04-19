"""Tests PRD retours utilisateur v2 (8 avril 2026).

TDD — tests ecrits AVANT les corrections.
Couvre :
- P2a : GET /api/audio/{filename} rejette tid vide avec 400
- P2b : GET /api/audio/{filename} accepte tid valide
- P3  : GET /api/assign filtre les voix sur selected_voices
- P4  : conversion WAV -> MP3 dans core/audio.py
"""
import copy
import json
import sys
from pathlib import Path
from unittest.mock import patch, AsyncMock

import pytest

OMNISTUDIO_DIR = Path(__file__).resolve().parent.parent / "omnistudio"
sys.path.insert(0, str(OMNISTUDIO_DIR))

from test_endpoints import (
    server, _mock_graph_app, _mock_state, _mock_vox_client,
    _DEFAULT_STATE_VALUES, FAKE_USER, FAKE_THREAD_ID,
)
import dependencies as _deps
from auth import get_current_user as _auth_get_current_user
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def reset_state():
    _mock_state.values = copy.deepcopy(_DEFAULT_STATE_VALUES)
    _mock_graph_app.get_state.return_value = _mock_state
    yield


@pytest.fixture(autouse=True)
def mock_session_db():
    """Mock session ownership pour eviter les appels DB."""
    targets = [_deps]
    for mod_name in ["routers.audio", "routers.assign"]:
        try:
            mod = __import__(mod_name, fromlist=["_verify_session_owner"])
            if hasattr(mod, "_verify_session_owner"):
                targets.append(mod)
        except ImportError:
            pass
    patches = []
    for mod in targets:
        if hasattr(mod, "_verify_session_owner"):
            patches.append(patch.object(mod, "_verify_session_owner", return_value=None))
        if hasattr(mod, "_touch_session"):
            patches.append(patch.object(mod, "_touch_session", return_value=None))
    for p in patches:
        p.start()
    yield
    for p in patches:
        p.stop()


@pytest.fixture
def client():
    """TestClient avec validate_token mocke (auth hybride query param)."""
    server.app.state.limiter.reset()
    with patch("routers.audio.validate_token", new_callable=AsyncMock, return_value=FAKE_USER):
        with TestClient(server.app, raise_server_exceptions=False) as c:
            yield c


class TestP2AudioTidValidation:
    """P2a : le endpoint /api/audio doit rejeter les requetes avec tid vide."""

    def test_audio_tid_empty_returns_400(self, client):
        """GET /api/audio/test.wav avec tid= vide doit retourner 400.

        ATTENDU : 400 "Thread ID invalide"
        """
        resp = client.get("/api/audio/test.wav?token=fake&tid=")
        assert resp.status_code == 400
        assert "Thread ID" in resp.json().get("detail", "")

    def test_audio_tid_missing_returns_400(self, client):
        """GET /api/audio/test.wav sans tid doit retourner 400."""
        resp = client.get("/api/audio/test.wav?token=fake")
        assert resp.status_code == 400

    def test_audio_tid_invalid_format_returns_error(self, client):
        """GET /api/audio/test.wav avec tid=../etc (path traversal) doit retourner 400."""
        resp = client.get("/api/audio/test.wav?token=fake&tid=../etc")
        assert resp.status_code == 400

    def test_audio_tid_valid_file_missing_returns_404(self, client):
        """GET /api/audio/test.wav avec tid valide mais fichier inexistant doit retourner 404."""
        resp = client.get(
            f"/api/audio/inexistant.wav?token=fake&tid={FAKE_THREAD_ID}"
        )
        assert resp.status_code == 404

    def test_audio_tid_valid_file_exists_returns_200(self, client):
        """GET /api/audio/{file} avec tid valide et fichier existant doit retourner 200."""
        audio_dir = Path("data/voices") / FAKE_THREAD_ID
        audio_dir.mkdir(parents=True, exist_ok=True)
        wav_file = audio_dir / "preview_test.wav"
        wav_file.write_bytes(
            b"RIFF" + (36).to_bytes(4, "little") +
            b"WAVEfmt " + (16).to_bytes(4, "little") +
            (1).to_bytes(2, "little") +
            (1).to_bytes(2, "little") +
            (24000).to_bytes(4, "little") +
            (48000).to_bytes(4, "little") +
            (2).to_bytes(2, "little") +
            (16).to_bytes(2, "little") +
            b"data" + (0).to_bytes(4, "little")
        )
        try:
            resp = client.get(
                f"/api/audio/preview_test.wav?token=fake&tid={FAKE_THREAD_ID}"
            )
            assert resp.status_code == 200
            assert resp.headers.get("content-type", "").startswith("audio/")
        finally:
            wav_file.unlink(missing_ok=True)
            audio_dir.rmdir()


# ---------------------------------------------------------------------------
# P3 : filtrage des voix dans l'assignation
# ---------------------------------------------------------------------------

@pytest.fixture
def auth_client():
    """TestClient avec auth standard (header Bearer)."""
    async def fake_get_current_user(request=None):
        return FAKE_USER
    server.app.dependency_overrides[_auth_get_current_user] = fake_get_current_user
    server.app.state.limiter.reset()
    with TestClient(server.app, raise_server_exceptions=False) as c:
        yield c
    server.app.dependency_overrides.clear()


@pytest.fixture
def auth_headers():
    return {"Authorization": "Bearer fake", "X-Thread-Id": FAKE_THREAD_ID}


def _make_steps(n):
    return [
        {
            "step_id": str(i),
            "text_original": f"Texte etape {i}.",
            "text_tts": f"Texte etape {i}.",
            "cleaning_status": "validated",
            "language_override": "fr",
            "speed_factor": 1.0,
        }
        for i in range(1, n + 1)
    ]


class TestP3VoiceFiltering:
    """P3 : la liste des voix dans /api/assign doit respecter selected_voices."""

    def test_no_selected_voices_returns_all(self, auth_client, auth_headers):
        """Sans selected_voices, toutes les voix doivent etre retournees.

        ATTENDU : comportement actuel preserve (retrocompatibilite).
        """
        _mock_state.values["steps"] = _make_steps(2)
        _mock_state.values["assignments"] = {}
        # Pas de selected_voices dans le state
        if "selected_voices" in _mock_state.values:
            del _mock_state.values["selected_voices"]

        resp = auth_client.get("/api/assign", headers=auth_headers)
        assert resp.status_code == 200
        voices = resp.json()["data"]["voices"]
        voice_names = [v["name"] for v in voices]
        assert "Lea" in voice_names
        assert "Jean" in voice_names

    def test_selected_voices_filters_list(self, auth_client, auth_headers):
        """Avec selected_voices=["Lea"], seule Lea doit apparaitre.

        ATTENDU (apres fix) : voices ne contient que Lea.
        AVANT FIX : voices contient Lea ET Jean.
        """
        _mock_state.values["steps"] = _make_steps(2)
        _mock_state.values["assignments"] = {}
        _mock_state.values["selected_voices"] = ["Lea"]

        resp = auth_client.get("/api/assign", headers=auth_headers)
        assert resp.status_code == 200
        voices = resp.json()["data"]["voices"]
        voice_names = [v["name"] for v in voices]
        assert "Lea" in voice_names
        assert "Jean" not in voice_names, \
            f"Jean ne devrait pas etre dans la liste (selected_voices=[Lea]), obtenu {voice_names}"

    def test_selected_voices_empty_list_returns_all(self, auth_client, auth_headers):
        """Avec selected_voices=[], toutes les voix doivent etre retournees (fallback).

        ATTENDU : meme comportement que sans selected_voices.
        """
        _mock_state.values["steps"] = _make_steps(2)
        _mock_state.values["assignments"] = {}
        _mock_state.values["selected_voices"] = []

        resp = auth_client.get("/api/assign", headers=auth_headers)
        assert resp.status_code == 200
        voices = resp.json()["data"]["voices"]
        voice_names = [v["name"] for v in voices]
        assert len(voice_names) >= 2

    def test_selected_voices_includes_custom(self, auth_client, auth_headers):
        """Les voix custom verrouillees doivent toujours apparaitre meme si non selectionnees.

        ATTENDU : si locked_voices=["alexandra"] et selected_voices=["Lea"],
        la liste contient Lea + alexandra (dont alexandra est owned par user).
        """
        _mock_vox_client.get_voices.return_value = [
            {"name": "Lea", "type": "native"},
            {"name": "Jean", "type": "native"},
            {"name": "alexandra", "type": "custom"},
        ]
        _mock_state.values["steps"] = _make_steps(2)
        _mock_state.values["assignments"] = {}
        _mock_state.values["selected_voices"] = ["Lea"]
        _mock_state.values["locked_voices"] = ["alexandra"]

        # Mock _read_voice_meta pour que alexandra soit owned par user fake
        # (sinon le filter ownership PRD-032 la masquerait)
        with patch("routers.assign._read_voice_meta") as mock_meta:
            mock_meta.return_value = {"owner": FAKE_USER["user_id"], "system": False, "source": "clone"}
            resp = auth_client.get("/api/assign", headers=auth_headers)
        assert resp.status_code == 200
        voices = resp.json()["data"]["voices"]
        voice_names = [v["name"] for v in voices]
        assert "Lea" in voice_names, "Voix selectionnee doit etre presente"
        assert "alexandra" in voice_names, "Voix custom verrouillee doit toujours etre presente"
        assert "Jean" not in voice_names, "Voix non selectionnee doit etre filtree"

        # Restaurer les voix mockees par defaut
        _mock_vox_client.get_voices.return_value = [
            {"name": "Lea", "type": "native", "description": "Voix native Lea", "gender": "female"},
            {"name": "Jean", "type": "native", "description": "Voix native Jean", "gender": "male"},
        ]


# ---------------------------------------------------------------------------
# P4 : conversion WAV -> MP3
# ---------------------------------------------------------------------------

class TestP4ConvertToMp3:
    """P4 : core/audio.py doit exposer une fonction convert_to_mp3."""

    def test_convert_to_mp3_exists(self):
        """La fonction convert_to_mp3 doit exister dans core.audio.

        ATTENDU (apres fix) : import reussit.
        AVANT FIX : ImportError.
        """
        from core.audio import convert_to_mp3
        assert callable(convert_to_mp3)

    def test_convert_to_mp3_creates_file(self, tmp_path):
        """convert_to_mp3 doit creer un fichier .mp3 a partir d'un .wav."""
        from core.audio import convert_to_mp3

        # Creer un WAV minimal valide
        wav_path = tmp_path / "test.wav"
        wav_path.write_bytes(
            b"RIFF" + (36).to_bytes(4, "little") +
            b"WAVEfmt " + (16).to_bytes(4, "little") +
            (1).to_bytes(2, "little") +   # PCM
            (1).to_bytes(2, "little") +   # mono
            (24000).to_bytes(4, "little") +  # sample rate
            (48000).to_bytes(4, "little") +  # byte rate
            (2).to_bytes(2, "little") +   # block align
            (16).to_bytes(2, "little") +  # bits per sample
            b"data" + (0).to_bytes(4, "little")
        )
        mp3_path = tmp_path / "test.mp3"
        result = convert_to_mp3(str(wav_path), str(mp3_path))
        assert result is True
        assert mp3_path.exists()

    def test_convert_to_mp3_missing_input_returns_false(self, tmp_path):
        """convert_to_mp3 avec fichier source inexistant doit retourner False."""
        from core.audio import convert_to_mp3
        result = convert_to_mp3("/inexistant.wav", str(tmp_path / "out.mp3"))
        assert result is False


class TestP4ExportRequestFormat:
    """P4 : ExportRequest doit accepter un champ output_format."""

    def test_export_request_accepts_mp3(self):
        """ExportRequest doit accepter output_format='mp3'.

        ATTENDU (apres fix) : pas d'erreur de validation.
        AVANT FIX : champ inconnu.
        """
        from routers.export import ExportRequest
        req = ExportRequest(output_format="mp3")
        assert req.output_format == "mp3"

    def test_export_request_default_wav(self):
        """ExportRequest sans output_format doit etre 'wav' par defaut."""
        from routers.export import ExportRequest
        req = ExportRequest()
        assert req.output_format == "wav"
