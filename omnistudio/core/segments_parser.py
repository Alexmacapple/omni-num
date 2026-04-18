"""Parser multi-voix [voice:X] — PRD v1.5 décision 8 + annexe M.

Regex stricte anti-XSS : ^[a-zA-Z][a-zA-Z0-9_-]{2,49}$
- Commence par une lettre
- 3 à 50 caractères
- Alphanumériques + _ et - uniquement
- Rejette <, >, ', ", espaces, entités HTML, chiffres en tête

Comportement :
- Tag valide (regex OK) : segment attribué à la voix
- Tag invalide (nom hors regex) : conservation du texte littéral + log warning
- Voix inexistante (regex OK mais pas dans /voices) : 422 côté /api/assign
"""
import logging
import re
from typing import List, Optional, TypedDict

logger = logging.getLogger(__name__)

# Regex stricte : groupe capturant le nom de voix valide
# Le pattern à l'intérieur de [voice:...] doit matcher la regex de validation
VOICE_NAME_PATTERN = r"[a-zA-Z][a-zA-Z0-9_-]{2,49}"
TAG_RE = re.compile(r"\[voice:(" + VOICE_NAME_PATTERN + r")\]")


class SegmentAssignment(TypedDict):
    segment_id: str
    step_id: str
    text: str
    voice: str
    language: str
    speed: float
    instruct: Optional[str]
    duration: Optional[float]


def _make_segment(
    step_id: str,
    idx: int,
    text: str,
    voice: str,
    language: str = "fr",
    speed: float = 1.0,
) -> SegmentAssignment:
    """Factory d'un SegmentAssignment avec valeurs par défaut."""
    return {
        "segment_id": f"{step_id}_seg_{idx:03d}",
        "step_id": step_id,
        "text": text,
        "voice": voice,
        "language": language,
        "speed": speed,
        "instruct": None,
        "duration": None,
    }


def parse_segments(
    step_text: str,
    default_voice: str,
    step_id: str,
    language: str = "fr",
    speed: float = 1.0,
) -> List[SegmentAssignment]:
    """Parse les tags [voice:X] dans step_text et découpe en segments.

    Règles:
    - Texte avant le 1er tag : voix par défaut
    - Texte entre [voice:A] et le prochain tag : voix A
    - Dernier segment : voix du dernier tag
    - Si 2 tags consécutifs sans texte entre (ex. [voice:A][voice:B] Texte) :
      le second écrase le premier, 1 seul segment B
    - Tag en fin sans texte après : segment vide ignoré

    Le regex ne matche que les tags dont le nom passe la validation.
    Tout tag malformé reste dans le texte littéralement.

    Args:
        step_text: texte de l'étape, peut contenir des [voice:X].
        default_voice: voix à utiliser avant le 1er tag et si pas de tag.
        step_id: identifiant de l'étape parent (pour segment_id).
        language: code langue par défaut.
        speed: multiplicateur de vitesse par défaut.

    Returns:
        Liste de SegmentAssignment (au moins 1 segment).
    """
    if not step_text or not step_text.strip():
        return []

    parts = TAG_RE.split(step_text)
    # parts = [before_first_tag, voice_1, between_1_2, voice_2, ..., after_last_tag]

    segments: List[SegmentAssignment] = []
    current_voice = default_voice
    idx = 0

    for i, part in enumerate(parts):
        if i == 0:
            # Texte avant le 1er tag
            text = part.strip()
            if text:
                segments.append(_make_segment(step_id, idx, text, current_voice, language, speed))
                idx += 1
        elif i % 2 == 1:
            # Groupe capturé (nom de voix)
            current_voice = part
        else:
            # Texte entre deux tags
            text = part.strip()
            if text:
                segments.append(_make_segment(step_id, idx, text, current_voice, language, speed))
                idx += 1

    # Si aucun segment produit (texte vide ou tags orphelins), fallback au texte brut
    if not segments:
        text = step_text.strip()
        if text:
            segments.append(_make_segment(step_id, 0, text, default_voice, language, speed))

    return segments
