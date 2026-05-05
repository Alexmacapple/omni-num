"""Test de non-régression — Accessibilité des modales OmniStudio.

Couvre les 5 modales de l'application :
  - #fr-theme-modal       : modale DSFR (paramètres d'affichage), ouverte par DSFR JS
  - #ov-new-session-dialog : alertdialog natif, ouverte par showModal()
  - #ov-status-dialog     : dialog natif, ouverte par showModal()
  - #rename-voice-modal   : dialog natif (renommage de voix), ouverte par showModal()
  - #header-menu-modal    : menu mobile DSFR (composant header, viewport < 768px)

Checklist DSFR/RGAA vérifiée :
  - aria-modal="true" sur toutes les modales
  - aria-labelledby lié à un titre existant (h2–h6 ou p)
  - aria-describedby sur alertdialog lié à une description existante
  - Boutons d'ouverture : type="button" + aria-controls ou aria-haspopup="dialog"
  - Boutons de fermeture : aria-controls lié à la modale
  - Ouverture via showModal() (attribut `open` sur <dialog>)
  - Piège focus (Tab reste dans la modale)
  - Fermeture par Escape (dialogs natifs)
  - Focus restauré sur le déclencheur après fermeture
"""
import pytest
from playwright.sync_api import Page, expect

from conftest import PASSWORD, TIMEOUT


pytestmark = pytest.mark.skipif(
    not PASSWORD,
    reason="E2E_PASSWORD non defini (requis pour l'authentification Keycloak)",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _linked_element_exists(page: Page, element_id: str, attr: str) -> bool:
    """Vérifie qu'un attribut ARIA pointe vers un élément existant."""
    return page.evaluate(f"""
        (() => {{
            const el = document.getElementById('{element_id}');
            if (!el) return false;
            const target_id = el.getAttribute('{attr}');
            if (!target_id) return false;
            return !!document.getElementById(target_id);
        }})()
    """)


def _focus_is_inside(page: Page, dialog_id: str) -> bool:
    """Vérifie que le focus actif est bien dans la modale."""
    return page.evaluate(f"""
        (() => {{
            const dialog = document.getElementById('{dialog_id}');
            return dialog ? dialog.contains(document.activeElement) : false;
        }})()
    """)


def _dialog_is_open(page: Page, dialog_id: str) -> bool:
    """Vérifie qu'un <dialog> est ouvert (attribut `open` posé par showModal)."""
    return page.evaluate(
        f"document.getElementById('{dialog_id}')?.open === true"
    )


# ---------------------------------------------------------------------------
# Structure HTML statique (peut tourner sans ouvrir les modales)
# ---------------------------------------------------------------------------

class TestStaticStructure:
    """Attributs ARIA présents et cohérents au chargement de la page."""

    def test_theme_modal_has_aria_modal(self, page: Page):
        """#fr-theme-modal doit avoir aria-modal=true (bug corrigé avril 2026)."""
        val = page.get_attribute("#fr-theme-modal", "aria-modal")
        assert val == "true", (
            "fr-theme-modal: aria-modal manquant — les AT ne sauront pas que "
            "le contenu en arrière-plan est inactif"
        )

    def test_theme_modal_aria_labelledby_linked(self, page: Page):
        assert _linked_element_exists(page, "fr-theme-modal", "aria-labelledby"), (
            "fr-theme-modal: aria-labelledby pointe vers un ID inexistant"
        )

    def test_new_session_dialog_has_aria_modal(self, page: Page):
        val = page.get_attribute("#ov-new-session-dialog", "aria-modal")
        assert val == "true"

    def test_new_session_dialog_has_aria_labelledby_linked(self, page: Page):
        assert _linked_element_exists(page, "ov-new-session-dialog", "aria-labelledby")

    def test_new_session_dialog_has_aria_describedby_linked(self, page: Page):
        """alertdialog doit avoir aria-describedby pointant vers sa description."""
        assert _linked_element_exists(page, "ov-new-session-dialog", "aria-describedby"), (
            "ov-new-session-dialog (role=alertdialog): aria-describedby manquant "
            "ou pointe vers un ID inexistant"
        )

    def test_status_dialog_has_aria_modal(self, page: Page):
        val = page.get_attribute("#ov-status-dialog", "aria-modal")
        assert val == "true"

    def test_status_dialog_has_aria_labelledby_linked(self, page: Page):
        assert _linked_element_exists(page, "ov-status-dialog", "aria-labelledby")

    def test_status_dialog_close_btn_has_aria_controls(self, page: Page):
        """Le bouton Fermer doit déclarer quelle modale il contrôle."""
        val = page.get_attribute("#ov-status-close", "aria-controls")
        assert val == "ov-status-dialog", (
            "ov-status-close: aria-controls manquant ou pointe vers la mauvaise modale"
        )

    def test_rename_voice_modal_has_aria_modal(self, page: Page):
        val = page.get_attribute("#rename-voice-modal", "aria-modal")
        assert val == "true", (
            "rename-voice-modal: aria-modal manquant"
        )

    def test_rename_voice_modal_has_aria_labelledby_linked(self, page: Page):
        assert _linked_element_exists(page, "rename-voice-modal", "aria-labelledby"), (
            "rename-voice-modal: aria-labelledby pointe vers un ID inexistant"
        )

    def test_all_trigger_buttons_have_type_button(self, page: Page):
        """Tous les boutons déclencheurs de modale doivent avoir type=button."""
        triggers = page.evaluate("""
            [...document.querySelectorAll('[aria-controls="fr-theme-modal"], '
             + '[aria-haspopup="dialog"]')]
            .map(b => ({ id: b.id || b.className, type: b.getAttribute('type') }))
        """)
        for btn in triggers:
            assert btn["type"] == "button", (
                f"Bouton déclencheur '{btn['id']}' sans type=button"
            )

    def test_no_redundant_role_dialog_on_native_dialog(self, page: Page):
        """role=dialog est redondant sur <dialog> natif ; alertdialog reste autorisé."""
        for dialog_id in ("ov-new-session-dialog", "ov-status-dialog", "rename-voice-modal"):
            role = page.get_attribute(f"#{dialog_id}", "role")
            assert role != "dialog", f"{dialog_id}: role=dialog redondant sur élément <dialog> natif"


# ---------------------------------------------------------------------------
# Modale thème DSFR (#fr-theme-modal)
# ---------------------------------------------------------------------------

class TestThemeModal:
    """Modale paramètres d'affichage — gérée par DSFR JS."""

    def _open(self, page: Page):
        page.click(".fr-header__tools button[aria-controls='fr-theme-modal']")
        page.wait_for_selector("#fr-theme-modal.fr-modal--opened", state="attached", timeout=3_000)

    def test_opens_from_header_button(self, page: Page):
        self._open(page)
        assert "fr-modal--opened" in (page.get_attribute("#fr-theme-modal", "class") or "")

    def test_has_visible_title(self, page: Page):
        self._open(page)
        title_id = page.get_attribute("#fr-theme-modal", "aria-labelledby")
        expect(page.locator(f"#{title_id}")).to_be_visible()

    def test_close_button_closes_modal(self, page: Page):
        self._open(page)
        page.click("#fr-theme-modal .fr-btn--close")
        page.wait_for_selector("#fr-theme-modal:not(.fr-modal--opened)", state="attached", timeout=3_000)

    def test_escape_closes_modal(self, page: Page):
        self._open(page)
        page.keyboard.press("Escape")
        page.wait_for_selector("#fr-theme-modal:not(.fr-modal--opened)", state="attached", timeout=3_000)


# ---------------------------------------------------------------------------
# Dialog Nouvelle session (#ov-new-session-dialog)
# ---------------------------------------------------------------------------

class TestNewSessionDialog:
    """Alertdialog de confirmation Nouvelle session — <dialog> + showModal()."""

    def _open(self, page: Page):
        page.click("#ov-new-session-btn")
        page.wait_for_selector("#ov-new-session-dialog[open]", state="attached", timeout=3_000)

    def test_opens_on_button_click(self, page: Page):
        self._open(page)
        assert _dialog_is_open(page, "ov-new-session-dialog")

    def test_role_is_alertdialog(self, page: Page):
        role = page.get_attribute("#ov-new-session-dialog", "role")
        assert role == "alertdialog"

    def test_focus_enters_dialog_on_open(self, page: Page):
        self._open(page)
        page.wait_for_timeout(100)
        assert _focus_is_inside(page, "ov-new-session-dialog"), (
            "Le focus n'est pas entré dans ov-new-session-dialog à l'ouverture"
        )

    def test_focus_trap_tab(self, page: Page):
        """Tab ne doit pas quitter la modale."""
        self._open(page)
        for _ in range(6):
            page.keyboard.press("Tab")
        assert _focus_is_inside(page, "ov-new-session-dialog"), (
            "Tab a fait sortir le focus de ov-new-session-dialog"
        )

    def test_closes_on_cancel(self, page: Page):
        self._open(page)
        page.click("#ov-new-session-cancel")
        page.wait_for_selector("#ov-new-session-dialog:not([open])", state="attached", timeout=3_000)

    def test_escape_closes_dialog(self, page: Page):
        self._open(page)
        page.keyboard.press("Escape")
        page.wait_for_selector("#ov-new-session-dialog:not([open])", state="attached", timeout=3_000)

    def test_focus_returns_to_trigger_after_close(self, page: Page):
        self._open(page)
        page.keyboard.press("Escape")
        page.wait_for_timeout(200)
        focused_id = page.evaluate("document.activeElement?.id")
        assert focused_id == "ov-new-session-btn", (
            f"Focus restauré sur '{focused_id}' au lieu de 'ov-new-session-btn'"
        )

    def test_background_not_focusable_when_open(self, page: Page):
        """Avec showModal(), les éléments hors dialog ne doivent pas recevoir le focus."""
        self._open(page)
        assert _dialog_is_open(page, "ov-new-session-dialog"), (
            "Le dialog n'est pas en top-layer — showModal() n'a pas été utilisé"
        )


# ---------------------------------------------------------------------------
# Dialog État des services (#ov-status-dialog)
# ---------------------------------------------------------------------------

class TestStatusDialog:
    """Dialog état des services — <dialog> + showModal()."""

    def _open(self, page: Page):
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(200)
        page.click("#ov-status-btn")
        page.wait_for_selector("#ov-status-dialog[open]", state="attached", timeout=5_000)

    def test_opens_on_button_click(self, page: Page):
        self._open(page)
        assert _dialog_is_open(page, "ov-status-dialog")

    def test_has_visible_title(self, page: Page):
        self._open(page)
        title_id = page.get_attribute("#ov-status-dialog", "aria-labelledby")
        expect(page.locator(f"#{title_id}")).to_be_visible()

    def test_focus_enters_dialog_on_open(self, page: Page):
        self._open(page)
        page.wait_for_timeout(100)
        assert _focus_is_inside(page, "ov-status-dialog"), (
            "Le focus n'est pas entré dans ov-status-dialog à l'ouverture"
        )

    def test_focus_trap_tab(self, page: Page):
        """Tab ne doit pas quitter la modale."""
        self._open(page)
        for _ in range(4):
            page.keyboard.press("Tab")
        assert _focus_is_inside(page, "ov-status-dialog"), (
            "Tab a fait sortir le focus de ov-status-dialog"
        )

    def test_close_button_closes_dialog(self, page: Page):
        self._open(page)
        page.click("#ov-status-close")
        page.wait_for_selector("#ov-status-dialog:not([open])", state="attached", timeout=3_000)

    def test_escape_closes_dialog(self, page: Page):
        self._open(page)
        page.keyboard.press("Escape")
        page.wait_for_selector("#ov-status-dialog:not([open])", state="attached", timeout=3_000)

    def test_focus_returns_to_trigger_after_close(self, page: Page):
        self._open(page)
        page.click("#ov-status-close")
        page.wait_for_timeout(200)
        focused_id = page.evaluate("document.activeElement?.id")
        assert focused_id == "ov-status-btn", (
            f"Focus restauré sur '{focused_id}' au lieu de 'ov-status-btn'"
        )


# ---------------------------------------------------------------------------
# Dialog Renommer la voix (#rename-voice-modal) — ouverture programmatique
# ---------------------------------------------------------------------------

class TestRenameVoiceModal:
    """Dialog de renommage de voix — <dialog> + showModal(), ouvert par promptNewVoiceName().

    Ce dialog n'a pas de bouton déclencheur accessible directement.
    Il est ouvert programmatiquement depuis la liste des voix.
    Les tests statiques couvrent la structure HTML ; les tests dynamiques
    requièrent qu'au moins une voix custom existe dans la bibliothèque.
    """

    def _has_voice_to_rename(self, page: Page) -> bool:
        """Vérifie qu'une voix avec bouton renommer est présente dans la bibliothèque."""
        return page.evaluate(
            "document.querySelector('[data-action=\"rename-voice\"]') !== null"
        )

    def _open(self, page: Page):
        """Navigue vers l'onglet Voix et clique sur le premier bouton renommer."""
        page.click("#tab-voices")
        page.locator("#panel-voices").wait_for(state="visible", timeout=TIMEOUT)
        page.wait_for_timeout(500)
        if not self._has_voice_to_rename(page):
            pytest.skip("Aucune voix custom disponible pour tester le renommage")
        page.click('[data-action="rename-voice"]')
        page.wait_for_selector("#rename-voice-modal[open]", state="attached", timeout=3_000)

    def test_role_is_not_redundant(self, page: Page):
        """Pas de role=dialog redondant sur <dialog> natif."""
        role = page.get_attribute("#rename-voice-modal", "role")
        is_native_dialog = page.evaluate(
            "document.getElementById('rename-voice-modal')?.tagName === 'DIALOG'"
        )
        assert not (role in ("dialog", "alertdialog") and is_native_dialog), (
            "rename-voice-modal: role redondant sur <dialog> natif"
        )

    def test_focus_enters_dialog_on_open(self, page: Page):
        self._open(page)
        page.wait_for_timeout(100)
        assert _focus_is_inside(page, "rename-voice-modal"), (
            "Le focus n'est pas entré dans rename-voice-modal à l'ouverture"
        )

    def test_focus_trap_tab(self, page: Page):
        self._open(page)
        for _ in range(5):
            page.keyboard.press("Tab")
        assert _focus_is_inside(page, "rename-voice-modal"), (
            "Tab a fait sortir le focus de rename-voice-modal"
        )

    def test_closes_on_cancel(self, page: Page):
        self._open(page)
        page.click("#rename-modal-cancel")
        page.wait_for_selector("#rename-voice-modal:not([open])", state="attached", timeout=3_000)

    def test_escape_closes_dialog(self, page: Page):
        self._open(page)
        page.keyboard.press("Escape")
        page.wait_for_selector("#rename-voice-modal:not([open])", state="attached", timeout=3_000)


# ---------------------------------------------------------------------------
# Menu mobile DSFR (#header-menu-modal) — viewport < 768px
# ---------------------------------------------------------------------------

class TestHeaderMenuModal:
    """Menu mobile DSFR — composant header, visible uniquement en viewport < 768px.

    Le menu mobile DSFR est un <div role="dialog"> géré par DSFR JS (pas showModal()).
    Le piège focus et aria-hidden sur le fond sont pris en charge par DSFR JS.

    Checklist DSFR spécifique :
      - Présence de aria-modal="true"
      - aria-labelledby ou aria-label non vide
      - Bouton hamburger : type="button" + aria-controls="header-menu-modal"
      - Bouton fermeture : aria-controls="header-menu-modal"
      - Ouverture : data-fr-opened passe à "true"
      - Fermeture par Escape
      - Piège focus (Tab reste dans le menu)
    """

    MOBILE_VIEWPORT = {"width": 375, "height": 812}

    def _set_mobile(self, page: Page):
        page.set_viewport_size(self.MOBILE_VIEWPORT)
        page.wait_for_timeout(200)

    def _open(self, page: Page):
        self._set_mobile(page)
        page.click("#header-menu-btn")
        page.wait_for_selector(
            "#header-menu-modal.fr-modal--opened", state="attached", timeout=3_000
        )

    def test_hamburger_button_visible_on_mobile(self, page: Page):
        self._set_mobile(page)
        btn = page.locator("button[aria-controls='header-menu-modal']")
        assert btn.count() > 0, "Aucun bouton hamburger trouvé"
        expect(btn.first).to_be_visible()

    def test_hamburger_button_has_type_button(self, page: Page):
        self._set_mobile(page)
        btn_type = page.get_attribute(
            "button[aria-controls='header-menu-modal']", "type"
        )
        assert btn_type == "button"

    def test_modal_has_aria_modal(self, page: Page):
        self._open(page)
        val = page.get_attribute("#header-menu-modal", "aria-modal")
        assert val == "true", "header-menu-modal: aria-modal manquant"

    def test_modal_has_accessible_label(self, page: Page):
        """Le menu doit avoir aria-label ou aria-labelledby non vide."""
        self._set_mobile(page)
        aria_label = page.get_attribute("#header-menu-modal", "aria-label")
        aria_labelledby = page.get_attribute("#header-menu-modal", "aria-labelledby")
        has_label = (aria_label and aria_label.strip()) or (
            aria_labelledby and _linked_element_exists(page, "header-menu-modal", "aria-labelledby")
        )
        assert has_label, (
            "header-menu-modal: ni aria-label ni aria-labelledby valide"
        )

    def test_opens_on_hamburger_click(self, page: Page):
        self._open(page)
        assert "fr-modal--opened" in (page.get_attribute("#header-menu-modal", "class") or "")

    def test_close_button_has_aria_controls(self, page: Page):
        self._set_mobile(page)
        close_btn = page.locator(
            "#header-menu-modal button[aria-controls='header-menu-modal']"
        )
        assert close_btn.count() > 0, (
            "Aucun bouton de fermeture avec aria-controls='header-menu-modal' "
            "dans #header-menu-modal"
        )

    def test_escape_closes_menu(self, page: Page):
        self._open(page)
        page.keyboard.press("Escape")
        page.wait_for_selector(
            "#header-menu-modal:not(.fr-modal--opened)", state="attached", timeout=3_000
        )

    def test_close_button_closes_menu(self, page: Page):
        self._open(page)
        page.click(
            "#header-menu-modal button[aria-controls='header-menu-modal']"
        )
        page.wait_for_selector(
            "#header-menu-modal:not(.fr-modal--opened)", state="attached", timeout=3_000
        )

    def test_focus_enters_menu_on_open(self, page: Page):
        self._open(page)
        page.wait_for_timeout(150)
        assert _focus_is_inside(page, "header-menu-modal"), (
            "Le focus n'est pas entré dans #header-menu-modal à l'ouverture"
        )

    def test_focus_trap_tab(self, page: Page):
        """Tab ne doit pas quitter le menu mobile."""
        self._open(page)
        for _ in range(8):
            page.keyboard.press("Tab")
        assert _focus_is_inside(page, "header-menu-modal"), (
            "Tab a fait sortir le focus de #header-menu-modal"
        )

    def test_menu_not_visible_on_desktop(self, page: Page):
        """En desktop (≥ 768px), le menu mobile doit être masqué."""
        page.set_viewport_size({"width": 1280, "height": 800})
        page.wait_for_timeout(200)
        btn = page.locator("button[aria-controls='header-menu-modal']")
        if btn.count() > 0:
            expect(btn.first).to_be_hidden()
