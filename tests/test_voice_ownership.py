"""Tests isolation multi-user des voix custom — Phase 2 rouges.

Spécification : PRD-MIGRATION-001 v1.5 décision 7 (traite PRD-032).
Code cible :
- omnistudio/core/schemas.py (enrichir avec owner, system)
- omnistudio/dependencies.py::check_voice_ownership
- omnistudio/routers/voices.py (filtrage + scope)

Règles :
- GET /api/voices filtre : owner == JWT.sub OR system == true
- POST /voices/custom injecte owner = JWT.sub, system = false
- DELETE, PATCH, rename vérifient owner == JWT.sub (403 sinon)
- Voix system: true ne sont jamais supprimables
- Export scope owner, Import force owner = user.sub
"""
import pytest


ALEX_SUB = "f3a8b9c1-2d4e-5f67-89a0-b1c2d3e4f5a6"
BOB_SUB = "c2b7d9e1-5f8a-4b3c-9d0e-1f2a3b4c5d6e"


@pytest.fixture
def meta_alex():
    return {
        "name": "MaVoixAlex",
        "owner": ALEX_SUB,
        "system": False,
        "description": "Voix perso Alex",
        "source": "design",
        "instruct": "female, young adult, high pitch",
        "language": "fr",
    }


@pytest.fixture
def meta_bob():
    return {"name": "VoixDeBob", "owner": BOB_SUB, "system": False,
            "description": "Voix Bob", "source": "clone", "language": "fr"}


@pytest.fixture
def meta_marianne_system():
    return {
        "name": "Marianne",
        "owner": None,
        "system": True,
        "description": "Voix féminine posée, chaleureuse et nette",
        "source": "design",
        "instruct": "female, middle-aged, moderate pitch, warm and clear",
        "language": "fr",
    }


class TestSchemaOwner:
    def test_owner_requis_si_non_system(self, meta_alex):
        from core.schemas import VoiceMeta
        VoiceMeta(**meta_alex)  # ne lève pas

    def test_system_true_n_exige_pas_owner(self, meta_marianne_system):
        from core.schemas import VoiceMeta
        VoiceMeta(**meta_marianne_system)

    def test_owner_vide_et_non_system_rejete(self):
        from core.schemas import VoiceMeta
        with pytest.raises(ValueError):
            VoiceMeta(name="X", owner=None, system=False, source="design",
                      language="fr", description="")


class TestFiltrageGetVoices:
    def test_alex_voit_ses_voix_plus_systeme(self, meta_alex, meta_bob, meta_marianne_system):
        from dependencies import filter_voices_for_user
        all_voices = [meta_alex, meta_bob, meta_marianne_system]
        visible = filter_voices_for_user(all_voices, ALEX_SUB)
        names = {v["name"] for v in visible}
        assert "MaVoixAlex" in names
        assert "Marianne" in names
        assert "VoixDeBob" not in names

    def test_bob_voit_ses_voix_plus_systeme(self, meta_alex, meta_bob, meta_marianne_system):
        from dependencies import filter_voices_for_user
        visible = filter_voices_for_user([meta_alex, meta_bob, meta_marianne_system], BOB_SUB)
        names = {v["name"] for v in visible}
        assert "VoixDeBob" in names
        assert "Marianne" in names
        assert "MaVoixAlex" not in names


class TestCheckVoiceOwnership:
    def test_alex_peut_modifier_sa_voix(self, meta_alex):
        from dependencies import check_voice_ownership
        assert check_voice_ownership(meta_alex, ALEX_SUB) is True

    def test_alex_ne_peut_pas_modifier_voix_bob(self, meta_bob):
        from dependencies import check_voice_ownership
        assert check_voice_ownership(meta_bob, ALEX_SUB) is False

    def test_nul_ne_peut_modifier_voix_system(self, meta_marianne_system):
        from dependencies import check_voice_ownership
        assert check_voice_ownership(meta_marianne_system, ALEX_SUB) is False
        assert check_voice_ownership(meta_marianne_system, BOB_SUB) is False


class TestRoutesDELETE:
    """403 si l'utilisateur n'est pas owner."""

    def test_delete_voix_alex_par_bob_403(self):
        """Route : DELETE /api/voices/MaVoixAlex appelée par Bob → 403."""
        # Test d'intégration avec client HTTP (à compléter Phase 3)
        pytest.skip("Intégration FastAPI — Phase 3")

    def test_delete_voix_system_toujours_403(self):
        """DELETE /api/voices/Marianne (system: true) → 403 quel que soit l'user."""
        pytest.skip("Intégration FastAPI — Phase 3")


class TestExportImportScope:
    def test_export_scope_uniquement_mes_voix(self):
        """Export d'Alex contient MaVoixAlex + 6 voix système, pas celles de Bob."""
        pytest.skip("Intégration FastAPI — Phase 3")

    def test_import_force_owner_du_user(self):
        """ZIP contenant owner=Bob, importé par Alex → owner réécrit à Alex.sub."""
        pytest.skip("Intégration FastAPI — Phase 3")


class TestInjectionAutomatique:
    def test_post_voices_custom_injecte_owner_jwt_sub(self):
        """POST /api/voices/custom : user.sub est injecté comme owner."""
        pytest.skip("Intégration FastAPI — Phase 3")
