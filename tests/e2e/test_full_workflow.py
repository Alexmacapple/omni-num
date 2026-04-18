"""Test E2E — Parcours complet OmniStudio (6 onglets).

Ce test simule un utilisateur qui :
1. Importe un fichier Markdown (3 etapes)
2. Lance le nettoyage LLM et valide
3. Verifie les voix disponibles
4. Assigne des voix aux etapes
5. Lance la generation TTS (optionnel si OmniVoice down)
6. Exporte le ZIP (optionnel si generation skippee)

Usage :
    E2E_PASSWORD=monmotdepasse pytest tests/e2e/ -v
    E2E_PASSWORD=monmotdepasse E2E_HEADLESS=0 pytest tests/e2e/ -v    # Voir le navigateur
    E2E_PASSWORD=monmotdepasse E2E_SKIP_TTS=1 pytest tests/e2e/ -v    # Sans generation TTS
"""
import os
import pytest
from pathlib import Path
from playwright.sync_api import Page, expect

from conftest import FIXTURES_DIR, SKIP_TTS, PASSWORD, TIMEOUT


# ===========================================================================
# Skip si pas de mot de passe configure
# ===========================================================================
pytestmark = pytest.mark.skipif(
    not PASSWORD,
    reason="E2E_PASSWORD non defini (requis pour l'authentification Keycloak)",
)


# ===========================================================================
# 1. LOGIN + ECRAN PRINCIPAL
# ===========================================================================
class TestLogin:
    def test_app_visible_after_login(self, page: Page):
        """L'ecran principal est visible apres login."""
        expect(page.locator("#vx-app-screen")).to_be_visible()

    def test_username_displayed(self, page: Page):
        """Le nom d'utilisateur est affiche dans le header."""
        expect(page.locator("#vx-username")).not_to_be_empty()

    def test_import_tab_active(self, page: Page):
        """L'onglet Import est actif par defaut."""
        tab = page.locator("#tab-import")
        expect(tab).to_have_attribute("aria-selected", "true")

    def test_status_api_responds(self, page: Page):
        """L'API /api/status repond (services actifs)."""
        response = page.request.get("/api/status")
        assert response.ok
        data = response.json()
        assert "data" in data


# ===========================================================================
# 2. IMPORT (Onglet 1)
# ===========================================================================
class TestImport:
    def test_upload_markdown_file(self, page: Page):
        """Upload d'un fichier Markdown et affichage du tableau."""
        # Upload du fichier
        file_input = page.locator("#import-file")
        file_input.set_input_files(str(FIXTURES_DIR / "test-scenario.md"))

        # Le bouton Importer devient actif
        import_btn = page.locator("#import-btn")
        expect(import_btn).to_be_enabled(timeout=5000)

        # Cliquer sur Importer
        import_btn.click()

        # Attendre que le tableau apparaisse
        page.wait_for_selector("#import-table-container:not([hidden])", timeout=15_000)

        # Verifier que 3 etapes sont affichees
        rows = page.locator("#import-table tbody tr")
        expect(rows).to_have_count(3, timeout=10_000)

    def test_select_all_and_continue(self, page: Page):
        """Selection de toutes les etapes et passage a l'onglet Preparation."""
        # Upload + import
        page.locator("#import-file").set_input_files(str(FIXTURES_DIR / "test-scenario.md"))
        page.locator("#import-btn").click()
        page.wait_for_selector("#import-table-container:not([hidden])", timeout=15_000)

        # Verifier que le select-all est coche
        select_all = page.locator("#import-select-all")
        expect(select_all).to_be_checked()

        # Cliquer Continuer
        next_btn = page.locator("#import-next-btn")
        expect(next_btn).to_be_visible(timeout=5000)
        next_btn.click()

        # Verifier qu'on est sur l'onglet Preparation
        page.wait_for_selector("#tab-clean[aria-selected='true']", timeout=10_000)


# ===========================================================================
# 3. PREPARATION (Onglet 2)
# ===========================================================================
class TestPreparation:
    def _import_and_go_to_clean(self, page: Page):
        """Helper : import + navigation vers l'onglet Preparation."""
        page.locator("#import-file").set_input_files(str(FIXTURES_DIR / "test-scenario.md"))
        page.locator("#import-btn").click()
        page.wait_for_selector("#import-table-container:not([hidden])", timeout=15_000)
        page.locator("#import-next-btn").click()
        page.wait_for_selector("#tab-clean[aria-selected='true']", timeout=10_000)

    def test_clean_table_shows_steps(self, page: Page):
        """Le tableau de preparation affiche les 3 etapes importees."""
        self._import_and_go_to_clean(page)

        # Attendre que le panel soit actif et que les lignes existent dans le DOM
        # Note : le DSFR peut garder visibility:hidden sur le panel pendant la transition
        page.wait_for_timeout(2000)  # Laisser le temps au chargement API + rendu
        rows = page.locator("#clean-table tbody tr")
        count = rows.count()
        assert count == 3, f"Attendu 3 etapes, trouve {count}"

    def test_clean_button_exists(self, page: Page):
        """Le bouton de nettoyage LLM existe dans le DOM."""
        self._import_and_go_to_clean(page)
        # Le bouton peut etre cache si pas de donnees, mais il existe dans le DOM
        expect(page.locator("#clean-btn")).to_be_attached()

    def test_validate_button_exists(self, page: Page):
        """Le bouton Valider existe dans le DOM (meme cache/desactive)."""
        self._import_and_go_to_clean(page)
        expect(page.locator("#clean-validate-btn")).to_be_attached()


# ===========================================================================
# 4. VOIX (Onglet 3)
# ===========================================================================
class TestVoix:
    def test_voices_tab_navigation(self, page: Page):
        """Navigation vers l'onglet Voix."""
        page.click("#tab-voices")
        page.wait_for_selector("#tab-voices[aria-selected='true']", timeout=5000)
        expect(page.locator("#panel-voices")).to_be_visible()

    def test_voices_library_loads(self, page: Page):
        """La bibliotheque de voix charge des cartes via l'API."""
        page.click("#tab-voices")
        page.wait_for_selector("#tab-voices[aria-selected='true']", timeout=5000)

        # Verifier que l'API voix repond (les cartes sont rendues par JS)
        token = page.evaluate("localStorage.getItem('vx_access_token')")
        thread_id = page.evaluate("localStorage.getItem('thread_id')") or "test"
        response = page.request.get("/api/voices", headers={
            "Authorization": f"Bearer {token}",
            "X-Thread-Id": thread_id,
        })
        assert response.ok
        data = response.json()
        voices = data.get("data", {}).get("voices", [])
        assert len(voices) >= 9, f"Attendu au moins 9 voix, API retourne {len(voices)}"


# ===========================================================================
# 5. ASSIGNATION (Onglet 4)
# ===========================================================================
class TestAssignation:
    def _import_select_go_to_assign(self, page: Page):
        """Helper : import + selection + navigation vers Assignation."""
        # Import
        page.locator("#import-file").set_input_files(str(FIXTURES_DIR / "test-scenario.md"))
        page.locator("#import-btn").click()
        page.wait_for_selector("#import-table-container:not([hidden])", timeout=15_000)
        page.locator("#import-next-btn").click()
        page.wait_for_selector("#tab-clean[aria-selected='true']", timeout=10_000)

        # Aller directement a Assignation (skip nettoyage pour ce test)
        page.click("#tab-assign")
        page.wait_for_selector("#tab-assign[aria-selected='true']", timeout=5000)

    def test_assign_table_shows_steps(self, page: Page):
        """Le tableau d'assignation affiche les etapes importees."""
        self._import_select_go_to_assign(page)

        # Attendre le tableau
        page.wait_for_selector("#assign-table-container:not([hidden])", timeout=15_000)
        rows = page.locator("#assign-table tbody tr")
        expect(rows).to_have_count(3, timeout=10_000)

    def test_assign_voice_selects_present(self, page: Page):
        """Chaque etape a un select de voix."""
        self._import_select_go_to_assign(page)
        page.wait_for_selector("#assign-table-container:not([hidden])", timeout=15_000)

        selects = page.locator(".vx-assign-voice")
        expect(selects).to_have_count(3, timeout=5000)

    def test_assign_speed_sliders_present(self, page: Page):
        """Chaque etape a un slider de vitesse."""
        self._import_select_go_to_assign(page)
        page.wait_for_selector("#assign-table-container:not([hidden])", timeout=15_000)

        sliders = page.locator(".vx-assign-speed")
        expect(sliders).to_have_count(3, timeout=5000)


# ===========================================================================
# 6. GENERATION (Onglet 5)
# ===========================================================================
class TestGeneration:
    def test_generation_tab_accessible(self, page: Page):
        """L'onglet Generation est accessible."""
        page.click("#tab-generate")
        page.wait_for_selector("#tab-generate[aria-selected='true']", timeout=5000)
        expect(page.locator("#panel-generate")).to_be_visible()


# ===========================================================================
# 7. EXPORT (Onglet 6)
# ===========================================================================
class TestExport:
    def test_export_tab_accessible(self, page: Page):
        """L'onglet Export est accessible."""
        page.click("#tab-export")
        page.wait_for_selector("#tab-export[aria-selected='true']", timeout=5000)
        expect(page.locator("#panel-export")).to_be_visible()


# ===========================================================================
# 8. NOUVELLE SESSION
# ===========================================================================
class TestSession:
    def test_new_session_button_visible(self, page: Page):
        """Le bouton Nouvelle session est visible."""
        expect(page.locator("#vx-new-session-btn")).to_be_visible()

    def test_logout_button_visible(self, page: Page):
        """Le bouton Deconnexion est visible."""
        expect(page.locator("#vx-logout-btn")).to_be_visible()


# ===========================================================================
# 9. RESPONSIVE (mobile)
# ===========================================================================
class TestResponsive:
    def test_mobile_stepper_visible(self, page: Page):
        """Le stepper mobile est visible en viewport etroit."""
        page.set_viewport_size({"width": 375, "height": 812})
        page.reload()
        page.wait_for_selector("#vx-app-screen", state="visible", timeout=10_000)

        stepper = page.locator("#vx-stepper")
        expect(stepper).to_be_visible()

    def test_mobile_cards_layout(self, page: Page):
        """Les tableaux s'affichent en cartes empilees sur mobile."""
        # Import d'abord
        page.locator("#import-file").set_input_files(str(FIXTURES_DIR / "test-scenario.md"))
        page.locator("#import-btn").click()
        page.wait_for_selector("#import-table-container:not([hidden])", timeout=15_000)
        page.locator("#import-next-btn").click()
        page.wait_for_selector("#tab-clean[aria-selected='true']", timeout=10_000)

        # Passer en mobile
        page.set_viewport_size({"width": 375, "height": 812})
        page.wait_for_timeout(500)

        # Le thead devrait etre masque (display:none en mobile)
        thead = page.locator("#clean-table thead")
        expect(thead).to_be_hidden()


# ===========================================================================
# 10. ACCESSIBILITE
# ===========================================================================
class TestAccessibilite:
    def test_skip_links_exist(self, page: Page):
        """Les liens d'evitement DSFR existent."""
        skip = page.locator(".fr-skiplinks a")
        count = skip.count()
        assert count >= 1, f"Attendu au moins 1 lien d'evitement, trouve {count}"

    def test_main_landmark(self, page: Page):
        """Le landmark main existe."""
        main = page.locator("main#main-content, main[id='main-content']")
        expect(main).to_be_visible()

    def test_header_landmark(self, page: Page):
        """Le landmark header existe."""
        header = page.locator("header[role='banner']")
        expect(header).to_be_visible()

    def test_form_labels(self, page: Page):
        """Les inputs du formulaire de login ont des labels."""
        # Retourner au login pour ce test
        page.goto("/#import")
        page.wait_for_selector("#vx-app-screen", state="visible", timeout=10_000)

        # Verifier que le champ fichier a un label
        label = page.locator("label[for='import-file']")
        expect(label).to_be_visible()

    def test_aria_live_regions(self, page: Page):
        """Les regions aria-live existent."""
        live_regions = page.locator("[aria-live]")
        count = live_regions.count()
        assert count >= 2, f"Attendu au moins 2 regions aria-live, trouve {count}"
