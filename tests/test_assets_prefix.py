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
FRONTEND_DIST = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "omnistudio", "frontend", "out-dist")
)


def _list_files(base_dir: str, pattern: str):
    if not os.path.isdir(base_dir):
        pytest.skip(f"Frontend non présent ({base_dir}) — Phase 3 non démarrée")
    out = []
    for root, _, files in os.walk(base_dir):
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
        files = _list_files(FRONTEND_OUT, ".html")
        for f in files:
            content = open(f).read()
            # Retirer la balise <base ...> avant la vérification (elle est légitime)
            stripped = re.sub(r'<base\b[^>]*>', '', content)
            absolu = re.findall(r'href="/[a-zA-Z]', stripped)
            assert absolu == [], f"Chemins absolus dans {f} : {absolu}"

    def test_aucun_src_absolu_dans_index_html(self):
        files = _list_files(FRONTEND_OUT, ".html")
        for f in files:
            content = open(f).read()
            stripped = re.sub(r'<base\b[^>]*>', '', content)
            absolu = re.findall(r'src="/[a-zA-Z]', stripped)
            assert absolu == [], f"src= absolu dans {f} : {absolu}"

    def test_base_href_omni_present(self):
        """<base href="/omni/"> doit être dans le <head> de index.html."""
        files = [f for f in _list_files(FRONTEND_OUT, ".html") if f.endswith("index.html")]
        for f in files:
            content = open(f).read()
            assert '<base href="/omni/">' in content, f"<base> manquant dans {f}"


class TestJSSansFetchAbsolu:
    def test_aucun_fetch_slash_api(self):
        """Aucun fetch('/api/...') dans le JS. Doit être fetch('api/...')."""
        files = _list_files(FRONTEND_OUT, ".js")
        absolus = []
        for f in files:
            content = open(f).read()
            matches = re.findall(r"fetch\(['\"]\/[a-zA-Z]", content)
            if matches:
                absolus.append((f, matches))
        assert absolus == [], f"fetch absolus trouvés : {absolus}"

    def test_aucun_new_url_slash(self):
        files = _list_files(FRONTEND_OUT, ".js")
        for f in files:
            content = open(f).read()
            matches = re.findall(r"new URL\(['\"]\/[a-zA-Z]", content)
            assert matches == [], f"new URL absolu dans {f} : {matches}"


class TestBundleProduction:
    def test_css_source_force_hidden_prioritaire(self):
        css_file = os.path.join(FRONTEND_OUT, "css", "app.css")
        if not os.path.isfile(css_file):
            pytest.skip(f"CSS source absent ({css_file})")

        content = open(css_file).read()
        assert re.search(r"\[hidden\]\s*\{\s*display:\s*none\s*!important;", content), (
            "Le CSS source doit forcer [hidden] à display:none !important pour neutraliser DSFR"
        )

    def test_index_prod_utilise_assets_minifies_relatifs(self):
        index_file = os.path.join(FRONTEND_DIST, "index.html")
        if not os.path.isfile(index_file):
            pytest.skip(f"Build prod absent ({index_file})")

        content = open(index_file).read()
        assert '<base href="/omni/">' in content
        assert 'href="css/app.min.css?v=' in content
        assert 'src="js/app.min.js?v=' in content
        assert 'href="favicon.svg"' in content

        stripped = re.sub(r'<base\b[^>]*>', '', content)
        assert re.findall(r'href="/[a-zA-Z]', stripped) == []
        assert re.findall(r'src="/[a-zA-Z]', stripped) == []

    def test_bundle_prod_pas_stale_voxstudio(self):
        files = [
            os.path.join(FRONTEND_DIST, "index.html"),
            os.path.join(FRONTEND_DIST, "css", "app.min.css"),
            os.path.join(FRONTEND_DIST, "js", "app.min.js"),
        ]
        if not all(os.path.isfile(f) for f in files):
            pytest.skip("Build prod incomplet — out-dist absent")

        stale_markers = ["VoxStudio", "vx_access_token", "vx-login-screen", "data-vx-active"]
        for f in files:
            content = open(f).read()
            for marker in stale_markers:
                assert marker not in content, f"Bundle stale detecte dans {f}: {marker}"


class TestScriptVerify:
    def test_script_verify_assets_prefix_existe(self):
        """Le script scripts/verify-assets-prefix.sh est présent et exécutable."""
        script = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "scripts", "verify-assets-prefix.sh")
        )
        assert os.path.isfile(script), f"Script absent : {script}"
        assert os.access(script, os.X_OK), "Script non exécutable"
