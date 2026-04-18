"""Routeur Status — sante systeme et modeles TTS (PRD-010, Phase 3).

Endpoints :
- GET /api/status (public)
- GET /api/health (public, monitoring probe — PRD-027)
- POST /api/models/preload
- GET /api/tts/status
"""
import asyncio
import os
import shutil
import sqlite3

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from auth import get_current_user
from config import DB_PATH, KEYCLOAK_URL, KEYCLOAK_REALM
from dependencies import (
    _proxy_omnivoice,
    _sessions_db_path,
    _omnivoice_client,
    api_error,
    api_response,
    vox_client,
)

router = APIRouter()


@router.get("/api/status")
async def system_status():
    """Statut systeme (public, pas de JWT)."""
    # OmniVoice
    omnivoice_ok = False
    models_status = None
    try:
        resp = await _omnivoice_client.get("/", timeout=5.0)
        omnivoice_ok = resp.status_code == 200
        if omnivoice_ok:
            models_resp = await _omnivoice_client.get("/models/status", timeout=5.0)
            if models_resp.status_code == 200:
                models_status = models_resp.json()
    except Exception:
        pass

    # Outils audio
    import shutil
    sox_ok = shutil.which("sox") is not None
    ffmpeg_ok = shutil.which("ffmpeg") is not None

    # Albert API (LLM nettoyage)
    albert_ok = False
    albert_model = ""
    try:
        api_key = os.getenv("OPENAI_API_KEY", "")
        if api_key:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    "https://albert.api.etalab.gouv.fr/v1/models",
                    headers={"Authorization": f"Bearer {api_key}"},
                    timeout=5.0,
                )
                albert_ok = resp.status_code == 200
                if albert_ok:
                    from config import LLM_PROVIDER
                    albert_model = LLM_PROVIDER
    except Exception:
        pass

    return api_response({
        "omnivoice": omnivoice_ok,
        "models": models_status,
        "audio_tools": {"sox": sox_ok, "ffmpeg": ffmpeg_ok},
        "albert": {"ok": albert_ok, "model": albert_model},
    })


@router.post("/api/models/preload")
async def preload_models(user=Depends(get_current_user)):
    """Pre-charger les modeles TTS."""
    try:
        resp = await _proxy_omnivoice("POST", "/models/preload", params={"design": True, "preset": True, "clone_1_7b": True})
        return api_response(resp.json() if resp.status_code == 200 else None)
    except HTTPException:
        raise
    except Exception as e:
        return api_error("OMNIVOICE_UNAVAILABLE", str(e), 502)


@router.get("/api/tts/status")
async def tts_status(user=Depends(get_current_user)):
    """Proxy vers OmniVoice : sante, modeles et etat generation."""
    healthy = await asyncio.to_thread(vox_client.health_check)
    models = await asyncio.to_thread(vox_client.get_models_status)

    # Etat generation (semaphore Phase 2)
    generation = None
    try:
        resp = await asyncio.to_thread(
            lambda: httpx.get(f"{vox_client.base_url}/generation/status", timeout=5.0)
        )
        if resp.status_code == 200:
            generation = resp.json()
    except Exception:
        pass

    return api_response({
        "healthy": healthy,
        "models": models,
        "generation": generation,
    })


@router.get("/api/health")
async def health_check():
    """Probe de sante pour monitoring (PRD-027).

    Retourne 200 si tout est OK, 503 si un service critique est down.
    Pas d'authentification requise (utilisable par load balancer).
    """
    healthy = True
    checks = {}

    # 1. OmniVoice accessible ?
    try:
        resp = await _proxy_omnivoice("GET", "/")
        checks["omnivoice"] = "ok" if resp.status_code == 200 else "error"
    except Exception:
        checks["omnivoice"] = "error"
        healthy = False

    # 2. Keycloak accessible ?
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}")
            checks["keycloak"] = "ok" if resp.status_code == 200 else "error"
    except Exception:
        checks["keycloak"] = "error"
        healthy = False

    # 3. Base de donnees sessions accessible ?
    try:
        conn = sqlite3.connect(_sessions_db_path)
        conn.execute("SELECT 1")
        conn.close()
        checks["sessions_db"] = "ok"
    except Exception:
        checks["sessions_db"] = "error"
        healthy = False

    # 4. Base checkpoint LangGraph accessible ?
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("SELECT 1")
        conn.close()
        checks["checkpoint_db"] = "ok"
    except Exception:
        checks["checkpoint_db"] = "error"
        healthy = False

    # 5. Outils audio disponibles ?
    checks["sox"] = "ok" if shutil.which("sox") else "missing"
    checks["ffmpeg"] = "ok" if shutil.which("ffmpeg") else "missing"

    return JSONResponse(
        content={
            "status": "healthy" if healthy else "unhealthy",
            "version": "1.0.0",
            "checks": checks,
        },
        status_code=200 if healthy else 503,
    )
