"""Tests pour core/voice_profiles.py — Templates de voix pre-valides."""

import pytest
from core.voice_profiles import VOICE_TEMPLATES


REQUIRED_FIELDS = {"name", "badge", "gender", "description", "voice_instruct"}
VALID_GENDERS = {"masculin", "féminin"}


class TestVoiceTemplates:
    """Tests de la liste VOICE_TEMPLATES."""

    def test_has_6_entries(self):
        assert len(VOICE_TEMPLATES) == 6

    @pytest.mark.parametrize("index", range(6))
    def test_required_fields_present(self, index):
        template = VOICE_TEMPLATES[index]
        missing = REQUIRED_FIELDS - set(template.keys())
        assert not missing, f"Template {index} manque les champs : {missing}"

    def test_all_badges_are_template(self):
        for tpl in VOICE_TEMPLATES:
            assert tpl["badge"] == "Template", (
                f"Badge invalide pour '{tpl['name']}' : '{tpl['badge']}'"
            )

    def test_all_genders_valid(self):
        for tpl in VOICE_TEMPLATES:
            assert tpl["gender"] in VALID_GENDERS, (
                f"Genre invalide pour '{tpl['name']}' : '{tpl['gender']}'"
            )

    def test_voice_instruct_non_empty(self):
        for tpl in VOICE_TEMPLATES:
            assert len(tpl["voice_instruct"].strip()) > 0, (
                f"voice_instruct vide pour '{tpl['name']}'"
            )

    def test_names_unique(self):
        names = [tpl["name"] for tpl in VOICE_TEMPLATES]
        assert len(names) == len(set(names)), (
            f"Noms en double detectes : {[n for n in names if names.count(n) > 1]}"
        )
