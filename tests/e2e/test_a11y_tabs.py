"""Test de non-régression — Roving tabindex DSFR fr-tabs (OmniStudio).

Vérifie que le composant onglets respecte le pattern ARIA Tabs APG :
- Seul l'onglet actif a tabindex="0", les inactifs ont tabindex="-1"
- Le roving tabindex se met à jour dynamiquement après changement d'onglet
- Les sous-onglets (onglet Voix) suivent le même pattern

Contexte : bug introduit dans app.js qui forçait tabindex="0" sur tous les
onglets via MutationObserver, cassant la navigation clavier DSFR/RGAA.
Corrigé en avril 2026 (voice-num) et porté sur OmniStudio. Ce test empêche toute réintroduction.

Faux positif Tanaguru — Déclaration de conformité (RGAA 4.1.2)
---------------------------------------------------------------
Tanaguru signale les <button tabindex="-1"> comme "non atteignables au
clavier". C'est un faux positif : les outils automatiques lisent le DOM
statiquement et ne comprennent pas le roving tabindex du pattern ARIA Tabs.

Critères concernés : 7.3 et 12.9
Justification : conforme au motif de conception ARIA Tabs (APG WAI-ARIA) et
au composant natif fr-tabs du DSFR. Selon la note technique du test 12.9.1
RGAA : "Certains éléments d'interface complexes [...] font appel à des
navigations optimisées qui utilisent généralement les flèches de direction
pour passer d'une partie du composant à l'autre (par exemple, un système
d'onglets). Le test sur le piège au clavier se limite alors à vérifier que
le composant est atteint avec la tabulation et qu'il est possible de passer
au composant suivant ou revenir au composant précédent."

NE PAS remettre tabindex="0" sur les onglets inactifs pour faire taire
Tanaguru — ce serait une régression d'accessibilité réelle.
"""
import pytest
from playwright.sync_api import Page, expect

from conftest import PASSWORD, TIMEOUT


pytestmark = pytest.mark.skipif(
    not PASSWORD,
    reason="E2E_PASSWORD non defini (requis pour l'authentification Keycloak)",
)

MAIN_TAB_IDS = [
    "tab-import",
    "tab-clean",
    "tab-voices",
    "tab-assign",
    "tab-generate",
    "tab-export",
]

SUB_TAB_IDS = [
    "sub-tab-library",
    "sub-tab-design",
    "sub-tab-clone",
]


class TestRovingTabindex:
    """Roving tabindex sur les onglets principaux et les sous-onglets."""

    def test_initial_state_main_tabs(self, page: Page):
        """Au chargement, seul l'onglet actif (Import) a tabindex=0."""
        for tab_id in MAIN_TAB_IDS:
            btn = page.locator(f"#{tab_id}")
            expected = "0" if tab_id == "tab-import" else "-1"
            assert btn.get_attribute("tabindex") == expected, (
                f"{tab_id} : tabindex attendu={expected}, "
                f"obtenu={btn.get_attribute('tabindex')} "
                f"(bug tabindex-override DSFR ?)"
            )

    def test_tabindex_updates_after_switch(self, page: Page):
        """Après un clic sur 'Préparation', le roving tabindex se met à jour."""
        page.locator("#tab-clean").click()

        for tab_id in MAIN_TAB_IDS:
            btn = page.locator(f"#{tab_id}")
            expected = "0" if tab_id == "tab-clean" else "-1"
            expect(btn).to_have_attribute("tabindex", expected, timeout=3_000)

        # Revenir sur Import pour ne pas perturber les autres tests
        page.locator("#tab-import").click()
        expect(page.locator("#tab-import")).to_have_attribute("tabindex", "0", timeout=3_000)

    def test_initial_state_sub_tabs(self, page: Page):
        """Dans l'onglet Voix, seul le sous-onglet actif (Bibliothèque) a tabindex=0."""
        page.locator("#tab-voices").click()
        page.locator("#panel-voices").wait_for(state="visible", timeout=TIMEOUT)

        for tab_id in SUB_TAB_IDS:
            btn = page.locator(f"#{tab_id}")
            expected = "0" if tab_id == "sub-tab-library" else "-1"
            assert btn.get_attribute("tabindex") == expected, (
                f"{tab_id} : tabindex attendu={expected}, "
                f"obtenu={btn.get_attribute('tabindex')}"
            )

    def test_sub_tab_switch_updates_tabindex(self, page: Page):
        """Après un clic sur 'Créer', le roving tabindex des sous-onglets se met à jour."""
        page.locator("#tab-voices").click()
        page.locator("#panel-voices").wait_for(state="visible", timeout=TIMEOUT)

        page.locator("#sub-tab-design").click()

        for tab_id in SUB_TAB_IDS:
            btn = page.locator(f"#{tab_id}")
            expected = "0" if tab_id == "sub-tab-design" else "-1"
            expect(btn).to_have_attribute("tabindex", expected, timeout=3_000)

    def test_aria_selected_consistent_with_tabindex(self, page: Page):
        """aria-selected=true <=> tabindex=0 sur tous les onglets."""
        page.locator("#tab-import").click()
        page.wait_for_timeout(300)

        for tab_id in MAIN_TAB_IDS:
            btn = page.locator(f"#{tab_id}")
            selected = btn.get_attribute("aria-selected")
            tabindex = btn.get_attribute("tabindex")
            assert (selected == "true") == (tabindex == "0"), (
                f"{tab_id} : incohérence aria-selected={selected} / tabindex={tabindex}"
            )
