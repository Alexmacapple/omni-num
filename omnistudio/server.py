"""OmniStudio DSFR — Assembleur FastAPI (PRD-013)."""
import os
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware
from starlette.responses import FileResponse
from starlette.staticfiles import StaticFiles

from fastapi.exceptions import RequestValidationError
from slowapi.errors import RateLimitExceeded

from config import CORS_ORIGINS, FRONTEND_DIR, FRONTEND_DIST_DIR, MINIFY, OMNISTUDIO_PORT
from dependencies import (
    _check_disk_quota,
    _init_sessions_db,
    _purge_old_sessions,
    _purge_temp_files,
    _purge_stale_exports,
    _purge_orphan_voices,
    _close_resources,
    api_response,
    limiter,
    logger,
)
from routers import register_all


# ---------------------------------------------------------------------------
# Exception handlers (PRD-015)
# ---------------------------------------------------------------------------
async def _unhandled_exception_handler(request: Request, exc: Exception):
    """Masque les stacktraces en production."""
    if isinstance(exc, HTTPException):
        raise exc
    logger.error("Erreur non geree: %s", exc, exc_info=True)
    return api_response(
        error={"code": "INTERNAL_ERROR", "message": "Erreur interne du serveur."},
        status_code=500,
    )


async def _validation_exception_handler(request: Request, exc: RequestValidationError):
    """Erreurs de validation Pydantic au format api_error."""
    return api_response(
        error={"code": "VALIDATION_ERROR", "message": str(exc.errors())},
        status_code=422,
    )


# ---------------------------------------------------------------------------
# Rate limiting handler (PRD-011)
# ---------------------------------------------------------------------------
def _rate_limit_handler(request: Request, exc: RateLimitExceeded):
    """Handler 429 au format api_error standard."""
    return api_response(
        error={
            "code": "RATE_LIMITED",
            "message": "Trop de requetes. Reessayez dans quelques secondes.",
        },
        status_code=429,
    )


# ---------------------------------------------------------------------------
# Middleware securite (PRD-011)
# ---------------------------------------------------------------------------
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        # Pas de CSP restrictif sur la documentation API (Swagger UI charge depuis CDN)
        if request.url.path in ("/docs", "/redoc", "/openapi.json"):
            return response
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "font-src 'self'; "
            "connect-src 'self'; "
            "media-src 'self' blob:; "
            "object-src 'none'; "
            "base-uri 'self'; "
            "form-action 'self'; "
            "frame-ancestors 'none'"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(self), geolocation=()"
        # HSTS conditionnel sur HTTPS (PRD-028)
        if request.headers.get("x-forwarded-proto") == "https":
            hsts_max_age = int(os.getenv("OMNISTUDIO_HSTS_MAX_AGE", "300"))
            response.headers["Strict-Transport-Security"] = f"max-age={hsts_max_age}; includeSubDomains"
        # COOP et X-Permitted-Cross-Domain-Policies (PRD-028)
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["X-Permitted-Cross-Domain-Policies"] = "none"
        return response


class CacheControlMiddleware(BaseHTTPMiddleware):
    """Cache-Control pour les assets statiques (PRD-028)."""
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        path = request.url.path
        # Mode dev (MINIFY=false) : pas de cache sur JS/CSS/HTML
        if not MINIFY:
            if path.endswith((".js", ".css", ".html")):
                response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            return response
        # Assets DSFR (fonts, icônes, CSS, JS) : cache 1 an (immuables, version 1.11.2 fixe)
        if path.startswith("/dsfr/") or path.endswith((".woff2", ".woff", ".svg")):
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        # CSS et JS applicatifs : cache 7 jours (versionnés par hash ?v=)
        elif path.endswith((".js", ".css")):
            response.headers["Cache-Control"] = "public, max-age=604800"
        return response


# ---------------------------------------------------------------------------
# Lifespan (PRD-012)
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app):
    _init_sessions_db()
    _purge_old_sessions()
    _purge_temp_files()
    _purge_stale_exports()
    _purge_orphan_voices()
    _check_disk_quota()
    mode = "PRODUCTION (minifié)" if MINIFY else "DÉVELOPPEMENT (sources)"
    logger.info("OmniStudio DSFR demarre sur le port %d — mode %s", OMNISTUDIO_PORT, mode)
    yield
    # Shutdown (PRD-026)
    logger.info("Arret en cours...")
    await _close_resources()
    logger.info("OmniStudio arrete proprement.")


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(
    title="OmniStudio",
    description="API de production vocale — Import, préparation, design voix, génération TTS et export.",
    version="1.0.0",
    lifespan=lifespan,
    root_path=os.getenv("OMNISTUDIO_ROOT_PATH", "/omni"),
)
app.state.limiter = limiter
app.add_exception_handler(Exception, _unhandled_exception_handler)
app.add_exception_handler(RequestValidationError, _validation_exception_handler)
app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(CacheControlMiddleware)
# CORS ajoute APRES SecurityHeaders → s'execute EN PREMIER (Starlette LIFO, PRD-014)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "X-Thread-Id", "Content-Type"],
    expose_headers=["Content-Disposition"],
)
app.add_middleware(GZipMiddleware, minimum_size=500)
register_all(app)

# Repertoire frontend actif (PRD-028)
ACTIVE_FRONTEND = FRONTEND_DIST_DIR if MINIFY else FRONTEND_DIR

# Fichiers statiques (front DSFR) — APRES les routeurs
# Vérifier que les répertoires existent avant de les monter
css_dir = os.path.join(ACTIVE_FRONTEND, "css")
dsfr_dir = os.path.join(ACTIVE_FRONTEND, "dsfr")
if os.path.isdir(css_dir):
    app.mount("/css", StaticFiles(directory=css_dir), name="css")
else:
    logger.warning("Repertoire CSS non trouve: %s", css_dir)
if os.path.isdir(dsfr_dir):
    app.mount("/dsfr", StaticFiles(directory=dsfr_dir), name="dsfr")
else:
    logger.warning("Repertoire DSFR non trouve: %s", dsfr_dir)


@app.api_route("/js/{path:path}", methods=["GET", "HEAD"])
async def serve_js(path: str):
    """Servir les fichiers JS — cache gere par CacheControlMiddleware (PRD-028)."""
    js_dir = os.path.join(ACTIVE_FRONTEND, "js")
    file_path = os.path.join(js_dir, path)
    # Sécurité : vérifier que file_path est bien dans js_dir (prévention directory traversal)
    if not os.path.abspath(file_path).startswith(os.path.abspath(js_dir)):
        raise HTTPException(status_code=403, detail="Acces refuse")
    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="Fichier non trouve")
    return FileResponse(file_path)


@app.api_route("/", methods=["GET", "HEAD"])
async def serve_index():
    """SPA : sert index.html."""
    return FileResponse(os.path.join(ACTIVE_FRONTEND, "index.html"))


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=OMNISTUDIO_PORT, log_level="info")
