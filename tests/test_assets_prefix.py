"""Tests assets sans préfixe absolu — Phase 2 rouges.

Spécification : PRD v1.5 décision 2 + point Codex #1 + Phase 0bis.
Vérifie que le frontend omnistudio n'a plus de chemins absolus /css/, /js/,
qui casseraient sous `<base href="/omni/">`.
"""
import os
import re
import pytest


FRONTEND_OUT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "omnistudio", "frontend", "out")
)


def _list_files(pattern: str):
    if not os.path.isdir(FRONTEND_OUT):
        pytest.skip(f"Frontend non présent ({FRONTEND_OUT}) — Phase 3 non démarrée")
    out = []
    for root, _, files in os.walk(FRONTEND_OUT):
        for f in files:
            if f.endswith(pattern):
                out.append(os.path.join(root, f))
    return out


class TestHTMLSansCheminsAbsolus:
    def test_aucun_href_absolu_dans_index_html(self):
        """Aucun <link href="/..."> ni <script src="/..."> dans index.html.

        Règle : tous les chemins doivent être relatifs, résolus par <base href="/omni/">.
        Exception : la balise <base> elle-même est autorisée (son rôle est justement
        d'être absolue).
        """
        files = _list_files(".html")
        for f in files:
            content = open(f).read()
            # Retirer la balise <base ...> avant la vérification (elle est légitime)
            stripped = re.sub(r'<base\b[^>]*>', '', content)
            absolu = re.findall(r'href="/[a-zA-Z]', stripped)
            assert absolu == [], f"Chemins absolus dans {f} : {absolu}"

    def test_aucun_src_absolu_dans_index_html(self):
        files = _list_files(".html")
        for f in files:
            content = open(f).read()
            stripped = re.sub(r'<base\b[^>]*>', '', content)
            absolu = re.findall(r'src="/[a-zA-Z]', stripped)
            assert absolu == [], f"src= absolu dans {f} : {absolu}"

    def test_base_href_omni_present(self):
        """<base href="/omni/"> doit être dans le <head> de index.html."""
        files = [f for f in _list_files(".html") if f.endswith("index.html")]
        for f in files:
            content = open(f).read()
            assert '<base href="/omni/">' in content, f"<base> manquant dans {f}"


class TestJSSansFetchAbsolu:
    def test_aucun_fetch_slash_api(self):
        """Aucun fetch('/api/...') dans le JS. Doit être fetch('api/...')."""
        files = _list_files(".js")
        absolus = []
        for f in files:
            content = open(f).read()
            matches = re.findall(r"fetch\(['\"]\/[a-zA-Z]", content)
            if matches:
                absolus.append((f, matches))
        assert absolus == [], f"fetch absolus trouvés : {absolus}"

    def test_aucun_new_url_slash(self):
        files = _list_files(".js")
        for f in files:
            content = open(f).read()
            matches = re.findall(r"new URL\(['\"]\/[a-zA-Z]", content)
            assert matches == [], f"new URL absolu dans {f} : {matches}"


class TestScriptVerify:
    def test_script_verify_assets_prefix_existe(self):
        """Le script scripts/verify-assets-prefix.sh est présent et exécutable."""
        script = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "scripts", "verify-assets-prefix.sh")
        )
        assert os.path.isfile(script), f"Script absent : {script}"
        assert os.access(script, os.X_OK), "Script non exécutable"
