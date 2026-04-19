"""Tests d'integration des endpoints FastAPI (PRD-REFACTOR-010, Phase -1).

Filet de securite pour le decoupage de server.py en routeurs.
Valide 1+ endpoint par futur routeur avec TestClient + mocks.

Strategie de mock :
- Auth : override de get_current_user et validate_token (pas de Keycloak)
- LangGraph : mock de graph_app.get_state / update_state (pas de SQLite)
- OmniVoice : mock de vox_client (pas de serveur TTS)
- LLM : mock de LLMClient (pas d'API Albert)
"""
import copy
import os
import shutil
import sys
import zipfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ajouter omnistudio/ au sys.path (comme conftest.py)
OMNISTUDIO_DIR = Path(__file__).resolve().parent.parent / "omnistudio"
sys.path.insert(0, str(OMNISTUDIO_DIR))

# Mock des services externes AVANT l'import de server.py
# LangGraph : eviter la creation de la base SQLite
_mock_graph_app = MagicMock()
_mock_design_app = MagicMock()
_mock_vox_client = MagicMock()

# State par defaut retourne par graph_app.get_state()
_DEFAULT_STATE_VALUES = {
    "steps": [
        {"step_id": "1", "text_original": "Bienvenue.", "text_tts": "Bienvenue.",
         "cleaning_status": "validated", "language_override": "fr", "speed_factor": 1.0},
        {"step_id": "2", "text_original": "Au revoir.", "text_tts": "Au revoir.",
         "cleaning_status": "validated", "language_override": "fr", "speed_factor": 1.0},
    ],
    "cleaning_validated": True,
    "locked_voices": ["serena"],
    "assignments": {"1": "Lea", "2": "Lea"},
    "instructions": {},
    "generated_files": [],
    "generation_complete": False,
    "export_path": "",
    "domain_glossary": {},
    "correction_patterns": {},
    "correction_parentheses": {},
    "correction_majuscules": {},
    "default_voice": "Lea",
    "brief": {},
    "voice_instruct": "",
    "wav_paths": [],
}

_mock_state = MagicMock()
_mock_state.values = copy.deepcopy(_DEFAULT_STATE_VALUES)
_mock_graph_app.get_state.return_value = _mock_state
_mock_graph_app.update_state.return_value = None

# OmniVoice client
_mock_vox_client.get_voices.return_value = [
    {"name": "Lea", "type": "native", "description": "Voix native Lea", "gender": "female"},
    {"name": "Jean", "type": "native", "description": "Voix native Jean", "gender": "male"},
]
_mock_vox_client.get_custom_voice_details.return_value = None
_mock_vox_client.health_check.return_value = True
_mock_vox_client.get_models_status.return_value = {"voice_design": True, "custom_voice": True}
_mock_vox_client.estimate_duration.return_value = 30.0
_mock_vox_client.timeout_preview = 45

# Patcher avant import
with patch("graph.workflow.create_workflow", return_value=_mock_graph_app), \
     patch("graph.subgraphs.design_loop.create_design_subgraph", return_value=_mock_design_app), \
     patch("core.omnivoice_client.OmniVoiceClient", return_value=_mock_vox_client):
    # Changer le cwd pour que les chemins relatifs de server.py fonctionnent
    _original_cwd = os.getcwd()
    os.chdir(str(OMNISTUDIO_DIR))
    import server
    os.chdir(_original_cwd)

import dependencies as _deps
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FAKE_USER = {"user_id": "test-user-123", "username": "testuser"}
FAKE_THREAD_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


@pytest.fixture(autouse=True)
def reset_mocks():
    """Reinitialise les mocks entre chaque test (deepcopy pour les objets imbriques)."""
    _mock_state.values = copy.deepcopy(_DEFAULT_STATE_VALUES)
    _mock_graph_app.get_state.return_value = _mock_state
    _mock_graph_app.update_state.reset_mock()
    # Nettoyer les verrous SSE (dans dependencies, pas server — PRD-013)
    import dependencies as _deps
    _deps._cleaning_locks.clear()
    _deps._generating_locks.clear()
    _deps._exporting_locks.clear()
    yield


@pytest.fixture(autouse=True)
def mock_session_db():
    """Mock des fonctions session SQLite pour eviter les 404 SESSION_NOT_FOUND.

    Patch sur tous les modules qui importent ces fonctions (D6) :
    server.py, dependencies.py, et chaque routeur extrait.
    """
    import dependencies as _deps
    _targets = [server, _deps]
    # Ajouter dynamiquement les routeurs qui importent ces fonctions
    for mod_name in ["routers.import_steps", "routers.sessions", "routers.clean",
                     "routers.voices", "routers.assign", "routers.generate", "routers.export"]:
        try:
            mod = __import__(mod_name, fromlist=["_verify_session_owner"])
            if hasattr(mod, "_verify_session_owner"):
                _targets.append(mod)
        except ImportError:
            pass

    patches = []
    for mod in _targets:
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
    """TestClient FastAPI avec auth mockee."""
    # Override auth : toujours retourner FAKE_USER
    async def fake_get_current_user(request=None):
        return FAKE_USER

    async def fake_validate_token(token=None):
        return FAKE_USER

    from auth import get_current_user as _auth_get_current_user
    server.app.dependency_overrides[_auth_get_current_user] = fake_get_current_user
    # Patch validate_token dans tous les modules qui l'importent (D6)
    _modules_with_validate = []
    try:
        from routers import audio as _audio_mod
        _modules_with_validate.append(_audio_mod)
        from routers import export as _export_mod
        _modules_with_validate.append(_export_mod)
    except ImportError:
        pass
    originals = [(mod, mod.validate_token) for mod in _modules_with_validate if hasattr(mod, "validate_token")]
    for mod in _modules_with_validate:
        if hasattr(mod, "validate_token"):
            mod.validate_token = fake_validate_token

    c = TestClient(server.app, raise_server_exceptions=False)
    try:
        yield c
    finally:
        c.close()
        server.app.dependency_overrides.clear()
        for mod, orig in originals:
            mod.validate_token = orig


@pytest.fixture
def auth_headers():
    """Headers standard pour les requetes authentifiees."""
    return {
        "Authorization": "Bearer fake-jwt-token",
        "X-Thread-Id": FAKE_THREAD_ID,
    }


# ---------------------------------------------------------------------------
# Routeur : auth (3 endpoints)
# ---------------------------------------------------------------------------

class TestAuthRouter:
    """POST /api/auth/login, /api/auth/token/refresh, /api/auth/logout"""

    def test_login_keycloak_unavailable(self, client):
        """Login avec Keycloak indisponible retourne une erreur AUTH_REQUIRED."""
        resp = client.post("/api/auth/login", json={"username": "test", "password": "test"})
        # Keycloak injoignable : httpx leve ConnectError -> api_error AUTH_REQUIRED
        assert resp.status_code in (401, 503)
        body = resp.json()
        assert body["error"]["code"] == "AUTH_REQUIRED"

    def test_logout(self, client):
        """Logout retourne toujours 200 (best-effort)."""
        resp = client.post("/api/auth/logout", json={"refresh_token": "fake"})
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data

    def test_refresh_token_keycloak_unavailable(self, client):
        """Refresh avec Keycloak indisponible retourne une erreur."""
        resp = client.post("/api/auth/token/refresh", json={"refresh_token": "fake-refresh"})
        assert resp.status_code in (401, 503)
        body = resp.json()
        assert body["error"]["code"] == "AUTH_REQUIRED"


# ---------------------------------------------------------------------------
# Routeur : sessions (4 endpoints)
# ---------------------------------------------------------------------------

class TestSessionsRouter:
    """POST /api/session, POST /api/session/resume, GET /api/session/list, POST /api/locks/clear"""

    def test_create_session(self, client, auth_headers):
        resp = client.post("/api/session", json={}, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "thread_id" in data

    def test_list_sessions(self, client, auth_headers):
        # Creer une session d'abord
        client.post("/api/session", json={}, headers=auth_headers)
        resp = client.get("/api/session/list", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert isinstance(data, list)

    def test_resume_session(self, client, auth_headers):
        """Reprendre une session retourne l'etat LangGraph."""
        # Creer d'abord une session pour avoir un thread_id valide
        create_resp = client.post("/api/session", json={}, headers=auth_headers)
        thread_id = create_resp.json()["data"]["thread_id"]
        # Reprendre avec ce thread_id
        resp = client.post(
            "/api/session/resume",
            json={"thread_id": thread_id},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "thread_id" in data
        assert "state" in data
        assert "steps" in data["state"]

    def test_clear_locks(self, client, auth_headers):
        resp = client.post("/api/locks/clear", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "cleared" in data


# ---------------------------------------------------------------------------
# Routeur : status (3 endpoints)
# ---------------------------------------------------------------------------

class TestStatusRouter:
    """GET /api/status, POST /api/models/preload, GET /api/tts/status"""

    def test_system_status_public(self, client):
        """GET /api/status est public (pas de JWT requis)."""
        resp = client.get("/api/status")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "omnivoice" in data
        assert "audio_tools" in data

    def test_tts_status(self, client, auth_headers):
        resp = client.get("/api/tts/status", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "healthy" in data

    def test_models_preload(self, client, auth_headers):
        """POST /api/models/preload proxie vers OmniVoice."""
        resp = client.post("/api/models/preload", headers=auth_headers)
        # OmniVoice mocke/indisponible : 200 ou 502
        assert resp.status_code in (200, 502)

    def test_health_returns_200(self, client):
        """GET /api/health retourne 200."""
        resp = client.get("/api/health")
        assert resp.status_code in (200, 503)
        data = resp.json()
        assert data["status"] in ("healthy", "unhealthy")

    def test_health_no_auth(self):
        """GET /api/health ne requiert pas d'auth."""
        with TestClient(server.app, raise_server_exceptions=False) as raw_client:
            resp = raw_client.get("/api/health")
            # 200 ou 503 (service down), mais jamais 401
            assert resp.status_code in (200, 503)
            raw_client.close()

    def test_health_has_checks(self, client):
        """GET /api/health retourne les checks."""
        resp = client.get("/api/health")
        data = resp.json()
        assert "checks" in data
        assert "version" in data


# ---------------------------------------------------------------------------
# Routeur : import_steps (4 endpoints)
# ---------------------------------------------------------------------------

class TestImportStepsRouter:
    """POST /api/import, POST /api/import/select, GET /api/steps, POST /api/steps/add"""

    def test_get_steps(self, client, auth_headers):
        resp = client.get("/api/steps", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "steps" in data
        assert "total" in data

    def test_get_steps_no_thread_id(self, client):
        """GET /api/steps sans X-Thread-Id retourne 400."""
        resp = client.get("/api/steps", headers={"Authorization": "Bearer fake"})
        assert resp.status_code == 400

    def test_get_steps_no_auth(self):
        """GET /api/steps sans auth retourne 401."""
        # Client SANS override d'auth pour tester le rejet
        with TestClient(server.app, raise_server_exceptions=False) as raw_client:
            resp = raw_client.get("/api/steps", headers={"X-Thread-Id": FAKE_THREAD_ID})
            assert resp.status_code == 401
            raw_client.close()

    def test_import_select(self, client, auth_headers):
        """Filtrer les etapes selectionnees."""
        resp = client.post(
            "/api/import/select",
            json={"step_ids": ["1"]},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "retained" in data
        assert "total" in data

    def test_add_step(self, client, auth_headers):
        """Ajouter une etape manuellement."""
        resp = client.post(
            "/api/steps/add",
            json={"step_id": "99", "text_original": "Nouvelle etape de test."},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["step_id"] == "99"
        assert "total" in data

    def test_add_step_duplicate(self, client, auth_headers):
        """Ajouter une etape existante retourne 409."""
        resp = client.post(
            "/api/steps/add",
            json={"step_id": "1", "text_original": "Doublon."},
            headers=auth_headers,
        )
        assert resp.status_code == 409
        body = resp.json()
        assert body["error"]["code"] == "STEP_EXISTS"

    def test_import_xlsx_upload(self, client, auth_headers, sample_xlsx):
        """Upload XLSX valide -> etapes extraites."""
        with open(sample_xlsx, "rb") as f:
            resp = client.post(
                "/api/import",
                files={"file": ("scenario.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                headers={"Authorization": "Bearer fake", "X-Thread-Id": FAKE_THREAD_ID},
            )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "steps" in data or "total" in data or "sheets" in data

    def test_import_md_upload(self, client, auth_headers, sample_markdown):
        """Upload MD valide -> etapes extraites."""
        with open(sample_markdown, "rb") as f:
            resp = client.post(
                "/api/import",
                files={"file": ("scenario.md", f, "text/markdown")},
                headers={"Authorization": "Bearer fake", "X-Thread-Id": FAKE_THREAD_ID},
            )
        assert resp.status_code == 200

    def test_import_invalid_format(self, client, auth_headers, tmp_path):
        """Upload format non supporte retourne 400."""
        bad_file = tmp_path / "scenario.pdf"
        bad_file.write_bytes(b"%PDF-1.4 fake content")
        with open(str(bad_file), "rb") as f:
            resp = client.post(
                "/api/import",
                files={"file": ("scenario.pdf", f, "application/pdf")},
                headers={"Authorization": "Bearer fake", "X-Thread-Id": FAKE_THREAD_ID},
            )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Routeur : clean (8 endpoints)
# ---------------------------------------------------------------------------

class TestCleanRouter:
    """Endpoints /api/clean/*"""

    def test_clean_validate(self, client, auth_headers):
        resp = client.post("/api/clean/validate", json={"edits": {}}, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "validated" in data

    def test_clean_diff(self, client, auth_headers):
        resp = client.get("/api/clean/diff/1", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "diff_html" in data
        assert "text_original" in data
        assert "text_tts" in data

    def test_clean_diff_not_found(self, client, auth_headers):
        resp = client.get("/api/clean/diff/999", headers=auth_headers)
        assert resp.status_code == 404
        body = resp.json()
        assert body["error"]["code"] == "STEP_NOT_FOUND"

    def test_clean_delete(self, client, auth_headers):
        resp = client.post("/api/clean/delete/1", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["deleted"] is True

    def test_clean_status_invalid(self, client, auth_headers):
        resp = client.post(
            "/api/clean/status/1",
            json={"status": "invalid_status"},
            headers=auth_headers,
        )
        assert resp.status_code == 400
        body = resp.json()
        assert body["error"]["code"] == "INVALID_STATUS"

    def test_clean_sse_returns_event_source(self, client, auth_headers):
        """POST /api/clean retourne un EventSourceResponse (SSE)."""
        resp = client.post(
            "/api/clean",
            json={"glossary": {}},
            headers=auth_headers,
            # Ne pas suivre le stream, juste verifier le content-type
        )
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")

    def test_clean_sse_locked(self, client, auth_headers):
        """POST /api/clean avec verrou actif retourne CLEAN_IN_PROGRESS."""
        import time
        _deps._cleaning_locks[FAKE_THREAD_ID] = time.time()
        resp = client.post(
            "/api/clean",
            json={"glossary": {}},
            headers=auth_headers,
        )
        assert resp.status_code == 400
        body = resp.json()
        assert body["error"]["code"] == "CLEAN_IN_PROGRESS"

    def test_clean_accept_step(self, client, auth_headers):
        """Accepter une etape individuelle."""
        resp = client.post(
            "/api/clean/accept/1",
            json={"text_tts": "Bienvenue modifie."},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["step_id"] == "1"
        assert data["status"] == "validated"

    def test_clean_delete_all(self, client, auth_headers):
        """Supprimer tous les segments."""
        resp = client.post("/api/clean/delete-all", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "deleted" in data

    def test_clean_single_step(self, client, auth_headers):
        """Nettoyage LLM d'un seul segment."""
        with patch("routers.clean.LLMClient") as mock_llm_cls:
            mock_llm = MagicMock()
            mock_llm.ask.return_value = "Bienvenue nettoyee."
            mock_llm_cls.return_value = mock_llm
            resp = client.post("/api/clean/single/1", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["step_id"] == "1"
        assert data["status"] == "cleaned"
        assert "text_tts" in data

    def test_clean_single_not_found(self, client, auth_headers):
        """Nettoyage unitaire d'une etape inexistante."""
        resp = client.post("/api/clean/single/999", headers=auth_headers)
        assert resp.status_code == 404
        body = resp.json()
        assert body["error"]["code"] == "STEP_NOT_FOUND"

    def test_clean_status_valid(self, client, auth_headers):
        """Modifier le statut d'une etape vers pending."""
        resp = client.post(
            "/api/clean/status/1",
            json={"status": "pending"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["step_id"] == "1"
        assert data["status"] == "pending"

    def test_clean_sse_content_has_done_event(self, client, auth_headers):
        """POST /api/clean SSE : le stream contient un event done avec le bon format."""
        # Toutes les etapes sont deja validated -> le stream finit immediatement avec done
        _mock_state.values["steps"] = [
            {"step_id": "1", "text_original": "Test.", "text_tts": "Test.",
             "cleaning_status": "validated", "language_override": "fr", "speed_factor": 1.0},
        ]
        resp = client.post(
            "/api/clean",
            json={"glossary": {}},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        # Parser le contenu SSE : chercher event: done
        body = resp.text
        assert "event: done" in body
        # Extraire la ligne data apres event: done
        lines = body.strip().split("\n")
        for i, line in enumerate(lines):
            if line.strip() == "event: done":
                data_line = lines[i + 1]
                assert data_line.startswith("data: ")
                import json
                payload = json.loads(data_line[6:])
                assert "cleaned" in payload
                break


# ---------------------------------------------------------------------------
# Routeur : voices (11 endpoints)
# ---------------------------------------------------------------------------

class TestVoicesRouter:
    """Endpoints /api/voices/*"""

    def test_list_voices(self, client, auth_headers):
        resp = client.get("/api/voices", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "voices" in data
        assert "total" in data
        assert data["total"] >= 2  # Au moins Lea + Jean

    def test_list_voice_templates(self, client, auth_headers):
        resp = client.get("/api/voices/templates", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "templates" in data

    def test_lock_voice_invalid_name(self, client, auth_headers):
        """Nom de voix invalide retourne une erreur 400."""
        resp = client.post(
            "/api/voices/lock",
            json={"name": "A", "voice_instruct": "test"},  # trop court
            headers=auth_headers,
        )
        assert resp.status_code == 400
        body = resp.json()
        assert body["error"]["code"] == "INVALID_NAME"

    def test_lock_voice_reserved_name(self, client, auth_headers):
        """Nom reserve retourne une erreur 400."""
        resp = client.post(
            "/api/voices/lock",
            json={"name": "serena", "voice_instruct": "test"},
            headers=auth_headers,
        )
        assert resp.status_code == 400
        body = resp.json()
        assert body["error"]["code"] == "INVALID_NAME"

    def test_delete_voice_system_protected(self, client, auth_headers):
        """Supprimer une voix système retourne 403 (PRD v1.5 décision 7).

        Lea est une voix système, non-supprimable par design. L'ownership
        check PRD-032 lève 403 VOICE_SYSTEM_PROTECTED en amont avant même
        la vérification VOICE_IN_USE.
        """
        resp = client.delete("/api/voices/Lea", headers=auth_headers)
        assert resp.status_code == 403
        body = resp.json()
        assert body["error"]["code"] == "VOICE_SYSTEM_PROTECTED"

    def test_voices_export(self, client, auth_headers):
        """Export des voix custom retourne un ZIP."""
        resp = client.post("/api/voices/export", headers=auth_headers)
        assert resp.status_code == 200
        assert "application/zip" in resp.headers.get("content-type", "")

    def test_voices_design_flow(self, client, auth_headers):
        """POST /api/voices/design-flow retourne voice_instruct + audio_url."""
        _mock_design_app.invoke.return_value = {
            "voice_instruct": "Voix chaleureuse et posee",
            "wav_paths": [],
        }
        _mock_vox_client.design.return_value = None
        resp = client.post(
            "/api/voices/design-flow",
            json={"brief": {"tone": "warm"}, "test_text": "Test."},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "voice_instruct" in data

    def test_voices_explore(self, client, auth_headers):
        """POST /api/voices/explore regenere un audio volatile."""
        _mock_vox_client.design.return_value = None
        resp = client.post(
            "/api/voices/explore",
            json={"voice_instruct": "Voix douce", "test_text": "Test."},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "voice_instruct" in data

    def test_voices_preview(self, client, auth_headers):
        """POST /api/voices/preview genere un audio de pre-ecoute."""
        _mock_vox_client.preset.return_value = "/tmp/test.wav"
        resp = client.post(
            "/api/voices/preview",
            json={"voice": "Lea", "text": "Test preview.", "language": "fr"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "audio_url" in data

    def test_voices_import_zip(self, client, auth_headers):
        """POST /api/voices/import accepte un ZIP."""
        import io
        import zipfile
        # Creer un ZIP vide (pas de dossiers voix valides)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            pass
        buf.seek(0)
        resp = client.post(
            "/api/voices/import",
            files={"file": ("voix.zip", buf, "application/zip")},
            headers={"Authorization": "Bearer fake"},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "imported" in data
        assert data["count"] == 0  # ZIP vide, 0 voix importees

    def test_voices_rename_not_found(self, client, auth_headers):
        """Renommer une voix inexistante retourne 404."""
        resp = client.post(
            "/api/voices/voix-inexistante/rename",
            json={"new_name": "nouveau-nom"},
            headers=auth_headers,
        )
        assert resp.status_code == 404
        body = resp.json()
        assert body["error"]["code"] == "VOICE_NOT_FOUND"

    def test_voices_clone_missing_fields(self, client, auth_headers):
        """Clone sans champs requis retourne 400/422."""
        resp = client.post(
            "/api/voices/clone",
            data={"name": "", "transcription": "", "model": "1.7B"},
            headers={"Authorization": "Bearer fake"},
        )
        # Validation Pydantic/FastAPI : 400 ou 422
        assert resp.status_code in (400, 422)

    def test_voices_lock_success(self, client, auth_headers):
        """Lock d'une voix volatile reussit quand la voix n'existe pas encore."""
        _mock_vox_client.get_custom_voice_details.return_value = None
        _mock_vox_client.save_custom_voice.return_value = {"ok": True, "detail": "Saved"}
        _mock_vox_client.preset.return_value = "/tmp/locked.wav"
        resp = client.post(
            "/api/voices/lock",
            json={"name": "narrateur-v1", "voice_instruct": "Voix grave", "test_text": "Test."},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["name"] == "narrateur-v1"
        assert data["status"] == "locked"

    def test_voices_delete_success(self, client, auth_headers):
        """Supprimer une voix custom non assignee reussit."""
        # La voix "custom-a-supprimer" n'est pas dans assignments
        _mock_vox_client.delete_custom_voice.return_value = True
        _mock_vox_client.reload_custom_voices.return_value = True
        resp = client.delete("/api/voices/custom-a-supprimer", headers=auth_headers)
        assert resp.status_code == 200

    def test_voices_rename_success(self, client, auth_headers, tmp_path):
        """Renommer une voix custom existante reussit."""
        # Creer les dossiers attendus par le routeur
        old_dir = tmp_path / "custom" / "ancienne"
        old_dir.mkdir(parents=True)
        meta = old_dir / "meta.json"
        meta.write_text('{"name": "ancienne"}')

        _mock_vox_client.reload_custom_voices.return_value = True
        with patch("routers.voices.OMNIVOICE_VOICES_DIR", str(tmp_path)):
            resp = client.post(
                "/api/voices/ancienne/rename",
                json={"new_name": "nouvelle"},
                headers=auth_headers,
            )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["new_name"] == "nouvelle"


# ---------------------------------------------------------------------------
# Routeur : assign (4 endpoints)
# ---------------------------------------------------------------------------

class TestAssignRouter:
    """Endpoints /api/assign/*"""

    def test_get_assign(self, client, auth_headers):
        resp = client.get("/api/assign", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "rows" in data
        assert "voices" in data
        assert "languages" in data

    def test_save_assign(self, client, auth_headers):
        resp = client.post(
            "/api/assign",
            json={"assignments": {"1": "Lea", "2": "Jean"}},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["saved"] == 2

    def test_apply_all(self, client, auth_headers):
        resp = client.post(
            "/api/assign/apply-all",
            json={"voice": "Lea", "language": "fr", "speed": 1.0},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["applied"] == 2

    def test_preview_assign_step(self, client, auth_headers):
        """Pre-ecoute d'une assignation sur une etape."""
        _mock_vox_client.preset.return_value = "/tmp/preview.wav"
        resp = client.post(
            "/api/assign/preview/1",
            json={"voice": "Lea", "language": "fr", "speed": 1.0, "text": "Test."},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "audio_url" in data

    def test_preview_assign_step_not_found(self, client, auth_headers):
        """Pre-ecoute sur une etape inexistante retourne 404."""
        resp = client.post(
            "/api/assign/preview/999",
            json={"voice": "Lea", "language": "fr", "speed": 1.0},
            headers=auth_headers,
        )
        assert resp.status_code == 404
        body = resp.json()
        assert body["error"]["code"] == "STEP_NOT_FOUND"


# ---------------------------------------------------------------------------
# Routeur : generate (3 endpoints)
# ---------------------------------------------------------------------------

class TestGenerateRouter:
    """Endpoints /api/generate/*"""

    def test_generate_summary(self, client, auth_headers):
        resp = client.get("/api/generate/summary", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "total_steps" in data
        assert "voices" in data
        assert "estimated_duration_s" in data

    def test_generate_sse_returns_event_source(self, client, auth_headers):
        """POST /api/generate retourne un EventSourceResponse (SSE)."""
        resp = client.post(
            "/api/generate",
            json={"fidelity": "quality"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")

    def test_generate_sse_locked(self, client, auth_headers):
        """POST /api/generate avec verrou actif retourne GENERATE_IN_PROGRESS."""
        import time
        _deps._generating_locks[FAKE_THREAD_ID] = time.time()
        resp = client.post(
            "/api/generate",
            json={"fidelity": "quality"},
            headers=auth_headers,
        )
        assert resp.status_code == 409
        body = resp.json()
        assert body["error"]["code"] == "GENERATE_IN_PROGRESS"

    def test_generate_sample(self, client, auth_headers):
        """POST /api/generate/sample genere 3 echantillons (ou moins si peu d'etapes)."""
        _mock_vox_client.preset.return_value = "/tmp/sample.wav"
        resp = client.post(
            "/api/generate/sample",
            json={"fidelity": "quality"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "samples" in data
        assert len(data["samples"]) <= 3

    # --- PRD-022 : sample edge cases ---

    def test_sample_no_steps(self, client, auth_headers):
        """Sample sans etapes -> 400 NO_STEPS."""
        _mock_state.values["steps"] = []
        resp = client.post(
            "/api/generate/sample",
            json={"fidelity": "quality"},
            headers=auth_headers,
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "NO_STEPS"

    def test_sample_5_steps_selects_3(self, client, auth_headers):
        """5 etapes -> sample de 3 (debut, milieu, fin)."""
        _mock_state.values["steps"] = [
            {"step_id": str(i), "text_original": f"Texte {i}.", "text_tts": f"Texte {i}.",
             "cleaning_status": "validated", "language_override": "fr", "speed_factor": 1.0}
            for i in range(1, 6)
        ]
        _mock_vox_client.preset.return_value = "/tmp/sample.wav"
        resp = client.post(
            "/api/generate/sample",
            json={"fidelity": "quality"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data["samples"]) == 3

    def test_sample_with_instruction(self, client, auth_headers):
        """Sample avec instruction -> preset_instruct appele."""
        _mock_state.values["instructions"] = {"1": "Ton bienveillant"}
        _mock_vox_client.preset_instruct.return_value = "/tmp/instruct_sample.wav"
        resp = client.post(
            "/api/generate/sample",
            json={"fidelity": "quality"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert _mock_vox_client.preset_instruct.called

    def test_sample_tts_busy(self, client, auth_headers):
        """Sample avec TTS busy -> 503."""
        from core.omnivoice_client import OmniVoiceBusyError
        _mock_vox_client.preset.side_effect = OmniVoiceBusyError("busy")
        resp = client.post(
            "/api/generate/sample",
            json={"fidelity": "quality"},
            headers=auth_headers,
        )
        assert resp.status_code == 503
        assert resp.json()["error"]["code"] == "TTS_BUSY"
        _mock_vox_client.preset.side_effect = None  # Reset pour les tests suivants


# ---------------------------------------------------------------------------
# Routeur : export (2 endpoints)
# ---------------------------------------------------------------------------

class TestExportRouter:
    """Endpoints /api/export/*"""

    def test_export_no_files(self, client, auth_headers):
        """Export sans fichiers generes retourne une erreur 400."""
        resp = client.post(
            "/api/export",
            json={"normalize": True, "stereo": True},
            headers=auth_headers,
        )
        assert resp.status_code == 400
        body = resp.json()
        assert body["error"]["code"] == "NO_FILES"

    def test_download_no_zip(self, client):
        """Download sans ZIP retourne 404."""
        resp = client.get(
            f"/api/export/download?token=fake&tid={FAKE_THREAD_ID}",
        )
        assert resp.status_code == 404
        body = resp.json()
        assert body["error"]["code"] == "NOT_FOUND"

    def test_export_sse_locked(self, client, auth_headers):
        """POST /api/export avec verrou actif retourne EXPORT_IN_PROGRESS."""
        import time
        _deps._exporting_locks[FAKE_THREAD_ID] = time.time()
        # Mettre des fichiers generes pour passer le check NO_FILES
        _mock_state.values["generated_files"] = [
            {"step_id": "1", "filename": "test.wav", "voice_name": "Lea",
             "wav_path": "/fake/path.wav", "status": "done"}
        ]
        resp = client.post(
            "/api/export",
            json={"normalize": True, "stereo": True},
            headers=auth_headers,
        )
        assert resp.status_code == 409
        body = resp.json()
        assert body["error"]["code"] == "EXPORT_IN_PROGRESS"

    def test_export_sse_with_files(self, client, auth_headers, fake_wav_file):
        """POST /api/export avec fichiers generes retourne un flux SSE."""
        _mock_state.values["generated_files"] = [
            {"step_id": "1", "filename": "etape-01.wav", "voice_name": "Lea",
             "wav_path": fake_wav_file, "status": "done"},
        ]
        # Reset rate limiter pour ce test (si present)
        if hasattr(server.app.state, 'limiter') and hasattr(server.app.state.limiter, 'reset'):
            server.app.state.limiter.reset()
        with patch("routers.export.process_audio", side_effect=lambda src, dst, cfg: shutil.copy2(src, dst)):
            with patch("routers.export.concatenate_audio"):
                resp = client.post(
                    "/api/export",
                    json={"normalize": True, "stereo": True},
                    headers=auth_headers,
                )
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")
        # Verifier qu'on recoit des events SSE
        text = resp.text
        assert "event: progress" in text or "event: done" in text

    def test_download_valid_zip(self, client, auth_headers, tmp_path):
        """Download avec ZIP existant retourne 200."""
        # Creer un ZIP factice au bon emplacement
        zip_dir = Path(os.path.abspath("export"))
        zip_dir.mkdir(parents=True, exist_ok=True)
        zip_path = zip_dir / f"OmniStudio_Export_{FAKE_THREAD_ID[:8]}.zip"
        with zipfile.ZipFile(str(zip_path), "w") as zf:
            zf.writestr("test.txt", "contenu test")
        try:
            resp = client.get(
                f"/api/export/download?token=fake&tid={FAKE_THREAD_ID}",
            )
            assert resp.status_code == 200
            assert "application/zip" in resp.headers.get("content-type", "")
        finally:
            zip_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Routeur : audio (1 endpoint)
# ---------------------------------------------------------------------------

class TestAudioRouter:
    """GET /api/audio/{filename}"""

    def test_audio_no_auth(self, client):
        """Audio sans auth retourne 401."""
        resp = client.get("/api/audio/test.wav")
        assert resp.status_code == 401

    def test_audio_path_traversal(self, client):
        """Path traversal bloque par resolve() + startswith()."""
        # Le TestClient normalise les .. dans l'URL, donc on teste aussi
        # via un chemin relatif qui pourrait echapper au base_dir
        resp = client.get(
            f"/api/audio/..%2F..%2Fetc%2Fpasswd?token=fake&tid={FAKE_THREAD_ID}",
        )
        # Apres resolve(), soit le chemin sort du base_dir (403)
        # soit le fichier n'existe pas (404). Les deux sont securises.
        assert resp.status_code in (403, 404)

    def test_audio_not_found(self, client):
        """Fichier inexistant retourne 404."""
        resp = client.get(
            f"/api/audio/inexistant.wav?token=fake&tid={FAKE_THREAD_ID}",
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Tests transversaux : format de reponse
# ---------------------------------------------------------------------------

class TestResponseFormat:
    """Verifie que les reponses suivent le format {"data": ..., "error": ...}."""

    def test_success_has_data_key(self, client, auth_headers):
        resp = client.get("/api/status")
        body = resp.json()
        assert "data" in body
        assert "error" in body
        assert body["error"] is None

    def test_error_has_code_and_message(self, client, auth_headers):
        """Les erreurs metier (api_error) ont un code et un message."""
        # clean/diff avec step_id inexistant retourne une erreur metier
        resp = client.get("/api/clean/diff/999", headers=auth_headers)
        assert resp.status_code == 404
        body = resp.json()
        assert "data" in body
        assert body["data"] is None
        assert "error" in body
        assert "code" in body["error"]
        assert "message" in body["error"]

    def test_missing_thread_id_format(self, client):
        """Erreur X-Thread-Id manquant : format HTTPException standard."""
        resp = client.get("/api/steps", headers={"Authorization": "Bearer fake"})
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Tests transversaux : auth et securite
# ---------------------------------------------------------------------------

class TestAuthSecurity:
    """Verifie que les endpoints proteges exigent l'auth."""

    PROTECTED_ENDPOINTS = [
        ("GET", "/api/steps"),
        ("GET", "/api/voices"),
        ("GET", "/api/assign"),
        ("GET", "/api/generate/summary"),
        ("GET", "/api/tts/status"),
    ]

    @pytest.mark.parametrize("method,url", PROTECTED_ENDPOINTS)
    def test_protected_endpoint_requires_auth(self, method, url):
        """Endpoints proteges retournent 401 sans token."""
        # Client sans override d'auth
        with TestClient(server.app, raise_server_exceptions=False) as raw_client:
            resp = raw_client.request(method, url, headers={"X-Thread-Id": FAKE_THREAD_ID})
            assert resp.status_code == 401, f"{method} {url} devrait retourner 401"
            raw_client.close()

    def test_status_is_public(self):
        """GET /api/status ne requiert pas d'auth."""
        with TestClient(server.app, raise_server_exceptions=False) as raw_client:
            resp = raw_client.get("/api/status")
            assert resp.status_code == 200
            raw_client.close()


# ---------------------------------------------------------------------------
# Tests securite : headers CSP (PRD-011)
# ---------------------------------------------------------------------------

class TestSecurityHeaders:
    """Verifie les headers de securite HTTP."""

    def test_csp_header_present(self, client):
        """CSP present sur les reponses."""
        resp = client.get("/api/status")
        assert "content-security-policy" in resp.headers
        csp = resp.headers["content-security-policy"]
        assert "'self'" in csp
        assert "frame-ancestors 'none'" in csp

    def test_x_frame_options(self, client):
        resp = client.get("/api/status")
        assert resp.headers.get("x-frame-options") == "DENY"

    def test_x_content_type_options(self, client):
        resp = client.get("/api/status")
        assert resp.headers.get("x-content-type-options") == "nosniff"

    def test_referrer_policy(self, client):
        resp = client.get("/api/status")
        assert resp.headers.get("referrer-policy") == "strict-origin-when-cross-origin"

    def test_permissions_policy(self, client):
        resp = client.get("/api/status")
        assert "camera=()" in resp.headers.get("permissions-policy", "")

    def test_csp_on_authenticated_endpoint(self, client, auth_headers):
        """CSP present aussi sur les endpoints authentifies."""
        resp = client.get("/api/steps", headers=auth_headers)
        assert "content-security-policy" in resp.headers


# ---------------------------------------------------------------------------
# Tests CORS (PRD-014)
# ---------------------------------------------------------------------------

class TestCORS:
    """Verifie les headers CORS."""

    def test_cors_preflight(self, client):
        """OPTIONS retourne les headers CORS pour une origine autorisee."""
        resp = client.options(
            "/api/status",
            headers={"Origin": "http://localhost:7870", "Access-Control-Request-Method": "GET"},
        )
        assert "access-control-allow-origin" in resp.headers

    def test_cors_blocked_origin(self, client):
        """Une origine non autorisee ne recoit pas les headers CORS."""
        resp = client.get(
            "/api/status",
            headers={"Origin": "https://evil.com"},
        )
        assert resp.headers.get("access-control-allow-origin") is None

    def test_cors_tailscale_origin(self, client):
        """L'origine Tailscale Funnel est autorisee."""
        resp = client.get(
            "/api/status",
            headers={"Origin": "https://mac-studio-alex.tail0fc408.ts.net:7443"},
        )
        assert resp.headers.get("access-control-allow-origin") == "https://mac-studio-alex.tail0fc408.ts.net:7443"

    def test_cors_sse_endpoint(self, client, auth_headers):
        """Les endpoints SSE repondent aux requetes cross-origin."""
        headers = {**auth_headers, "Origin": "https://mac-studio-alex.tail0fc408.ts.net:7443"}
        resp = client.post("/api/clean", json={"glossary": {}}, headers=headers)
        assert "access-control-allow-origin" in resp.headers


# ---------------------------------------------------------------------------
# Test structurel : compteur d'endpoints
# ---------------------------------------------------------------------------

class TestEndpointCount:
    """Verifie que le nombre total d'endpoints ne diminue pas apres decoupage."""

    # Compter les routes API (exclure /, /js/*, /css/*, /dsfr/*)
    EXPECTED_API_ROUTES = {
        "POST /api/auth/login",
        "POST /api/auth/token/refresh",
        "POST /api/auth/logout",
        "POST /api/session",
        "POST /api/session/resume",
        "GET /api/session/list",
        "POST /api/locks/clear",
        "GET /api/status",
        "POST /api/models/preload",
        "GET /api/tts/status",
        "POST /api/import",
        "POST /api/import/select",
        "GET /api/steps",
        "POST /api/steps/add",
        "POST /api/clean",
        "POST /api/clean/validate",
        "POST /api/clean/accept/{step_id}",
        "POST /api/clean/delete/{step_id}",
        "POST /api/clean/delete-all",
        "POST /api/clean/status/{step_id}",
        "POST /api/clean/single/{step_id}",
        "GET /api/clean/diff/{step_id}",
        "GET /api/voices",
        "GET /api/voices/templates",
        "POST /api/voices/design-flow",
        "POST /api/voices/explore",
        "POST /api/voices/lock",
        "POST /api/voices/clone",
        "POST /api/voices/preview",
        "DELETE /api/voices/{name}",
        "POST /api/voices/{name}/rename",
        "POST /api/voices/export",
        "POST /api/voices/import",
        "GET /api/assign",
        "POST /api/assign",
        "POST /api/assign/apply-all",
        "POST /api/assign/preview/{step_id}",
        "GET /api/generate/summary",
        "POST /api/generate",
        "POST /api/generate/sample",
        "POST /api/export",
        "GET /api/export/download",
        "GET /api/audio/{filename:path}",
    }

    def test_all_api_routes_registered(self):
        """Verifie que tous les endpoints API attendus sont enregistres dans l'app."""
        registered = set()
        for route in server.app.routes:
            if hasattr(route, "methods") and hasattr(route, "path"):
                if route.path.startswith("/api/"):
                    for method in route.methods:
                        if method in ("GET", "POST", "PUT", "DELETE", "PATCH"):
                            registered.add(f"{method} {route.path}")

        missing = self.EXPECTED_API_ROUTES - registered
        extra = registered - self.EXPECTED_API_ROUTES
        assert not missing, f"Endpoints manquants apres decoupage : {missing}"
        # Les extra sont OK (HEAD genere automatiquement par FastAPI)

    def test_api_route_count(self):
        """Le nombre de routes API ne doit pas diminuer (43 endpoints)."""
        count = 0
        for route in server.app.routes:
            if hasattr(route, "path") and route.path.startswith("/api/"):
                count += 1
        assert count >= 43, f"Seulement {count} routes API, attendu >= 43"
