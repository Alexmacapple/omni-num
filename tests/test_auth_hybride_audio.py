"""Tests auth hybride /api/audio Bearer OR query token + ownership — Phase 2 rouges.

Spécification : PRD v1.5 risque #11 (contournement IDOR).
Point Codex #3 : la regex du parser multi-voix doit empêcher XSS (séparément).
Ici : les 2 chemins d'auth convergent vers check_voice_ownership.
"""
import pytest


ALEX_SUB = "alex-sub-12345"
BOB_SUB = "bob-sub-67890"


class TestAuthBearerAvecOwnership:
    def test_alex_bearer_accede_a_son_audio(self):
        """Alex avec Bearer valide sur /api/audio/<son_thread>/fichier.wav → 200."""
        pytest.skip("Intégration FastAPI client — Phase 3")

    def test_alex_bearer_tente_audio_bob_403(self):
        """Alex avec Bearer tente d'accéder /api/audio/<thread_bob>/fichier.wav → 403."""
        pytest.skip("Intégration FastAPI — Phase 3")


class TestAuthQueryToken:
    def test_alex_query_token_accede_a_son_audio(self):
        """Alex avec ?token=<son_JWT>&tid=<son_thread> → 200."""
        pytest.skip("Intégration FastAPI — Phase 3")

    def test_alex_query_token_tente_audio_bob_403(self):
        """Alex avec ?token=<son_JWT>&tid=<thread_bob> → 403 (non-contournement IDOR)."""
        pytest.skip("Intégration FastAPI — Phase 3")


class TestCoherenceEntreChemins:
    def test_bearer_et_query_token_meme_ownership_check(self):
        """Les 2 chemins d'auth convergent vers la même fonction check_voice_ownership."""
        pytest.skip("Refactor intermédiaire nécessaire — helper get_audio_user_sub à extraire en Phase 3")


class TestAbsenceAuth:
    def test_ni_bearer_ni_query_401(self):
        pytest.skip("Intégration FastAPI — Phase 3")

    def test_token_invalide_401(self):
        pytest.skip("Intégration FastAPI — Phase 3")
