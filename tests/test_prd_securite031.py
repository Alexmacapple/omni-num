"""Tests PRD-SECURITE-031 : durcissement securite post-revue.

TDD — tests ecrits AVANT les corrections.
Couvre :
- Fixes 1-3, 8 : IDOR (assign, generate, export, voices) — cross-user 403
- Fix 4 : JWT issuer verifie
- Fix 9 : locks/clear cross-user 403
"""
import copy
import json
import os
import sys
import time
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock

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

# 2e utilisateur pour tests cross-user
FAKE_USER_B = {"user_id": "other-user-456", "username": "otheruser"}
FAKE_THREAD_ID_B = "11111111-2222-3333-4444-555555555555"


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
def real_session_owner():
    """NE PAS mocker _verify_session_owner — on veut tester le vrai comportement.

    On mock uniquement _touch_session (pas de SQLite pour le touch).
    On mock _verify_session_owner avec une vraie logique :
    - FAKE_THREAD_ID appartient a FAKE_USER
    - FAKE_THREAD_ID_B appartient a FAKE_USER_B
    - Tout autre combo -> 403
    """
    def fake_verify(thread_id, user_id):
        from fastapi import HTTPException
        ownership = {
            FAKE_THREAD_ID: FAKE_USER["user_id"],
            FAKE_THREAD_ID_B: FAKE_USER_B["user_id"],
        }
        if thread_id not in ownership:
            raise HTTPException(status_code=404, detail="Session introuvable")
        if ownership[thread_id] != user_id:
            raise HTTPException(status_code=403, detail="Session non autorisee")

    targets = [_deps]
    for mod_name in ["routers.assign", "routers.generate", "routers.export",
                     "routers.voices", "routers.sessions", "routers.clean",
                     "routers.import_steps", "routers.audio"]:
        try:
            mod = __import__(mod_name, fromlist=["_verify_session_owner"])
            if hasattr(mod, "_verify_session_owner"):
                targets.append(mod)
        except ImportError:
            pass

    patches = []
    for mod in targets:
        if hasattr(mod, "_verify_session_owner"):
            patches.append(patch.object(mod, "_verify_session_owner", side_effect=fake_verify))
        if hasattr(mod, "_touch_session"):
            patches.append(patch.object(mod, "_touch_session", return_value=None))
    for p in patches:
        p.start()
    yield
    for p in patches:
        p.stop()


@pytest.fixture
def client_user_a():
    """Client authentifie comme FAKE_USER (proprietaire de FAKE_THREAD_ID)."""
    async def fake_auth(request=None):
        return FAKE_USER
    server.app.dependency_overrides[_auth_get_current_user] = fake_auth
    server.app.state.limiter.reset()
    original_sleep = asyncio.sleep
    async def fast_sleep(delay, *args, **kwargs):
        await original_sleep(0)
    with patch("routers.generate.asyncio.sleep", side_effect=fast_sleep):
        with TestClient(server.app, raise_server_exceptions=False) as c:
            yield c
    server.app.dependency_overrides.clear()


@pytest.fixture
def headers_own():
    """Headers avec le thread_id du user A (autorise)."""
    return {"Authorization": "Bearer fake", "X-Thread-Id": FAKE_THREAD_ID}


@pytest.fixture
def headers_foreign():
    """Headers avec le thread_id du user B (interdit pour user A)."""
    return {"Authorization": "Bearer fake", "X-Thread-Id": FAKE_THREAD_ID_B}


class TestFix1IDORAssign:
    """Fix 1 : les endpoints assign doivent verifier la propriete de session."""

    def test_get_assign_own_session_ok(self, client_user_a, headers_own):
        resp = client_user_a.get("/api/assign", headers=headers_own)
        assert resp.status_code == 200

    def test_get_assign_foreign_session_403(self, client_user_a, headers_foreign):
        """User A ne peut pas lire les assignations de la session de User B."""
        resp = client_user_a.get("/api/assign", headers=headers_foreign)
        assert resp.status_code == 403

    def test_post_assign_foreign_session_403(self, client_user_a, headers_foreign):
        """User A ne peut pas modifier les assignations de User B."""
        resp = client_user_a.post("/api/assign", json={"assignments": {"1": "Lea"}},
                                  headers=headers_foreign)
        assert resp.status_code == 403

    def test_assign_preview_foreign_session_403(self, client_user_a, headers_foreign):
        """User A ne peut pas previsualiser dans la session de User B."""
        resp = client_user_a.post("/api/assign/preview/1",
                                  json={"voice": "Lea", "text": "test"},
                                  headers=headers_foreign)
        assert resp.status_code == 403


class TestFix2IDORGenerate:
    """Fix 2 : les endpoints generate doivent verifier la propriete de session."""

    def test_generate_summary_foreign_403(self, client_user_a, headers_foreign):
        """User A ne peut pas voir le resume de generation de User B."""
        resp = client_user_a.get("/api/generate/summary", headers=headers_foreign)
        assert resp.status_code == 403

    def test_generate_sse_foreign_403(self, client_user_a, headers_foreign):
        """User A ne peut pas lancer la generation de User B."""
        resp = client_user_a.post("/api/generate",
                                  json={"fidelity": "speed"},
                                  headers=headers_foreign)
        # L'endpoint doit rejeter avant le streaming SSE (PRD-035 Bug 9)
        assert resp.status_code == 403, f"Attendu 403, obtenu {resp.status_code}"

    def test_generate_sample_foreign_403(self, client_user_a, headers_foreign):
        """User A ne peut pas generer des echantillons de User B."""
        resp = client_user_a.post("/api/generate/sample",
                                  json={"fidelity": "speed"},
                                  headers=headers_foreign)
        assert resp.status_code == 403


class TestFix3IDORExport:
    """Fix 3 : les endpoints export doivent verifier la propriete de session."""

    def test_export_sse_foreign_403(self, client_user_a, headers_foreign):
        """User A ne peut pas lancer l'export de User B."""
        resp = client_user_a.post("/api/export",
                                  json={},
                                  headers=headers_foreign)
        # L'endpoint doit rejeter avant le streaming SSE (PRD-035 Bug 9)
        assert resp.status_code == 403, f"Attendu 403, obtenu {resp.status_code}"


class TestFix4JWTIssuer:
    """Fix 4 : jwt.decode doit verifier le claim issuer."""

    def test_jwt_decode_includes_issuer_param(self):
        """Verifie que auth.py passe le parametre issuer a jwt.decode."""
        import auth
        import inspect
        source = inspect.getsource(auth.get_current_user)
        assert "issuer" in source, "get_current_user ne verifie pas l'issuer JWT"

    def test_validate_token_includes_issuer_param(self):
        """Verifie que validate_token passe le parametre issuer a jwt.decode."""
        import auth
        import inspect
        source = inspect.getsource(auth.validate_token)
        assert "issuer" in source, "validate_token ne verifie pas l'issuer JWT"


class TestFix8IDORVoices:
    """Fix 8 : les endpoints voices thread-bound doivent verifier la propriete."""

    def test_voices_preview_foreign_403(self, client_user_a, headers_foreign):
        """User A ne peut pas previsualiser une voix dans la session de User B."""
        resp = client_user_a.post("/api/voices/preview",
                                  json={"voice": "Lea", "text": "test", "language": "fr"},
                                  headers=headers_foreign)
        assert resp.status_code == 403


class TestFix9LockssClear:
    """Fix 9 : /api/locks/clear doit verifier la propriete de session."""

    def test_locks_clear_foreign_403(self, client_user_a, headers_foreign):
        """User A ne peut pas nettoyer les verrous de User B."""
        resp = client_user_a.post("/api/locks/clear", headers=headers_foreign)
        assert resp.status_code == 403
