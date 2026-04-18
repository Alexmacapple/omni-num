"""Routeur Sessions — gestion des sessions LangGraph + verrous SSE (PRD-010, Phase 2).

Endpoints :
- POST /api/session
- POST /api/session/resume
- GET /api/session/list
- POST /api/locks/clear
"""
import asyncio
import sqlite3
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request

from auth import get_current_user
from config import SESSION_MAX_PER_USER
from dependencies import (
    _cleaning_locks,
    _exporting_locks,
    _generating_locks,
    _sessions_db_path,
    _touch_session,
    _verify_session_owner,
    api_response,
    get_thread_id,
    graph_app,
    logger,
)

router = APIRouter()


@router.post("/api/locks/clear")
async def clear_locks(user=Depends(get_current_user), thread_id: str = Depends(get_thread_id)):
    """Libere tous les verrous SSE pour la session courante."""
    _verify_session_owner(thread_id, user["user_id"])
    cleared = []
    for name, locks in [("cleaning", _cleaning_locks), ("generating", _generating_locks), ("exporting", _exporting_locks)]:
        if thread_id in locks:
            del locks[thread_id]
            cleared.append(name)
    logger.info(f"Verrous liberes pour {thread_id}: {cleared or 'aucun'}")
    return api_response({"cleared": cleared})


@router.post("/api/session")
async def create_session(request: Request, user=Depends(get_current_user)):
    """Creer une nouvelle session LangGraph."""
    body = await request.json() if request.headers.get("content-type", "").startswith("application/json") else {}
    label = body.get("label", "")

    # Verifier la limite par utilisateur (transaction atomique — PRD-035 Bug 2)
    conn = sqlite3.connect(_sessions_db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        count = conn.execute(
            "SELECT COUNT(*) FROM user_sessions WHERE user_id = ?", (user["user_id"],)
        ).fetchone()[0]

        if count >= SESSION_MAX_PER_USER:
            # Supprimer la plus ancienne
            conn.execute("""
                DELETE FROM user_sessions WHERE thread_id = (
                    SELECT thread_id FROM user_sessions WHERE user_id = ? ORDER BY updated_at ASC LIMIT 1
                )
            """, (user["user_id"],))

        thread_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT INTO user_sessions (thread_id, user_id, created_at, updated_at, label) VALUES (?, ?, ?, ?, ?)",
            (thread_id, user["user_id"], now, now, label),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return api_response({"thread_id": thread_id, "label": label})


@router.post("/api/session/resume")
async def resume_session(request: Request, user=Depends(get_current_user)):
    """Reprendre une session existante."""
    body = await request.json()
    thread_id = body.get("thread_id", "")
    _verify_session_owner(thread_id, user["user_id"])
    _touch_session(thread_id)

    config = {"configurable": {"thread_id": thread_id}}
    state = await asyncio.to_thread(graph_app.get_state, config)
    state_values = state.values if state else {}

    return api_response({
        "thread_id": thread_id,
        "state": {
            "steps": state_values.get("steps", []),
            "cleaning_validated": state_values.get("cleaning_validated", False),
            "locked_voices": state_values.get("locked_voices", []),
            "assignments": state_values.get("assignments", {}),
            "generation_complete": state_values.get("generation_complete", False),
            "export_path": state_values.get("export_path", ""),
        },
    })


@router.get("/api/session/list")
async def list_sessions(user=Depends(get_current_user)):
    """Lister les sessions de l'utilisateur."""
    conn = sqlite3.connect(_sessions_db_path)
    rows = conn.execute(
        "SELECT thread_id, created_at, updated_at, label FROM user_sessions WHERE user_id = ? ORDER BY updated_at DESC",
        (user["user_id"],),
    ).fetchall()
    conn.close()

    sessions = [
        {"thread_id": r[0], "created_at": r[1], "updated_at": r[2], "label": r[3]}
        for r in rows
    ]
    return api_response(sessions)
