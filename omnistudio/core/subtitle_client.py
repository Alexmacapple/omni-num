"""SubtitleClient — génération SRT via faster-whisper.

PRD v1.5 décision 16 + annexe K.
Produit 4 formats SRT + TXT + JSON à partir d'un WAV.
Dépendance : faster-whisper (~500 Mo) + modèle `large-v3-turbo-ct2` (~800 Mo).
"""
import json
import logging
import os
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Langues supportées par Whisper (~99 des 646 d'OmniVoice)
# Liste non exhaustive — faster-whisper retourne la langue détectée.
_WHISPER_SUPPORTED = {
    "en", "fr", "de", "es", "it", "pt", "ru", "zh", "ja", "ko", "ar", "nl",
    "pl", "tr", "sv", "no", "da", "fi", "cs", "el", "he", "hu", "id", "ms",
    "ro", "th", "uk", "vi",
}

# Contraintes par format (PRD annexe K)
FORMAT_CONSTRAINTS = {
    "standard": {"max_lines": 3, "max_duration_s": 8.0, "max_chars_per_line": 42},
    "word": {"max_lines": 1, "max_duration_s": 2.0, "max_chars_per_line": None},
    "shorts": {"max_lines": 1, "max_duration_s": 3.0, "max_chars_per_line": 30},
    "multiline": {"max_lines": 2, "max_duration_s": 6.0, "max_chars_per_line": 38},
}


def _format_timestamp(seconds: float) -> str:
    """Formate un timestamp SRT : HH:MM:SS,mmm."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


class SubtitleClient:
    """Génère les sous-titres depuis un WAV via faster-whisper.

    Usage :
        client = SubtitleClient()
        segments = client.transcribe("audio.wav", language="fr")
        srt = client.generate_srt(segments)
    """

    def __init__(self, model_name: str = "deepdml/faster-whisper-large-v3-turbo-ct2"):
        self.model_name = model_name
        self._model = None  # Lazy load au premier appel
        self._cache_dir = os.getenv(
            "OMNISTUDIO_WHISPER_CACHE",
            os.path.join(os.path.dirname(__file__), "..", "..", "data", "models"),
        )

    def _load_model(self):
        """Charge le modèle faster-whisper (~800 Mo) en mémoire au premier usage."""
        if self._model is not None:
            return
        try:
            from faster_whisper import WhisperModel
            logger.info("Chargement faster-whisper model %s (premier usage)...", self.model_name)
            self._model = WhisperModel(
                self.model_name,
                device="auto",
                compute_type="default",
                download_root=self._cache_dir,
            )
            logger.info("faster-whisper chargé.")
        except ImportError:
            logger.error("faster-whisper non installé : pip install faster-whisper pysrt")
            raise

    def is_language_supported(self, language: str) -> bool:
        """Whisper supporte ~99 langues (sous-ensemble des 646 OmniVoice)."""
        if not language or language == "auto":
            return True
        return language.lower().split("-")[0] in _WHISPER_SUPPORTED

    def transcribe(self, wav_path: str, language: str = "auto") -> Optional[List[Dict]]:
        """Transcrit un WAV en segments avec timestamps (mot par mot).

        Retourne None si langue non supportée (skip propre, log info).
        """
        if not self.is_language_supported(language):
            logger.info("Langue '%s' non supportée par Whisper, skip.", language)
            return None

        self._load_model()
        try:
            lang = None if language == "auto" else language
            segments_iter, info = self._model.transcribe(
                wav_path, language=lang, word_timestamps=True
            )
            segments = []
            for seg in segments_iter:
                segments.append({
                    "start": seg.start,
                    "end": seg.end,
                    "text": seg.text.strip(),
                    "words": [
                        {"word": w.word, "start": w.start, "end": w.end}
                        for w in (seg.words or [])
                    ],
                })
            return segments
        except Exception as e:
            logger.error("Erreur transcribe %s : %s", wav_path, e)
            return None

    def chunk_subtitles(
        self, segments: List[Dict], max_lines: int = 3, max_duration_s: float = 8.0
    ) -> List[Dict]:
        """Découpe les segments longs en chunks respectant les contraintes.

        Un chunk = un bloc SRT.
        """
        chunks = []
        for seg in segments:
            duration = seg["end"] - seg["start"]
            if duration <= max_duration_s:
                chunks.append(seg)
            else:
                # Diviser en N chunks égaux
                n_chunks = int(duration // max_duration_s) + 1
                chunk_duration = duration / n_chunks
                text = seg["text"]
                # Découpe simpliste du texte (approximation)
                words = text.split()
                words_per_chunk = max(1, len(words) // n_chunks)
                for i in range(n_chunks):
                    start = seg["start"] + i * chunk_duration
                    end = start + chunk_duration
                    chunk_words = words[i * words_per_chunk:(i + 1) * words_per_chunk]
                    chunks.append({
                        "start": start,
                        "end": end,
                        "text": " ".join(chunk_words),
                    })
        return chunks

    def generate_srt(self, segments: List[Dict]) -> str:
        """Format SRT standard (3 lignes max, 8 s max, 42 chars/ligne)."""
        constraints = FORMAT_CONSTRAINTS["standard"]
        chunks = self.chunk_subtitles(segments, constraints["max_lines"], constraints["max_duration_s"])
        lines = []
        for i, c in enumerate(chunks, start=1):
            lines.append(str(i))
            lines.append(f"{_format_timestamp(c['start'])} --> {_format_timestamp(c['end'])}")
            lines.append(c["text"])
            lines.append("")
        return "\n".join(lines)

    def generate_word_srt(self, segments: List[Dict]) -> str:
        """Format mot par mot (karaoke)."""
        lines = []
        idx = 1
        for seg in segments:
            for word in seg.get("words", []):
                lines.append(str(idx))
                lines.append(f"{_format_timestamp(word['start'])} --> {_format_timestamp(word['end'])}")
                lines.append(word["word"].strip())
                lines.append("")
                idx += 1
        return "\n".join(lines)

    def generate_shorts_srt(self, segments: List[Dict]) -> str:
        """Format Shorts : 1 ligne, max 3 s, max 30 chars/ligne."""
        constraints = FORMAT_CONSTRAINTS["shorts"]
        chunks = self.chunk_subtitles(segments, constraints["max_lines"], constraints["max_duration_s"])
        lines = []
        for i, c in enumerate(chunks, start=1):
            lines.append(str(i))
            lines.append(f"{_format_timestamp(c['start'])} --> {_format_timestamp(c['end'])}")
            lines.append(c["text"][:constraints["max_chars_per_line"]])
            lines.append("")
        return "\n".join(lines)

    def generate_multiline_srt(self, segments: List[Dict]) -> str:
        """Format Multilignes : 2 lignes, max 6 s, 38 chars/ligne."""
        constraints = FORMAT_CONSTRAINTS["multiline"]
        chunks = self.chunk_subtitles(segments, constraints["max_lines"], constraints["max_duration_s"])
        lines = []
        for i, c in enumerate(chunks, start=1):
            lines.append(str(i))
            lines.append(f"{_format_timestamp(c['start'])} --> {_format_timestamp(c['end'])}")
            # Retour ligne à max_chars_per_line
            text = c["text"]
            max_chars = constraints["max_chars_per_line"]
            if len(text) > max_chars:
                # Split simpliste à l'espace le plus proche
                cut = text.rfind(" ", 0, max_chars)
                if cut > 0:
                    lines.append(text[:cut])
                    lines.append(text[cut:].strip()[:max_chars])
                else:
                    lines.append(text[:max_chars])
            else:
                lines.append(text)
            lines.append("")
        return "\n".join(lines)

    def generate_txt(self, segments: List[Dict]) -> str:
        """Texte brut concaténé."""
        return " ".join(seg["text"].strip() for seg in segments)

    def generate_json(self, segments: List[Dict]) -> Dict:
        """JSON structuré avec segments + word timestamps."""
        return {"segments": segments}
