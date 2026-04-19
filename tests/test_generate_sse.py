"""Tests SSE pour routers/generate.py — generation batch.

Couvre les chemins non testes :
- SSE event_generator complet (batch + progress + done)
- Resume (skip etapes deja generees)
- Erreur TTS pendant le batch
"""
import asyncio
import copy
import json
import os
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# Reutiliser le setup de test_endpoints.py
OMNISTUDIO_DIR = Path(__file__).resolve().parent.parent / "omnistudio"
sys.path.insert(0, str(OMNISTUDIO_DIR))

# Importer les mocks et fixtures de test_endpoints
from test_endpoints import (
    server, _mock_graph_app, _mock_state, _mock_vox_client,
    _mock_design_app, _DEFAULT_STATE_VALUES, FAKE_USER, FAKE_THREAD_ID,
)
import dependencies as _deps
from auth import get_current_user as _auth_get_current_user


@pytest.fixture(autouse=True)
def reset_state():
    """Reset state et verrous entre chaque test."""
    _mock_state.values = copy.deepcopy(_DEFAULT_STATE_VALUES)
    _mock_graph_app.get_state.return_value = _mock_state
    _mock_graph_app.update_state.reset_mock()
    _deps._generating_locks.clear()
    _deps._exporting_locks.clear()
    _deps._cleaning_locks.clear()
    yield


@pytest.fixture(autouse=True)
def mock_session_db():
    """Mock session ownership."""
    targets = [server, _deps]
    for mod_name in ["routers.generate"]:
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
    """TestClient avec auth mockee et heartbeat accelere."""
    async def fake_get_current_user(request=None):
        return FAKE_USER
    server.app.dependency_overrides[_auth_get_current_user] = fake_get_current_user
    # Reset rate limiter (si present)
    if hasattr(server.app.state, 'limiter') and hasattr(server.app.state.limiter, 'reset'):
        server.app.state.limiter.reset()
    original_sleep = asyncio.sleep
    async def fast_sleep(delay, *args, **kwargs):
        await original_sleep(0)
    sleep_patch = patch("routers.generate.asyncio.sleep", side_effect=fast_sleep)
    sleep_patch.start()
    c = TestClient(server.app, raise_server_exceptions=False)
    try:
        yield c
    finally:
        c.close()
        sleep_patch.stop()
        server.app.dependency_overrides.clear()


@pytest.fixture
def auth_headers():
    return {"Authorization": "Bearer fake", "X-Thread-Id": FAKE_THREAD_ID}


class TestGenerateSSE:
    """Tests du flux SSE /api/generate."""

    def test_generate_sse_batch_flow(self, client, auth_headers, tmp_path):
        """SSE complet : batch -> progress -> done."""
        # Mock batch_preset pour retourner des WAV
        wav_path = str(tmp_path / "batch_001.wav")
        Path(wav_path).write_bytes(b"RIFF" + b"\x00" * 40)
        _mock_vox_client.batch_preset.return_value = [wav_path, wav_path]

        resp = client.post(
            "/api/generate",
            json={"fidelity": "quality", "resume": False},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")
        text = resp.text
        # Doit contenir des events progress et done
        assert "event: batch_start" in text or "event: progress" in text
        assert "event: done" in text

    def test_generate_sse_resume_skips(self, client, auth_headers, tmp_path):
        """Resume=True skip les etapes deja dans generated_files."""
        _mock_state.values["generated_files"] = [
            {"step_id": "1", "filename": "step1.wav", "voice_name": "Lea",
             "wav_path": "/fake/step1.wav", "status": "done"},
            {"step_id": "2", "filename": "step2.wav", "voice_name": "Lea",
             "wav_path": "/fake/step2.wav", "status": "done"},
        ]
        resp = client.post(
            "/api/generate",
            json={"fidelity": "quality", "resume": True},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        text = resp.text
        # Toutes les etapes sont deja faites -> done directement
        assert "event: done" in text
        done_data = None
        for line in text.split("\n"):
            if line.startswith("data:") and "resumed" in line:
                done_data = json.loads(line[5:])
        if done_data:
            assert done_data.get("resumed") is True

    def test_generate_sse_no_assignments_still_works(self, client, auth_headers, tmp_path):
        """Sans assignations explicites, utilise Lea par defaut."""
        _mock_state.values["assignments"] = {}
        wav_path = str(tmp_path / "default.wav")
        Path(wav_path).write_bytes(b"RIFF" + b"\x00" * 40)
        _mock_vox_client.batch_preset.return_value = [wav_path, wav_path]

        resp = client.post(
            "/api/generate",
            json={"fidelity": "speed"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert "event: done" in resp.text

    # --- PRD-022 : Instructions emotionnelles (bloc 226-282) ---

    def test_generate_with_instructions(self, client, auth_headers, tmp_path):
        """Steps avec instructions -> preset_instruct appele, events progress."""
        _mock_state.values["instructions"] = {"1": "Ton chaleureux", "2": "Ton neutre"}
        wav_path = str(tmp_path / "instruct.wav")
        Path(wav_path).write_bytes(b"RIFF" + b"\x00" * 40)
        _mock_vox_client.preset_instruct.return_value = wav_path

        resp = client.post(
            "/api/generate",
            json={"fidelity": "quality"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        text = resp.text
        assert "event: progress" in text
        assert "event: done" in text
        assert "instruction" in text.lower()

    def test_generate_instruct_tts_busy(self, client, auth_headers):
        """preset_instruct leve OmniVoiceBusyError -> event error TTS_BUSY."""
        from core.omnivoice_client import OmniVoiceBusyError
        _mock_state.values["instructions"] = {"1": "Ton chaleureux"}
        _mock_vox_client.preset_instruct.side_effect = OmniVoiceBusyError("busy")

        resp = client.post(
            "/api/generate",
            json={"fidelity": "quality"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert "TTS_BUSY" in resp.text

    def test_generate_instruct_tts_timeout(self, client, auth_headers):
        """preset_instruct leve OmniVoiceTimeoutError -> event error TTS_TIMEOUT."""
        from core.omnivoice_client import OmniVoiceTimeoutError
        _mock_state.values["instructions"] = {"1": "Ton chaleureux"}
        _mock_vox_client.preset_instruct.side_effect = OmniVoiceTimeoutError("timeout")

        resp = client.post(
            "/api/generate",
            json={"fidelity": "quality"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert "TTS_TIMEOUT" in resp.text

    # --- PRD-022 : Force unlock (bloc 89-94) ---

    def test_generate_force_unlock_old(self, client, auth_headers, tmp_path):
        """force=True avec verrou > 30s -> libere et demarre."""
        _deps._generating_locks[FAKE_THREAD_ID] = time.time() - 60
        wav_path = str(tmp_path / "force.wav")
        Path(wav_path).write_bytes(b"RIFF" + b"\x00" * 40)
        _mock_vox_client.batch_preset.return_value = [wav_path, wav_path]

        resp = client.post(
            "/api/generate",
            json={"fidelity": "quality", "force": True},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert "event: done" in resp.text or "event: progress" in resp.text

    def test_generate_force_ignore_recent(self, client, auth_headers):
        """force=True avec verrou < 30s -> verrou conserve, 409."""
        _deps._generating_locks[FAKE_THREAD_ID] = time.time() - 5
        resp = client.post(
            "/api/generate",
            json={"fidelity": "quality", "force": True},
            headers=auth_headers,
        )
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "GENERATE_IN_PROGRESS"

    # --- PRD-022 : Batch errors (bloc 179-197) ---

    def test_generate_batch_tts_busy(self, client, auth_headers):
        """batch_preset leve OmniVoiceBusyError -> event error."""
        from core.omnivoice_client import OmniVoiceBusyError
        _mock_vox_client.batch_preset.side_effect = OmniVoiceBusyError("busy")

        resp = client.post(
            "/api/generate",
            json={"fidelity": "quality"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert "TTS_BUSY" in resp.text

    def test_generate_batch_exception(self, client, auth_headers):
        """batch_preset leve Exception -> wav_paths vide, progress avec audio_url null."""
        _mock_vox_client.batch_preset.side_effect = Exception("network error")

        resp = client.post(
            "/api/generate",
            json={"fidelity": "quality"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        text = resp.text
        # Le batch echoue mais le SSE continue avec null audio_url
        assert "event: done" in text
