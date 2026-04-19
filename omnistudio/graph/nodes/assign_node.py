from typing import Dict
from graph.state import WorkflowState

def assign_voices_node(state: WorkflowState) -> Dict:
    """
    Nœud d'assignation : valide que toutes les étapes ont une voix assignée.
    Si une étape n'a pas de voix, elle utilise la voix par défaut.
    """
    steps = state.get("steps", [])
    assignments = state.get("assignments", {})
    default_voice = state.get("default_voice", "Lea")

    new_assignments = assignments.copy()
    for step in steps:
        sid = str(step.get("step_id", ""))
        if sid and sid not in new_assignments:
            new_assignments[sid] = default_voice

    return {
        "assignments": new_assignments,
        # Note: Ne pas retourner iteration_count ici pour permettre à l'Annotated[int, add]
        # de s'accumuler correctement dans le state agrégé
    }
