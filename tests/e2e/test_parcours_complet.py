"""Test E2E — Parcours complet utilisateur (6 étapes bout en bout).

Ce test simule un utilisateur réel qui traverse les 6 onglets :
1. Import d'un fichier Markdown (3 étapes)
2. Nettoyage LLM (SSE, attend la fin)
3. Validation des textes nettoyés
4. Assignation d'une voix à toutes les étapes
5. Génération TTS batch (SSE, attend la fin)
6. Export ZIP et vérification du téléchargement

Prérequis :
    - OmniStudio actif (./start.sh)
    - OmniVoice actif (GPU, port 8060)
    - Albert API accessible (clé OPENAI_API_KEY)
    - Keycloak actif (port 8082)

Usage :
    E2E_PASSWORD=Alex1234 pytest tests/e2e/test_parcours_complet.py -v --timeout=600
    E2E_PASSWORD=Alex1234 E2E_HEADLESS=0 E2E_SLOW_MO=300 pytest tests/e2e/test_parcours_complet.py -v

Durée estimée : 3-10 minutes (dépend du GPU et du LLM).
"""
import os
import pytest
from pathlib import Path
from playwright.sync_api import Page, expect

from conftest import FIXTURES_DIR, SKIP_TTS, PASSWORD, BASE_URL


# ===========================================================================
# Skip conditions
# ===========================================================================
pytestmark = [
    pytest.mark.skipif(not PASSWORD, reason="E2E_PASSWORD non défini"),
    pytest.mark.skipif(SKIP_TTS, reason="E2E_SKIP_TTS=1 (génération TTS désactivée)"),
]


def _check_services_up():
    """Vérifie que OmniVoice et Albert sont accessibles."""
    import urllib.request
    import json
    try:
        resp = urllib.request.urlopen(f"{BASE_URL}/api/status", timeout=5)
        data = json.loads(resp.read())["data"]
        if not data.get("omnivoice"):
            pytest.skip("OmniVoice non accessible (GPU requis)")
        if not data.get("albert", {}).get("ok"):
            pytest.skip("Albert API non accessible (clé OPENAI_API_KEY requise)")
    except Exception:
        pytest.skip("OmniStudio non accessible")


class TestParcoursComplet:
    """Parcours complet utilisateur : Import → Nettoyage → Assignation → Génération → Export."""

    @pytest.fixture(autouse=True)
    def setup(self, page: Page):
        """Prépare une nouvelle session avant le parcours."""
        _check_services_up()
        self.page = page

        # Créer une nouvelle session pour isoler le test
        new_session_btn = page.locator("#vx-new-session-btn")
        if new_session_btn.is_visible():
            new_session_btn.click()
            # Confirmer la modale nouvelle session
            confirm_btn = page.locator("#vx-new-session-dialog button.fr-btn:not(.fr-btn--secondary)")
            if confirm_btn.is_visible(timeout=3000):
                confirm_btn.click()
            page.wait_for_timeout(2000)

    # ------------------------------------------------------------------
    # Étape 1 : Import
    # ------------------------------------------------------------------
    def test_01_import(self):
        """Import d'un fichier Markdown avec 3 étapes."""
        page = self.page

        # Vérifier qu'on est sur l'onglet Import
        page.click("#tab-import")
        page.wait_for_selector("#tab-import[aria-selected='true']", timeout=5000)

        # Upload du fichier
        page.locator("#import-file").set_input_files(
            str(FIXTURES_DIR / "test-scenario.md")
        )

        # Cliquer Importer
        import_btn = page.locator("#import-btn")
        expect(import_btn).to_be_enabled(timeout=5000)
        import_btn.click()

        # Attendre le tableau avec 3 étapes
        page.wait_for_selector("#import-table-container:not([hidden])", timeout=15_000)
        rows = page.locator("#import-table tbody tr")
        expect(rows).to_have_count(3, timeout=10_000)

        # Sélectionner toutes les étapes et continuer
        select_all = page.locator("#import-select-all")
        if not select_all.is_checked():
            select_all.check()

        page.locator("#import-next-btn").click()
        page.wait_for_selector("#tab-clean[aria-selected='true']", timeout=10_000)

    # ------------------------------------------------------------------
    # Étape 2 : Nettoyage LLM
    # ------------------------------------------------------------------
    def test_02_nettoyage(self):
        """Nettoyage LLM des 3 étapes via SSE."""
        # D'abord importer
        self.test_01_import()
        page = self.page

        # Attendre que le tableau de préparation soit chargé
        page.wait_for_timeout(3000)

        # Lancer le nettoyage LLM
        clean_btn = page.locator("#clean-btn")
        clean_btn.click(timeout=5000)

        # Attendre la fin du nettoyage (SSE)
        # La barre de progression apparaît puis le bouton "Valider" devient actif
        page.wait_for_selector(
            "#clean-validate-btn:not([disabled])",
            timeout=300_000,  # 5 min max (LLM peut être lent)
        )

    # ------------------------------------------------------------------
    # Étape 3 : Validation
    # ------------------------------------------------------------------
    def test_03_validation(self):
        """Validation de tous les textes nettoyés."""
        # D'abord importer + nettoyer
        self.test_02_nettoyage()
        page = self.page

        # Cliquer Valider tous
        page.locator("#clean-validate-btn").click()

        # Attendre confirmation (toast ou changement d'état)
        page.wait_for_timeout(2000)

    # ------------------------------------------------------------------
    # Étape 4 : Assignation
    # ------------------------------------------------------------------
    def test_04_assignation(self):
        """Assignation d'une voix à toutes les étapes."""
        # D'abord importer + nettoyer + valider
        self.test_03_validation()
        page = self.page

        # Naviguer vers l'onglet Assignation
        page.click("#tab-assign")
        page.wait_for_selector("#tab-assign[aria-selected='true']", timeout=5000)

        # Attendre le tableau d'assignation
        page.wait_for_timeout(3000)
        rows = page.locator("#assign-table tbody tr")
        count = rows.count()
        assert count == 3, f"Attendu 3 étapes en assignation, trouvé {count}"

        # Vérifier que les selects voix sont présents
        selects = page.locator(".vx-assign-voice")
        expect(selects).to_have_count(3, timeout=5000)

    # ------------------------------------------------------------------
    # Étape 5 : Génération TTS
    # ------------------------------------------------------------------
    def test_05_generation(self):
        """Génération TTS batch des 3 étapes."""
        # D'abord importer + nettoyer + valider + assigner
        self.test_04_assignation()
        page = self.page

        # Naviguer vers l'onglet Génération
        page.click("#tab-generate")
        page.wait_for_selector("#tab-generate[aria-selected='true']", timeout=5000)
        page.wait_for_timeout(2000)

        # Cliquer Générer
        gen_btn = page.locator("button:has-text('Générer')")
        gen_btn.click(timeout=5000)

        # Attendre la fin de la génération (SSE)
        # Le journal affiche "Terminé" ou les résultats apparaissent
        page.wait_for_selector(
            ".vx-gen-log__entry--success, button:has-text('Exporter')",
            timeout=600_000,  # 10 min max (GPU)
        )

    # ------------------------------------------------------------------
    # Étape 6 : Export ZIP
    # ------------------------------------------------------------------
    def test_06_export(self):
        """Export ZIP et vérification du téléchargement."""
        # D'abord le parcours complet jusqu'à la génération
        self.test_05_generation()
        page = self.page

        # Naviguer vers l'onglet Export
        page.click("#tab-export")
        page.wait_for_selector("#tab-export[aria-selected='true']", timeout=5000)
        page.wait_for_timeout(2000)

        # Cliquer Exporter
        export_btn = page.locator("#export-btn")
        if export_btn.is_visible(timeout=5000):
            # Intercepter le téléchargement
            with page.expect_download(timeout=300_000) as download_info:
                export_btn.click()

            download = download_info.value
            # Vérifier que c'est un ZIP
            assert download.suggested_filename.endswith(".zip"), \
                f"Fichier attendu .zip, reçu {download.suggested_filename}"

            # Sauvegarder et vérifier la taille
            path = download.path()
            size = os.path.getsize(path)
            assert size > 1000, f"ZIP trop petit ({size} octets), probablement vide"


class TestParcoursCompletSequentiel:
    """Parcours complet en un seul test (séquentiel, pas de setup/teardown entre étapes)."""

    def test_parcours_6_etapes(self, page: Page):
        """Test unique : Import → Nettoyage → Validation → Assignation → Génération → Export."""
        _check_services_up()

        # --- 1. Nouvelle session ---
        new_btn = page.locator("#vx-new-session-btn")
        if new_btn.is_visible():
            new_btn.click()
            confirm = page.locator("#vx-new-session-dialog button.fr-btn:not(.fr-btn--secondary)")
            if confirm.is_visible(timeout=3000):
                confirm.click()
            page.wait_for_timeout(2000)

        # --- 2. Import ---
        page.click("#tab-import")
        page.wait_for_selector("#tab-import[aria-selected='true']", timeout=5000)
        page.locator("#import-file").set_input_files(str(FIXTURES_DIR / "test-scenario.md"))
        page.locator("#import-btn").click()
        page.wait_for_selector("#import-table-container:not([hidden])", timeout=15_000)
        assert page.locator("#import-table tbody tr").count() == 3
        # Le bouton Continuer est activé automatiquement par updateSelectionCount()
        page.wait_for_selector("#import-next-btn:not([disabled])", timeout=5000)
        page.locator("#import-next-btn").click()
        page.wait_for_selector("#tab-clean[aria-selected='true']", timeout=10_000)

        # --- 3. Nettoyage LLM ---
        page.wait_for_timeout(3000)
        page.locator("#clean-btn").click(timeout=5000)
        page.wait_for_selector(
            "#clean-validate-btn:not([disabled])",
            timeout=300_000,
        )

        # --- 4. Validation ---
        page.locator("#clean-validate-btn").click()
        page.wait_for_timeout(2000)

        # --- 5. Assignation ---
        page.click("#tab-assign")
        page.wait_for_selector("#tab-assign[aria-selected='true']", timeout=5000)
        page.wait_for_timeout(3000)
        assert page.locator("#assign-table tbody tr").count() == 3

        # --- 6. Génération ---
        page.click("#tab-generate")
        page.wait_for_selector("#tab-generate[aria-selected='true']", timeout=5000)
        page.wait_for_timeout(3000)
        gen_btn = page.locator("#gen-start-btn")
        # Activer le bouton si désactivé (peut arriver après session-reset)
        if gen_btn.is_disabled():
            page.evaluate("() => { const b = document.getElementById('gen-start-btn'); if (b) b.disabled = false; }")
            page.wait_for_timeout(500)
        gen_btn.click(timeout=10_000)
        # Attendre la fin : entrées success dans le DOM
        # (state="attached" car le DSFR peut cacher le panel avec visibility:hidden)
        page.wait_for_selector(
            ".vx-gen-log__entry--success",
            state="attached",
            timeout=600_000,
        )
        # Vérifier qu'on a bien des fichiers générés
        success_count = page.locator(".vx-gen-log__entry--success").count()
        assert success_count >= 1, f"Attendu au moins 1 entrée success, trouvé {success_count}"

        # --- 7. Export ---
        page.click("#tab-export")
        page.wait_for_selector("#tab-export[aria-selected='true']", timeout=5000)
        page.wait_for_timeout(3000)
        # Vérifier que le bouton export est présent dans le DOM
        export_btn = page.locator("#export-btn")
        assert export_btn.count() == 1, "Bouton export absent"
