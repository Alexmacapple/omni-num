from typing import Dict, List
from collections import defaultdict
from graph.state import WorkflowState


def group_segments_for_batch(segments: List[Dict]) -> List[Dict]:
    """Groupe les segments par (voice, language, speed) pour optimiser les batch OmniVoice.

    Contrairement à voxstudio qui groupait par étape, omni-num groupe par segment
    (PRD v1.5 décision 8, permet le batch inter-étapes pour la même voix).

    Returns:
        Liste de groupes [{"voice": str, "language": str, "speed": float, "segments": [...]}, ...]
    """
    grouped = defaultdict(list)
    for seg in segments:
        key = (seg["voice"], seg.get("language", "fr"), seg.get("speed", 1.0))
        grouped[key].append(seg)

    return [
        {"voice": v, "language": l, "speed": s, "segments": segs}
        for (v, l, s), segs in grouped.items()
    ]


def _validate_assignments(steps: List[Dict], assignments: Dict[str, str]) -> List[str]:
    """Vérifie que chaque étape a une voix assignée."""
    missing = []
    for step in steps:
        sid = str(step.get("step_id", ""))
        if sid and sid not in assignments:
            missing.append(sid)
    return missing


def generate_batch_node(state: WorkflowState) -> Dict:
    """
    Nœud de validation pré-génération.

    Vérifie les pré-conditions avant la génération batch :
    - Toutes les étapes ont une voix assignée
    - Les textes nettoyés sont disponibles

    La génération réelle est pilotée par l'UI via le pattern yield
    (incompatible avec graph.invoke, cf. PRD l.1134-1161).
    Le groupement par voix est géré directement par tab_generate.py.
    """
    steps = state.get("steps", [])
    assignments = state.get("assignments", {})
    generated = state.get("generated_files", [])

    # Vérifier que des étapes existent
    if not steps:
        return {
            "generation_complete": False,
            "iteration_count": 1,
        }

    # Vérifier que toutes les étapes ont une assignation
    missing = _validate_assignments(steps, assignments)
    if missing:
        # Assignation incomplète — le graphe ne devrait pas arriver ici
        # mais on gère le cas défensif
        return {
            "generation_complete": False,
            "iteration_count": 1,
        }

    # Vérifier que les textes nettoyés sont disponibles
    steps_without_text = [
        str(s.get("step_id", ""))
        for s in steps
        if not (s.get("text_tts") or s.get("text_original"))
    ]
    if steps_without_text:
        return {
            "generation_complete": False,
            "iteration_count": 1,
        }

    # Si des fichiers sont déjà générés, vérifier la complétude
    generated_ids = {str(g.get("step_id", "")) for g in generated}
    step_ids = {str(s.get("step_id", "")) for s in steps}
    complete = step_ids.issubset(generated_ids) and len(step_ids) > 0

    return {
        "generation_complete": complete,
        "iteration_count": 1,
    }
