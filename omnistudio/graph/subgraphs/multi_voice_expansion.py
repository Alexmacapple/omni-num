"""Sous-graphe d'expansion multi-voix — PRD v1.5 décision 8 (traite PRD-033).

Lit les textes d'étape et produit des segments via le parser [voice:X].
Vérifie l'ownership de chaque voix référencée avant d'accepter l'assignation.
"""
import logging
from typing import Dict, List

from fastapi import HTTPException

from core.segments_parser import parse_segments, SegmentAssignment

logger = logging.getLogger(__name__)


def _check_voice_accessible(voice_name: str, user_voices: List[str], system_voices: List[str]) -> bool:
    """Vérifie qu'une voix est accessible à l'utilisateur (soit perso soit système)."""
    return voice_name in user_voices or voice_name in system_voices


def expand_step(state: Dict, step_id: str) -> List[SegmentAssignment]:
    """Expanse une étape en N segments via le parser [voice:X].

    Args:
        state: WorkflowState partiel avec :
            - steps: {step_id: {"text": str, ...}}
            - assignments: {step_id: {"voice": str, "language": str, "speed": float}}
            - user_sub: str (identifiant du user)
            - user_voices: List[str] (noms des voix que user possède)
            - system_voices: List[str] (voix système, accessibles à tous)
        step_id: l'étape à expanser.

    Returns:
        Liste de segments avec text, voice, language, speed.

    Raises:
        HTTPException 422 si le texte référence une voix inaccessible.
    """
    steps = state.get("steps", {})
    if step_id not in steps:
        raise HTTPException(
            status_code=422,
            detail=f"Étape '{step_id}' non trouvée dans le state.",
        )

    assignments = state.get("assignments", {})
    if step_id not in assignments:
        raise HTTPException(
            status_code=422,
            detail=f"Assignation vocale manquante pour l'étape '{step_id}'.",
        )

    step = steps[step_id]
    assignment = assignments[step_id]
    default_voice = assignment["voice"]
    language = assignment.get("language", "fr")
    speed = assignment.get("speed", 1.0)

    segments = parse_segments(
        step_text=step["text"],
        default_voice=default_voice,
        step_id=step_id,
        language=language,
        speed=speed,
    )

    # Vérification ownership sur chaque voix référencée (via tags)
    user_voices = state.get("user_voices", [])
    system_voices = state.get("system_voices", [])

    for seg in segments:
        voice = seg["voice"]
        if not _check_voice_accessible(voice, user_voices, system_voices):
            available = sorted(set(user_voices + system_voices))
            logger.warning(
                "Segment %s référence voix inaccessible '%s' (user=%s)",
                seg["segment_id"], voice, state.get("user_sub"),
            )
            raise HTTPException(
                status_code=422,
                detail=f"Voix '{voice}' introuvable. Voix disponibles : {', '.join(available)}",
            )

    return segments


def expand_all_steps(state: Dict) -> Dict:
    """Expanse toutes les étapes du State en segment_assignments.

    Appelé depuis generate_node avant l'appel batch TTS.

    Returns:
        Un dict partial à merger dans le State (segment_assignments).
    """
    all_segments: List[SegmentAssignment] = []
    steps = state.get("steps", {})

    if not steps:
        # Pas d'étapes à expanser
        return {"segment_assignments": []}

    for step_id in steps:
        try:
            segments = expand_step(state, step_id)
            all_segments.extend(segments)
        except HTTPException as e:
            logger.error(f"Erreur expansion étape {step_id}: {e.detail}")
            raise

    return {"segment_assignments": all_segments}
