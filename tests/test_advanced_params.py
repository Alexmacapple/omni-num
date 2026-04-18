"""Tests 11 paramètres avancés de synthèse — Phase 2 rouges.

Spécification : PRD v1.5 décision 14 + annexe J.
"""
import pytest
from pydantic import ValidationError


ADVANCED_PARAMS = {
    "num_step": {"min": 4, "max": 64, "default": 32},
    "guidance_scale": {"min": 0, "max": 4, "default": 2.0},
    "duration": {"min": 0.1, "max": 600, "default": None},
    "t_shift": {"min": 0, "max": 1, "default": 0.1},
    "position_temperature": {"min": 0, "max": 20, "default": 5.0},
    "class_temperature": {"min": 0, "max": 5, "default": 0.0},
    "layer_penalty_factor": {"min": 0, "max": 20, "default": 5.0},
    "audio_chunk_duration": {"min": 1, "max": 60, "default": 15.0},
    "audio_chunk_threshold": {"min": 5, "max": 120, "default": 30.0},
}


class TestSchemaPydantic:
    def test_parametres_dans_generate_request(self):
        from core.schemas import GenerateRequest
        req = GenerateRequest(text="Hello", voice="Marianne", num_step=64)
        assert req.num_step == 64

    @pytest.mark.parametrize("param,config", ADVANCED_PARAMS.items())
    def test_validation_limites_hautes(self, param, config):
        from core.schemas import GenerateRequest
        # Dépassement : valeur = max + 1
        over = config["max"] + 1
        with pytest.raises(ValidationError):
            GenerateRequest(text="x", voice="Marianne", **{param: over})

    @pytest.mark.parametrize("param,config", ADVANCED_PARAMS.items())
    def test_validation_limites_basses(self, param, config):
        from core.schemas import GenerateRequest
        under = config["min"] - 1 if config["min"] > 0 else -1
        with pytest.raises(ValidationError):
            GenerateRequest(text="x", voice="Marianne", **{param: under})


class TestBoolParams:
    def test_denoise_defaut_true(self):
        from core.schemas import GenerateRequest
        req = GenerateRequest(text="x", voice="Marianne")
        assert req.denoise is True

    def test_postprocess_output_defaut_true(self):
        from core.schemas import GenerateRequest
        req = GenerateRequest(text="x", voice="Marianne")
        assert req.postprocess_output is True


class TestPropagation:
    def test_params_passes_a_omnivoice(self):
        """Les 11 params sont bien transmis au client OmniVoice."""
        pytest.skip("Mock OmniVoice — Phase 3")


class TestUIAccordeon:
    def test_accordeon_ferme_par_defaut(self):
        pytest.skip("Test JS — Playwright Phase 8")

    def test_aria_expanded_correct(self):
        pytest.skip("Audit a11y — Phase 4")

    def test_bouton_reinitialiser_defauts(self):
        pytest.skip("Test JS — Playwright Phase 8")
