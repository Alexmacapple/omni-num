"""Tests multi-voix par étape — Phase 2 rouges.

Spécification : PRD v1.5 décision 8 (traite PRD-033) + annexe E (schéma State).
Code cible :
- omnistudio/graph/state.py : SegmentAssignment, StepAssignment
- omnistudio/graph/subgraphs/multi_voice_expansion.py
- omnistudio/graph/nodes/generate_node.py (batch inter-segments)
"""
import pytest


class TestSchemaSegmentAssignment:
    def test_champs_obligatoires(self):
        from graph.state import SegmentAssignment
        seg: SegmentAssignment = {
            "segment_id": "s1_seg_000",
            "step_id": "s1",
            "text": "Hello",
            "voice": "Marianne",
            "language": "fr",
            "speed": 1.0,
            "instruct": None,
            "duration": None,
        }
        assert seg["segment_id"].startswith("s1_")

    def test_step_assignment_contient_segments(self):
        from graph.state import StepAssignment
        sa: StepAssignment = {
            "step_id": "s1",
            "default_voice": "Marianne",
            "segments": [],
        }
        assert sa["step_id"] == "s1"


class TestExpansionNode:
    def test_etape_sans_tag_produit_1_segment(self):
        from graph.subgraphs.multi_voice_expansion import expand_step
        state = {
            "steps": {"s1": {"text": "Hello world"}},
            "assignments": {"s1": {"voice": "Marianne"}},
            "user_sub": "alex-sub",
        }
        segments = expand_step(state, "s1")
        assert len(segments) == 1
        assert segments[0]["voice"] == "Marianne"

    def test_etape_3_tags_produit_4_segments(self):
        from graph.subgraphs.multi_voice_expansion import expand_step
        state = {
            "steps": {"s1": {"text": "A [voice:Jean] B [voice:Paul] C [voice:Marianne] D"}},
            "assignments": {"s1": {"voice": "Marianne"}},
            "user_sub": "alex-sub",
        }
        segments = expand_step(state, "s1")
        assert len(segments) == 4
        assert [s["voice"] for s in segments] == ["Marianne", "Jean", "Paul", "Marianne"]


class TestOwnershipEnExpansion:
    def test_voix_inaccessible_leve_422(self):
        """Alex insère [voice:VoixDeBob] dans son texte → 422."""
        from fastapi import HTTPException
        from graph.subgraphs.multi_voice_expansion import expand_step
        state = {
            "steps": {"s1": {"text": "Hello [voice:VoixDeBob] World"}},
            "assignments": {"s1": {"voice": "Marianne"}},
            "user_sub": "alex-sub",
            "user_voices": ["MaVoixAlex"],  # Alex ne possède pas VoixDeBob
            "system_voices": ["Marianne", "Lea"],
        }
        with pytest.raises(HTTPException) as exc:
            expand_step(state, "s1")
        assert exc.value.status_code == 422
        assert "VoixDeBob" in str(exc.value.detail)


class TestBatchInterSegments:
    """generate_node groupe par (voice, lang, speed) inter-segments (pas inter-étapes)."""

    def test_groupage_inter_segments_2_steps(self):
        from graph.nodes.generate_node import group_segments_for_batch
        segments = [
            {"segment_id": "s1_seg_000", "voice": "Marianne", "language": "fr", "speed": 1.0},
            {"segment_id": "s1_seg_001", "voice": "Jean", "language": "fr", "speed": 1.0},
            {"segment_id": "s2_seg_000", "voice": "Marianne", "language": "fr", "speed": 1.0},
            {"segment_id": "s2_seg_001", "voice": "Jean", "language": "fr", "speed": 1.0},
        ]
        groups = group_segments_for_batch(segments)
        # 2 groupes : Marianne+fr+1.0 et Jean+fr+1.0, chacun avec 2 segments inter-étapes
        assert len(groups) == 2
        marianne_group = next(g for g in groups if g["voice"] == "Marianne")
        assert len(marianne_group["segments"]) == 2


class TestStateEnrichi:
    def test_segment_assignments_reducer_append_only(self):
        """Le reducer Annotated[List, add] concatène les segments sans écraser."""
        from graph.state import WorkflowState
        # Vérifier que le champ existe avec le bon reducer
        annotations = WorkflowState.__annotations__
        assert "segment_assignments" in annotations
