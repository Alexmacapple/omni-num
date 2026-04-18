"""Tests PRD-UX-030 : corrections retours utilisateur v1.

TDD — tests ecrits AVANT les corrections.
Couvre :
- Fix 3 : reduction des chunks batch (90 -> 20)
- Fix 4 : estimation de duree (libelle qualitatif)
- Fix 3 bis : reprise (already_done > 0 apres un chunk reussi)
"""
import copy
import json
import os
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import asyncio

import pytest
from fastapi.testclient import TestClient

OMNISTUDIO_DIR = Path(__file__).resolve().parent.parent / "omnistudio"
sys.path.insert(0, str(OMNISTUDIO_DIR))

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
    """TestClient avec auth mockee et asyncio.sleep patche pour eviter les timeouts."""
    async def fake_get_current_user(request=None):
        return FAKE_USER
    server.app.dependency_overrides[_auth_get_current_user] = fake_get_current_user
    server.app.state.limiter.reset()
    # Patcher asyncio.sleep UNIQUEMENT dans le module generate pour accelerer les heartbeats
    original_sleep = asyncio.sleep
    async def fast_sleep(delay, *args, **kwargs):
        await original_sleep(0)
    with patch("routers.generate.asyncio.sleep", side_effect=fast_sleep):
        with TestClient(server.app, raise_server_exceptions=False) as c:
            yield c
    server.app.dependency_overrides.clear()


@pytest.fixture
def auth_headers():
    return {"Authorization": "Bearer fake", "X-Thread-Id": FAKE_THREAD_ID}


def _make_steps(n: int):
    """Genere n etapes pour les tests."""
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


def _make_assignments(n: int, voice: str = "Lea"):
    """Genere les assignations pour n etapes."""
    return {str(i): voice for i in range(1, n + 1)}


class TestFix3ChunkSize:
    """Fix 3 : les batches doivent etre decoupes en chunks <= 20."""

    def test_batch_49_steps_produces_multiple_chunks(self, client, auth_headers, tmp_path):
        """49 etapes doivent produire 3 chunks (20+20+9), pas 1 chunk de 49.

        ATTENDU : batch_preset appele 3 fois (pas 1 fois).
        AVANT FIX : batch_preset appele 1 fois avec 49 textes.
        """
        n = 49
        _mock_state.values["steps"] = _make_steps(n)
        _mock_state.values["assignments"] = _make_assignments(n)

        wav_path = str(tmp_path / "chunk.wav")
        Path(wav_path).write_bytes(b"RIFF" + b"\x00" * 40)

        def fake_batch(texts, voice, **kwargs):
            return [wav_path] * len(texts)

        _mock_vox_client.batch_preset.side_effect = fake_batch

        resp = client.post(
            "/api/generate",
            json={"fidelity": "speed"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert "event: done" in resp.text

        # Verification : batch_preset appele plusieurs fois, jamais avec > 20 textes
        calls = _mock_vox_client.batch_preset.call_args_list
        assert len(calls) >= 2, f"Attendu >= 2 appels batch, obtenu {len(calls)}"
        for call in calls:
            texts_arg = call.args[0] if call.args else call.kwargs.get("texts", [])
            assert len(texts_arg) <= 20, f"Chunk trop gros : {len(texts_arg)} textes (max 20)"

    def test_batch_15_steps_single_chunk(self, client, auth_headers, tmp_path):
        """15 etapes doivent tenir en 1 seul chunk."""
        n = 15
        _mock_state.values["steps"] = _make_steps(n)
        _mock_state.values["assignments"] = _make_assignments(n)

        wav_path = str(tmp_path / "small.wav")
        Path(wav_path).write_bytes(b"RIFF" + b"\x00" * 40)
        _mock_vox_client.batch_preset.reset_mock()
        _mock_vox_client.batch_preset.side_effect = None
        _mock_vox_client.batch_preset.return_value = [wav_path] * n

        resp = client.post(
            "/api/generate",
            json={"fidelity": "speed"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert "event: done" in resp.text
        assert _mock_vox_client.batch_preset.call_count == 1

    def test_batch_start_events_per_chunk(self, client, auth_headers, tmp_path):
        """Chaque chunk doit emettre un event batch_start."""
        n = 45
        _mock_state.values["steps"] = _make_steps(n)
        _mock_state.values["assignments"] = _make_assignments(n)

        wav_path = str(tmp_path / "chunk.wav")
        Path(wav_path).write_bytes(b"RIFF" + b"\x00" * 40)

        def fake_batch(texts, voice, **kwargs):
            return [wav_path] * len(texts)

        _mock_vox_client.batch_preset.side_effect = fake_batch

        resp = client.post(
            "/api/generate",
            json={"fidelity": "speed"},
            headers=auth_headers,
        )
        text = resp.text
        batch_starts = text.count("event: batch_start")
        assert batch_starts >= 2, f"Attendu >= 2 batch_start, obtenu {batch_starts}"


class TestFix3Resume:
    """Fix 3 bis : la reprise doit fonctionner apres un chunk reussi."""

    def test_resume_skips_already_generated(self, client, auth_headers, tmp_path):
        """Si 20 etapes sont deja generees, la reprise ne traite que les 29 restantes.

        Simule le scenario : chunk 1 (20 etapes) reussi, timeout sur chunk 2.
        La relance avec resume=True doit skip les 20 premieres.
        """
        n = 49
        _mock_state.values["steps"] = _make_steps(n)
        _mock_state.values["assignments"] = _make_assignments(n)
        # 20 etapes deja generees
        _mock_state.values["generated_files"] = [
            {"step_id": str(i), "filename": f"step{i}.wav",
             "voice_name": "Lea", "wav_path": f"/fake/step{i}.wav", "status": "done"}
            for i in range(1, 21)
        ]

        wav_path = str(tmp_path / "resume.wav")
        Path(wav_path).write_bytes(b"RIFF" + b"\x00" * 40)

        _mock_vox_client.batch_preset.reset_mock()
        _mock_vox_client.batch_preset.side_effect = lambda texts, voice, **kw: [wav_path] * len(texts)

        resp = client.post(
            "/api/generate",
            json={"fidelity": "speed", "resume": True, "force": True},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert "event: done" in resp.text

        # Verification : seules 29 etapes traitees (pas 49)
        total_texts = sum(
            len(call.args[0] if call.args else call.kwargs.get("texts", []))
            for call in _mock_vox_client.batch_preset.call_args_list
        )
        assert total_texts == 29, f"Attendu 29 textes traites, obtenu {total_texts}"


class TestFix3TimeoutMessage:
    """Fix 3 : le message TTS_TIMEOUT doit inclure le numero d'etape."""

    def test_timeout_message_contains_step_number(self, client, auth_headers):
        """Le message d'erreur TTS_TIMEOUT doit indiquer l'etape d'interruption."""
        from core.omnivoice_client import OmniVoiceTimeoutError

        n = 30
        _mock_state.values["steps"] = _make_steps(n)
        _mock_state.values["assignments"] = _make_assignments(n)
        _mock_vox_client.batch_preset.side_effect = OmniVoiceTimeoutError("timeout")

        resp = client.post(
            "/api/generate",
            json={"fidelity": "speed"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert "TTS_TIMEOUT" in resp.text

        # Le message doit contenir un indicateur de progression (etape/total)
        for line in resp.text.split("\n"):
            if "TTS_TIMEOUT" in line and line.startswith("data:"):
                data = json.loads(line[5:])
                msg = data.get("message", "")
                # Doit contenir "etape" ou un format X/Y
                assert "/" in msg or "tape" in msg.lower(), \
                    f"Message timeout sans numero d'etape : '{msg}'"
                break


class TestFix4EstimationDuree:
    """Fix 4 : l'estimation doit indiquer clairement la nature de la duree."""

    def test_summary_label_not_misleading(self, client, auth_headers):
        """Le champ estimated_duration_s ne doit pas etre presente comme temps d'attente.

        Le endpoint /api/generate/summary retourne estimated_duration_s.
        Le frontend doit l'afficher comme duree audio ou estimation qualitative,
        pas comme 'Xs estimees' (qui suggere un temps d'attente).

        Ce test verifie que le backend retourne bien la donnee.
        La verification du libelle est frontend (test manuel).
        """
        resp = client.get("/api/generate/summary", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "estimated_duration_s" in data
        assert isinstance(data["estimated_duration_s"], (int, float))

    def test_estimate_duration_is_audio_duration(self):
        """Verifie que estimate_duration retourne bien une duree audio (tokens * 0.05).

        Ce test documente le comportement actuel pour detecter si quelqu'un
        change la formule sans mettre a jour le libelle frontend.
        """
        from core.omnivoice_client import OmniVoiceClient
        client = OmniVoiceClient.__new__(OmniVoiceClient)
        client.base_url = "http://localhost:8070"
        client.timeout_admin = 10

        # Mock du tokenizer qui retourne 200 tokens
        with patch("httpx.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"tokens": list(range(200))}
            mock_post.return_value = mock_resp

            duration = client.estimate_duration(["Texte de test"])

        # 200 tokens * 0.05 = 10.0 secondes (duree audio, pas temps GPU)
        assert duration == 10.0
