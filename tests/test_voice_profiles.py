"""Tests pour core/voice_profiles.py — 12 templates EN format OmniVoice."""

import pytest
from core.voice_profiles import VOICE_TEMPLATES


REQUIRED_FIELDS = {"name", "badge", "gender", "description", "voice_instruct"}
# Formats EN (items whitelist OmniVoice) — PRD-MIGRATION-001 v1.5 décision 10
VALID_GENDERS_EN = {"male", "female"}


class TestVoiceTemplates:
    """Tests de la liste VOICE_TEMPLATES (12 templates EN format OmniVoice)."""

    def test_has_12_entries(self):
        assert len(VOICE_TEMPLATES) == 12

    @pytest.mark.parametrize("index", range(12))
    def test_required_fields_present(self, index):
        template = VOICE_TEMPLATES[index]
        missing = REQUIRED_FIELDS - set(template.keys())
        assert not missing, f"Template {index} manque les champs : {missing}"

    def test_all_badges_non_empty(self):
        """Les badges peuvent varier (Institution, Formation, Promo, etc.)."""
        for tpl in VOICE_TEMPLATES:
            assert tpl["badge"], f"Badge vide pour '{tpl['name']}'"

    def test_all_genders_valid(self):
        """Genres en anglais pour format OmniVoice whitelist."""
        for tpl in VOICE_TEMPLATES:
            assert tpl["gender"] in VALID_GENDERS_EN, (
                f"Genre invalide pour '{tpl['name']}' : '{tpl['gender']}'"
            )

    def test_voice_instruct_non_empty(self):
        for tpl in VOICE_TEMPLATES:
            assert len(tpl["voice_instruct"].strip()) > 0, (
                f"voice_instruct vide pour '{tpl['name']}'"
            )

    def test_voice_instruct_comma_separated_items(self):
        """Chaque voice_instruct est une liste d'items séparés par virgules."""
        for tpl in VOICE_TEMPLATES:
            items = [it.strip() for it in tpl["voice_instruct"].split(",")]
            assert len(items) >= 2, (
                f"voice_instruct de '{tpl['name']}' doit contenir >= 2 items : "
                f"'{tpl['voice_instruct']}'"
            )

    def test_names_unique(self):
        names = [tpl["name"] for tpl in VOICE_TEMPLATES]
        assert len(names) == len(set(names)), (
            f"Noms en double detectes : {[n for n in names if names.count(n) > 1]}"
        )
