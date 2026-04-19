from pydantic import BaseModel, Field, model_validator, field_validator
from typing import Any, List, Dict, Optional
import re


class ApiError(BaseModel):
    """Erreur API structurée."""
    code: str
    message: str


class ApiResponse(BaseModel):
    """Réponse API uniforme (wrapper api_response)."""
    data: Optional[Any] = None
    error: Optional[ApiError] = None


class ScenarioStep(BaseModel):
    """Une étape du scénario importé."""
    step_id: str
    text_original: str
    text_tts: str = ""
    cleaning_status: str = "pending"  # pending | cleaned | validated
    language_override: Optional[str] = None
    speed_factor: float = 1.0

class VoiceInfo(BaseModel):
    """Une voix verrouillée (native ou custom)."""
    name: str
    type: str                     # "native" | "custom"
    source: str = ""              # "preset" | "design" | "clone"
    gender: str = ""
    description: str = ""
    voice_instruct: str = ""

class DraftVoice(BaseModel):
    """Une voix en cours de design (volatile)."""
    draft_id: str
    voice_instruct: str
    brief: Dict = {}
    wav_history: List[str] = []
    favorite_index: int = -1
    status: str = "designing"     # designing | locked
    locked_as: str = ""

class StepAssignment(BaseModel):
    """Assignation voix ↔ étape."""
    step_id: str
    voice_name: str
    instruct: str = ""            # instruction émotionnelle (natives)

class GeneratedFile(BaseModel):
    """Fichier audio généré."""
    step_id: str
    filename: str
    voice_name: str
    wav_path: str
    status: str                   # pending | generating | done | error
    duration_seconds: float = 0.0
    size_kb: float = 0.0

class PostProcessConfig(BaseModel):
    """Configuration du post-traitement."""
    normalize: bool = True
    stereo: bool = True
    sample_rate: int = 48000
    bit_depth: int = 24
    tool: str = "sox"             # sox | ffmpeg


# =============================================================================
# Schémas omni-num spécifiques (PRD v1.5)
# =============================================================================


class VoiceMeta(BaseModel):
    """Métadonnées d'une voix custom (PRD v1.5 décision 7, traite PRD-032).

    Règle : owner obligatoire sauf si system=True.
    Regex validation XSS : ^[a-zA-Z][a-zA-Z0-9_-]{2,49}$
    """
    name: str = Field(..., min_length=3, max_length=50)
    owner: Optional[str] = None
    system: bool = False
    description: str = ""
    source: str = "design"  # "design" | "clone"
    instruct: Optional[str] = None
    language: str = "fr"
    created_at: Optional[str] = None

    @field_validator("name")
    @classmethod
    def validate_voice_name(cls, v):
        """Validation XSS stricte du nom de voix."""
        if not re.match(r"^[a-zA-Z][a-zA-Z0-9_-]{2,49}$", v):
            raise ValueError("Nom de voix doit commencer par une lettre, 3-50 caractères alphanumériques + tirets/underscores")
        return v

    @model_validator(mode="after")
    def check_owner_required(self):
        if not self.system and not self.owner:
            raise ValueError("owner requis si system=False")
        return self


class SegmentAssignmentSchema(BaseModel):
    """Un segment attribué à une voix (décision 8, traite PRD-033)."""
    segment_id: str
    step_id: str
    text: str
    voice: str
    language: str = "fr"
    speed: float = 1.0
    instruct: Optional[str] = None
    duration: Optional[float] = None


class GenerateRequest(BaseModel):
    """Requête génération avec 11 paramètres avancés (PRD v1.5 décision 14, annexe J)."""
    text: str = Field(..., min_length=1, max_length=10000)
    voice: str
    language: str = "fr"
    speed: float = Field(1.0, ge=0.5, le=2.0)

    @field_validator("voice")
    @classmethod
    def validate_voice_name(cls, v):
        """Validation XSS stricte du nom de voix."""
        if not re.match(r"^[a-zA-Z][a-zA-Z0-9_-]{2,49}$", v):
            raise ValueError("Nom de voix doit commencer par une lettre, 3-50 caractères alphanumériques + tirets/underscores")
        return v

    # 11 paramètres avancés OmniVoice (annexe J)
    num_step: int = Field(32, ge=4, le=64)
    guidance_scale: float = Field(2.0, ge=0.0, le=4.0)
    duration: Optional[float] = Field(None, ge=0.1, le=600.0)
    denoise: bool = True
    t_shift: float = Field(0.1, ge=0.0, le=1.0)
    position_temperature: float = Field(5.0, ge=0.0, le=20.0)
    class_temperature: float = Field(0.0, ge=0.0, le=5.0)
    layer_penalty_factor: float = Field(5.0, ge=0.0, le=20.0)
    postprocess_output: bool = True
    audio_chunk_duration: float = Field(15.0, ge=1.0, le=60.0)
    audio_chunk_threshold: float = Field(30.0, ge=5.0, le=120.0)


class DesignAttributesRequest(BaseModel):
    """Requête Voice Design mode Guidé — composition EN depuis selects."""
    gender: str  # Male, Female
    age: str  # Child, Teenager, Young Adult, Middle-aged, Elderly
    pitch: str  # Very Low Pitch, Low Pitch, Moderate Pitch, High Pitch, Very High Pitch
    style: str = "Neutral"  # Neutral, Whisper
    language: str = "fr"
    accent: Optional[str] = None  # English Accent (si language=en)
    dialect: Optional[str] = None  # Chinese Dialect (si language=zh)
    extra_en: str = ""  # Texte libre additionnel
