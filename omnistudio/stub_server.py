"""Stub FastAPI — Phase 0bis Architecture check.

Minimal pour valider root_path="/omni" + assets statiques + Funnel path-based.
Ne fait rien d'applicatif, juste servir un index.html + 1 CSS + 1 JS pour prouver
que tout est correctement routé sous le préfixe /omni.

Critères de sortie Phase 0bis :
- GET http://localhost:7870/          → 200 OK (index.html)
- GET http://localhost:7870/css/test.css → 200 OK
- GET http://localhost:7870/js/test.js   → 200 OK
- GET https://mac-studio-alex.tail0fc408.ts.net/omni/ → 200 OK (via Funnel)
- GET https://mac-studio-alex.tail0fc408.ts.net/omni/css/test.css → 200 OK
- GET https://mac-studio-alex.tail0fc408.ts.net/omni/js/test.js   → 200 OK
"""

import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# Stub server — pour Phase 0bis validation architecture.
# Tailscale Funnel avec --set-path=/omni STRIPPE le préfixe avant de forwarder
# au backend. La cohérence cross-contexte (local direct OU via Funnel) est
# assurée par <base href="/omni/"> dans l'index.html, qui normalise tous les
# liens côté navigateur. root_path peut être défini mais FastAPI voit les
# requêtes à la racine de toute façon.
app = FastAPI(
    title="OmniStudio Stub",
    description="Stub Phase 0bis — architecture check",
    docs_url="/docs",
    redoc_url="/redoc",
    root_path=os.getenv("OMNISTUDIO_ROOT_PATH", "/omni"),
)

_BASE = os.path.dirname(os.path.abspath(__file__))
_FRONTEND = os.path.join(_BASE, "frontend", "out-stub")

# Vérifier que le répertoire frontend existe
if not os.path.isdir(_FRONTEND):
    raise RuntimeError(f"Frontend directory not found: {_FRONTEND}")


@app.get("/")
async def index():
    """Sert index.html à la racine (ou /omni/ via Funnel)."""
    index_path = os.path.join(_FRONTEND, "index.html")
    if not os.path.isfile(index_path):
        return {"error": "index.html not found"}
    return FileResponse(index_path)


@app.get("/api/health")
async def health():
    """Health check — rappelle root_path pour vérification."""
    return {
        "ok": True,
        "root_path": app.root_path,
        "frontend_dir": _FRONTEND,
    }


# Mount statique pour css/, js/
# En local : http://localhost:7870/css/test.css
# Via Funnel : https://mac-studio-alex.tail0fc408.ts.net/omni/css/test.css
css_dir = os.path.join(_FRONTEND, "css")
js_dir = os.path.join(_FRONTEND, "js")
if os.path.isdir(css_dir):
    app.mount("/css", StaticFiles(directory=css_dir), name="css")
if os.path.isdir(js_dir):
    app.mount("/js", StaticFiles(directory=js_dir), name="js")


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("OMNISTUDIO_PORT", "7870"))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
