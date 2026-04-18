"""Tests voix aléatoire POST /auto — Phase 2 rouges.

Spécification : PRD v1.5 décision 15.
"""
import pytest


class TestRouteRandom:
    def test_route_generate_random_proxy_auto(self):
        """POST /api/generate/random proxie vers OmniVoice POST /auto."""
        pytest.skip("Mock OmniVoice — Phase 3")

    def test_3_appels_successifs_3_audios_differents(self):
        """Vérifie le non-déterminisme de /auto (voix change à chaque appel)."""
        pytest.skip("Test audio — Phase 8")

    def test_voix_aleatoire_non_sauvegardee_en_custom(self):
        """L'audio généré n'ajoute PAS de voix à voices/custom/."""
        pytest.skip("Intégration — Phase 3")


class TestUXBoutonRandom:
    def test_bouton_visible_onglet5(self):
        pytest.skip("Test JS — Playwright Phase 8")

    def test_toast_informatif_apres_generation(self):
        """Toast DSFR : « Voix aléatoire générée. Pour la conserver... »"""
        pytest.skip("Test JS — Playwright Phase 8")


class TestRateLimiting:
    def test_rate_limit_5_par_minute(self):
        """Même limite que /api/generate/sample."""
        pytest.skip("Mock slowapi — Phase 3")
