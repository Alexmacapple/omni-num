import sys
import os
import struct
import pytest
from pathlib import Path
from unittest.mock import MagicMock

# Ajouter omnistudio/ au sys.path
OMNISTUDIO_DIR = Path(__file__).resolve().parent.parent / "omnistudio"
sys.path.insert(0, str(OMNISTUDIO_DIR))


@pytest.fixture
def sample_steps():
    """5 etapes type pour les tests."""
    return [
        {"step_id": "1", "text_original": "Bienvenue dans le portail DN.", "text_tts": "", "cleaning_status": "pending", "language_override": None, "speed_factor": 1.0},
        {"step_id": "2", "text_original": "Liste :\n- Premier point\n- Deuxième point", "text_tts": "", "cleaning_status": "pending", "language_override": None, "speed_factor": 1.0},
        {"step_id": "3", "text_original": "Contactez le MOA (maîtrise d'ouvrage) pour plus d'informations.", "text_tts": "", "cleaning_status": "pending", "language_override": None, "speed_factor": 1.0},
        {"step_id": "4", "text_original": "Le SIRET est obligatoire", "text_tts": "", "cleaning_status": "pending", "language_override": None, "speed_factor": 1.0},
        {"step_id": "5", "text_original": "Merci et à bientôt !", "text_tts": "", "cleaning_status": "pending", "language_override": None, "speed_factor": 1.0},
    ]


@pytest.fixture
def sample_state(sample_steps):
    """WorkflowState complet initialise."""
    return {
        "llm_provider": "Albert Large 120B",
        "llm_model_override": "",
        "llm_temperature": 0.7,
        "api_healthy": True,
        "models_loaded": True,
        "fidelity_mode": "1.7B",
        "default_language": "fr",
        "iteration_count": 0,
        "source_file": "",
        "source_format": "",
        "excel_sheet": "PLAN",
        "steps": sample_steps,
        "cleaning_mode": "auto",
        "cleaning_validated": False,
        "cleaning_log": [],
        "domain_glossary": {},
        "correction_patterns": {},
        "correction_parentheses": {},
        "correction_majuscules": {},
        "decision": "",
        "iteration": 0,
        "available_voices": [],
        "draft_voices": [],
        "locked_voices": [],
        "voice_instruct": "",
        "wav_paths": [],
        "brief": {},
        "favorite_index": -1,
        "locked_name": "",
        "assignments": {},
        "instructions": {},
        "default_voice": "Lea",
        "generated_files": [],
        "generation_complete": False,
        "post_process_config": {},
        "export_path": "",
    }


@pytest.fixture
def fake_wav_file(tmp_path):
    """Cree un faux fichier WAV (header RIFF minimal + silence)."""
    wav_path = tmp_path / "test.wav"
    # Header WAV minimal : 44 bytes + 1000 bytes de silence
    data_size = 1000
    sample_rate = 24000
    channels = 1
    bits_per_sample = 16
    byte_rate = sample_rate * channels * bits_per_sample // 8
    block_align = channels * bits_per_sample // 8

    header = struct.pack(
        '<4sI4s4sIHHIIHH4sI',
        b'RIFF', 36 + data_size, b'WAVE',
        b'fmt ', 16, 1, channels, sample_rate, byte_rate, block_align, bits_per_sample,
        b'data', data_size
    )
    wav_path.write_bytes(header + b'\x00' * data_size)
    return str(wav_path)


@pytest.fixture
def sample_generated_files(fake_wav_file):
    """Liste de GeneratedFile pour les tests d'export."""
    return [
        {"step_id": "1", "filename": "etape-01.wav", "voice_name": "Lea", "wav_path": fake_wav_file, "status": "done"},
        {"step_id": "2", "filename": "etape-02.wav", "voice_name": "Lea", "wav_path": fake_wav_file, "status": "done"},
    ]


@pytest.fixture
def sample_xlsx(tmp_path):
    """Cree un fichier Excel temporaire avec 3 etapes."""
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "PLAN"
    ws.append(["Etape", "Scripts"])
    ws.append(["1", "Bienvenue dans le portail."])
    ws.append(["2", "Connectez-vous via Pro Connect."])
    ws.append(["3", "Merci et à bientôt."])
    path = tmp_path / "test_scenario.xlsx"
    wb.save(str(path))
    return str(path)


@pytest.fixture
def sample_markdown(tmp_path):
    """Cree un fichier Markdown temporaire avec 3 etapes."""
    content = """# Scenario Test

### Étape 1

Bienvenue dans le portail.

### Étape 2

Connectez-vous via Pro Connect.

### Étape 3

Merci et à bientôt.
"""
    path = tmp_path / "test_scenario.md"
    path.write_text(content, encoding="utf-8")
    return str(path)
