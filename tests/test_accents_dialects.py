"""Tests Voice Design 6 catégories (accents + dialectes) — Phase 2 rouges.

Spécification : PRD v1.5 décision 12 + annexes I (mapping dialectes).
"""
import pytest


ENGLISH_ACCENTS = [
    "American", "Australian", "British", "Chinese", "Canadian",
    "Indian", "Korean", "Portuguese", "Russian", "Japanese",
]

CHINESE_DIALECTS_UI_TO_CHARS = {
    "Henan": "河南话",
    "Shaanxi": "陕西话",
    "Sichuan": "四川话",
    "Guizhou": "贵州话",
    "Yunnan": "云南话",
    "Guilin": "桂林话",
    "Jinan": "济南话",
    "Shijiazhuang": "石家庄话",
    "Gansu": "甘肃话",
    "Ningxia": "宁夏话",
    "Qingdao": "青岛话",
    "Northeast": "东北话",
}


class TestEnglishAccents10:
    @pytest.mark.parametrize("accent", ENGLISH_ACCENTS)
    def test_chaque_accent_compose_chaine(self, accent):
        from core.omnivoice_client import design_from_attributes
        result = design_from_attributes(
            gender="Female", age="Middle-aged", pitch="Moderate Pitch", style="Neutral",
            language="en", accent=accent
        )
        assert accent.lower() in result.lower()


class TestChineseDialects12:
    @pytest.mark.parametrize("ui_name,chars", list(CHINESE_DIALECTS_UI_TO_CHARS.items()))
    def test_mapping_ui_vers_caracteres(self, ui_name, chars):
        from core.omnivoice_client import map_dialect_to_chinese_chars
        assert map_dialect_to_chinese_chars(ui_name) == chars

    @pytest.mark.parametrize("ui_name,chars", list(CHINESE_DIALECTS_UI_TO_CHARS.items()))
    def test_compose_envoie_caracteres(self, ui_name, chars):
        from core.omnivoice_client import design_from_attributes
        result = design_from_attributes(
            gender="Male", age="Middle-aged", pitch="Moderate Pitch", style="Neutral",
            language="zh", dialect=ui_name
        )
        assert chars in result


class TestActivationConditionnelle:
    def test_accent_passe_en_arg_mais_language_fr_ignore(self):
        from core.omnivoice_client import design_from_attributes
        result = design_from_attributes(
            gender="Female", age="Middle-aged", pitch="Moderate Pitch", style="Neutral",
            language="fr", accent="British"
        )
        assert "british" not in result.lower()

    def test_dialect_passe_en_arg_mais_language_en_ignore(self):
        from core.omnivoice_client import design_from_attributes
        result = design_from_attributes(
            gender="Male", age="Middle-aged", pitch="Moderate Pitch", style="Neutral",
            language="en", dialect="Sichuan"
        )
        assert "四川话" not in result


class TestSelectsAttributesFromOmniVoice:
    """Les selects Guidé sont peuplés via GET /design/attributes."""

    def test_proxy_get_design_attributes(self):
        pytest.skip("Mock OmniVoice — Phase 3")
