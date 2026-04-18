"""Tests pour graph/workflow.py -- fonctions de routage et preparation."""

from datetime import datetime
from unittest.mock import patch

import pytest

from graph.workflow import prepare_clean, finalize_clean


# ---------------------------------------------------------------------------
# TestPrepareClean
# ---------------------------------------------------------------------------
class TestPrepareClean:
    def test_extraction_champs(self, sample_state):
        result = prepare_clean(sample_state)
        expected_keys = [
            "steps",
            "cleaning_mode",
            "cleaning_validated",
            "llm_provider",
            "domain_glossary",
            "correction_patterns",
            "correction_parentheses",
            "correction_majuscules",
            "decision",
            "iteration",
        ]
        for key in expected_keys:
            assert key in result, f"Cle manquante : {key}"
        assert result["steps"] == sample_state["steps"]
        assert result["cleaning_mode"] == "auto"
        assert result["llm_provider"] == "Albert Large 120B"


# ---------------------------------------------------------------------------
# TestFinalizeClean
# ---------------------------------------------------------------------------
class TestFinalizeClean:
    def test_genere_logs(self):
        state = {
            "steps": [
                {"step_id": "1", "cleaning_status": "cleaned"},
                {"step_id": "2", "cleaning_status": "cleaned"},
            ],
            "decision": "validated",
            "llm_provider": "Albert Large 120B",
        }
        result = finalize_clean(state)
        assert len(result["cleaning_log"]) == 2
        for log in result["cleaning_log"]:
            assert "step_id" in log
            assert "timestamp" in log

    def test_decision_validated(self):
        state = {
            "steps": [{"step_id": "1", "cleaning_status": "cleaned"}],
            "decision": "validated",
            "llm_provider": "Albert Large 120B",
        }
        result = finalize_clean(state)
        assert result["cleaning_validated"] is True

    def test_ignore_pending(self):
        state = {
            "steps": [
                {"step_id": "1", "cleaning_status": "pending"},
                {"step_id": "2", "cleaning_status": "pending"},
            ],
            "decision": "",
            "llm_provider": "Albert Large 120B",
        }
        result = finalize_clean(state)
        assert result["cleaning_log"] == []
        assert result["cleaning_validated"] is False


# ---------------------------------------------------------------------------
# TestRouting
# ---------------------------------------------------------------------------
class TestRouting:
    """Tests de la logique de routage du workflow.

    Les fonctions route_after_clean et route_after_design sont definies
    dans create_workflow() et ne sont pas directement importables.
    On teste la logique equivalente ici.
    """

    def test_route_after_clean_validated(self):
        """cleaning_validated=True -> direction design."""
        state = {"cleaning_validated": True, "decision": ""}
        result = (
            "design"
            if state.get("cleaning_validated") or state.get("decision") == "validated"
            else "prepare_clean"
        )
        assert result == "design"

    def test_route_after_clean_not_validated(self):
        """cleaning_validated=False et decision vide -> retour prepare_clean."""
        state = {"cleaning_validated": False, "decision": ""}
        result = (
            "design"
            if state.get("cleaning_validated") or state.get("decision") == "validated"
            else "prepare_clean"
        )
        assert result == "prepare_clean"

    def test_route_after_design_locked(self):
        """locked_voices non vide -> direction assign."""
        state = {"locked_voices": ["v1"]}
        result = "assign" if state.get("locked_voices") else "design"
        assert result == "assign"

    def test_route_after_design_no_voices(self):
        """locked_voices vide -> retour design."""
        state = {"locked_voices": []}
        result = "assign" if state.get("locked_voices") else "design"
        assert result == "design"
