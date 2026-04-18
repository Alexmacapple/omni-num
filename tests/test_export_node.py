"""Tests du noeud de validation pre-export (export_node)."""

import pytest

from graph.nodes.export_node import export_zip_node


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def export_steps():
    """Etapes pour les tests d'export."""
    return [
        {"step_id": "1", "text_original": "Bienvenue.", "text_tts": "Bienvenue."},
        {"step_id": "2", "text_original": "Au revoir.", "text_tts": "Au revoir."},
    ]


@pytest.fixture
def valid_generated_files():
    """Fichiers generes valides (status done, wav_path present)."""
    return [
        {"step_id": "1", "filename": "e01.wav", "wav_path": "/tmp/e01.wav", "status": "done"},
        {"step_id": "2", "filename": "e02.wav", "wav_path": "/tmp/e02.wav", "status": "done"},
    ]


@pytest.fixture
def default_post_config():
    """Configuration post-traitement par defaut attendue."""
    return {
        "normalize": True,
        "stereo": True,
        "sample_rate": 48000,
        "bit_depth": 24,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestExportZipNode:
    """Tests du noeud export_zip_node."""

    def test_export_no_steps(self):
        """Pas de steps -> generation_complete=False."""
        state = {"steps": [], "generated_files": [], "post_process_config": {}}
        result = export_zip_node(state)
        assert result["generation_complete"] is False

    def test_export_no_generated_files(self, export_steps):
        """Steps presentes mais pas de generated_files -> False."""
        state = {
            "steps": export_steps,
            "generated_files": [],
            "post_process_config": {},
        }
        result = export_zip_node(state)
        assert result["generation_complete"] is False

    def test_export_partial_files(self, export_steps):
        """generated_files ne couvre pas toutes les etapes -> False."""
        partial = [
            {"step_id": "1", "wav_path": "/tmp/e01.wav", "status": "done"},
            # manque step_id 2
        ]
        state = {
            "steps": export_steps,
            "generated_files": partial,
            "post_process_config": {},
        }
        result = export_zip_node(state)
        assert result["generation_complete"] is False

    def test_export_invalid_status(self, export_steps):
        """Fichiers avec status != 'done' -> False."""
        files = [
            {"step_id": "1", "wav_path": "/tmp/e01.wav", "status": "done"},
            {"step_id": "2", "wav_path": "/tmp/e02.wav", "status": "error"},
        ]
        state = {
            "steps": export_steps,
            "generated_files": files,
            "post_process_config": {},
        }
        result = export_zip_node(state)
        assert result["generation_complete"] is False

    def test_export_missing_wav_path(self, export_steps):
        """Fichiers sans wav_path -> False."""
        files = [
            {"step_id": "1", "wav_path": "/tmp/e01.wav", "status": "done"},
            {"step_id": "2", "wav_path": "", "status": "done"},
        ]
        state = {
            "steps": export_steps,
            "generated_files": files,
            "post_process_config": {},
        }
        result = export_zip_node(state)
        assert result["generation_complete"] is False

    def test_export_complete(self, export_steps, valid_generated_files):
        """Tout est valide -> generation_complete=True."""
        state = {
            "steps": export_steps,
            "generated_files": valid_generated_files,
            "post_process_config": {"normalize": False},
        }
        result = export_zip_node(state)
        assert result["generation_complete"] is True
        assert result["iteration_count"] == 1

    def test_export_default_post_config(
        self, export_steps, valid_generated_files, default_post_config
    ):
        """post_process_config vide -> retourne la config par defaut."""
        state = {
            "steps": export_steps,
            "generated_files": valid_generated_files,
            "post_process_config": {},
        }
        result = export_zip_node(state)
        assert result["post_process_config"] == default_post_config

    def test_export_custom_post_config(self, export_steps, valid_generated_files):
        """post_process_config fourni -> preservee telle quelle."""
        custom = {"normalize": False, "stereo": False, "sample_rate": 44100, "bit_depth": 16}
        state = {
            "steps": export_steps,
            "generated_files": valid_generated_files,
            "post_process_config": custom,
        }
        result = export_zip_node(state)
        assert result["post_process_config"] == custom
