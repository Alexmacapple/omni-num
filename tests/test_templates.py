"""Tests pour core/templates.py — Nettoyage Layer A (sans LLM)."""

import pytest
from core.templates import apply_layer_a


class TestApplyLayerA:
    """Tests de la fonction apply_layer_a."""

    def test_empty_string_returns_empty(self):
        assert apply_layer_a("") == ""

    def test_removes_dash_lists(self):
        text = "\n- premier\n- deuxième"
        result = apply_layer_a(text)
        assert "- " not in result
        assert "premier" in result
        assert "deuxième" in result
        # Les tirets sont remplaces par des points
        assert ". premier" in result
        assert ". deuxième" in result

    def test_removes_numbered_lists(self):
        text = "\n1- premier"
        result = apply_layer_a(text)
        assert "1-" not in result
        assert ". premier" in result

    def test_collapses_double_spaces(self):
        text = "mot1  mot2   mot3"
        result = apply_layer_a(text)
        assert "  " not in result

    def test_removes_parentheses(self):
        text = "Le MOA (maîtrise d'ouvrage) gère le projet"
        result = apply_layer_a(text)
        assert "(" not in result
        assert ")" not in result

    def test_removes_quotes(self):
        text = 'Le terme "agile" est utilisé'
        result = apply_layer_a(text)
        assert '"' not in result

    def test_adds_final_period_if_missing(self):
        text = "Texte sans point final"
        result = apply_layer_a(text)
        assert result.endswith(".")

    def test_preserves_existing_period(self):
        text = "Texte avec point."
        result = apply_layer_a(text)
        assert result.endswith(".")
        assert not result.endswith("..")

    def test_preserves_exclamation(self):
        text = "Bravo !"
        result = apply_layer_a(text)
        assert result.endswith("!")
        assert not result.endswith(".!")

    def test_preserves_question_mark(self):
        text = "Comment faire ?"
        result = apply_layer_a(text)
        assert result.endswith("?")
        assert not result.endswith(".?")

    def test_full_realistic_case(self):
        text = (
            'Le MOA (maîtrise d\'ouvrage) gère :\n'
            '- la planification\n'
            '- le "budget"\n'
            '- les ressources  humaines'
        )
        result = apply_layer_a(text)
        # Pas de parentheses
        assert "(" not in result
        assert ")" not in result
        # Pas de guillemets
        assert '"' not in result
        # Pas de doubles espaces
        assert "  " not in result
        # Pas de tirets de liste
        assert "\n-" not in result
        # Se termine par un point
        assert result.endswith(".")
        # Le contenu est preserve
        assert "planification" in result
        assert "budget" in result
        assert "ressources" in result
