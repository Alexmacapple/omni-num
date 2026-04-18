from typing import Annotated, TypedDict, List, Dict, Optional
from operator import add

class WorkflowState(TypedDict):
    # --- Global ---
    llm_provider: str
    llm_model_override: str
    llm_temperature: float
    api_healthy: bool
    models_loaded: bool
    fidelity_mode: str
    default_language: str
    iteration_count: Annotated[int, add]

    # --- Import ---
    source_file: str
    source_format: str
    excel_sheet: str

    # --- Nettoyage / CleanState compatible ---
    steps: List[Dict]
    cleaning_mode: str
    cleaning_validated: bool
    cleaning_log: Annotated[List[Dict], add]
    domain_glossary: Dict[str, str]
    correction_patterns: Dict[str, str]
    correction_parentheses: Dict[str, str]
    correction_majuscules: Dict[str, str]
    decision: str  # Utilisé par les sub-graphs
    iteration: int # Compteur de boucle interne

    # --- Voix / DesignState compatible ---
    available_voices: List[Dict]
    draft_voices: Annotated[List[Dict], add]
    locked_voices: Annotated[List[str], add]
    voice_instruct: str
    wav_paths: Annotated[List[str], add]
    brief: Dict
    favorite_index: int
    locked_name: str

    # --- Selection et assignation ---
    selected_voices: List[str]
    assignments: Dict[str, str]
    instructions: Dict[str, str]
    default_voice: str

    # --- Multi-voix par étape (PRD v1.5 décision 8, traite PRD-033) ---
    # segment_assignments : liste plate des segments, append-only via reducer
    # step_assignments : groupement par step_id (1 à N segments par étape)
    # user_sub : sub JWT du user courant (pour check_voice_ownership)
    # user_voices : noms des voix custom que le user possède
    # system_voices : noms des 6 voix système (toujours accessibles)
    segment_assignments: Annotated[List[Dict], add]
    step_assignments: List[Dict]
    user_sub: str
    user_voices: List[str]
    system_voices: List[str]

    # --- Génération & Export ---
    generated_files: Annotated[List[Dict], add]
    generation_complete: bool
    post_process_config: Dict
    export_path: str

    # --- Sous-titres SRT (PRD v1.5 décision 16) ---
    # include_subtitles : si true, Phase 6 export génère SRT via faster-whisper
    include_subtitles: bool


# ---------------------------------------------------------------------------
# Types secondaires (pour annotation explicite côté node)
# ---------------------------------------------------------------------------

class SegmentAssignment(TypedDict):
    """Un segment d'étape attribué à une voix (PRD annexe E)."""
    segment_id: str
    step_id: str
    text: str
    voice: str
    language: str
    speed: float
    instruct: Optional[str]
    duration: Optional[float]


class StepAssignment(TypedDict):
    """Groupement des segments d'une étape (avec voix par défaut)."""
    step_id: str
    default_voice: str
    segments: List[SegmentAssignment]

# On garde les types pour la documentation interne mais le WorkflowState est le "SuperState"
CleanState = WorkflowState
DesignState = WorkflowState
