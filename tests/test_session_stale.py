"""Tests anti-cascade session stale — Phase 2 rouges.

Spécification : PRD v1.5 décision 9 (traite PRD-034).
Code cible :
- omnistudio/dependencies.py::release_stale_locks
- omnistudio/routers/clean.py, generate.py, export.py (check is_stale)
- frontend/out/js/api-client.js (compteur 3 erreurs, fr-alert)

Seuil : OMNISTUDIO_STALE_THRESHOLD_MIN = 10 (configurable).
"""
import os
import pytest
from datetime import datetime, timedelta, timezone


class TestIsStale:
    def test_session_recente_pas_stale(self):
        from dependencies import is_session_stale
        recent = datetime.now(timezone.utc) - timedelta(minutes=5)
        assert is_session_stale(recent) is False

    def test_session_ancienne_stale(self):
        from dependencies import is_session_stale
        old = datetime.now(timezone.utc) - timedelta(minutes=15)
        assert is_session_stale(old) is True

    def test_seuil_configurable_via_env(self):
        from dependencies import is_session_stale
        os.environ["OMNISTUDIO_STALE_THRESHOLD_MIN"] = "5"
        middle = datetime.now(timezone.utc) - timedelta(minutes=7)
        assert is_session_stale(middle) is True
        os.environ["OMNISTUDIO_STALE_THRESHOLD_MIN"] = "10"


class TestReleaseStaleLocks:
    def test_verrous_orphelins_liberes_au_demarrage_sse(self):
        from dependencies import release_stale_locks, _cleaning_locks
        thread_id_ancien = "stale-thread-1"
        thread_id_recent = "fresh-thread-2"
        _cleaning_locks[thread_id_ancien] = datetime.now(timezone.utc) - timedelta(minutes=15)
        _cleaning_locks[thread_id_recent] = datetime.now(timezone.utc) - timedelta(minutes=3)
        release_stale_locks()
        assert thread_id_ancien not in _cleaning_locks
        assert thread_id_recent in _cleaning_locks


class TestInterceptorFrontCompteur3:
    """L'intercepteur front compte 3 erreurs consécutives par thread_id.

    Tests front via api-client.js : à simuler en JSDOM ou en vérification statique.
    """

    def test_3_erreurs_409_successives_declenchent_alert(self):
        pytest.skip("Test JS — à vérifier via Playwright en Phase 8")


class TestEventStaleSSE:
    """SSE emet un event 'stale' et ferme proprement si is_stale=True."""

    def test_sse_generate_emet_stale_et_ferme(self):
        pytest.skip("Intégration FastAPI + SSE — Phase 3")


class TestAntiCascadeSeuil:
    """Le seuil 3 erreurs n'est pas dépassé si les erreurs ne sont pas successives."""

    def test_erreur_isolee_ne_declenche_pas_alert(self):
        pytest.skip("Test JS — à vérifier via Playwright en Phase 8")
