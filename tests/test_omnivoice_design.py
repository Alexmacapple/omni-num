"""Tests Voice Design modes Guidé + Expert — Phase 2 rouges.

Spécification : PRD v1.5 décision 5 + 12.
Code cible :
- omnistudio/core/omnivoice_client.py::design_from_attributes
- omnistudio/routers/voices.py (gestion 422)
"""
import pytest


class TestDesignFromAttributes:
    """Composition de la chaîne EN depuis les selects Guidé."""

    def test_composition_4_attributs_basiques(self):
        from core.omnivoice_client import design_from_attributes
        result = design_from_attributes(
            gender="Female", age="Young Adult", pitch="High Pitch", style="Neutral"
        )
        assert "female" in result.lower()
        assert "young adult" in result.lower()
        assert "high pitch" in result.lower()

    def test_style_whisper_ajoute(self):
        from core.omnivoice_client import design_from_attributes
        result = design_from_attributes(
            gender="Male", age="Middle-aged", pitch="Low Pitch", style="Whisper"
        )
        assert "whisper" in result.lower()

    def test_accent_anglais_ajoute_si_langue_en(self):
        from core.omnivoice_client import design_from_attributes
        result = design_from_attributes(
            gender="Female", age="Middle-aged", pitch="Moderate Pitch", style="Neutral",
            language="en", accent="British"
        )
        assert "british" in result.lower()

    def test_dialecte_chinois_mappe_vers_caracteres(self):
        from core.omnivoice_client import design_from_attributes
        result = design_from_attributes(
            gender="Male", age="Middle-aged", pitch="Moderate Pitch", style="Neutral",
            language="zh", dialect="Sichuan"
        )
        assert "四川话" in result


class TestModeExpert:
    def test_saisie_anglaise_directe_acceptee(self):
        from core.omnivoice_client import OmniVoiceClient
        client = OmniVoiceClient()
        # En mode Expert, on envoie la chaîne EN telle quelle
        # (test d'intégration à faire avec mock OmniVoice)
        pytest.skip("Mock OmniVoice — Phase 3")

    def test_saisie_francaise_rejetee_422(self):
        """OmniVoice rejette le français pour /design (erreur 422 native)."""
        pytest.skip("Mock OmniVoice 422 — Phase 3")


class TestConditionnelAccentDialect:
    def test_accent_hors_langue_en_est_ignore(self):
        """Si language='fr' et accent='British' → accent ignoré (UI le désactive)."""
        from core.omnivoice_client import design_from_attributes
        result = design_from_attributes(
            gender="Female", age="Middle-aged", pitch="Moderate Pitch", style="Neutral",
            language="fr", accent="British"  # UI ne devrait pas envoyer ça
        )
        # Backend ignore defensivement
        assert "british" not in result.lower()


class TestToastErreur422:
    def test_message_toast_explicite(self):
        """Le toast DSFR affiché sur 422 doit mentionner « mots non reconnus »."""
        pytest.skip("Test JS — Playwright Phase 8")
