"""Tests pour core/schemas.py — Modeles Pydantic du workflow."""

import pytest
from pydantic import ValidationError
from core.schemas import (
    ScenarioStep,
    VoiceInfo,
    DraftVoice,
    StepAssignment,
    GeneratedFile,
    PostProcessConfig,
)


class TestScenarioStep:
    """Tests du modele ScenarioStep."""

    def test_creation_complete(self):
        step = ScenarioStep(
            step_id="1",
            text_original="Bienvenue dans le portail.",
            text_tts="Bienvenue dans le portail.",
            cleaning_status="cleaned",
            speed_factor=0.9,
        )
        assert step.step_id == "1"
        assert step.text_original == "Bienvenue dans le portail."
        assert step.text_tts == "Bienvenue dans le portail."
        assert step.cleaning_status == "cleaned"
        assert step.speed_factor == 0.9

    def test_defaults(self):
        step = ScenarioStep(step_id="2", text_original="Texte brut.")
        assert step.text_tts == ""
        assert step.cleaning_status == "pending"
        assert step.speed_factor == 1.0
        assert step.language_override is None

    def test_missing_required_field_raises(self):
        with pytest.raises(ValidationError):
            ScenarioStep(step_id="3")  # text_original manquant

    def test_missing_step_id_raises(self):
        with pytest.raises(ValidationError):
            ScenarioStep(text_original="Texte sans id.")


class TestVoiceInfo:
    """Tests du modele VoiceInfo."""

    def test_native_voice(self):
        voice = VoiceInfo(name="Lea", type="native")
        assert voice.name == "Lea"
        assert voice.type == "native"
        assert voice.source == ""
        assert voice.gender == ""

    def test_custom_voice(self):
        voice = VoiceInfo(
            name="narrateur-pro",
            type="custom",
            source="design",
            gender="masculin",
            description="Voix grave et posee.",
            voice_instruct="A deep, authoritative male voice.",
        )
        assert voice.type == "custom"
        assert voice.source == "design"
        assert voice.voice_instruct.startswith("A deep")


class TestDraftVoice:
    """Tests du modele DraftVoice."""

    def test_defaults(self):
        draft = DraftVoice(draft_id="d1", voice_instruct="test instruct")
        assert draft.status == "designing"
        assert draft.brief == {}
        assert draft.wav_history == []
        assert draft.favorite_index == -1
        assert draft.locked_as == ""

    def test_locked_status(self):
        draft = DraftVoice(
            draft_id="d2",
            voice_instruct="instruct",
            status="locked",
            locked_as="ma-voix",
        )
        assert draft.status == "locked"
        assert draft.locked_as == "ma-voix"


class TestStepAssignment:
    """Tests du modele StepAssignment."""

    def test_creation(self):
        assign = StepAssignment(step_id="1", voice_name="Lea")
        assert assign.step_id == "1"
        assert assign.voice_name == "Lea"
        assert assign.instruct == ""

    def test_with_instruct(self):
        assign = StepAssignment(
            step_id="2",
            voice_name="narrateur-pro",
            instruct="Ton chaleureux et engageant.",
        )
        assert assign.instruct == "Ton chaleureux et engageant."


class TestGeneratedFile:
    """Tests du modele GeneratedFile."""

    def test_all_fields(self):
        gen = GeneratedFile(
            step_id="1",
            filename="etape-01.wav",
            voice_name="Lea",
            wav_path="/tmp/audio/etape-01.wav",
            status="done",
            duration_seconds=3.5,
            size_kb=168.0,
        )
        assert gen.step_id == "1"
        assert gen.filename == "etape-01.wav"
        assert gen.voice_name == "Lea"
        assert gen.wav_path == "/tmp/audio/etape-01.wav"
        assert gen.status == "done"
        assert gen.duration_seconds == 3.5
        assert gen.size_kb == 168.0

    def test_defaults(self):
        gen = GeneratedFile(
            step_id="2",
            filename="etape-02.wav",
            voice_name="Lea",
            wav_path="/tmp/audio/etape-02.wav",
            status="pending",
        )
        assert gen.duration_seconds == 0.0
        assert gen.size_kb == 0.0


class TestPostProcessConfig:
    """Tests du modele PostProcessConfig."""

    def test_defaults(self):
        config = PostProcessConfig()
        assert config.normalize is True
        assert config.stereo is True
        assert config.sample_rate == 48000
        assert config.bit_depth == 24
        assert config.tool == "sox"

    def test_custom_values(self):
        config = PostProcessConfig(
            normalize=False,
            stereo=False,
            sample_rate=44100,
            bit_depth=16,
            tool="ffmpeg",
        )
        assert config.normalize is False
        assert config.stereo is False
        assert config.sample_rate == 44100
        assert config.bit_depth == 16
        assert config.tool == "ffmpeg"
