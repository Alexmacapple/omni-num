"""Tests du parser multi-voix [voice:X] — Phase 2 rouges.

Spécification : PRD-MIGRATION-001 v1.5 annexe M (20 cas limites).
Code cible : omnistudio/graph/segments_parser.py::parse_segments

Regex stricte : ^[a-zA-Z][a-zA-Z0-9_-]{2,49}$ (anti-XSS).
"""
import pytest


def _parser():
    """Import du parser — échoue tant que Phase 3 n'est pas faite."""
    from core.segments_parser import parse_segments
    return parse_segments


class TestParserBasique:
    def test_texte_sans_tag_1_segment_voix_defaut(self):
        p = _parser()
        result = p("Hello world", default_voice="Marianne", step_id="s1")
        assert len(result) == 1
        assert result[0]["voice"] == "Marianne"
        assert result[0]["text"] == "Hello world"

    def test_tag_en_tete(self):
        p = _parser()
        result = p("[voice:Jean] Hello", default_voice="Marianne", step_id="s1")
        assert len(result) == 1
        assert result[0]["voice"] == "Jean"
        assert result[0]["text"] == "Hello"

    def test_deux_tags_trois_segments(self):
        p = _parser()
        result = p("Hello. [voice:Jean] Hi. [voice:Paul] Bye.",
                   default_voice="Marianne", step_id="s1")
        assert len(result) == 3
        assert [s["voice"] for s in result] == ["Marianne", "Jean", "Paul"]

    def test_tags_consecutifs_B_ecrase_A(self):
        p = _parser()
        # [voice:A][voice:B] : A est écrasé par B immédiatement (pas de segment A vide)
        result = p("[voice:A][voice:B] Texte", default_voice="Marianne", step_id="s1")
        assert len(result) == 1
        assert result[0]["voice"] == "B"


class TestCasLimites:
    def test_tag_orphelin_fin(self):
        """Tag en fin sans texte après → 1 segment défaut."""
        p = _parser()
        result = p("Texte final [voice:Marianne]", default_voice="Jean", step_id="s1")
        assert len(result) == 1
        assert result[0]["voice"] == "Jean"
        assert result[0]["text"] == "Texte final"

    def test_multilignes_tag_sur_ligne_seule(self):
        p = _parser()
        result = p("Hello\n[voice:Jean]\nWorld", default_voice="Marianne", step_id="s1")
        assert len(result) == 2
        assert result[0]["voice"] == "Marianne"
        assert result[1]["voice"] == "Jean"


class TestRegexValidationXSS:
    """Regex stricte ^[a-zA-Z][a-zA-Z0-9_-]{2,49}$ (PRD annexe M)."""

    def test_nom_vide_invalide(self):
        p = _parser()
        result = p("[voice:]", default_voice="Marianne", step_id="s1")
        # Tag invalide → texte littéral, 1 segment défaut
        assert len(result) == 1
        assert result[0]["voice"] == "Marianne"
        assert "[voice:]" in result[0]["text"]

    def test_nom_trop_court(self):
        p = _parser()
        result = p("[voice:AB]", default_voice="Marianne", step_id="s1")
        assert result[0]["voice"] == "Marianne"
        assert "[voice:AB]" in result[0]["text"]

    def test_nom_trop_long(self):
        p = _parser()
        nom = "a" * 51
        result = p(f"[voice:{nom}]", default_voice="Marianne", step_id="s1")
        assert result[0]["voice"] == "Marianne"

    def test_nom_avec_espace_invalide(self):
        p = _parser()
        result = p("[voice:Jean Doe]", default_voice="Marianne", step_id="s1")
        assert result[0]["voice"] == "Marianne"

    def test_xss_balise_script(self):
        """Protection XSS : <script> rejeté par regex."""
        p = _parser()
        result = p("[voice:Jean<script>alert(1)</script>]",
                   default_voice="Marianne", step_id="s1")
        assert result[0]["voice"] == "Marianne"
        # Le texte est préservé littéralement, pas interprété
        assert "<script>" in result[0]["text"]

    def test_xss_entite_html(self):
        p = _parser()
        result = p("[voice:Jean&lt;script&gt;]", default_voice="Marianne", step_id="s1")
        assert result[0]["voice"] == "Marianne"

    def test_xss_apostrophe(self):
        """Protection SQL injection : ' rejeté."""
        p = _parser()
        result = p("[voice:Jean'OR 1=1]", default_voice="Marianne", step_id="s1")
        assert result[0]["voice"] == "Marianne"

    def test_nom_commence_par_chiffre_invalide(self):
        p = _parser()
        result = p("[voice:123Paul]", default_voice="Marianne", step_id="s1")
        assert result[0]["voice"] == "Marianne"


class TestValidationNomsPermis:
    def test_tiret_autorise(self):
        p = _parser()
        result = p("[voice:Jean-Paul] Texte", default_voice="Marianne", step_id="s1")
        assert result[0]["voice"] == "Jean-Paul"

    def test_underscore_autorise(self):
        p = _parser()
        result = p("[voice:Jean_Paul] Texte", default_voice="Marianne", step_id="s1")
        assert result[0]["voice"] == "Jean_Paul"

    def test_chiffres_apres_lettre_autorise(self):
        p = _parser()
        result = p("[voice:Voice1] Texte", default_voice="Marianne", step_id="s1")
        assert result[0]["voice"] == "Voice1"


class TestCaseSensitivity:
    def test_VOICE_majuscule_non_reconnu(self):
        """La syntaxe est stricte : [voice:X], pas [VOICE:X]."""
        p = _parser()
        result = p("[VOICE:Jean] Hello", default_voice="Marianne", step_id="s1")
        assert result[0]["voice"] == "Marianne"
        assert "[VOICE:Jean]" in result[0]["text"]


class TestSegmentIdIncremental:
    def test_segment_id_format(self):
        p = _parser()
        result = p("A [voice:Jean] B [voice:Paul] C", default_voice="Marianne", step_id="s42")
        assert result[0]["segment_id"] == "s42_seg_000"
        assert result[1]["segment_id"] == "s42_seg_001"
        assert result[2]["segment_id"] == "s42_seg_002"
