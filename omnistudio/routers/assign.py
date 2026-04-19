"""Routeur Assign — Endpoints onglet 4 (assignation voix/langue/vitesse).

Endpoints :
- GET  /api/assign                    : Charger les assignations
- POST /api/assign                    : Sauvegarder les assignations
- POST /api/assign/apply-all          : Appliquer une voix a toutes les etapes
- POST /api/assign/preview/{step_id}  : Pre-ecoute avec parametres
"""
import asyncio
import os
import re
import time
from typing import Dict

from fastapi import APIRouter, Depends, Request, HTTPException
from pydantic import BaseModel, field_validator

from auth import get_current_user
from core.audio import change_speed
from core.omnivoice_client import OmniVoiceBusyError, OmniVoiceTimeoutError
from dependencies import (
    graph_app,
    vox_client,
    api_response,
    api_error,
    get_thread_id,
    limiter,
    logger,
    _generating_locks,
    _exporting_locks,
    _is_locked,
    _lock,
    _unlock,
    _verify_session_owner,
    _touch_session,
)
from routers.voices import _read_voice_meta

# ---------------------------------------------------------------------------
# Constantes locales
# ---------------------------------------------------------------------------

# Voix natives OmniVoice (acceptent les instructions emotionnelles)
NATIVE_VOICE_NAMES = {
    "vivian", "serena", "uncle_fu", "dylan", "eric",
    "ryan", "aiden", "ono_anna", "sohee"
}

# ---------------------------------------------------------------------------
# Modeles Pydantic
# ---------------------------------------------------------------------------


class AssignRequest(BaseModel):
    assignments: Dict[str, str]
    instructions: Dict[str, str] = {}
    speeds: Dict[str, float] = {}
    languages: Dict[str, str] = {}

    @field_validator('assignments')
    @classmethod
    def validate_assignments(cls, v):
        """Valider que chaque voix respecte le format (prevention XSS)."""
        for step_id, voice in v.items():
            if voice and not re.match(r'^[a-zA-Z][a-zA-Z0-9_-]{2,49}$', voice):
                raise ValueError(f'Voix invalide pour étape {step_id}: {voice}')
        return v


class ApplyAllRequest(BaseModel):
    voice: str
    language: str = "fr"
    speed: float = 1.0
    instruction: str = ""
    selected_voices: list[str] = []

    @field_validator('voice')
    @classmethod
    def validate_voice(cls, v):
        """Valider format voix contre regex ^[a-zA-Z][a-zA-Z0-9_-]{2,49}$ (prevention XSS)."""
        if not v or not re.match(r'^[a-zA-Z][a-zA-Z0-9_-]{2,49}$', v):
            raise ValueError('Nom de voix invalide (format: lettres/chiffres/tirets/underscores, 3-50 car)')
        return v

    @field_validator('selected_voices')
    @classmethod
    def validate_selected_voices(cls, v):
        """Valider chaque voix dans la liste."""
        for voice in v:
            if not voice or not re.match(r'^[a-zA-Z][a-zA-Z0-9_-]{2,49}$', voice):
                raise ValueError(f'Voix invalide: {voice}')
        return v


class PreviewAssignRequest(BaseModel):
    voice: str
    language: str = "fr"
    speed: float = 1.0
    instruction: str = ""
    text: str = ""

    @field_validator('voice')
    @classmethod
    def validate_voice(cls, v):
        """Valider format voix contre regex ^[a-zA-Z][a-zA-Z0-9_-]{2,49}$ (prevention XSS)."""
        if not v or not re.match(r'^[a-zA-Z][a-zA-Z0-9_-]{2,49}$', v):
            raise ValueError('Nom de voix invalide (format: lettres/chiffres/tirets/underscores, 3-50 car)')
        return v


# ---------------------------------------------------------------------------
# Routeur
# ---------------------------------------------------------------------------

router = APIRouter()


@router.get("/api/assign")
async def get_assign(
    user=Depends(get_current_user),
    thread_id: str = Depends(get_thread_id)
):
    """Charger les assignations voix/langue/vitesse de la session."""
    _verify_session_owner(thread_id, user["user_id"])
    config = {"configurable": {"thread_id": thread_id}}
    state = await asyncio.to_thread(lambda: graph_app.get_state(config).values)
    steps = state.get("steps", [])
    assignments = state.get("assignments", {})
    instructions = state.get("instructions", {})

    # Voix disponibles filtrées par ownership (PRD v1.5 décision 7 + PRD-032)
    # Un user ne voit que : voix système + voix dont il est owner
    omnivoice_voices = await asyncio.to_thread(vox_client.get_voices)
    user_sub = user["user_id"]
    voices = []
    for v in omnivoice_voices:
        vtype = v.get("type", "native")
        if vtype == "native":
            voices.append({"name": v["name"], "type": "native", "system": True})
            continue
        if vtype != "custom":
            continue
        meta = _read_voice_meta(v["name"])
        is_system = meta.get("system", False)
        owner = meta.get("owner")
        if not is_system and owner != user_sub:
            continue  # voix d'un autre user, masquer
        voices.append({
            "name": v["name"],
            "type": "custom",
            "source": v.get("source", meta.get("source", "unknown")),
            "system": is_system,
        })
    # Filtrer sur selected_voices si defini et non vide
    selected = state.get("selected_voices", [])
    locked = state.get("locked_voices", [])
    if selected:
        allowed = set(selected) | set(locked)
        voices = [v for v in voices if v["name"] in allowed]
    voice_names = [v["name"] for v in voices]
    # Priorite : voix verrouillees dans la session, sinon premiere voix disponible
    default_voice = locked[-1] if locked else (voice_names[0] if voice_names else "Lea")

    rows = []
    for s in steps:
        sid = str(s["step_id"])
        rows.append({
            "step_id": sid,
            "text_preview": (s.get("text_tts") or s["text_original"])[:80],
            "text_full": s.get("text_tts") or s["text_original"],
            "language": s.get("language_override", "fr") or "fr",
            "voice": assignments.get(sid, default_voice),
            "speed": s.get("speed_factor", 1.0),
            "instruction": instructions.get(sid, "")
        })

    return api_response({
        "rows": rows,
        "voices": voices,
        "languages": ["fr", "en", "zh", "jp", "ko"],
        "default_voice": state.get("default_voice", ""),
    })


@router.post("/api/assign")
async def save_assign(
    req: AssignRequest,
    user=Depends(get_current_user),
    thread_id: str = Depends(get_thread_id)
):
    """Sauvegarder les assignations pour toutes les étapes."""
    _verify_session_owner(thread_id, user["user_id"])
    config = {"configurable": {"thread_id": thread_id}}
    state = await asyncio.to_thread(lambda: graph_app.get_state(config).values)
    steps = state.get("steps", [])

    # Filtrer instructions : uniquement pour voix natives
    clean_instructions = {}
    for sid, inst in req.instructions.items():
        voice = req.assignments.get(sid, "")
        if voice.lower() in NATIVE_VOICE_NAMES and inst:
            clean_instructions[sid] = inst

    # Mettre a jour speed_factor et language_override dans les steps
    for s in steps:
        sid = str(s["step_id"])
        if sid in req.speeds:
            s["speed_factor"] = req.speeds[sid]
        if sid in req.languages:
            s["language_override"] = req.languages[sid]

    await asyncio.to_thread(
        graph_app.update_state, config, {
            "assignments": req.assignments,
            "instructions": clean_instructions,
            "steps": steps
        }
    )

    return api_response({"saved": len(req.assignments)})


@router.post("/api/assign/apply-all")
async def apply_all(
    req: ApplyAllRequest,
    user=Depends(get_current_user),
    thread_id: str = Depends(get_thread_id)
):
    """Appliquer voix, langue, vitesse et instruction à toutes les étapes."""
    _verify_session_owner(thread_id, user["user_id"])
    config = {"configurable": {"thread_id": thread_id}}
    state = await asyncio.to_thread(lambda: graph_app.get_state(config).values)
    steps = state.get("steps", [])

    assignments = {}
    instructions = {}
    is_native = req.voice.lower() in NATIVE_VOICE_NAMES

    for s in steps:
        sid = str(s["step_id"])
        assignments[sid] = req.voice
        s["speed_factor"] = req.speed
        s["language_override"] = req.language
        if is_native and req.instruction:
            instructions[sid] = req.instruction

    update = {
        "assignments": assignments,
        "instructions": instructions,
        "steps": steps,
        "default_voice": req.voice,
    }
    # Pydantic v2 : utiliser model_fields_set pour verifier les champs explicitement fournis
    if hasattr(req, 'model_fields_set') and "selected_voices" in req.model_fields_set:
        update["selected_voices"] = req.selected_voices
    elif req.selected_voices:
        # Fallback : si non fourni explicitement mais non vide, inclure
        update["selected_voices"] = req.selected_voices
    await asyncio.to_thread(graph_app.update_state, config, update)

    return api_response({"applied": len(assignments), "voice": req.voice})


@router.post("/api/assign/preview/{step_id}")
@limiter.limit("10/minute")
async def preview_assign(
    request: Request,
    step_id: str,
    req: PreviewAssignRequest,
    user=Depends(get_current_user),
    thread_id: str = Depends(get_thread_id)
):
    """Pré-écouter une étape avec ses paramètres d'assignation."""
    _verify_session_owner(thread_id, user["user_id"])
    config = {"configurable": {"thread_id": thread_id}}
    state = await asyncio.to_thread(lambda: graph_app.get_state(config).values)
    steps = state.get("steps", [])
    step = next((s for s in steps if str(s["step_id"]) == step_id), None)

    if not step:
        return api_response(
            error={"code": "STEP_NOT_FOUND", "message": f"Etape {step_id} introuvable"},
            status_code=404
        )

    text = req.text.strip() if req.text.strip() else (step.get("text_tts") or step.get("text_original"))
    output_dir = f"data/voices/{thread_id}"
    os.makedirs(output_dir, exist_ok=True)

    is_native = req.voice.lower() in NATIVE_VOICE_NAMES

    try:
        if is_native and req.instruction:
            wav_path = await asyncio.to_thread(
                vox_client.preset_instruct, text, req.voice, req.instruction,
                language=req.language, output_dir=output_dir,
                timeout=vox_client.timeout_preview
            )
        else:
            wav_path = await asyncio.to_thread(
                vox_client.preset, text, req.voice,
                language=req.language, output_dir=output_dir,
                timeout=vox_client.timeout_preview
            )
    except OmniVoiceBusyError:
        return api_response(
            error={"code": "TTS_BUSY", "message": "Moteur TTS occupé. Réessayez dans quelques secondes."},
            status_code=503
        )
    except OmniVoiceTimeoutError:
        return api_response(
            error={"code": "TTS_TIMEOUT", "message": "Génération trop longue. Essayez un texte plus court."},
            status_code=504
        )

    if not wav_path:
        return api_response(
            error={"code": "OMNIVOICE_ERROR", "message": "Génération impossible"},
            status_code=502
        )

    # Post-traitement vitesse (SoX tempo, sans changer le pitch)
    if req.speed and req.speed != 1.0:
        await asyncio.to_thread(change_speed, wav_path, req.speed)

    filename = os.path.basename(wav_path)
    cache_bust = int(time.time())
    return api_response({"audio_url": f"/api/audio/{filename}?cb={cache_bust}"})
