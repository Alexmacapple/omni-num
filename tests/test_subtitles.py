"""Tests sous-titres SRT (faster-whisper) — Phase 2 rouges.

Spécification : PRD v1.5 décision 16 + annexe K (4 formats + chunking).
Code cible : omnistudio/core/subtitle_client.py
"""
import pytest


class TestSubtitleClientInit:
    def test_import_subtitle_client(self):
        from core.subtitle_client import SubtitleClient
        client = SubtitleClient()
        assert client is not None

    def test_lazy_model_load(self):
        """Le modèle faster-whisper est chargé au premier appel, pas à l'init."""
        from core.subtitle_client import SubtitleClient
        client = SubtitleClient()
        # Pas encore chargé
        assert client._model is None


class TestTranscription:
    def test_transcribe_wav_fr_retourne_segments(self):
        """Un WAV FR produit des segments avec timestamps."""
        pytest.skip("Nécessite faster-whisper + modèle 800 Mo téléchargé — Phase 3/6")

    def test_langue_non_supportee_retourne_none_et_log(self):
        """Langue hors des ~99 Whisper : retour None, log info (pas d'erreur)."""
        pytest.skip("Nécessite modèle — Phase 3")


class Test4FormatsSRT:
    def test_generate_srt_standard(self):
        from core.subtitle_client import SubtitleClient
        segments = [{"start": 0.0, "end": 3.5, "text": "Bonjour tout le monde."}]
        client = SubtitleClient()
        srt = client.generate_srt(segments)
        assert "00:00:00,000 --> 00:00:03,500" in srt
        assert "Bonjour tout le monde." in srt

    def test_generate_word_srt(self):
        from core.subtitle_client import SubtitleClient
        segments = [{"words": [
            {"word": "Hello", "start": 0.0, "end": 0.5},
            {"word": "world", "start": 0.5, "end": 1.0},
        ]}]
        client = SubtitleClient()
        word_srt = client.generate_word_srt(segments)
        assert "Hello" in word_srt
        assert "world" in word_srt

    def test_generate_shorts_srt_max_3s(self):
        from core.subtitle_client import SubtitleClient
        client = SubtitleClient()
        # Un segment long de 8 s doit être découpé en chunks ≤ 3 s
        segments = [{"start": 0.0, "end": 8.0, "text": "Un long texte de démonstration pour le format Shorts."}]
        shorts = client.generate_shorts_srt(segments)
        # Au moins 3 chunks (8/3 = 2.67)
        assert shorts.count(" --> ") >= 3

    def test_generate_multiline_srt_max_2_lignes(self):
        from core.subtitle_client import SubtitleClient
        client = SubtitleClient()
        segments = [{"start": 0.0, "end": 5.0, "text": "Ligne 1. Ligne 2. Ligne 3 qui dépasse."}]
        multi = client.generate_multiline_srt(segments)
        # Max 2 lignes par bloc
        for block in multi.split("\n\n"):
            lines = [l for l in block.split("\n") if l and "-->" not in l and not l.strip().isdigit()]
            assert len(lines) <= 2


class TestTXTJSON:
    def test_generate_txt(self):
        from core.subtitle_client import SubtitleClient
        client = SubtitleClient()
        segments = [{"start": 0, "end": 2, "text": "Hello"}, {"start": 2, "end": 4, "text": "World"}]
        txt = client.generate_txt(segments)
        assert "Hello" in txt
        assert "World" in txt

    def test_generate_json(self):
        from core.subtitle_client import SubtitleClient
        client = SubtitleClient()
        segments = [{"start": 0, "end": 2, "text": "Hello", "words": []}]
        j = client.generate_json(segments)
        assert "segments" in j


class TestChunking:
    def test_chunking_respecte_max_duration(self):
        from core.subtitle_client import SubtitleClient
        client = SubtitleClient()
        segments = [{"start": 0, "end": 20, "text": "Un texte de 20 secondes bien trop long."}]
        chunks = client.chunk_subtitles(segments, max_lines=3, max_duration_s=8)
        for c in chunks:
            assert (c["end"] - c["start"]) <= 8.0


class TestIntegrationExport:
    def test_zip_contient_dossier_subtitles_si_coche(self):
        """Export avec include_subtitles=True produit dossier subtitles/ dans le ZIP."""
        pytest.skip("Intégration export — Phase 3")

    def test_zip_sans_subtitles_si_non_coche(self):
        pytest.skip("Intégration export — Phase 3")

    def test_langue_non_supportee_skip_propre(self):
        """Fichier SRT absent pour l'étape en langue non-Whisper (mentionné dans manifest.json)."""
        pytest.skip("Intégration export — Phase 3")
