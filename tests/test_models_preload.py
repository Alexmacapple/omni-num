"""Tests préchargement modèle au démarrage — Phase 2 rouges.

Spécification : PRD v1.5 décision 17.
"""
import pytest


class TestPreloadStartSh:
    def test_start_sh_appelle_models_preload_apres_omnivoice_up(self):
        """start.sh fait `curl -X POST localhost:8070/models/preload` après OmniVoice up."""
        pytest.skip("Test shell — à vérifier via intégration — Phase 6")

    def test_env_var_omnistudio_preload_model_true_defaut(self):
        """OMNISTUDIO_PRELOAD_MODEL=true par défaut, false désactive le preload."""
        pytest.skip("Test shell — Phase 6")


class TestLatencePremiereRequete:
    def test_premiere_requete_preset_sous_3s_apres_boot(self):
        """Critère validation #21 : première requête preset < 3 s après preload."""
        pytest.skip("Test d'intégration start.sh — Phase 8")


class TestPreloadEnArrierePlan:
    def test_preload_n_empeche_pas_omnistudio_de_demarrer(self):
        """Le preload ne doit pas bloquer le démarrage d'omnistudio (risque #17)."""
        pytest.skip("Test shell — Phase 6")
