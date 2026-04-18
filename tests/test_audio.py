"""Tests pour core/audio.py -- post-traitement et concatenation audio."""

import os
import subprocess
from unittest.mock import MagicMock, patch, call

import pytest

from core.audio import process_audio, concatenate_audio


# ---------------------------------------------------------------------------
# TestProcessAudio
# ---------------------------------------------------------------------------
class TestProcessAudio:
    @patch("core.audio.subprocess.run")
    def test_sox_succes(self, mock_run, fake_wav_file, tmp_path):
        output = str(tmp_path / "output.wav")
        config = {"normalize": True, "stereo": True, "rate": 48000}
        result = process_audio(fake_wav_file, output, config)
        assert result is True
        mock_run.assert_called_once()

    @patch("core.audio.subprocess.run")
    def test_sox_echec_ffmpeg_succes(self, mock_run, fake_wav_file, tmp_path):
        output = str(tmp_path / "output.wav")
        config = {"normalize": True, "stereo": True, "rate": 48000}

        # Sox echoue, ffmpeg reussit
        def side_effect(cmd, **kwargs):
            if cmd[0] == "sox":
                raise subprocess.CalledProcessError(1, "sox")
            return MagicMock(returncode=0)

        mock_run.side_effect = side_effect
        result = process_audio(fake_wav_file, output, config)
        assert result is True
        assert mock_run.call_count == 2

    @patch("core.audio.subprocess.run")
    def test_tout_echec_copie(self, mock_run, fake_wav_file, tmp_path):
        output = str(tmp_path / "output.wav")
        config = {"normalize": True}

        # Sox et ffmpeg echouent tous les deux
        mock_run.side_effect = subprocess.CalledProcessError(1, "cmd")
        result = process_audio(fake_wav_file, output, config)
        assert result is False
        # Le fichier doit etre copie en fallback
        assert os.path.isfile(output)

    @patch("core.audio.subprocess.run")
    def test_config_normalize(self, mock_run, fake_wav_file, tmp_path):
        output = str(tmp_path / "output.wav")
        config = {"normalize": True}
        process_audio(fake_wav_file, output, config)
        cmd = mock_run.call_args[0][0]
        assert "gain" in cmd
        assert "-n" in cmd
        assert "-3" in cmd

    @patch("core.audio.subprocess.run")
    def test_config_stereo(self, mock_run, fake_wav_file, tmp_path):
        output = str(tmp_path / "output.wav")
        config = {"stereo": True}
        process_audio(fake_wav_file, output, config)
        cmd = mock_run.call_args[0][0]
        assert "channels" in cmd
        assert "2" in cmd

    @patch("core.audio.subprocess.run")
    def test_config_rate(self, mock_run, fake_wav_file, tmp_path):
        output = str(tmp_path / "output.wav")
        config = {"rate": 48000}
        process_audio(fake_wav_file, output, config)
        cmd = mock_run.call_args[0][0]
        assert "rate" in cmd
        assert "48000" in cmd


# ---------------------------------------------------------------------------
# TestConcatenateAudio
# ---------------------------------------------------------------------------
class TestConcatenateAudio:
    def test_liste_vide(self, tmp_path):
        output = str(tmp_path / "concat.wav")
        result = concatenate_audio([], output)
        assert result is False

    @patch("core.audio.subprocess.run")
    def test_succes_sox(self, mock_run, fake_wav_file, tmp_path):
        output = str(tmp_path / "concat.wav")
        mock_run.return_value = MagicMock(returncode=0)
        result = concatenate_audio(
            [fake_wav_file, fake_wav_file],
            output,
            silence_duration=0.5,
        )
        assert result is True
        # Au moins 2 appels : creation silence + concatenation
        assert mock_run.call_count >= 2

    @patch("core.audio.subprocess.run")
    def test_sox_echec_ffmpeg_fallback(self, mock_run, fake_wav_file, tmp_path):
        output = str(tmp_path / "concat.wav")
        call_count = {"n": 0}

        def side_effect(cmd, **kwargs):
            call_count["n"] += 1
            # Premier appel (silence sox) : succes
            if call_count["n"] == 1:
                return MagicMock(returncode=0)
            # Deuxieme appel (concat sox) : echec
            if call_count["n"] == 2:
                raise subprocess.CalledProcessError(1, "sox")
            # Troisieme appel (ffmpeg fallback) : succes
            return MagicMock(returncode=0)

        mock_run.side_effect = side_effect
        result = concatenate_audio(
            [fake_wav_file, fake_wav_file],
            output,
        )
        assert result is True
