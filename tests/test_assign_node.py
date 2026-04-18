"""Tests pour graph/nodes/assign_node.py — Assignation des voix."""

import pytest
from graph.nodes.assign_node import assign_voices_node


class TestAssignVoicesNode:
    """Tests du noeud d'assignation des voix."""

    def test_no_existing_assignments_uses_default(self, sample_steps):
        state = {
            "steps": sample_steps,
            "assignments": {},
            "default_voice": "Lea",
        }
        result = assign_voices_node(state)
        assignments = result["assignments"]

        # Toutes les etapes ont la voix par defaut
        for step in sample_steps:
            sid = str(step["step_id"])
            assert sid in assignments
            assert assignments[sid] == "Lea"

    def test_existing_assignment_preserved(self, sample_steps):
        state = {
            "steps": sample_steps,
            "assignments": {"2": "narrateur-pro"},
            "default_voice": "Lea",
        }
        result = assign_voices_node(state)
        assignments = result["assignments"]

        # L'assignation existante est conservee
        assert assignments["2"] == "narrateur-pro"
        # Les autres recoivent la voix par defaut
        assert assignments["1"] == "Lea"
        assert assignments["3"] == "Lea"

    def test_default_voice_is_serena_when_not_specified(self, sample_steps):
        state = {
            "steps": sample_steps,
            "assignments": {},
            # Pas de default_voice dans le state -> dict.get retourne "Lea"
        }
        result = assign_voices_node(state)
        assignments = result["assignments"]

        for step in sample_steps:
            sid = str(step["step_id"])
            assert assignments[sid] == "Lea"

    def test_custom_default_voice(self, sample_steps):
        state = {
            "steps": sample_steps,
            "assignments": {},
            "default_voice": "narrateur-dynamique",
        }
        result = assign_voices_node(state)
        assignments = result["assignments"]

        for step in sample_steps:
            sid = str(step["step_id"])
            assert assignments[sid] == "narrateur-dynamique"

    def test_iteration_count_is_one(self, sample_steps):
        state = {
            "steps": sample_steps,
            "assignments": {},
            "default_voice": "Lea",
        }
        result = assign_voices_node(state)
        assert result["iteration_count"] == 1

    def test_empty_steps_list(self):
        state = {
            "steps": [],
            "assignments": {},
            "default_voice": "Lea",
        }
        result = assign_voices_node(state)
        assert result["assignments"] == {}
        assert result["iteration_count"] == 1
