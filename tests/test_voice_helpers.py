"""Tests des helpers de Voice Design : normalize, describe_fr, composition
dropdowns, random naming, fetch_design_attributes.

Couvre les régressions des commits :
- 9cc119b (normalize_voice_instruct renvoyé dans la réponse)
- e97e057 (getSessionLanguage, mapping FR enrichi)
- 62d5595 (SRT, options Clone, dict FR étendu)
- 8a7f215 (random_auto nom unique)
- ca0bcdf (classifieur hybride, describe_instruct_fr, fetch_design_attributes)
- 40710e4 / ab92183 (MediaRecorder, cache-buster ES)
"""

import os
import pytest
from unittest.mock import patch, MagicMock

from core.omnivoice_client import (
    normalize_voice_instruct,
    describe_instruct_fr,
    OmniVoiceClient,
    _category_of,
    design_from_attributes,
)


# ---------------------------------------------------------------------------
# normalize_voice_instruct — dictionnaire FR enrichi
# ---------------------------------------------------------------------------

class TestNormalizeDictFR:
    """Vérifie que le dictionnaire FR→whitelist couvre les termes courants
    d'un prompt utilisateur français."""

    def test_genre_homme_femme(self):
        assert "male" in normalize_voice_instruct("Voix d'homme")
        assert "female" in normalize_voice_instruct("Voix de femme")
        assert "female" in normalize_voice_instruct("voix féminine chaleureuse")
        assert "male" in normalize_voice_instruct("voix masculine posée")

    def test_age_fr(self):
        assert "child" in normalize_voice_instruct("voix d'enfant, fillette")
        assert "middle-aged" in normalize_voice_instruct("femme mûre adulte")
        assert "elderly" in normalize_voice_instruct("personne âgée")
        assert "elderly" in normalize_voice_instruct("voix de vieillard")
        assert "young adult" in normalize_voice_instruct("jeune femme dynamique")

    def test_pitch_fr_enrichi(self):
        assert "low pitch" in normalize_voice_instruct("voix profonde grave")
        assert "low pitch" in normalize_voice_instruct("timbre de baryton")
        assert "low pitch" in normalize_voice_instruct("voix caverneuse")
        assert "low pitch" in normalize_voice_instruct("basse voix")
        assert "high pitch" in normalize_voice_instruct("aiguë")
        assert "very low pitch" in normalize_voice_instruct("très grave")

    def test_whisper_variantes_fr(self):
        assert "whisper" in normalize_voice_instruct("chuchotement")
        assert "whisper" in normalize_voice_instruct("voix chuchotée")
        assert "whisper" in normalize_voice_instruct("murmuré à l'oreille")
        assert "whisper" in normalize_voice_instruct("susurré")
        assert "whisper" in normalize_voice_instruct("soufflé doucement")

    def test_une_seule_categorie_par_mapping(self):
        """Règle stricte OmniVoice : 1 item max par catégorie (sinon 500)."""
        out = normalize_voice_instruct("voix féminine mature grave chuchotée")
        items = [i.strip() for i in out.split(",") if i.strip()]
        cats = [_category_of(it) for it in items]
        # Pas de doublon de catégorie
        assert len(cats) == len(set(cats))

    def test_prose_user_reelle(self):
        """Prose FR détaillée typique d'un utilisateur — doit extraire au moins
        female et middle-aged et ne rien inventer pour les termes non mappés."""
        prompt = (
            "Voix féminin française mature, timbre chaleureux et légèrement "
            "brillant, texture veloutée proche du micro, ton dynamique et "
            "captivant, accent neutre métropolitain"
        )
        out = normalize_voice_instruct(prompt)
        assert "female" in out
        assert "middle-aged" in out
        # Aucun accent francophone n'est dans la whitelist OmniVoice
        assert "accent" not in out

    def test_age_mot_isole_ne_matche_pas_elderly(self):
        """Le mapping `age` → elderly a été retiré car il créait des faux
        positifs sur des phrases comme « moyen age »."""
        out = normalize_voice_instruct("age moyen")
        items = out.split(",")
        assert "elderly" not in items

    def test_deja_whitelist_valide(self):
        """Une entrée déjà valide est conservée (déduplication par catégorie)."""
        assert normalize_voice_instruct("female, middle-aged, low pitch") == "female, middle-aged, low pitch"
        # Duplication de catégorie : premier gagne
        out = normalize_voice_instruct("female, male, middle-aged")
        items = [i.strip() for i in out.split(",")]
        assert items.count("male") + items.count("female") == 1

    def test_chaine_vide(self):
        assert normalize_voice_instruct("") == ""
        assert normalize_voice_instruct("   ") == ""


# ---------------------------------------------------------------------------
# describe_instruct_fr — traduction rule-based EN → FR lisible
# ---------------------------------------------------------------------------

class TestDescribeInstructFR:

    def test_basique(self):
        assert describe_instruct_fr("female, middle-aged") == "Voix féminine d'âge mûr"

    def test_avec_pitch_et_style(self):
        out = describe_instruct_fr("male, young adult, low pitch, whisper")
        assert out.startswith("Voix masculine de jeune adulte")
        assert "timbre grave" in out
        assert "style chuchoté" in out

    def test_avec_accent(self):
        out = describe_instruct_fr("female, middle-aged, british accent")
        assert "Voix féminine d'âge mûr" in out
        assert "accent britannique" in out

    def test_vide(self):
        assert describe_instruct_fr("") == ""
        assert describe_instruct_fr("   ") == ""

    def test_inconnu_ignore(self):
        """Un item hors whitelist est silencieusement ignoré (pas d'exception)."""
        out = describe_instruct_fr("female, warm tone, middle-aged")
        assert out == "Voix féminine d'âge mûr"

    def test_ordre_gender_age_premier(self):
        """Le genre et l'âge ouvrent toujours la phrase, puis les autres attributs."""
        out = describe_instruct_fr("low pitch, female, middle-aged")
        assert out.startswith("Voix féminine d'âge mûr")

    def test_accent_americain(self):
        assert "accent américain" in describe_instruct_fr("male, american accent")


# ---------------------------------------------------------------------------
# design_from_attributes — composition directe Colab-style
# ---------------------------------------------------------------------------

class TestDesignFromAttributes:

    def test_core_sans_accent(self):
        out = design_from_attributes("Female", "Young Adult", "High Pitch", "Neutral")
        assert out == "female, young adult, high pitch"

    def test_accent_anglais_uniquement_si_langue_en(self):
        out = design_from_attributes(
            "Female", "Middle-aged", "Moderate Pitch", "Neutral",
            language="en", accent="British"
        )
        assert "british accent" in out
        # Pas d'accent si langue FR
        out_fr = design_from_attributes(
            "Female", "Middle-aged", "Moderate Pitch", "Neutral",
            language="fr", accent="British"
        )
        assert "british accent" not in out_fr

    def test_whisper_inclus(self):
        out = design_from_attributes("Male", "Elderly", "Low Pitch", "whisper")
        assert "whisper" in out

    def test_neutral_ignore(self):
        out = design_from_attributes("Male", "Teenager", "Moderate Pitch", "Neutral")
        assert "neutral" not in out.lower()


# ---------------------------------------------------------------------------
# _compose_items_from_brief — classifieur hybride (dropdowns)
# ---------------------------------------------------------------------------

class TestComposeItemsFromBrief:

    def test_genre_mappe(self):
        from graph.subgraphs.design_loop import _compose_items_from_brief
        assert _compose_items_from_brief({"genre": "feminin"}) == ["female"]
        assert _compose_items_from_brief({"genre": "masculin"}) == ["male"]

    def test_age_mappe(self):
        from graph.subgraphs.design_loop import _compose_items_from_brief
        assert "young adult" in _compose_items_from_brief({"age": "jeune"})
        assert "middle-aged" in _compose_items_from_brief({"age": "mature"})
        assert "elderly" in _compose_items_from_brief({"age": "age"})

    def test_pitch_mappe(self):
        from graph.subgraphs.design_loop import _compose_items_from_brief
        assert "low pitch" in _compose_items_from_brief({"pitch": "low"})
        assert "very high pitch" in _compose_items_from_brief({"pitch": "very high"})

    def test_style_whisper(self):
        from graph.subgraphs.design_loop import _compose_items_from_brief
        assert "whisper" in _compose_items_from_brief({"style": "whisper"})

    def test_composition_complete(self):
        from graph.subgraphs.design_loop import _compose_items_from_brief
        brief = {
            "genre": "feminin",
            "age": "mature",
            "pitch": "low",
            "style": "",
            "english_accent": "",
            "chinese_dialect": "",
        }
        items = _compose_items_from_brief(brief)
        assert items == ["female", "middle-aged", "low pitch"]

    def test_accent_en_preserve(self):
        from graph.subgraphs.design_loop import _compose_items_from_brief
        items = _compose_items_from_brief({"english_accent": "British accent"})
        assert "british accent" in items

    def test_brief_vide(self):
        from graph.subgraphs.design_loop import _compose_items_from_brief
        assert _compose_items_from_brief({}) == []


# ---------------------------------------------------------------------------
# random_auto — nom de fichier unique par appel (pas de hash déterministe)
# ---------------------------------------------------------------------------

class TestRandomAutoUniqueFilename:

    @patch("core.omnivoice_client.httpx.post")
    def test_meme_texte_produit_fichiers_differents(self, mock_post, tmp_path):
        """Régression commit 8a7f215 : deux générations avec le même texte
        doivent créer deux fichiers différents (sinon le player HTML5 rejoue
        depuis son cache)."""
        mock_post.return_value = MagicMock(status_code=200, content=b"RIFF" + b"\x00" * 100)
        client = OmniVoiceClient()
        p1 = client.random_auto("bonjour", output_dir=str(tmp_path))
        p2 = client.random_auto("bonjour", output_dir=str(tmp_path))
        assert p1 is not None and p2 is not None
        assert p1 != p2, "Deux appels avec le même texte doivent produire des fichiers distincts"


# ---------------------------------------------------------------------------
# fetch_design_attributes — whitelist via API racine avec cache + fallback
# ---------------------------------------------------------------------------

class TestFetchDesignAttributes:

    def setup_method(self):
        # Reset le cache de classe avant chaque test
        OmniVoiceClient._design_attributes_cache = None
        OmniVoiceClient._design_attributes_cache_ts = 0.0

    @patch("core.omnivoice_client.httpx.get")
    def test_charge_depuis_endpoint(self, mock_get):
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"attributes": {"gender": ["male", "female"], "age": [], "pitch": [], "style": [], "english_accent": [], "chinese_dialect": []}},
        )
        client = OmniVoiceClient()
        data = client.fetch_design_attributes(force=True)
        assert data["gender"] == ["male", "female"]

    @patch("core.omnivoice_client.httpx.get")
    def test_cache_evite_appels_repetes(self, mock_get):
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"attributes": {"gender": ["male", "female"]}},
        )
        client = OmniVoiceClient()
        client.fetch_design_attributes(force=True)
        client.fetch_design_attributes()  # ne doit PAS refaire l'appel
        client.fetch_design_attributes()
        assert mock_get.call_count == 1

    @patch("core.omnivoice_client.httpx.get")
    def test_fallback_sur_constantes_si_endpoint_ko(self, mock_get):
        mock_get.side_effect = Exception("Connection refused")
        client = OmniVoiceClient()
        data = client.fetch_design_attributes(force=True)
        # Fallback doit contenir au minimum les catégories de base
        assert "gender" in data
        assert "male" in data["gender"]
        assert "female" in data["gender"]
