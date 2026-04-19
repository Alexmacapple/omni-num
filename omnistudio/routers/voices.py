"""Routeur Voices — bibliotheque vocale, design, clone, preview (PRD-010, Phase 7).

Endpoints :
- GET /api/voices
- GET /api/voices/templates
- POST /api/voices/design-flow
- POST /api/voices/explore
- POST /api/voices/lock
- POST /api/voices/clone
- POST /api/voices/preview
- DELETE /api/voices/{name}
- POST /api/voices/{name}/rename
- POST /api/voices/export
- POST /api/voices/import
"""
import asyncio
import glob as _glob
import io
import json
import os
import re
import shutil
import zipfile
from pathlib import Path
from typing import Dict, Optional

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from pydantic import BaseModel
from starlette.responses import StreamingResponse

from auth import get_current_user
from config import LLM_MODEL_OVERRIDE, LLM_PROVIDER, LLM_TEMPERATURE, OMNIVOICE_VOICES_DIR
from core.voice_profiles import VOICE_TEMPLATES
from core.omnivoice_client import OmniVoiceBusyError, OmniVoiceTimeoutError
from dependencies import (
    api_error,
    api_response,
    design_app,
    get_thread_id,
    graph_app,
    limiter,
    logger,
    vox_client,
    _verify_session_owner,
    _touch_session,
)
from graph.subgraphs.design_loop import generate_voice_instruct

router = APIRouter()

# ---------------------------------------------------------------------------
# Constantes et helpers locaux (D2)
# ---------------------------------------------------------------------------

ALLOWED_AUDIO_EXT = (".wav", ".mp3", ".flac", ".ogg")

RESERVED_VOICE_NAMES = {
    "vivian", "serena", "uncle-fu", "uncle_fu", "dylan", "eric",
    "ryan", "aiden", "ono-anna", "ono_anna", "sohee",
}
# PRD-010 : strict regex pour éviter XSS — commence par lettre, 2-49 chars total
VOICE_NAME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9_-]{2,49}$")


def _validate_voice_name(name: str) -> Optional[str]:
    """Retourne un message d'erreur si le nom est invalide, None sinon."""
    if not name:
        return "Le nom est obligatoire"
    if not VOICE_NAME_RE.match(name):
        return "Le nom doit contenir 3-50 caracteres (minuscules, chiffres, tirets)"
    if name in RESERVED_VOICE_NAMES:
        return f"Le nom '{name}' est reserve (voix native)"
    return None


# ---------------------------------------------------------------------------
# Modeles Pydantic
# ---------------------------------------------------------------------------

class DesignFlowRequest(BaseModel):
    brief: Dict
    test_text: str = "Ceci est un test de timbre et de rythme pour notre nouvelle voix studio."
    temperature: Optional[float] = None


class ExploreRequest(BaseModel):
    voice_instruct: str
    test_text: str
    regenerate_instruct: bool = False


class LockRequest(BaseModel):
    name: str
    voice_instruct: str
    description: str = ""
    test_text: str = "Ceci est un test de la voix verrouillee."


class PreviewRequest(BaseModel):
    voice: str
    text: str
    language: str = "fr"


class RenameVoiceRequest(BaseModel):
    new_name: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

def _read_voice_meta(voice_name: str) -> dict:
    """Lit meta.json d'une voix custom sur le disque OmniVoice.

    Retourne un dict partiel (owner, system, source, description...).
    Si le fichier est absent ou malformé, retourne un dict vide.
    """
    meta_path = Path(OMNIVOICE_VOICES_DIR) / "custom" / voice_name / "meta.json"
    if not meta_path.exists():
        return {}
    try:
        with open(meta_path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        logger.debug(f"Failed to read voice meta {voice_name}: {e}")
        return {}


def _inject_owner_in_meta(voice_name: str, user_sub: str) -> bool:
    """Patch meta.json post-création pour ajouter owner=<JWT.sub>, system=false.

    PRD-032 : isolation ownership voix custom. Idempotent — si meta.json contient
    déjà owner, on respecte la valeur existante (système ou ancien propriétaire).
    Retourne True si patch appliqué, False si meta.json absent ou erreur I/O.
    """
    meta_path = Path(OMNIVOICE_VOICES_DIR) / "custom" / voice_name / "meta.json"
    if not meta_path.exists():
        return False
    try:
        with open(meta_path, encoding="utf-8") as f:
            meta = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        logger.warning(f"Failed to read voice meta for {voice_name}: {e}")
        meta = {}
    if meta.get("system") is True:
        return False  # Ne jamais écraser une voix système
    meta.setdefault("owner", user_sub)
    meta["system"] = False
    try:
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2, ensure_ascii=False)
        return True
    except OSError as e:
        logger.error(f"Failed to write voice meta for {voice_name}: {e}")
        return False


@router.get("/api/voices")
async def list_voices(
    user=Depends(get_current_user),
    thread_id: str = Depends(get_thread_id),
):
    """Liste les voix accessibles à l'utilisateur.

    Filtre PRD v1.5 décision 7 (traite PRD-032) :
    - Voix custom : owner == user.sub OU system == true
    - Voix natives OmniVoice (inexistantes en pratique) : visibles à tous
    """
    _verify_session_owner(thread_id, user["user_id"])
    omnivoice_voices = await asyncio.to_thread(vox_client.get_voices)
    user_sub = user["user_id"]

    voices = []
    for v in omnivoice_voices:
        if v.get("type") == "custom":
            # Enrichir avec le meta.json local (owner, system)
            meta = _read_voice_meta(v["name"])
            owner = meta.get("owner")
            is_system = meta.get("system", False)

            # Filtrage ownership (PRD décision 7)
            if not is_system and owner != user_sub:
                continue  # voix d'un autre utilisateur, skip

            voices.append({
                "name": v["name"], "type": "custom",
                "source": v.get("source", meta.get("source", "unknown")),
                "description": v.get("description", meta.get("description", "")),
                "gender": v.get("gender", ""),
                "system": is_system,
                "owner": owner if not is_system else None,
            })
        else:
            # Voix native OmniVoice (en pratique il n'y en a pas, OmniVoice n'a pas de natives)
            voices.append({
                "name": v["name"], "type": "native",
                "description": v.get("description", f"Voix native {v['name']}"),
                "gender": v.get("gender", ""),
                "system": True,
                "owner": None,
            })

    return api_response({"voices": voices, "total": len(voices)})


@router.get("/api/voices/templates")
async def list_voice_templates(user=Depends(get_current_user)):
    """Lister les templates de voix (presets pour le design)."""
    return api_response({"templates": VOICE_TEMPLATES})


@router.post("/api/voices/design-flow")
@limiter.limit("5/minute")
async def voices_design_flow(
    request: Request,
    req: DesignFlowRequest,
    user=Depends(get_current_user),
    thread_id: str = Depends(get_thread_id),
):
    """Brief vocal -> voice_instruct (LLM) + audio exploratoire."""
    _verify_session_owner(thread_id, user["user_id"])
    config = {"configurable": {"thread_id": thread_id}}
    main_state = await asyncio.to_thread(lambda: graph_app.get_state(config).values)

    design_state = {
        "brief": req.brief,
        "llm_provider": main_state.get("llm_provider", LLM_PROVIDER),
        "llm_model_override": main_state.get("llm_model_override", LLM_MODEL_OVERRIDE),
        "llm_temperature": req.temperature if req.temperature is not None else main_state.get("llm_temperature", LLM_TEMPERATURE),
    }

    # Lancer le subgraphe design (interrupt_before=human_review)
    try:
        result = await asyncio.to_thread(design_app.invoke, design_state, config)
        voice_instruct = result.get("voice_instruct", "")
        wav_paths = result.get("wav_paths", [])
    except Exception:
        # Fallback : appel direct generate_voice_instruct
        result = await asyncio.to_thread(generate_voice_instruct, design_state, config)
        voice_instruct = result.get("voice_instruct", "")
        wav_paths = []

    # Persister dans le state principal
    await asyncio.to_thread(graph_app.update_state, config, {"brief": req.brief, "voice_instruct": voice_instruct})

    # Audio exploratoire
    output_dir = f"data/voices/{thread_id}"
    os.makedirs(output_dir, exist_ok=True)
    audio_url = None

    if wav_paths:
        src = wav_paths[-1]
        filename = os.path.basename(src)
        dest = os.path.join(output_dir, filename)
        if src != dest and os.path.exists(src):
            shutil.copy2(src, dest)
        audio_url = f"/api/audio/{filename}"
    else:
        wav_path = await asyncio.to_thread(
            vox_client.design, req.test_text, voice_instruct, "fr", output_dir
        )
        if wav_path:
            audio_url = f"/api/audio/{os.path.basename(wav_path)}"

    return api_response({
        "voice_instruct": voice_instruct,
        "audio_url": audio_url,
        "iteration": result.get("iteration", 1),
    })


@router.post("/api/voices/explore")
@limiter.limit("10/minute")
async def voices_explore(
    request: Request,
    req: ExploreRequest,
    user=Depends(get_current_user),
    thread_id: str = Depends(get_thread_id),
):
    """Regenerer un audio volatile (meme ou nouveau voice_instruct)."""
    _verify_session_owner(thread_id, user["user_id"])
    config = {"configurable": {"thread_id": thread_id}}
    voice_instruct = req.voice_instruct

    if req.regenerate_instruct:
        main_state = await asyncio.to_thread(lambda: graph_app.get_state(config).values)
        design_state = {
            "brief": main_state.get("brief", {}),
            "voice_instruct": voice_instruct,
            "llm_provider": main_state.get("llm_provider", LLM_PROVIDER),
            "llm_model_override": main_state.get("llm_model_override", LLM_MODEL_OVERRIDE),
            "llm_temperature": main_state.get("llm_temperature", LLM_TEMPERATURE),
            "iteration": main_state.get("iteration", 0),
        }
        result = await asyncio.to_thread(generate_voice_instruct, design_state, config)
        voice_instruct = result.get("voice_instruct", voice_instruct)

    await asyncio.to_thread(graph_app.update_state, config, {"voice_instruct": voice_instruct})

    # Generer un nouveau WAV volatile
    output_dir = f"data/voices/{thread_id}"
    os.makedirs(output_dir, exist_ok=True)

    # Purge des WAV d'exploration precedents
    for old_wav in _glob.glob(f"{output_dir}/explore_*.wav"):
        os.remove(old_wav)

    wav_path = await asyncio.to_thread(
        vox_client.design, req.test_text, voice_instruct, "fr", output_dir
    )

    audio_url = None
    if wav_path:
        audio_url = f"/api/audio/{os.path.basename(wav_path)}"
        await asyncio.to_thread(graph_app.update_state, config, {"wav_paths": [wav_path]})

    # Historique (max 5)
    state = await asyncio.to_thread(lambda: graph_app.get_state(config).values)
    all_paths = state.get("wav_paths", [])
    history = [f"/api/audio/{os.path.basename(p)}" for p in all_paths[-5:]]

    return api_response({
        "voice_instruct": voice_instruct,
        "audio_url": audio_url,
        "iteration": state.get("iteration", 0),
        "history": history,
    })


@router.post("/api/voices/lock", responses={
    400: {"description": "Nom invalide (INVALID_NAME)"},
    409: {"description": "Voix existante (VOICE_EXISTS)"},
    502: {"description": "Erreur OmniVoice (OMNIVOICE_ERROR)"},
    503: {"description": "Moteur TTS occupé (TTS_BUSY)"},
    504: {"description": "Génération trop longue (TTS_TIMEOUT)"},
})
@limiter.limit("5/minute")
async def voices_lock(
    request: Request,
    req: LockRequest,
    user=Depends(get_current_user),
    thread_id: str = Depends(get_thread_id),
):
    """Verrouiller une voix volatile en voix persistante."""
    _verify_session_owner(thread_id, user["user_id"])
    err = _validate_voice_name(req.name)
    if err:
        return api_response(error={"code": "INVALID_NAME", "message": err}, status_code=400)

    existing = await asyncio.to_thread(vox_client.get_custom_voice_details, req.name)
    if existing:
        return api_response(error={"code": "VOICE_EXISTS",
            "message": f"La voix '{req.name}' existe déjà."}, status_code=409)

    # Fidélité sonore : cloner la voix depuis le DERNIER WAV d'exploration.
    # Sinon source=design produirait un nouveau tirage ≠ de celui écouté.
    # Si aucun wav exploration disponible → fallback source=design (tirage neuf).
    config = {"configurable": {"thread_id": thread_id}}
    state = await asyncio.to_thread(lambda: graph_app.get_state(config).values)
    wav_paths = state.get("wav_paths", [])
    last_wav = wav_paths[-1] if wav_paths else None
    use_clone = last_wav and os.path.isfile(last_wav)

    if use_clone:
        logger.info("voices/lock: clone depuis %s (fidélité sonore)", last_wav)
        result = await asyncio.to_thread(
            vox_client.save_custom_voice,
            name=req.name, source="clone",
            audio_path=last_wav, transcription=req.test_text,
        )
    else:
        logger.info("voices/lock: pas de WAV exploration, fallback source=design")
        result = await asyncio.to_thread(
            vox_client.save_custom_voice,
            name=req.name, source="design", voice_instruct=req.voice_instruct,
        )
    if not result.get("ok"):
        return api_response(error={"code": "OMNIVOICE_ERROR",
            "message": result.get("detail", "Erreur OmniVoice")}, status_code=502)

    # PRD-032 : injection automatique owner=<JWT.sub> dans meta.json
    await asyncio.to_thread(_inject_owner_in_meta, req.name, user["user_id"])

    # Test immediat avec la voix verrouillee
    output_dir = f"data/voices/{thread_id}"
    os.makedirs(output_dir, exist_ok=True)
    try:
        wav_path = await asyncio.to_thread(
            vox_client.preset, req.test_text, req.name, "fr", "1.7B", output_dir,
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
    audio_url = f"/api/audio/{os.path.basename(wav_path)}" if wav_path else None

    # State LangGraph : locked_voices a un reducteur add -> uniquement le nouvel element
    await asyncio.to_thread(graph_app.update_state, config, {
        "locked_voices": [req.name], "locked_name": req.name, "decision": "lock",
    })

    return api_response({
        "name": req.name, "status": "locked",
        "audio_url": audio_url,
        "source": "clone" if use_clone else "design",
    })


@router.post("/api/voices/clone")
@limiter.limit("3/minute")
async def voices_clone(
    request: Request,
    audio: UploadFile = File(...),
    transcription: str = Form(...),
    name: str = Form(...),
    model: str = Form("1.7B"),
    description: str = Form(""),
    test_text: str = Form("Ceci est un test de la voix clonee."),
    user=Depends(get_current_user),
    thread_id: str = Depends(get_thread_id),
):
    """Cloner une voix depuis un audio de reference."""
    _verify_session_owner(thread_id, user["user_id"])
    if not name or not name.strip():
        return api_response(error={"code": "CLONE_INVALID", "message": "Le nom est requis"}, status_code=400)
    if not transcription or not transcription.strip():
        return api_response(error={"code": "CLONE_INVALID", "message": "La transcription est requise"}, status_code=400)

    err = _validate_voice_name(name)
    if err:
        return api_response(error={"code": "INVALID_NAME", "message": err}, status_code=400)

    if not audio.filename or not audio.filename.lower().endswith(ALLOWED_AUDIO_EXT):
        return api_response(error={"code": "INVALID_FORMAT",
            "message": f"Format audio non supporte. Acceptes : {', '.join(ALLOWED_AUDIO_EXT)}"}, status_code=400)

    upload_dir = f"data/voices/{thread_id}"
    os.makedirs(upload_dir, exist_ok=True)
    ext = os.path.splitext(audio.filename)[1]
    ref_path = os.path.join(upload_dir, f"ref_{name}{ext}")

    with open(ref_path, "wb") as f:
        content = await audio.read()
        f.write(content)

    try:
        result = await asyncio.to_thread(
            vox_client.save_custom_voice,
            name=name, source="clone", audio_path=ref_path,
            transcription=transcription, model=model,
        )
        if not result.get("ok"):
            return api_response(error={"code": "OMNIVOICE_ERROR",
                "message": result.get("detail", "Erreur de clonage")}, status_code=502)

        # PRD-032 : injection automatique owner=<JWT.sub> dans meta.json
        await asyncio.to_thread(_inject_owner_in_meta, name, user["user_id"])

        try:
            wav_path = await asyncio.to_thread(
                vox_client.preset, test_text, name, "fr", model, upload_dir,
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
        audio_url = f"/api/audio/{os.path.basename(wav_path)}" if wav_path else None

        config = {"configurable": {"thread_id": thread_id}}
        await asyncio.to_thread(graph_app.update_state, config, {"locked_voices": [name]})

        return api_response({
            "name": name, "status": "locked",
            "audio_url": audio_url, "source": "clone", "model": model,
        })
    finally:
        if os.path.exists(ref_path):
            os.remove(ref_path)


@router.post("/api/voices/preview")
@limiter.limit("10/minute")
async def voices_preview(
    request: Request,
    req: PreviewRequest,
    user=Depends(get_current_user),
    thread_id: str = Depends(get_thread_id),
):
    """Pre-ecoute d'une voix (native ou verrouillee)."""
    _verify_session_owner(thread_id, user["user_id"])
    output_dir = f"data/voices/{thread_id}"
    os.makedirs(output_dir, exist_ok=True)

    try:
        wav_path = await asyncio.to_thread(
            vox_client.preset, req.text, req.voice, req.language, "1.7B", output_dir,
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
        return api_response(error={"code": "OMNIVOICE_ERROR",
            "message": "Impossible de générer l'audio."}, status_code=502)

    return api_response({"audio_url": f"/api/audio/{os.path.basename(wav_path)}"})


@router.delete("/api/voices/{name}")
async def voices_delete(
    name: str,
    user=Depends(get_current_user),
    thread_id: str = Depends(get_thread_id),
):
    """Supprimer une voix custom.

    Vérifie ownership (PRD v1.5 décision 7) :
    - Voix `system: true` : jamais supprimable (403)
    - Voix d'un autre utilisateur : 403
    """
    _verify_session_owner(thread_id, user["user_id"])

    # Check ownership via meta.json
    meta = _read_voice_meta(name)
    if meta.get("system") is True:
        return api_error(
            "VOICE_SYSTEM_PROTECTED",
            "Voix système non modifiable (partagée par tous les utilisateurs).",
            status_code=403,
        )
    owner = meta.get("owner")
    if owner and owner != user["user_id"]:
        return api_error(
            "VOICE_NOT_OWNER",
            f"Voix '{name}' appartient à un autre utilisateur.",
            status_code=403,
        )

    config = {"configurable": {"thread_id": thread_id}}
    state = await asyncio.to_thread(lambda: graph_app.get_state(config).values)
    assignments = state.get("assignments", {})
    # Croiser avec les etapes existantes pour ignorer les assignations orphelines
    existing_step_ids = {str(s["step_id"]) for s in state.get("steps", [])}
    assigned_steps = [
        sid for sid, vname in assignments.items()
        if vname == name and sid in existing_step_ids
    ]

    if assigned_steps:
        return api_response(error={"code": "VOICE_IN_USE",
            "message": f"Cette voix est assignée aux étapes {', '.join(assigned_steps)}"}, status_code=409)

    ok = await asyncio.to_thread(vox_client.delete_custom_voice, name)
    if not ok:
        return api_response(error={"code": "OMNIVOICE_ERROR",
            "message": f"Impossible de supprimer la voix '{name}'"}, status_code=502)

    return api_response({"name": name, "deleted": True})


@router.post("/api/voices/{name}/rename")
async def voices_rename(
    name: str,
    req: RenameVoiceRequest,
    user=Depends(get_current_user),
    thread_id: str = Depends(get_thread_id),
):
    """Renommer une voix custom (dossier + meta + assignations)."""
    _verify_session_owner(thread_id, user["user_id"])
    new_name = req.new_name.strip()

    # Validation du nouveau nom
    err = _validate_voice_name(new_name)
    if err:
        return api_error("INVALID_NAME", err, 400)

    voices_dir = Path(OMNIVOICE_VOICES_DIR)
    old_dir = voices_dir / "custom" / name
    new_dir = voices_dir / "custom" / new_name

    if not old_dir.is_dir():
        return api_error("VOICE_NOT_FOUND", f"Voix '{name}' introuvable.", 404)

    if new_dir.exists():
        return api_error("VOICE_EXISTS", f"Le nom '{new_name}' existe déjà.", 409)

    # Renommer le dossier et mettre a jour meta.json
    def do_rename():
        shutil.copytree(old_dir, new_dir)
        meta_path = new_dir / "meta.json"
        if meta_path.exists():
            with open(meta_path) as f:
                meta = json.load(f)
            meta["name"] = new_name
            with open(meta_path, "w") as f:
                json.dump(meta, f, indent=2)
        # Supprimer l'ancien dossier du disque
        shutil.rmtree(old_dir)
        # Recharger le registre OmniVoice (rescanne le disque)
        vox_client.reload_custom_voices()

    await asyncio.to_thread(do_rename)

    # Mettre a jour les assignations dans le LangGraph state
    config = {"configurable": {"thread_id": thread_id}}
    state = await asyncio.to_thread(lambda: graph_app.get_state(config).values)
    assignments = state.get("assignments", {})
    updated_assignments = {}
    for step_id, voice in assignments.items():
        updated_assignments[step_id] = new_name if voice == name else voice

    if updated_assignments != assignments:
        await asyncio.to_thread(
            lambda: graph_app.update_state(config, {"assignments": updated_assignments})
        )

    logger.info(f"Voix renommee: {name} -> {new_name} (thread {thread_id})")
    return api_response({"old_name": name, "new_name": new_name})


# --- Import/Export ZIP voix custom ---

@router.post("/api/voices/export")
async def voices_export(user=Depends(get_current_user)):
    """Exporter les voix custom en ZIP."""
    voices_dir = Path(OMNIVOICE_VOICES_DIR) / "custom"
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        if voices_dir.exists():
            for voice_dir in voices_dir.iterdir():
                if voice_dir.is_dir():
                    meta = voice_dir / "meta.json"
                    prompt = voice_dir / "prompt.pt"
                    if meta.exists() and prompt.exists():
                        zf.write(meta, f"{voice_dir.name}/meta.json")
                        zf.write(prompt, f"{voice_dir.name}/prompt.pt")
    zip_buffer.seek(0)
    return StreamingResponse(
        zip_buffer, media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=voix-custom.zip"},
    )


@router.post("/api/voices/import")
async def voices_import(
    file: UploadFile = File(...),
    overwrite: bool = False,
    user=Depends(get_current_user),
):
    """Importer des voix custom depuis un ZIP.

    PRD-032 : injecte automatiquement owner=<JWT.sub> dans chaque meta.json.
    """
    voices_dir = Path(OMNIVOICE_VOICES_DIR) / "custom"
    imported = []

    content = await file.read()
    with zipfile.ZipFile(io.BytesIO(content)) as zf:
        folders = {n.split("/")[0] for n in zf.namelist() if "/" in n}
        for folder in folders:
            if ".." in folder or folder.startswith("/"):
                continue
            dest = voices_dir / folder
            # Protection Zip Slip (PRD-029)
            if not dest.resolve().is_relative_to(voices_dir.resolve()):
                continue
            meta_path = f"{folder}/meta.json"
            prompt_path = f"{folder}/prompt.pt"
            if meta_path not in zf.namelist() or prompt_path not in zf.namelist():
                continue
            if dest.exists() and not overwrite:
                continue
            dest.mkdir(parents=True, exist_ok=True)
            meta_bytes = zf.read(meta_path)
            (dest / "meta.json").write_bytes(meta_bytes)
            (dest / "prompt.pt").write_bytes(zf.read(prompt_path))

            # PRD-032 : injecter owner=<JWT.sub> dans chaque voix importée
            await asyncio.to_thread(_inject_owner_in_meta, folder, user["user_id"])
            imported.append(folder)

    return api_response({"imported": imported, "count": len(imported)})


# ============================================================================
# Nouveaux endpoints omnistudio (PRD v1.5 décisions 11, 12, 5 : tags, attributes, transcribe)
# ============================================================================


@router.get("/api/voices/tags")
async def get_voice_tags(user=Depends(get_current_user)):
    """Retourne les 13 tags émotionnels non-verbaux (proxy OmniVoice GET /tags).

    Utilisé par la palette DSFR dans onglets 2 et 3 (PRD décision 11).
    """
    tags = await asyncio.to_thread(vox_client.get_tags)
    return api_response({"tags": tags, "count": len(tags)})


@router.get("/api/voices/design-attributes")
async def get_design_attributes_endpoint(user=Depends(get_current_user)):
    """Retourne les attributs Voice Design 6 catégories (proxy OmniVoice).

    Utilisé pour peupler dynamiquement les selects Guidé (PRD décision 12).
    """
    attrs = await asyncio.to_thread(vox_client.get_design_attributes)
    return api_response(attrs)


@router.post("/api/voices/transcribe")
async def transcribe_endpoint(
    audio: UploadFile = File(...),
    language: str = Form("auto"),
    user=Depends(get_current_user),
):
    """Transcrit un audio via Whisper intégré OmniVoice (proxy POST /transcribe).

    Utilisé par l'onglet 3 Clone pour remplir automatiquement reference_text (PRD décision 5).
    """
    temp_path = f"temp/transcribe_{user['user_id']}_{int(asyncio.get_running_loop().time()*1000)}.wav"
    os.makedirs("temp", exist_ok=True)
    with open(temp_path, "wb") as f:
        f.write(await audio.read())

    try:
        text = await asyncio.to_thread(vox_client.transcribe_audio, temp_path, language)
        if text is None:
            return api_error("TRANSCRIBE_FAILED", "Transcription impossible", status_code=500)
        return api_response({"text": text})
    finally:
        try:
            os.unlink(temp_path)
        except OSError:
            pass
