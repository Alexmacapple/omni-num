"""Tests du noeud de validation pre-generation (generate_node)."""

import pytest

from graph.nodes.generate_node import _validate_assignments, generate_batch_node


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def steps_with_text():
    """Etapes avec texte TTS disponible."""
    return [
        {"step_id": "1", "text_original": "Bienvenue.", "text_tts": "Bienvenue."},
        {"step_id": "2", "text_original": "Connectez-vous.", "text_tts": "Connectez-vous."},
        {"step_id": "3", "text_original": "Merci.", "text_tts": "Merci."},
    ]


@pytest.fixture
def full_assignments():
    """Assignations couvrant les 3 etapes."""
    return {"1": "Lea", "2": "Lea", "3": "Lea"}


@pytest.fixture
def full_generated_files():
    """Fichiers generes couvrant les 3 etapes."""
    return [
        {"step_id": "1", "wav_path": "/tmp/e1.wav", "status": "done"},
        {"step_id": "2", "wav_path": "/tmp/e2.wav", "status": "done"},
        {"step_id": "3", "wav_path": "/tmp/e3.wav", "status": "done"},
    ]


# ---------------------------------------------------------------------------
# Tests _validate_assignments
# ---------------------------------------------------------------------------


class TestValidateAssignments:
    """Tests de la fonction _validate_assignments."""

    def test_validate_assignments_all_present(self, steps_with_text, full_assignments):
        """Toutes les etapes ont une voix assignee -> liste vide."""
        result = _validate_assignments(steps_with_text, full_assignments)
        assert result == []

    def test_validate_assignments_missing(self, steps_with_text):
        """Etape sans voix assignee -> retourne les IDs manquants."""
        partial = {"1": "Lea"}  # manque 2 et 3
        result = _validate_assignments(steps_with_text, partial)
        assert "2" in result
        assert "3" in result
        assert "1" not in result

    def test_validate_assignments_empty_steps(self):
        """Aucune etape -> rien a valider, liste vide."""
        result = _validate_assignments([], {"1": "Lea"})
        assert result == []

    def test_validate_assignments_empty_both(self):
        """Aucune etape et aucune assignation -> liste vide."""
        result = _validate_assignments([], {})
        assert result == []


# ---------------------------------------------------------------------------
# Tests generate_batch_node
# ---------------------------------------------------------------------------


class TestGenerateBatchNode:
    """Tests du noeud generate_batch_node."""

    def test_generate_batch_no_steps(self):
        """State sans steps -> generation_complete=False."""
        state = {"steps": [], "assignments": {}, "generated_files": []}
        result = generate_batch_node(state)
        assert result["generation_complete"] is False
        assert result["iteration_count"] == 1

    def test_generate_batch_missing_assignments(self, steps_with_text):
        """Assignations incompletes -> generation_complete=False."""
        state = {
            "steps": steps_with_text,
            "assignments": {"1": "Lea"},  # manque 2 et 3
            "generated_files": [],
        }
        result = generate_batch_node(state)
        assert result["generation_complete"] is False

    def test_generate_batch_no_text(self):
        """Etapes sans text_tts ni text_original -> generation_complete=False."""
        steps = [
            {"step_id": "1", "text_original": "", "text_tts": ""},
            {"step_id": "2", "text_original": "", "text_tts": ""},
        ]
        assignments = {"1": "Lea", "2": "Lea"}
        state = {
            "steps": steps,
            "assignments": assignments,
            "generated_files": [],
        }
        result = generate_batch_node(state)
        assert result["generation_complete"] is False

    def test_generate_batch_complete(
        self, steps_with_text, full_assignments, full_generated_files
    ):
        """Tout est present, generated_files couvre toutes les etapes -> True."""
        state = {
            "steps": steps_with_text,
            "assignments": full_assignments,
            "generated_files": full_generated_files,
        }
        result = generate_batch_node(state)
        assert result["generation_complete"] is True
        assert result["iteration_count"] == 1

    def test_generate_batch_partial(
        self, steps_with_text, full_assignments
    ):
        """generated_files ne couvre pas toutes les etapes -> False."""
        partial_generated = [
            {"step_id": "1", "wav_path": "/tmp/e1.wav", "status": "done"},
            # manque 2 et 3
        ]
        state = {
            "steps": steps_with_text,
            "assignments": full_assignments,
            "generated_files": partial_generated,
        }
        result = generate_batch_node(state)
        assert result["generation_complete"] is False

    def test_generate_batch_text_original_only(self, full_assignments):
        """Etapes avec text_original mais sans text_tts -> accepte quand meme."""
        steps = [
            {"step_id": "1", "text_original": "Bonjour.", "text_tts": ""},
            {"step_id": "2", "text_original": "Au revoir.", "text_tts": ""},
        ]
        generated = [
            {"step_id": "1", "wav_path": "/tmp/e1.wav", "status": "done"},
            {"step_id": "2", "wav_path": "/tmp/e2.wav", "status": "done"},
        ]
        state = {
            "steps": steps,
            "assignments": {"1": "Lea", "2": "Lea"},
            "generated_files": generated,
        }
        result = generate_batch_node(state)
        assert result["generation_complete"] is True
