"""Routeur Generate — Endpoints onglet 5 (generation audio).

Endpoints :
- GET  /api/generate/summary  : Resume avant generation
- POST /api/generate          : Generation batch (SSE)
- POST /api/generate/sample   : Echantillon rapide (3 etapes)
"""
import asyncio
import json
import os
import re
import time

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from auth import get_current_user
from core.omnivoice_client import OmniVoiceBusyError, OmniVoiceTimeoutError
from routers.voices import _inject_owner_in_meta
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

# ---------------------------------------------------------------------------
# Modeles Pydantic
# ---------------------------------------------------------------------------


class GenerateRequest(BaseModel):
    fidelity: str = "quality"
    resume: bool = False
    force: bool = False


class SampleRequest(BaseModel):
    fidelity: str = "quality"


# ---------------------------------------------------------------------------
# Routeur
# ---------------------------------------------------------------------------

router = APIRouter()


@router.get("/api/generate/summary")
async def generate_summary(
    user=Depends(get_current_user),
    thread_id: str = Depends(get_thread_id)
):
    """Résumé avant génération : nombre d'étapes, voix utilisées, durée estimée."""
    _verify_session_owner(thread_id, user["user_id"])
    config = {"configurable": {"thread_id": thread_id}}
    state = await asyncio.to_thread(lambda: graph_app.get_state(config).values)
    steps = state.get("steps", [])
    assignments = state.get("assignments", {})
    instructions = state.get("instructions", {})

    texts = [s.get("text_tts") or s.get("text_original", "") for s in steps]
    est_duration = await asyncio.to_thread(vox_client.estimate_duration, texts)
    unique_voices = sorted(set(assignments.values())) if assignments else []

    return api_response({
        "total_steps": len(steps),
        "voices": unique_voices,
        "estimated_duration_s": int(est_duration),
        "has_instructions": bool(instructions)
    })


@router.post("/api/generate", responses={
    409: {"description": "Génération déjà en cours (GENERATE_IN_PROGRESS)"},
    503: {"description": "Moteur TTS occupé (TTS_BUSY)"},
    504: {"description": "Génération trop longue (TTS_TIMEOUT)"},
})
@limiter.limit("2/minute")
async def generate_production(
    request: Request,
    req: GenerateRequest,
    user=Depends(get_current_user),
    thread_id: str = Depends(get_thread_id)
):
    """Génération batch des fichiers audio via TTS (flux SSE)."""
    _verify_session_owner(thread_id, user["user_id"])
    # Verrou de concurrence (force=true libere un verrou ANCIEN uniquement)
    if req.force and thread_id in _generating_locks:
        from datetime import datetime, timezone
        locked_at = _generating_locks[thread_id]
        if locked_at.tzinfo is None:
            locked_at = locked_at.replace(tzinfo=timezone.utc)
        lock_age = (datetime.now(timezone.utc) - locked_at).total_seconds()
        if lock_age > 30:
            logger.warning(f"Liberation forcee du verrou generation pour {thread_id} (age={lock_age:.0f}s)")
            _unlock(_generating_locks, thread_id)
        else:
            logger.info(f"Verrou generation recent pour {thread_id} (age={lock_age:.0f}s), force ignore")
    if _is_locked(_generating_locks, thread_id):
        return api_response(
            error={"code": "GENERATE_IN_PROGRESS",
                   "message": "Une génération est déjà en cours sur cette session."},
            status_code=409
        )
    _lock(_generating_locks, thread_id)

    model = "0.6B" if req.fidelity == "speed" else "1.7B"
    config = {"configurable": {"thread_id": thread_id}}
    state = await asyncio.to_thread(lambda: graph_app.get_state(config).values)
    steps = state.get("steps", [])
    assignments = state.get("assignments", {})
    instructions = state.get("instructions", {})

    async def event_generator():
        output_dir = f"data/voices/{thread_id}"
        os.makedirs(output_dir, exist_ok=True)

        # Reprise : filtrer les etapes deja generees (generated_files est append-only)
        already_done = {str(g["step_id"]) for g in state.get("generated_files", [])} if req.resume else set()

        # Event initial immediat (evite timeout proxy Tailscale Funnel)
        yield {"event": "init", "data": json.dumps({"status": "starting"})}

        logger.info(f"Generation: {len(steps)} steps, already_done={len(already_done)}, assignments={len(assignments)}")

        # Grouper par (voix, langue, vitesse) pour le batch
        batch_groups = {}
        seq_items = []
        for step in steps:
            sid = str(step["step_id"])
            if sid in already_done:
                continue
            voice = assignments.get(sid, "Lea")
            text = step.get("text_tts") or step.get("text_original")
            lang = step.get("language_override", "fr") or "fr"
            instruct = instructions.get(sid, "")
            speed = step.get("speed_factor", 1.0)
            item = {"sid": sid, "voice": voice, "text": text, "lang": lang,
                    "instruct": instruct, "speed": speed}
            if instruct:
                seq_items.append(item)
            else:
                batch_groups.setdefault((voice, lang, speed), []).append(item)

        remaining = sum(len(items) for items in batch_groups.values()) + len(seq_items)
        total = remaining + len(already_done)
        done = len(already_done)

        logger.info(f"Generation: remaining={remaining}, batch_groups={len(batch_groups)}, seq_items={len(seq_items)}")

        if remaining == 0:
            yield {"event": "done", "data": json.dumps({
                "generated": total, "with_instruction": 0, "resumed": True
            })}
            return

        last_heartbeat = time.monotonic()

        # Batch par voix (chunks de 20 — PRD-UX-030 : eviter timeout sur voix clonees)
        for (voice, lang, speed), items in batch_groups.items():
            if await request.is_disconnected():
                logger.info(f"Client deconnecte, arret generation pour {thread_id}")
                return
            chunks = [items[i:i+20] for i in range(0, len(items), 20)]
            for cidx, chunk in enumerate(chunks, 1):
                yield {"event": "batch_start", "data": json.dumps({
                    "voice": voice, "count": len(chunk),
                    "chunk": cidx, "total_chunks": len(chunks),
                    "message": f"Batch {voice} ({len(chunk)} étapes)..."
                })}

                texts = [it["text"] for it in chunk]
                prefix = f"{voice.replace(' ', '_')}_{lang}_{speed}_{cidx}"
                spd = speed if speed != 1.0 else None
                try:
                    # Heartbeat pendant le batch (evite timeout navigateur)
                    batch_task = asyncio.ensure_future(asyncio.to_thread(
                        vox_client.batch_preset, texts, voice,
                        language=lang, model=model, output_dir=output_dir,
                        prefix=prefix, speed=spd
                    ))
                    while not batch_task.done():
                        await asyncio.sleep(10)
                        if not batch_task.done():
                            yield {"event": "heartbeat", "data": json.dumps({
                                "message": f"Génération {voice} en cours..."
                            })}
                    wav_paths = batch_task.result()
                except OmniVoiceBusyError:
                    yield {"event": "error", "data": json.dumps({
                        "code": "TTS_BUSY",
                        "message": "Moteur TTS occupé. Réessayez dans quelques secondes."
                    })}
                    return
                except OmniVoiceTimeoutError:
                    yield {"event": "error", "data": json.dumps({
                        "code": "TTS_TIMEOUT",
                        "message": f"Batch {voice} : génération trop longue (étape {done + 1}/{total})."
                    })}
                    return
                except Exception as exc:
                    logger.error(f"Erreur batch_preset {voice}: {exc}", exc_info=True)
                    wav_paths = []

                # Si batch echoue (liste vide), reporter chaque item comme echoue
                if not wav_paths:
                    wav_paths = [None] * len(chunk)

                for it, wav_path in zip(chunk, wav_paths):
                    audio_url = None
                    if wav_path:
                        filename = os.path.basename(wav_path)
                        audio_url = f"/api/audio/{filename}"
                        await asyncio.to_thread(graph_app.update_state, config, {"generated_files": [{
                            "step_id": it["sid"], "filename": filename,
                            "voice_name": it["voice"], "wav_path": str(wav_path),
                            "status": "done"
                        }]})
                    done += 1
                    progress = round((done / total) * 100)
                    yield {"event": "progress", "data": json.dumps({
                        "step_id": it["sid"], "index": done, "total": total,
                        "progress": progress, "voice": it["voice"],
                        "audio_url": audio_url,
                        "message": f"Étape {it['sid']} terminée ({done}/{total})"
                    })}

                # Heartbeat entre les chunks
                now = time.monotonic()
                if now - last_heartbeat > 15:
                    yield {"event": "heartbeat", "data": "{}"}
                    last_heartbeat = now

        # Sequentiel pour instructions emotionnelles
        for it in seq_items:
            if await request.is_disconnected():
                logger.info(f"Client deconnecte, arret generation pour {thread_id}")
                return
            yield {"event": "progress", "data": json.dumps({
                "step_id": it["sid"], "progress": round((done / total) * 100),
                "message": f"Génération étape {it['sid']} (instruction)..."
            })}

            spd = it["speed"] if it["speed"] != 1.0 else None
            try:
                instruct_task = asyncio.ensure_future(asyncio.to_thread(
                    vox_client.preset_instruct, it["text"], it["voice"], it["instruct"],
                    language=it["lang"], model=model, output_dir=output_dir, speed=spd
                ))
                while not instruct_task.done():
                    await asyncio.sleep(10)
                    if not instruct_task.done():
                        yield {"event": "heartbeat", "data": json.dumps({
                            "message": f"Génération {it['voice']} en cours..."
                        })}
                wav_path = instruct_task.result()
            except OmniVoiceBusyError:
                yield {"event": "error", "data": json.dumps({
                    "code": "TTS_BUSY",
                    "message": "Moteur TTS occupé. Réessayez dans quelques secondes."
                })}
                return
            except OmniVoiceTimeoutError:
                yield {"event": "error", "data": json.dumps({
                    "code": "TTS_TIMEOUT",
                    "message": f"Étape {it['sid']} : génération trop longue."
                })}
                return
            except Exception as exc:
                logger.error(f"Erreur preset_instruct {it['voice']}: {exc}", exc_info=True)
                wav_path = None

            audio_url = None
            if wav_path:
                filename = os.path.basename(wav_path)
                audio_url = f"/api/audio/{filename}"
                await asyncio.to_thread(graph_app.update_state, config, {"generated_files": [{
                    "step_id": it["sid"], "filename": filename,
                    "voice_name": it["voice"], "wav_path": str(wav_path),
                    "status": "done"
                }]})
            done += 1
            progress = round((done / total) * 100)
            yield {"event": "progress", "data": json.dumps({
                "step_id": it["sid"], "index": done, "total": total,
                "progress": progress, "voice": it["voice"],
                "audio_url": audio_url,
                "message": f"Étape {it['sid']} terminée ({done}/{total})"
            })}

            # Heartbeat
            now = time.monotonic()
            if now - last_heartbeat > 15:
                yield {"event": "heartbeat", "data": "{}"}
                last_heartbeat = now

        yield {"event": "done", "data": json.dumps({
            "generated": total, "with_instruction": len(seq_items)
        })}

    async def safe_generator():
        try:
            async for event in event_generator():
                yield event
        except Exception as exc:
            logger.error(f"Erreur generation SSE: {exc}")
            yield {"event": "error", "data": json.dumps({
                "message": f"Erreur de generation: {str(exc)}"
            })}
        finally:
            _unlock(_generating_locks, thread_id)

    return EventSourceResponse(safe_generator(), headers={
        "X-Accel-Buffering": "no",
        "Cache-Control": "no-cache, no-transform",
    })


@router.post("/api/generate/sample", responses={
    400: {"description": "Aucune étape (NO_STEPS)"},
    503: {"description": "Moteur TTS occupé (TTS_BUSY)"},
    504: {"description": "Génération trop longue (TTS_TIMEOUT)"},
})
@limiter.limit("5/minute")
async def generate_sample(
    request: Request,
    req: SampleRequest,
    user=Depends(get_current_user),
    thread_id: str = Depends(get_thread_id)
):
    """Échantillon rapide : génère 3 étapes (début, milieu, fin) pour pré-écoute."""
    _verify_session_owner(thread_id, user["user_id"])
    model = "0.6B" if req.fidelity == "speed" else "1.7B"
    config = {"configurable": {"thread_id": thread_id}}
    state = await asyncio.to_thread(lambda: graph_app.get_state(config).values)
    steps = state.get("steps", [])
    assignments = state.get("assignments", {})
    instructions = state.get("instructions", {})

    if not steps:
        return api_response(
            error={"code": "NO_STEPS", "message": "Aucune étape"},
            status_code=400
        )

    # Selectionner 3 etapes (debut, milieu, fin)
    if len(steps) <= 3:
        sample_steps = steps
    else:
        sample_steps = [steps[0], steps[len(steps) // 2], steps[-1]]

    output_dir = f"data/voices/{thread_id}"
    os.makedirs(output_dir, exist_ok=True)
    samples = []

    for step in sample_steps:
        sid = str(step["step_id"])
        voice = assignments.get(sid, "Lea")
        text = step.get("text_tts") or step.get("text_original")
        lang = step.get("language_override", "fr") or "fr"
        instruct = instructions.get(sid, "")
        speed = step.get("speed_factor", 1.0)
        spd = speed if speed != 1.0 else None

        try:
            if instruct:
                wav_path = await asyncio.to_thread(
                    vox_client.preset_instruct, text, voice, instruct,
                    language=lang, model=model, output_dir=output_dir, speed=spd
                )
            else:
                wav_path = await asyncio.to_thread(
                    vox_client.preset, text, voice,
                    language=lang, model=model, output_dir=output_dir, speed=spd
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
        samples.append({"step_id": sid, "audio_url": audio_url})

    return api_response({"samples": samples})


# ============================================================================
# Nouvel endpoint omnistudio — voix aléatoire (PRD v1.5 décision 15)
# ============================================================================


class RandomRequest(BaseModel):
    text: str
    language: str = "auto"


@router.post("/api/generate/random")
async def generate_random(
    req: RandomRequest,
    user=Depends(get_current_user),
    thread_id: str = Depends(get_thread_id),
):
    """Génère un audio avec une voix aléatoire cohérente (proxy OmniVoice POST /auto).

    Utile pour prototypage rapide sans sélection de voix (PRD décision 15).
    L'audio n'est PAS sauvegardé comme voix custom mais dans data/voices/{thread_id}/random/
    pour que l'endpoint /api/audio puisse le servir.
    """
    output_dir = f"data/voices/{thread_id}/random"
    os.makedirs(output_dir, exist_ok=True)
    try:
        filepath = await asyncio.to_thread(
            vox_client.random_auto, req.text, req.language, output_dir
        )
        if filepath is None:
            return api_error("RANDOM_FAILED", "Voix aléatoire échouée", status_code=500)

        filename = os.path.basename(filepath)
        return api_response({
            "audio_url": f"/api/audio/random/{filename}",
            "filename": filename,
            "message": "Voix aléatoire générée. Pour la conserver, cliquez sur « Ajouter à la bibliothèque ».",
        })
    except OmniVoiceBusyError:
        return api_error("TTS_BUSY", "Moteur TTS occupé, réessayez dans un moment", status_code=503)
    except OmniVoiceTimeoutError:
        return api_error("TTS_TIMEOUT", "Génération trop longue, réessayez", status_code=504)


class SaveRandomRequest(BaseModel):
    name: str
    filename: str  # basename du wav dans data/voices/{thread_id}/random/
    transcription: str = ""  # texte parlé dans le WAV (référence pour le clone)


_VOICE_NAME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9_-]{2,49}$")


@router.post("/api/voices/save-random")
@limiter.limit("5/minute")
async def save_random_voice(
    request: Request,
    req: SaveRandomRequest,
    user=Depends(get_current_user),
    thread_id: str = Depends(get_thread_id),
):
    """Conserve une voix aléatoire générée par /api/generate/random en voix custom.

    Utilise save_custom_voice source="clone" avec le WAV random comme audio
    de référence. Nom utilisateur validé par regex (PRD-SECURITE-031).
    """
    if not _VOICE_NAME_RE.match(req.name):
        return api_error("INVALID_NAME",
                         "Nom invalide. Format : lettre + 2-49 caractères alphanumériques, _ ou -.",
                         status_code=400)

    existing = await asyncio.to_thread(vox_client.get_custom_voice_details, req.name)
    if existing:
        return api_error("VOICE_EXISTS", f"La voix '{req.name}' existe déjà.", status_code=409)

    random_path = os.path.abspath(f"data/voices/{thread_id}/random/{req.filename}")
    random_root = os.path.abspath(f"data/voices/{thread_id}/random")
    if not random_path.startswith(random_root + os.sep):
        return api_error("INVALID_FILENAME", "Chemin non autorisé.", status_code=400)
    if not os.path.isfile(random_path):
        return api_error("FILE_NOT_FOUND",
                         "Fichier audio aléatoire introuvable. Régénérez la voix puis réessayez.",
                         status_code=404)

    transcription = req.transcription or "Bonjour, ceci est un test rapide avec une voix tirée au hasard."
    result = await asyncio.to_thread(
        vox_client.save_custom_voice,
        name=req.name, source="clone",
        audio_path=random_path, transcription=transcription,
    )
    if not result.get("ok"):
        return api_error("OMNIVOICE_ERROR", result.get("detail", "Erreur OmniVoice"), status_code=502)

    await asyncio.to_thread(_inject_owner_in_meta, req.name, user["user_id"])
    return api_response({"name": req.name, "source": "random-clone"})
