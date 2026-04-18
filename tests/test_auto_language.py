"""Tests auto-détection de langue — Phase 2 rouges.

Spécification : PRD v1.5 décision 13.
"""
import pytest


class TestAutoLanguage:
    def test_selects_langue_commencent_par_auto(self):
        """Le premier item du select de langue (onglets 4 + 5) est 'Auto'."""
        pytest.skip("Test JS — Playwright Phase 8")

    def test_valeur_auto_envoyee_a_omnivoice(self):
        """Quand l'utilisateur choisit Auto, language='auto' est passé à OmniVoice."""
        from core.omnivoice_client import OmniVoiceClient
        pytest.skip("Mock OmniVoice — Phase 3")

    def test_fallback_fr_si_langdetect_absent(self):
        """OmniVoice fallback FR si langdetect non installé."""
        pytest.skip("Test d'intégration OmniVoice — Phase 3")


class TestDetectionRealiste:
    def test_texte_francais_detecte_fr(self):
        """Audio généré depuis 'Bonjour tout le monde' en auto → prononciation FR."""
        pytest.skip("Test audio — Phase 8")

    def test_texte_anglais_detecte_en(self):
        pytest.skip("Test audio — Phase 8")

    def test_texte_chinois_detecte_zh(self):
        pytest.skip("Test audio — Phase 8")

    def test_texte_mixte_resultat_best_effort(self):
        """Texte FR+EN mixte : détection best-effort (langdetect choisit la dominante)."""
        pytest.skip("Test audio — Phase 8")


class TestUIInfoBulle:
    def test_info_bulle_explique_detection_automatique(self):
        pytest.skip("Audit UX — Phase 4")
