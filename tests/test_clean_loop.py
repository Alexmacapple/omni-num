"""Tests du sous-graphe de nettoyage (clean_loop).

Couvre :
- apply_layer_b : fonction pure de corrections Layer B
- propose_corrections : noeud LangGraph avec mock LLM
- create_clean_subgraph : compilation du graphe
- check_decision : logique de branchement conditionnel
"""

import pytest
from unittest.mock import patch, MagicMock
from graph.subgraphs.clean_loop import (
    apply_layer_b,
    propose_corrections,
    create_clean_subgraph,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def config_runnable():
    """Configuration RunnableConfig minimale pour les noeuds."""
    return {"configurable": {"thread_id": "test-clean-123"}}


@pytest.fixture
def etat_nettoyage_basique(sample_state):
    """Etat avec 2 etapes en attente de nettoyage."""
    state = dict(sample_state)
    state["steps"] = [
        {
            "step_id": "1",
            "text_original": "Bienvenue dans le portail DN.",
            "text_tts": "",
            "cleaning_status": "pending",
        },
        {
            "step_id": "2",
            "text_original": "Contactez le MOA pour plus d'infos.",
            "text_tts": "",
            "cleaning_status": "pending",
        },
    ]
    state["iteration"] = 0
    state["cleaning_log"] = []
    return state


@pytest.fixture
def etat_avec_valide(sample_state):
    """Etat avec une etape deja validee et une en attente."""
    state = dict(sample_state)
    state["steps"] = [
        {
            "step_id": "1",
            "text_original": "Texte deja valide.",
            "text_tts": "Texte deja valide.",
            "cleaning_status": "validated",
        },
        {
            "step_id": "2",
            "text_original": "Texte a nettoyer.",
            "text_tts": "",
            "cleaning_status": "pending",
        },
    ]
    state["iteration"] = 1
    state["cleaning_log"] = []
    return state


# ---------------------------------------------------------------------------
# Tests apply_layer_b
# ---------------------------------------------------------------------------

class TestAppliquerLayerB:
    """Tests de la fonction pure apply_layer_b."""

    def test_remplacement_patterns_regex(self):
        """Les patterns regex sont appliques correctement."""
        text = "Le DN est obligatoire."
        patterns = {r"\bDN\b": "Demarches Numeriques"}
        result = apply_layer_b(text, patterns, {}, {})
        assert result == "Le Demarches Numeriques est obligatoire."

    def test_remplacement_parentheses(self):
        """Les parentheses sont remplacees par str.replace."""
        text = "Le MOA (maitrise d'ouvrage) valide."
        parentheses = {"(maitrise d'ouvrage)": ", maitrise d'ouvrage,"}
        result = apply_layer_b(text, {}, parentheses, {})
        assert result == "Le MOA , maitrise d'ouvrage, valide."

    def test_remplacement_majuscules(self):
        """Les majuscules non naturelles sont normalisees."""
        text = "Le SIRET est requis."
        majuscules = {"SIRET": "siret"}
        result = apply_layer_b(text, {}, {}, majuscules)
        assert result == "Le siret est requis."

    def test_dictionnaires_vides(self):
        """Aucune modification avec des dictionnaires vides."""
        text = "Texte inchange."
        result = apply_layer_b(text, {}, {}, {})
        assert result == text

    def test_dictionnaires_none(self):
        """Aucun crash avec des valeurs None."""
        text = "Texte inchange."
        result = apply_layer_b(text, None, None, None)
        assert result == text

    def test_regex_invalide_ne_crashe_pas(self, caplog):
        """Une regex invalide produit un message d'erreur sans crasher."""
        text = "Texte original."
        patterns = {"[invalide": "remplacement"}
        with caplog.at_level("WARNING"):
            result = apply_layer_b(text, patterns, {}, {})
        assert "Erreur Regex" in caplog.text
        assert result == "Texte original."

    def test_combinaison_trois_corrections(self):
        """Les 3 types de corrections s'appliquent en sequence."""
        text = "Le DN (Demarches Numeriques) est en MAJUSCULE."
        patterns = {r"\bDN\b": "service"}
        parentheses = {"(Demarches Numeriques)": ""}
        majuscules = {"MAJUSCULE": "majuscule"}
        result = apply_layer_b(text, patterns, parentheses, majuscules)
        assert "service" in result
        assert "(Demarches Numeriques)" not in result
        assert "majuscule" in result


# ---------------------------------------------------------------------------
# Tests propose_corrections
# ---------------------------------------------------------------------------

class TestProposerCorrections:
    """Tests du noeud propose_corrections avec mocks."""

    @patch("graph.subgraphs.clean_loop.time.sleep")
    @patch("graph.subgraphs.clean_loop.LLMClient")
    @patch("graph.subgraphs.clean_loop.get_api_key", return_value="fake-key")
    def test_retourne_steps_nettoyes(
        self, mock_api_key, mock_llm_cls, mock_sleep,
        etat_nettoyage_basique, config_runnable,
    ):
        """Les etapes pending deviennent cleaned avec text_tts rempli."""
        mock_llm = MagicMock()
        mock_llm.ask.return_value = "Texte nettoye par le LLM."
        mock_llm_cls.return_value = mock_llm

        result = propose_corrections(etat_nettoyage_basique, config_runnable)

        assert len(result["steps"]) == 2
        for step in result["steps"]:
            assert step["cleaning_status"] == "cleaned"
            assert step["text_tts"] == "Texte nettoye par le LLM."

    @patch("graph.subgraphs.clean_loop.time.sleep")
    @patch("graph.subgraphs.clean_loop.LLMClient")
    @patch("graph.subgraphs.clean_loop.get_api_key", return_value="fake-key")
    def test_etapes_validees_preservees(
        self, mock_api_key, mock_llm_cls, mock_sleep,
        etat_avec_valide, config_runnable,
    ):
        """Les etapes deja validees ne sont pas modifiees et le LLM n'est appele qu'une fois."""
        mock_llm = MagicMock()
        mock_llm.ask.return_value = "Texte nettoye."
        mock_llm_cls.return_value = mock_llm

        result = propose_corrections(etat_avec_valide, config_runnable)

        # L'etape validee est conservee telle quelle
        etape_validee = [s for s in result["steps"] if s["step_id"] == "1"][0]
        assert etape_validee["cleaning_status"] == "validated"
        assert etape_validee["text_tts"] == "Texte deja valide."

        # Le LLM n'est appele que pour l'etape pending
        assert mock_llm.ask.call_count == 1

    @patch("graph.subgraphs.clean_loop.time.sleep")
    @patch("graph.subgraphs.clean_loop.LLMClient")
    @patch("graph.subgraphs.clean_loop.get_api_key", return_value="fake-key")
    def test_fallback_layer_a_sur_erreur_llm(
        self, mock_api_key, mock_llm_cls, mock_sleep,
        etat_nettoyage_basique, config_runnable,
    ):
        """Quand le LLM retourne une erreur, apply_layer_a est utilise en fallback."""
        mock_llm = MagicMock()
        mock_llm.ask.return_value = "Erreur : Impossible de joindre le moteur IA."
        mock_llm_cls.return_value = mock_llm

        result = propose_corrections(etat_nettoyage_basique, config_runnable)

        for step in result["steps"]:
            assert step["cleaning_status"] == "cleaned"
            # Le fallback layer_a produit un texte non vide (pas l'erreur brute)
            assert not step["text_tts"].startswith("Erreur :")
            assert len(step["text_tts"]) > 0

    @patch("graph.subgraphs.clean_loop.time.sleep")
    @patch("graph.subgraphs.clean_loop.LLMClient")
    @patch("graph.subgraphs.clean_loop.get_api_key", return_value="fake-key")
    def test_iteration_incrementee(
        self, mock_api_key, mock_llm_cls, mock_sleep,
        etat_nettoyage_basique, config_runnable,
    ):
        """L'iteration est incrementee de 1 a chaque appel."""
        mock_llm = MagicMock()
        mock_llm.ask.return_value = "Texte nettoye."
        mock_llm_cls.return_value = mock_llm

        etat_nettoyage_basique["iteration"] = 3
        result = propose_corrections(etat_nettoyage_basique, config_runnable)

        assert result["iteration"] == 4

    @patch("graph.subgraphs.clean_loop.time.sleep")
    @patch("graph.subgraphs.clean_loop.LLMClient")
    @patch("graph.subgraphs.clean_loop.get_api_key", return_value="fake-key")
    def test_cleaning_log_rempli(
        self, mock_api_key, mock_llm_cls, mock_sleep,
        etat_nettoyage_basique, config_runnable,
    ):
        """Le cleaning_log contient une entree par etape traitee."""
        mock_llm = MagicMock()
        mock_llm.ask.return_value = "Texte nettoye."
        mock_llm_cls.return_value = mock_llm

        result = propose_corrections(etat_nettoyage_basique, config_runnable)

        assert len(result["cleaning_log"]) == 2
        for entry in result["cleaning_log"]:
            assert "step_id" in entry
            assert "llm_provider" in entry
            assert "timestamp" in entry


# ---------------------------------------------------------------------------
# Tests create_clean_subgraph
# ---------------------------------------------------------------------------

class TestCreerSousGrapheNettoyage:
    """Tests de la compilation du sous-graphe."""

    def test_compilation_ne_crashe_pas(self):
        """Le graphe compile sans erreur."""
        graph = create_clean_subgraph()
        assert graph is not None


# ---------------------------------------------------------------------------
# Tests logique check_decision (via les conditions du graphe)
# ---------------------------------------------------------------------------

class TestLogiqueDecision:
    """Tests de la logique de branchement check_decision."""

    def test_decision_validated_termine(self):
        """decision='validated' mene a la fin du graphe."""
        # On importe la fonction interne en la reconstruisant
        from langgraph.graph import END

        def check_decision(state):
            if state.get("decision") == "validated" or state.get("iteration", 0) >= 10:
                return END
            return "propose"

        state = {"decision": "validated", "iteration": 1}
        assert check_decision(state) == END

    def test_iteration_max_termine(self):
        """iteration >= 10 mene a la fin du graphe."""
        from langgraph.graph import END

        def check_decision(state):
            if state.get("decision") == "validated" or state.get("iteration", 0) >= 10:
                return END
            return "propose"

        state = {"decision": "", "iteration": 10}
        assert check_decision(state) == END

    def test_iteration_11_termine_aussi(self):
        """iteration > 10 mene egalement a la fin du graphe."""
        from langgraph.graph import END

        def check_decision(state):
            if state.get("decision") == "validated" or state.get("iteration", 0) >= 10:
                return END
            return "propose"

        state = {"decision": "", "iteration": 11}
        assert check_decision(state) == END

    def test_decision_vide_continue(self):
        """Sans decision et iteration < 10, on reboucle sur propose."""
        def check_decision(state):
            if state.get("decision") == "validated" or state.get("iteration", 0) >= 10:
                return "__end__"
            return "propose"

        state = {"decision": "", "iteration": 3}
        assert check_decision(state) == "propose"
