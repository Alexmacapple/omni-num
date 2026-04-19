"""Routeur Clean — nettoyage LLM des textes (PRD-010, Phase 6).

Endpoints :
- POST /api/clean (SSE)
- POST /api/clean/validate
- POST /api/clean/accept/{step_id}
- POST /api/clean/delete/{step_id}
- POST /api/clean/delete-all
- POST /api/clean/status/{step_id}
- POST /api/clean/single/{step_id}
- GET /api/clean/diff/{step_id}
"""
import asyncio
import difflib
import json
import os
from typing import Dict, Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from jinja2 import Template

from auth import get_current_user
from config import LLM_API_KEY, LLM_MODEL_OVERRIDE, LLM_PROVIDER, LLM_TEMPERATURE
from core.llm_client import LLMClient
from core.templates import CLEANING_SYSTEM_PROMPT, CLEANING_USER_PROMPT, apply_layer_a
from dependencies import (
    _cleaning_locks,
    _is_locked,
    _lock,
    _unlock,
    _touch_session,
    _verify_session_owner,
    api_error,
    api_response,
    get_thread_id,
    graph_app,
    limiter,
    logger,
)
from graph.subgraphs.clean_loop import apply_layer_b

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers locaux (D2)
# ---------------------------------------------------------------------------

def _escape_html_diff(text: str) -> str:
    """Echappe HTML pour le diff (prevention XSS)."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _make_diff_html(orig: str, new: str) -> str:
    """Genere le HTML du diff mot a mot."""
    if not orig and not new:
        return "Aucun texte."
    if orig == new:
        return "Aucune difference."
    orig_words = (orig or "").split()
    new_words = (new or "").split()
    sm = difflib.SequenceMatcher(a=orig_words, b=new_words)
    parts = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            parts.append(_escape_html_diff(" ".join(orig_words[i1:i2])))
        elif tag == "delete":
            parts.append(f'<span class="ov-diff-del">{_escape_html_diff(" ".join(orig_words[i1:i2]))}</span>')
        elif tag == "insert":
            parts.append(f'<span class="ov-diff-ins">{_escape_html_diff(" ".join(new_words[j1:j2]))}</span>')
        elif tag == "replace":
            parts.append(f'<span class="ov-diff-del">{_escape_html_diff(" ".join(orig_words[i1:i2]))}</span>')
            parts.append(f'<span class="ov-diff-ins">{_escape_html_diff(" ".join(new_words[j1:j2]))}</span>')
    return " ".join(p for p in parts if p).strip()


# ---------------------------------------------------------------------------
# Modeles Pydantic
# ---------------------------------------------------------------------------

class CleanRequest(BaseModel):
    glossary: Dict[str, str] = {}
    corrections_json: Optional[Dict] = None


class ValidateAllRequest(BaseModel):
    edits: Dict[str, str] = {}


class AcceptRequest(BaseModel):
    text_tts: str = ""


class StatusRequest(BaseModel):
    status: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/api/clean")
@limiter.limit("3/minute")
async def clean_steps(req: CleanRequest, request: Request, user=Depends(get_current_user)):
    """Nettoyage LLM avec streaming SSE."""
    thread_id = get_thread_id(request)
    _verify_session_owner(thread_id, user["user_id"])
    _touch_session(thread_id)

    if _is_locked(_cleaning_locks, thread_id):
        return api_error("CLEAN_IN_PROGRESS", "Un nettoyage est déjà en cours sur cette session.")
    _lock(_cleaning_locks, thread_id)

    config = {"configurable": {"thread_id": thread_id}}

    patterns = (req.corrections_json or {}).get("patterns", {})
    parentheses = (req.corrections_json or {}).get("parentheses", {})
    majuscules = (req.corrections_json or {}).get("majuscules", {})

    await asyncio.to_thread(graph_app.update_state, config, {
        "cleaning_mode": "auto",
        "domain_glossary": req.glossary,
        "correction_patterns": patterns,
        "correction_parentheses": parentheses,
        "correction_majuscules": majuscules,
        "cleaning_validated": False,
    })

    state = await asyncio.to_thread(graph_app.get_state, config)
    steps = state.values.get("steps", []) if state and state.values else []

    async def event_generator():
        llm = LLMClient(
            provider=LLM_PROVIDER,
            api_key=LLM_API_KEY,
            temperature=LLM_TEMPERATURE,
            model_override=LLM_MODEL_OVERRIDE,
        )
        sys_tpl = Template(CLEANING_SYSTEM_PROMPT)
        system_prompt = sys_tpl.render(glossary=req.glossary)

        pending = [s for s in steps if s.get("cleaning_status") != "validated"]
        total = len(pending)
        llm_call_count = 0
        fallback_count = 0

        for step in steps:
            if step.get("cleaning_status") == "validated":
                continue

            if await request.is_disconnected():
                logger.info(f"Client deconnecte, arret nettoyage pour {thread_id}")
                # Sauvegarde incrementale avant arret
                await asyncio.to_thread(graph_app.update_state, config, {"steps": steps})
                return

            # Rate-limit avec heartbeats
            if llm_call_count > 0 and llm_call_count % 9 == 0:
                yield {"event": "rate_limit", "data": json.dumps({
                    "message": "Pause rate-limit (60s)...", "remaining": 60,
                })}
                for _ in range(4):
                    await asyncio.sleep(15)
                    yield {"event": "heartbeat", "data": "{}"}
            elif llm_call_count > 0:
                await asyncio.sleep(1)

            llm_call_count += 1
            progress = round((llm_call_count / total) * 100) if total > 0 else 100

            text = apply_layer_b(step["text_original"], patterns, parentheses, majuscules)
            user_prompt = Template(CLEANING_USER_PROMPT).render(text=text)
            proposed = await asyncio.to_thread(llm.ask, system_prompt, user_prompt)

            if proposed.startswith("Erreur :"):
                proposed = apply_layer_a(text)
                fallback_count += 1

            step["text_tts"] = proposed
            step["cleaning_status"] = "cleaned"

            yield {"event": "progress", "data": json.dumps({
                "step_id": step["step_id"],
                "index": llm_call_count,
                "total": total,
                "progress": progress,
                "text_tts": proposed,
                "message": f"Nettoyage etape {step['step_id']} ({llm_call_count}/{total})...",
            })}

            # Sauvegarde incrementale toutes les 5 etapes
            if llm_call_count % 5 == 0:
                await asyncio.to_thread(graph_app.update_state, config, {"steps": steps})

        # Sauvegarde finale
        await asyncio.to_thread(graph_app.update_state, config, {"steps": steps, "iteration_count": 1})

        yield {"event": "done", "data": json.dumps({"cleaned": total, "fallback": fallback_count})}

    async def safe_generator():
        try:
            async for event in event_generator():
                yield event
        finally:
            _unlock(_cleaning_locks, thread_id)

    return EventSourceResponse(safe_generator(), headers={
        "X-Accel-Buffering": "no",
        "Cache-Control": "no-cache, no-transform",
    })


@router.post("/api/clean/validate")
async def clean_validate(req: ValidateAllRequest, request: Request, user=Depends(get_current_user)):
    """Valider tous les textes."""
    thread_id = get_thread_id(request)
    _verify_session_owner(thread_id, user["user_id"])
    _touch_session(thread_id)

    config = {"configurable": {"thread_id": thread_id}}
    state = await asyncio.to_thread(graph_app.get_state, config)
    steps = state.values.get("steps", []) if state and state.values else []

    for s in steps:
        sid = str(s["step_id"])
        if sid in req.edits:
            s["text_tts"] = req.edits[sid]
        elif not s.get("text_tts"):
            s["text_tts"] = s["text_original"]
        s["cleaning_status"] = "validated"

    await asyncio.to_thread(graph_app.update_state, config, {
        "steps": steps,
        "cleaning_validated": True,
        "decision": "validated",
        "cleaning_log": [],
        "iteration_count": 1,
    }, "finalize_clean")

    return api_response({"validated": len(steps)})


@router.post("/api/clean/accept/{step_id}")
async def clean_accept(step_id: str, req: AcceptRequest, request: Request, user=Depends(get_current_user)):
    """Accepter une etape individuelle."""
    thread_id = get_thread_id(request)
    _verify_session_owner(thread_id, user["user_id"])
    _touch_session(thread_id)

    config = {"configurable": {"thread_id": thread_id}}
    state = await asyncio.to_thread(graph_app.get_state, config)
    steps = state.values.get("steps", []) if state and state.values else []

    found = False
    for s in steps:
        if str(s["step_id"]) == step_id:
            if req.text_tts:
                s["text_tts"] = req.text_tts
            s["cleaning_status"] = "validated"
            found = True
            break

    if not found:
        return api_error("STEP_NOT_FOUND", f"Etape {step_id} introuvable", 404)

    await asyncio.to_thread(graph_app.update_state, config, {"steps": steps})
    return api_response({"step_id": step_id, "status": "validated"})


@router.post("/api/clean/delete/{step_id}")
async def clean_delete(step_id: str, request: Request, user=Depends(get_current_user)):
    """Supprimer une etape."""
    thread_id = get_thread_id(request)
    _verify_session_owner(thread_id, user["user_id"])
    _touch_session(thread_id)

    config = {"configurable": {"thread_id": thread_id}}
    state = await asyncio.to_thread(graph_app.get_state, config)
    steps = state.values.get("steps", []) if state and state.values else []

    new_steps = [s for s in steps if str(s["step_id"]) != step_id]
    if len(new_steps) == len(steps):
        return api_error("STEP_NOT_FOUND", f"Etape {step_id} introuvable", 404)

    # Nettoyer assignments et instructions orphelins
    assignments = state.values.get("assignments", {})
    instructions = state.values.get("instructions", {})
    new_assignments = {k: v for k, v in assignments.items() if k != step_id}
    new_instructions = {k: v for k, v in instructions.items() if k != step_id}

    await asyncio.to_thread(graph_app.update_state, config, {
        "steps": new_steps,
        "assignments": new_assignments,
        "instructions": new_instructions,
    })

    # Supprimer le fichier audio orphelin sur disque
    generated = state.values.get("generated_files", [])
    for g in generated:
        if str(g.get("step_id")) == step_id:
            wav = g.get("wav_path", "")
            if wav and os.path.exists(wav):
                try:
                    os.remove(wav)
                except OSError as e:
                    logger.warning(f"Impossible de supprimer {wav} : {e}, poursuivre")

    return api_response({"step_id": step_id, "deleted": True, "remaining": len(new_steps)})


@router.post("/api/clean/delete-all")
async def clean_delete_all(request: Request, user=Depends(get_current_user)):
    """Supprimer tous les segments."""
    thread_id = get_thread_id(request)
    _verify_session_owner(thread_id, user["user_id"])
    _touch_session(thread_id)

    config = {"configurable": {"thread_id": thread_id}}
    state = await asyncio.to_thread(graph_app.get_state, config)
    steps = state.values.get("steps", []) if state and state.values else []
    count = len(steps)

    await asyncio.to_thread(graph_app.update_state, config, {"steps": []})
    return api_response({"deleted": count})


@router.post("/api/clean/status/{step_id}")
async def clean_status(step_id: str, req: StatusRequest, request: Request, user=Depends(get_current_user)):
    """Modifier le statut d'une etape."""
    thread_id = get_thread_id(request)
    _verify_session_owner(thread_id, user["user_id"])
    _touch_session(thread_id)

    if req.status not in ("pending", "cleaned", "validated"):
        return api_error("INVALID_STATUS", f"Statut invalide: {req.status}", 400)

    config = {"configurable": {"thread_id": thread_id}}
    state = await asyncio.to_thread(graph_app.get_state, config)
    steps = state.values.get("steps", []) if state and state.values else []

    found = False
    for s in steps:
        if str(s["step_id"]) == step_id:
            s["cleaning_status"] = req.status
            found = True
            break

    if not found:
        return api_error("STEP_NOT_FOUND", f"Etape {step_id} introuvable", 404)

    await asyncio.to_thread(graph_app.update_state, config, {"steps": steps})
    return api_response({"step_id": step_id, "status": req.status})


@router.post("/api/clean/single/{step_id}")
async def clean_single(step_id: str, request: Request, user=Depends(get_current_user)):
    """Nettoyage LLM d'un seul segment."""
    thread_id = get_thread_id(request)
    _verify_session_owner(thread_id, user["user_id"])
    _touch_session(thread_id)

    config = {"configurable": {"thread_id": thread_id}}
    state = await asyncio.to_thread(graph_app.get_state, config)
    steps = state.values.get("steps", []) if state and state.values else []
    glossary = state.values.get("domain_glossary", {}) if state and state.values else {}
    patterns = state.values.get("correction_patterns", {}) if state and state.values else {}
    parentheses = state.values.get("correction_parentheses", {}) if state and state.values else {}
    majuscules = state.values.get("correction_majuscules", {}) if state and state.values else {}

    step = None
    for s in steps:
        if str(s["step_id"]) == step_id:
            step = s
            break
    if not step:
        return api_error("STEP_NOT_FOUND", f"Etape {step_id} introuvable", 404)

    try:
        llm = LLMClient(
            provider=LLM_PROVIDER,
            api_key=LLM_API_KEY,
            temperature=LLM_TEMPERATURE,
            model_override=LLM_MODEL_OVERRIDE,
        )
        sys_tpl = Template(CLEANING_SYSTEM_PROMPT)
        system_prompt = sys_tpl.render(glossary=glossary)

        text = apply_layer_b(step["text_original"], patterns, parentheses, majuscules)
        user_prompt = Template(CLEANING_USER_PROMPT).render(text=text)
        proposed = await asyncio.to_thread(llm.ask, system_prompt, user_prompt)

        fallback = False
        if proposed.startswith("Erreur :"):
            proposed = apply_layer_a(text)
            fallback = True

        step["text_tts"] = proposed
        step["cleaning_status"] = "cleaned"
        await asyncio.to_thread(graph_app.update_state, config, {"steps": steps})

        return api_response({
            "step_id": step_id,
            "text_tts": proposed,
            "status": "cleaned",
            "fallback": fallback,
        })
    except Exception as exc:
        logger.error(f"Erreur nettoyage unitaire {step_id}: {exc}")
        return api_error("CLEAN_ERROR", str(exc), 500)


@router.get("/api/clean/diff/{step_id}")
async def clean_diff(step_id: str, request: Request, user=Depends(get_current_user)):
    """Voir le diff original/TTS."""
    thread_id = get_thread_id(request)
    _verify_session_owner(thread_id, user["user_id"])

    config = {"configurable": {"thread_id": thread_id}}
    state = await asyncio.to_thread(graph_app.get_state, config)
    steps = state.values.get("steps", []) if state and state.values else []

    step = next((s for s in steps if str(s["step_id"]) == step_id), None)
    if not step:
        return api_error("STEP_NOT_FOUND", f"Etape {step_id} introuvable", 404)

    orig = step.get("text_original", "")
    tts = step.get("text_tts", "")

    return api_response({
        "step_id": step_id,
        "text_original": orig,
        "text_tts": tts,
        "diff_html": _make_diff_html(orig, tts),
    })
