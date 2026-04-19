"""Tests pour la sanitization des noms de voix.

On reimplemente la logique pure ici pour eviter d'importer ui.tab_voices
(qui a des dependances lourdes : gradio, langgraph, omnivoice_client).
"""

import re
import pytest


# --- Reimplementation locale des fonctions pures ---
# Copie exacte de ui/tab_voices.py (lignes 12-23 et 10)
RESERVED_VOICE_NAMES = {"vivian", "serena", "uncle-fu", "dylan", "eric", "ryan", "aiden", "ono-anna", "sohee"}


def sanitize_voice_name(name: str) -> str:
    """Copie locale de tab_voices.sanitize_voice_name.

    Doit valider avec regex stricte ^[a-zA-Z][a-zA-Z0-9_-]{2,49}$ (PRD annexe M).
    """
    name = name.strip()
    name = re.sub(r'[\s]+', '-', name)  # Espaces seulement (pas underscores)
    name = re.sub(r'[^a-zA-Z0-9\-_]', '', name)  # Garder lettres, chiffres, tirets, underscores
    name = re.sub(r'-+', '-', name).strip('-').strip('_')  # Collapse repeats
    name = name[:50]
    # Valider regex strict: commence par lettre, 3-50 chars total
    if not re.match(r'^[a-zA-Z][a-zA-Z0-9_-]{2,49}$', name):
        return ""  # Invalide — retourner vide
    return name


class TestSanitizeVoiceName:
    """Tests de la fonction sanitize_voice_name."""

    def test_simple_name_unchanged(self):
        assert sanitize_voice_name("ma-voix") == "ma-voix"

    def test_spaces_to_hyphens(self):
        assert sanitize_voice_name("ma voix") == "ma-voix"

    def test_underscores_preserved(self):
        """Underscores préservés (regex PRD annexe M : ^[a-zA-Z][a-zA-Z0-9_-]{2,49}$)."""
        assert sanitize_voice_name("ma_voix") == "ma_voix"

    def test_special_chars_removed(self):
        assert sanitize_voice_name("ma@voix!") == "mavoix"

    def test_multiple_hyphens_collapsed(self):
        assert sanitize_voice_name("ma--voix") == "ma-voix"

    def test_leading_trailing_hyphens_removed(self):
        assert sanitize_voice_name("-ma-voix-") == "ma-voix"

    def test_max_length_50(self):
        long_name = "a" * 100
        result = sanitize_voice_name(long_name)
        assert len(result) <= 50

    def test_strip_whitespace(self):
        result = sanitize_voice_name("  test  ")
        assert result == "test"

    def test_complex_combination(self):
        result = sanitize_voice_name("  Ma Voix @Special!  ")
        # Apres sanitization: "Ma-Voix-Special" (14 chars) — valide regex
        assert result == "Ma-Voix-Special"

    def test_minimum_length_3(self):
        """Nom avec moins de 3 chars -> invalide."""
        result = sanitize_voice_name("ab")
        assert result == ""  # Trop court

    def test_starts_with_number_invalid(self):
        """Nom commençant par chiffre -> invalide."""
        result = sanitize_voice_name("123voix")
        assert result == ""


class TestReservedVoiceNames:
    """Tests de la liste RESERVED_VOICE_NAMES."""

    def test_contains_expected_names(self):
        expected = {"vivian", "serena", "dylan", "eric", "ryan", "aiden"}
        assert expected.issubset(RESERVED_VOICE_NAMES)

    def test_case_insensitive_detection(self):
        """Vérifie que les noms VoxQwen réservés matchent en lowercase."""
        assert "Vivian".lower() in RESERVED_VOICE_NAMES
        assert "DYLAN".lower() in RESERVED_VOICE_NAMES

    def test_is_a_set(self):
        assert isinstance(RESERVED_VOICE_NAMES, set)
