"""Routeur Audio — servir les fichiers WAV generes (PRD-010, Phase 4).

Endpoints :
- GET /api/audio/{filename:path}

Auth hybride : header Bearer OU query param ?token= (pour <audio src>).
"""
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Request
from starlette.responses import FileResponse

from auth import get_current_user, validate_token
from dependencies import THREAD_ID_RE, _verify_session_owner

router = APIRouter()


@router.get("/api/audio/{filename:path}")
async def serve_audio(
    filename: str,
    request: Request,
    token: str = Query(None),
    tid: str = Query(None),
):
    """Servir un fichier WAV. Auth via header OU query params (pour <audio src>)."""
    auth_header = request.headers.get("Authorization", "")
    user = None
    if auth_header.startswith("Bearer "):
        user = await get_current_user(request)
    elif token:
        user = await validate_token(token)
    else:
        raise HTTPException(status_code=401, detail="Token requis")

    thread_id = request.headers.get("X-Thread-Id", "") or tid or ""
    if not thread_id or not THREAD_ID_RE.match(thread_id):
        raise HTTPException(status_code=400, detail="Thread ID invalide")

    # PRD-UX-030 : verification BOLA — le thread_id appartient a l'utilisateur
    if not user or not user.get("user_id"):
        raise HTTPException(status_code=401, detail="Token invalide ou expiré")
    _verify_session_owner(thread_id, user["user_id"])

    base_dir = Path(f"data/voices/{thread_id}").resolve()
    file_path = (base_dir / filename).resolve()

    # Protection path traversal
    if not str(file_path).startswith(str(base_dir)):
        raise HTTPException(status_code=403, detail="Chemin non autorisé")
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Fichier audio introuvable")

    return FileResponse(
        str(file_path),
        media_type="audio/wav",
        headers={"Cache-Control": "private, max-age=3600"},
    )
