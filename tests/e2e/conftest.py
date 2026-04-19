"""Configuration E2E — Parcours complet OmniStudio via Playwright.

Prerequis :
    pip install -r tests/e2e/requirements.txt
    playwright install chromium
    ./start.sh  (serveur OmniStudio + Keycloak + OmniVoice)

Variables d'environnement :
    E2E_BASE_URL   : URL OmniStudio (defaut: http://localhost:7870)
    E2E_USERNAME   : Identifiant Keycloak (defaut: alex)
    E2E_PASSWORD   : Mot de passe Keycloak (requis)
    E2E_HEADLESS   : 0 pour voir le navigateur (defaut: 1)
    E2E_SLOW_MO    : Ralentir les actions en ms (defaut: 0)
    E2E_SKIP_TTS   : 1 pour sauter la generation TTS (defaut: 0)
"""
import os
import pytest
from pathlib import Path
from playwright.sync_api import Playwright, Browser, BrowserContext, Page


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
BASE_URL = os.getenv("E2E_BASE_URL", "http://localhost:7870")
USERNAME = os.getenv("E2E_USERNAME", "alex")
PASSWORD = os.getenv("E2E_PASSWORD", "")
HEADLESS = os.getenv("E2E_HEADLESS", "1") == "1"
SLOW_MO = int(os.getenv("E2E_SLOW_MO", "0"))
SKIP_TTS = os.getenv("E2E_SKIP_TTS", "0") == "1"
FIXTURES_DIR = Path(__file__).parent / "fixtures"
TIMEOUT = 60_000  # 60s par defaut pour les attentes


# ---------------------------------------------------------------------------
# Fixtures Playwright
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def browser(playwright: Playwright) -> Browser:
    browser = playwright.chromium.launch(headless=HEADLESS, slow_mo=SLOW_MO)
    yield browser
    browser.close()


@pytest.fixture(scope="session")
def auth_context(browser: Browser) -> BrowserContext:
    """Contexte authentifie (login une seule fois pour toute la session)."""
    context = browser.new_context(
        viewport={"width": 1280, "height": 900},
        base_url=BASE_URL,
    )
    context.set_default_timeout(TIMEOUT)
    page = context.new_page()

    # Login
    page.goto("/")
    page.wait_for_selector("#ov-login-form", state="visible")
    page.fill("#ov-username-input", USERNAME)
    page.fill("#ov-password-input", PASSWORD)
    page.click("#ov-login-form button[type='submit']")

    # Attendre que l'app s'affiche
    page.wait_for_selector("#ov-app-screen", state="visible", timeout=15_000)
    page.close()

    yield context
    context.close()


@pytest.fixture
def page(auth_context: BrowserContext) -> Page:
    """Page authentifiee pour chaque test."""
    p = auth_context.new_page()
    p.goto("/")
    p.wait_for_selector("#ov-app-screen", state="visible", timeout=10_000)
    yield p
    p.close()
