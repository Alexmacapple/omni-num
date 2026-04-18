from typing import Dict
from graph.state import WorkflowState


def export_zip_node(state: WorkflowState) -> Dict:
    """
    Nœud de validation pré-export.

    Vérifie les pré-conditions avant l'export ZIP :
    - La génération est complète (tous les fichiers produits)
    - Les fichiers générés couvrent toutes les étapes
    - La config de post-traitement est disponible

    L'assemblage ZIP réel est piloté par l'UI (tab_export.py)
    qui gère le post-traitement SoX/ffmpeg, la concaténation optionnelle,
    et la génération des documents (SCRIPT_PAROLES.md, EQUIVALENCES.md).
    """
    steps = state.get("steps", [])
    generated = state.get("generated_files", [])
    post_config = state.get("post_process_config", {})

    # Vérifier la complétude de la génération
    step_ids = {str(s.get("step_id", "")) for s in steps}
    generated_ids = {str(g.get("step_id", "")) for g in generated}
    all_generated = step_ids.issubset(generated_ids) and len(step_ids) > 0

    # Vérifier que chaque fichier généré a un chemin valide
    files_valid = all(
        g.get("wav_path") and g.get("status") == "done"
        for g in generated
    ) if generated else False

    # Config post-traitement par défaut si absente
    if not post_config:
        post_config = {
            "normalize": True,
            "stereo": True,
            "sample_rate": 48000,
            "bit_depth": 24,
        }

    return {
        "generation_complete": all_generated and files_valid,
        "post_process_config": post_config,
        "iteration_count": 1,
    }
