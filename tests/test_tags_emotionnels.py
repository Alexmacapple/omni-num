"""Tests tags émotionnels non-verbaux — Phase 2 rouges.

Spécification : PRD v1.5 décision 11 + annexe H (13 tags).
"""
import pytest


TAGS_13 = [
    "[laughter]", "[sigh]",
    "[confirmation-en]", "[question-en]",
    "[question-ah]", "[question-oh]", "[question-ei]", "[question-yi]",
    "[surprise-ah]", "[surprise-oh]", "[surprise-wa]", "[surprise-yo]",
    "[dissatisfaction-hnn]",
]


class TestRouteGetTags:
    def test_endpoint_tags_retourne_13_tags(self):
        """GET /api/voices/tags proxie vers OmniVoice GET /tags."""
        pytest.skip("Mock OmniVoice — Phase 3")


class TestTagsDansTexte:
    @pytest.mark.parametrize("tag", TAGS_13)
    def test_tag_accepte_dans_texte(self, tag):
        """Un tag valide dans le texte passe à OmniVoice tel quel (pas transformé)."""
        from core.omnivoice_client import OmniVoiceClient
        pytest.skip("Mock OmniVoice — Phase 3")

    def test_tag_inconnu_passe_tel_quel(self):
        """Un tag non officiel est envoyé tel quel à OmniVoice (qui décide)."""
        pytest.skip("Mock OmniVoice — Phase 3")


class TestInsertionCurseurJS:
    """Le JS tag-palette.js insère le tag à la position du curseur."""

    def test_insertion_milieu_avec_espaces(self):
        """Curseur en milieu d'un mot, ajoute espaces avant/après si nécessaire."""
        pytest.skip("Test JS — Playwright Phase 8")

    def test_insertion_debut_sans_espace_avant(self):
        pytest.skip("Test JS — Playwright Phase 8")

    def test_insertion_fin_sans_espace_apres(self):
        pytest.skip("Test JS — Playwright Phase 8")

    def test_aucun_double_espace(self):
        pytest.skip("Test JS — Playwright Phase 8")


class TestAccessibiliteTags:
    def test_chaque_bouton_a_aria_label(self):
        """Les 13 boutons de palette DSFR ont un aria-label explicite."""
        pytest.skip("Audit a11y — Phase 4")

    def test_palette_navigable_au_clavier(self):
        pytest.skip("Audit a11y — Phase 4")


class TestRendu:
    def test_texte_avec_laughter_audio_different_du_texte_brut(self):
        """Vérification empirique : l'audio contient un rire vs texte sans tag."""
        pytest.skip("Test audio — Phase 8")
