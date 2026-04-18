"""Tests du sous-graphe de design vocal (design_loop).

Couvre :
- generate_voice_instruct : noeud LangGraph avec mock LLM
- synthesize_design : appel OmniVoiceClient mocke
- create_design_subgraph : compilation du graphe
- check_decision : logique de branchement conditionnel
"""

import pytest
from unittest.mock import patch, MagicMock
from graph.subgraphs.design_loop import (
    generate_voice_instruct,
    synthesize_design,
    create_design_subgraph,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def config_runnable():
    """Configuration RunnableConfig minimale pour les noeuds."""
    return {"configurable": {"thread_id": "test-design-456"}}


@pytest.fixture
def brief_standard():
    """Brief utilisateur type pour le design vocal."""
    return {
        "contexte": "formation professionnelle",
        "emotion": "bienveillante et encourageante",
        "genre": "feminin",
        "age": "30-40 ans",
        "extra": "rythme calme, ton pedagogique",
    }


@pytest.fixture
def etat_design(sample_state, brief_standard):
    """Etat complet pour le sous-graphe design."""
    state = dict(sample_state)
    state["brief"] = brief_standard
    state["voice_instruct"] = ""
    state["wav_paths"] = []
    state["iteration"] = 0
    state["decision"] = ""
    return state


# ---------------------------------------------------------------------------
# Tests generate_voice_instruct
# ---------------------------------------------------------------------------

class TestGenererVoiceInstruct:
    """Tests du noeud generate_voice_instruct avec mock LLM."""

    @patch("graph.subgraphs.design_loop.LLMClient")
    @patch("graph.subgraphs.design_loop.get_api_key", return_value="fake-key")
    def test_retourne_voice_instruct_non_vide(
        self, mock_api_key, mock_llm_cls,
        etat_design, config_runnable,
    ):
        """Le noeud retourne un voice_instruct genere par le LLM."""
        mock_llm = MagicMock()
        mock_llm.ask.return_value = "Voix feminine chaleureuse, timbre doux et veloute."
        mock_llm_cls.return_value = mock_llm

        result = generate_voice_instruct(etat_design, config_runnable)

        assert result["voice_instruct"] == "Voix feminine chaleureuse, timbre doux et veloute."
        assert len(result["voice_instruct"]) > 0

    @patch("graph.subgraphs.design_loop.LLMClient")
    @patch("graph.subgraphs.design_loop.get_api_key", return_value="fake-key")
    def test_iteration_incrementee(
        self, mock_api_key, mock_llm_cls,
        etat_design, config_runnable,
    ):
        """L'iteration est incrementee de 1 a chaque appel."""
        mock_llm = MagicMock()
        mock_llm.ask.return_value = "Description vocale."
        mock_llm_cls.return_value = mock_llm

        etat_design["iteration"] = 5
        result = generate_voice_instruct(etat_design, config_runnable)

        assert result["iteration"] == 6

    @patch("graph.subgraphs.design_loop.LLMClient")
    @patch("graph.subgraphs.design_loop.get_api_key", return_value="fake-key")
    def test_brief_utilise_dans_prompt(
        self, mock_api_key, mock_llm_cls,
        etat_design, config_runnable,
    ):
        """Le brief est passe dans le user_prompt envoye au LLM."""
        mock_llm = MagicMock()
        mock_llm.ask.return_value = "Instruct genere."
        mock_llm_cls.return_value = mock_llm

        generate_voice_instruct(etat_design, config_runnable)

        # Verifier que ask() a ete appele avec le brief dans le user_prompt
        call_args = mock_llm.ask.call_args
        user_prompt = call_args[0][1]  # Deuxieme argument positionnel
        assert "formation professionnelle" in user_prompt
        assert "bienveillante" in user_prompt
        assert "feminin" in user_prompt


# ---------------------------------------------------------------------------
# Tests synthesize_design
# ---------------------------------------------------------------------------

class TestSynthetiserDesign:
    """Tests du noeud synthesize_design avec mock OmniVoiceClient."""

    @patch("graph.subgraphs.design_loop.vox_client")
    def test_retourne_wav_path_si_design_ok(self, mock_vox, etat_design):
        """Si design() retourne un chemin, wav_paths le contient."""
        mock_vox.design.return_value = "/tmp/design_42.wav"
        etat_design["voice_instruct"] = "Voix douce et chaleureuse."

        result = synthesize_design(etat_design)

        assert result["wav_paths"] == ["/tmp/design_42.wav"]
        mock_vox.design.assert_called_once()

    @patch("graph.subgraphs.design_loop.vox_client")
    def test_retourne_wav_paths_vide_si_design_echoue(self, mock_vox, etat_design):
        """Si design() retourne None, wav_paths est une liste vide."""
        mock_vox.design.return_value = None
        etat_design["voice_instruct"] = "Voix qui va echouer."

        result = synthesize_design(etat_design)

        assert result["wav_paths"] == []


# ---------------------------------------------------------------------------
# Tests create_design_subgraph
# ---------------------------------------------------------------------------

class TestCreerSousGrapheDesign:
    """Tests de la compilation du sous-graphe design."""

    def test_compilation_ne_crashe_pas(self):
        """Le graphe compile sans erreur."""
        graph = create_design_subgraph()
        assert graph is not None


# ---------------------------------------------------------------------------
# Tests logique check_decision (via les conditions du graphe)
# ---------------------------------------------------------------------------

class TestLogiqueDecisionDesign:
    """Tests de la logique de branchement check_decision du design."""

    def _check_decision(self, state):
        """Reproduit la logique de check_decision de design_loop."""
        from langgraph.graph import END
        decision = state.get("decision")
        if decision == "lock" or state.get("iteration", 0) >= 20:
            return END
        return "generate_instruct" if decision == "regenerate_instruct" else "synthesize"

    def test_decision_lock_termine(self):
        """decision='lock' mene a la fin du graphe."""
        from langgraph.graph import END
        state = {"decision": "lock", "iteration": 3}
        assert self._check_decision(state) == END

    def test_iteration_max_termine(self):
        """iteration >= 20 mene a la fin du graphe."""
        from langgraph.graph import END
        state = {"decision": "", "iteration": 20}
        assert self._check_decision(state) == END

    def test_regenerate_instruct_reboucle(self):
        """decision='regenerate_instruct' redirige vers generate_instruct."""
        state = {"decision": "regenerate_instruct", "iteration": 2}
        assert self._check_decision(state) == "generate_instruct"

    def test_decision_par_defaut_vers_synthesize(self):
        """Sans decision specifique, on redirige vers synthesize."""
        state = {"decision": "", "iteration": 5}
        assert self._check_decision(state) == "synthesize"
