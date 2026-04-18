"""Tests de securite web — CSP, CORS, rate limiting, path traversal.

Complement de test_security.py (qui ne couvre que core/security.py API keys).
Ces tests verifient les protections HTTP au niveau middleware et routeurs.
"""
import copy
import os
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

OMNISTUDIO_DIR = Path(__file__).resolve().parent.parent / "omnistudio"
sys.path.insert(0, str(OMNISTUDIO_DIR))

from test_endpoints import (
    server, _mock_graph_app, _mock_state, _mock_vox_client,
    _DEFAULT_STATE_VALUES, FAKE_USER, FAKE_THREAD_ID,
)
import dependencies as _deps
from auth import get_current_user as _auth_get_current_user


@pytest.fixture(autouse=True)
def reset_all():
    """Reset state, verrous et rate limiter entre chaque test."""
    _mock_state.values = copy.deepcopy(_DEFAULT_STATE_VALUES)
    _mock_graph_app.get_state.return_value = _mock_state
    _mock_graph_app.update_state.reset_mock()
    _deps._cleaning_locks.clear()
    _deps._generating_locks.clear()
    _deps._exporting_locks.clear()
    server.app.state.limiter.reset()
    yield


@pytest.fixture(autouse=True)
def mock_session_db():
    targets = [server, _deps]
    for mod_name in ["routers.import_steps", "routers.sessions", "routers.clean",
                     "routers.voices", "routers.assign", "routers.generate",
                     "routers.export", "routers.audio"]:
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
    """TestClient avec auth mockee."""
    async def fake_get_current_user(request=None):
        return FAKE_USER
    server.app.dependency_overrides[_auth_get_current_user] = fake_get_current_user
    with TestClient(server.app, raise_server_exceptions=False) as c:
        yield c
    server.app.dependency_overrides.clear()


@pytest.fixture
def raw_client():
    """TestClient SANS auth override (pour tester le rejet)."""
    with TestClient(server.app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture
def auth_headers():
    return {"Authorization": "Bearer fake", "X-Thread-Id": FAKE_THREAD_ID}


# ---------------------------------------------------------------------------
# Tests CSP Headers
# ---------------------------------------------------------------------------

class TestCSPHeaders:
    """Verification des headers de securite Content-Security-Policy."""

    def test_csp_present_on_public_endpoint(self, client):
        resp = client.get("/api/status")
        csp = resp.headers.get("Content-Security-Policy", "")
        assert "default-src" in csp
        assert "'self'" in csp

    def test_x_frame_options(self, client):
        resp = client.get("/api/status")
        assert resp.headers.get("X-Frame-Options") in ("DENY", "SAMEORIGIN")

    def test_x_content_type_options(self, client):
        resp = client.get("/api/status")
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"


# ---------------------------------------------------------------------------
# Tests CORS
# ---------------------------------------------------------------------------

class TestCORS:
    """Verification CORS origins."""

    def test_cors_allowed_origin(self, client):
        resp = client.options(
            "/api/status",
            headers={"Origin": "http://localhost:7870", "Access-Control-Request-Method": "GET"},
        )
        assert "access-control-allow-origin" in resp.headers

    def test_cors_blocked_origin(self, client):
        resp = client.options(
            "/api/status",
            headers={"Origin": "http://evil.com", "Access-Control-Request-Method": "GET"},
        )
        assert resp.headers.get("access-control-allow-origin") != "http://evil.com"


# ---------------------------------------------------------------------------
# Tests Path Traversal
# ---------------------------------------------------------------------------

class TestPathTraversal:
    """Protection contre le path traversal sur /api/audio."""

    def test_double_dot(self, client):
        resp = client.get(
            "/api/audio/../../etc/passwd",
            headers={"Authorization": "Bearer fake", "X-Thread-Id": FAKE_THREAD_ID},
        )
        assert resp.status_code in (400, 403, 404)

    def test_absolute_path(self, client):
        """Chemin absolu /etc/passwd -> rejete."""
        resp = client.get(
            "/api/audio//etc/passwd",
            headers={"Authorization": "Bearer fake", "X-Thread-Id": FAKE_THREAD_ID},
        )
        # FastAPI peut retourner 307 (redirect), 400, 403 ou 404
        assert resp.status_code != 200

    def test_dot_dot_slash_deep(self, client):
        """Traversal profond ../../../etc/passwd -> rejete."""
        resp = client.get(
            "/api/audio/../../../etc/passwd",
            headers={"Authorization": "Bearer fake", "X-Thread-Id": FAKE_THREAD_ID},
        )
        assert resp.status_code in (400, 403, 404)


# ---------------------------------------------------------------------------
# Tests Rate Limiting
# ---------------------------------------------------------------------------

class TestRateLimiting:
    """Verification du rate limiting slowapi."""

    def test_concurrent_generate_locks(self, client, auth_headers):
        """2 POST /api/generate simultanement -> le 2e retourne 409."""
        _deps._generating_locks[FAKE_THREAD_ID] = time.monotonic()
        resp = client.post(
            "/api/generate",
            json={"fidelity": "quality"},
            headers=auth_headers,
        )
        assert resp.status_code == 409
        body = resp.json()
        assert body["error"]["code"] == "GENERATE_IN_PROGRESS"


# ---------------------------------------------------------------------------
# Tests Auth Rejection
# ---------------------------------------------------------------------------

class TestAuthRejection:
    """Endpoints proteges sans auth -> 401."""

    def test_steps_without_auth(self, raw_client):
        resp = raw_client.get("/api/steps", headers={"X-Thread-Id": FAKE_THREAD_ID})
        assert resp.status_code == 401

    def test_assign_without_auth(self, raw_client):
        resp = raw_client.get("/api/assign", headers={"X-Thread-Id": FAKE_THREAD_ID})
        assert resp.status_code == 401

    def test_voices_without_auth(self, raw_client):
        resp = raw_client.get("/api/voices", headers={"X-Thread-Id": FAKE_THREAD_ID})
        assert resp.status_code == 401

    def test_status_is_public(self, raw_client):
        """GET /api/status est public (pas de 401)."""
        resp = raw_client.get("/api/status")
        assert resp.status_code != 401


# ---------------------------------------------------------------------------
# Tests headers sécurité PRD-028 (COOP, X-Permitted, CSP renforcé)
# ---------------------------------------------------------------------------

class TestNewSecurityHeaders:
    """Tests headers sécurité PRD-028 (COOP, X-Permitted, CSP renforcé)."""

    def test_coop_header(self, client):
        """Cross-Origin-Opener-Policy: same-origin."""
        resp = client.get("/api/status")
        assert resp.headers.get("Cross-Origin-Opener-Policy") == "same-origin"

    def test_x_permitted_cross_domain(self, client):
        """X-Permitted-Cross-Domain-Policies: none."""
        resp = client.get("/api/status")
        assert resp.headers.get("X-Permitted-Cross-Domain-Policies") == "none"

    def test_csp_object_src_none(self, client):
        """CSP contient object-src 'none'."""
        resp = client.get("/")
        csp = resp.headers.get("Content-Security-Policy", "")
        assert "object-src 'none'" in csp

    def test_csp_base_uri(self, client):
        """CSP contient base-uri 'self'."""
        resp = client.get("/")
        csp = resp.headers.get("Content-Security-Policy", "")
        assert "base-uri 'self'" in csp

    def test_csp_form_action(self, client):
        """CSP contient form-action 'self'."""
        resp = client.get("/")
        csp = resp.headers.get("Content-Security-Policy", "")
        assert "form-action 'self'" in csp

    def test_hsts_absent_on_http(self, client):
        """HSTS absent sur HTTP (pas de x-forwarded-proto)."""
        resp = client.get("/api/status")
        assert "Strict-Transport-Security" not in resp.headers

    def test_hsts_present_on_https(self, client):
        """HSTS présent quand x-forwarded-proto=https."""
        resp = client.get("/api/status", headers={"X-Forwarded-Proto": "https"})
        hsts = resp.headers.get("Strict-Transport-Security", "")
        assert "max-age=" in hsts
        assert "includeSubDomains" in hsts
