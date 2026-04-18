"""Tests route /transcribe (Whisper intégré OmniVoice) — Phase 2 rouges.

Spécification : PRD v1.5 décision 5 (Voice Clone).
"""
import pytest


class TestRouteTranscribe:
    def test_endpoint_transcribe_proxy_omnivoice(self):
        """POST /api/voices/transcribe → OmniVoice POST /transcribe."""
        pytest.skip("Mock OmniVoice — Phase 3")

    def test_retour_json_contient_texte(self):
        """Le retour doit contenir le champ `text` (transcription brute)."""
        pytest.skip("Mock OmniVoice — Phase 3")

    def test_rate_limit_5_par_minute(self):
        pytest.skip("Mock slowapi — Phase 3")


class TestIntegrationClone:
    def test_bouton_transcrire_rempli_ref_text(self):
        """Dans onglet 3 Clone, bouton « Transcrire » remplit le champ reference_text."""
        pytest.skip("Test JS — Playwright Phase 8")


class TestFallbackSansRefText:
    def test_clone_sans_ref_text_declenche_whisper_60s(self):
        """Si ref_text manquant, OmniVoice fait une transcription lente (~60 s).

        Hors périmètre omnistudio : OmniVoice gère. omnistudio force l'usage de /transcribe avant /clone.
        """
        pytest.skip("Comportement OmniVoice — test à faire côté OmniVoice")
