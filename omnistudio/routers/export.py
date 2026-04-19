"""Routeur Export — Endpoints onglet 6 (post-traitement et export ZIP).

Endpoints :
- POST /api/export           : Export ZIP avec post-traitement (SSE)
- GET  /api/export/download   : Telecharger le ZIP (auth hybride)
"""
import asyncio
import json
import os
import shutil
import time
import zipfile
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from slugify import slugify
from sse_starlette.sse import EventSourceResponse
from starlette.responses import FileResponse

from auth import get_current_user, validate_token
from core.audio import process_audio, concatenate_audio, convert_to_mp3
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
    THREAD_ID_RE,
    _verify_session_owner,
    _touch_session,
)

# ---------------------------------------------------------------------------
# Modeles Pydantic
# ---------------------------------------------------------------------------


class ExportRequest(BaseModel):
    normalize: bool = True
    stereo: bool = True
    sample_rate: int = 48000
    bit_depth: int = 24
    make_unique: bool = False
    silence_duration: float = 1.0
    output_format: str = "wav"
    # PRD v1.5 décision 16 — sous-titres SRT via faster-whisper (Phase 3ter)
    include_subtitles: bool = False
    subtitle_format: str = "standard"  # standard | word | shorts | multiline


# Singleton SubtitleClient (lazy load du modèle ~800 Mo au premier usage)
_subtitle_client = None


def _get_subtitle_client():
    """Instancie SubtitleClient au premier appel. Retourne None si import échoue."""
    global _subtitle_client
    if _subtitle_client is not None:
        return _subtitle_client
    try:
        from core.subtitle_client import SubtitleClient
        _subtitle_client = SubtitleClient()
        return _subtitle_client
    except ImportError:
        logger.warning("SubtitleClient indisponible (faster-whisper non installé). Sous-titres désactivés.")
        return None


# ---------------------------------------------------------------------------
# Routeur
# ---------------------------------------------------------------------------

router = APIRouter()


@router.post("/api/export", responses={
    400: {"description": "Aucun fichier généré (NO_FILES)"},
    409: {"description": "Export déjà en cours (EXPORT_IN_PROGRESS)"},
})
@limiter.limit("2/minute")
async def export_zip(
    request: Request,
    req: ExportRequest,
    user=Depends(get_current_user),
    thread_id: str = Depends(get_thread_id)
):
    """Export ZIP avec post-traitement audio : normalisation, stéréo, 48 kHz (flux SSE)."""
    _verify_session_owner(thread_id, user["user_id"])
    # Verrou de concurrence
    if _is_locked(_exporting_locks, thread_id):
        return api_response(
            error={"code": "EXPORT_IN_PROGRESS",
                   "message": "Un export est déjà en cours sur cette session."},
            status_code=409
        )
    _lock(_exporting_locks, thread_id)

    config = {"configurable": {"thread_id": thread_id}}
    state = await asyncio.to_thread(lambda: graph_app.get_state(config).values)
    steps = state.get("steps", [])
    # Filtrer generated_files contre steps : les etapes supprimees
    # restent dans generated_files (reducer add) mais ne doivent pas etre exportees
    valid_step_ids = {str(s["step_id"]) for s in steps}
    generated = [g for g in state.get("generated_files", []) if str(g["step_id"]) in valid_step_ids]
    cleaning_log = state.get("cleaning_log", [])
    instructions = state.get("instructions", {})
    assignments = state.get("assignments", {})

    if not generated:
        _unlock(_exporting_locks, thread_id)
        return api_response(
            error={"code": "NO_FILES",
                   "message": "Aucun fichier audio généré. Lancez d'abord la génération."},
            status_code=400
        )

    async def event_generator():
        last_heartbeat = time.monotonic()

        # Repertoires
        export_base = os.path.abspath(f"export/{thread_id}")
        audio_dir = f"{export_base}/audio"
        if os.path.exists(export_base):
            shutil.rmtree(export_base)
        os.makedirs(audio_dir, exist_ok=True)

        audio_config = {
            "normalize": req.normalize, "stereo": req.stereo,
            "rate": req.sample_rate, "bit_depth": req.bit_depth
        }

        # Voix pour tracabilite
        omnivoice_voices = await asyncio.to_thread(vox_client.get_voices)
        voice_map = {v.get("name"): v for v in omnivoice_voices if v.get("name")}

        # Tri securise : step_id peut etre non-numerique
        def safe_sort_key(x):
            try:
                return int(x["step_id"])
            except (ValueError, TypeError):
                return 0

        # Deduplication : le reducer LangGraph `add` accumule les entrees,
        # on garde uniquement la derniere generation par step_id
        seen = {}
        for item in generated:
            seen[item["step_id"]] = item
        sorted_generated = sorted(seen.values(), key=safe_sort_key)
        total = len(sorted_generated)
        processed_files = []
        skipped = []

        # Post-traitement
        for i, item in enumerate(sorted_generated):
            if await request.is_disconnected():
                logger.info(f"Client deconnecte, arret export pour {thread_id}")
                return
            sid = item["step_id"]
            raw = item["wav_path"]
            if not os.path.exists(raw):
                raw = os.path.abspath(raw)
            if not os.path.exists(raw):
                skipped.append(sid)
                continue

            step_info = next((s for s in steps if str(s["step_id"]) == str(sid)), {})
            txt = step_info.get("text_tts") or step_info.get("text_original") or "step"
            slug = slugify(txt, max_length=40)
            try:
                prefix = f"{int(sid):02d}"
            except (ValueError, TypeError):
                prefix = str(sid)
            fname = f"etape-{prefix}-{slug}.wav"
            fpath = f"{audio_dir}/{fname}"

            progress = round(((i + 1) / total) * 85)
            yield {"event": "progress", "data": json.dumps({
                "step": "post-traitement", "index": i + 1, "total": total,
                "progress": progress,
                "message": f"Post-traitement etape {sid} ({i + 1}/{total})..."
            })}

            await asyncio.to_thread(process_audio, raw, fpath, audio_config)
            # Vérifier que le fichier a été créé
            if not os.path.exists(fpath):
                logger.warning(f"Fichier audio non créé après process_audio: {fpath}")
                skipped.append(sid)
                continue
            # Conversion MP3 si demandee
            if req.output_format == "mp3":
                mp3_path = fpath.rsplit(".", 1)[0] + ".mp3"
                ok = await asyncio.to_thread(convert_to_mp3, fpath, mp3_path)
                if ok and os.path.exists(mp3_path):
                    os.unlink(fpath)
                    fpath = mp3_path
                elif not ok:
                    logger.warning(f"Conversion MP3 échouée pour {fpath}, garde WAV")
            processed_files.append(fpath)

            # Sous-titres SRT (PRD v1.5 décision 16) — opt-in via include_subtitles
            if req.include_subtitles:
                client = _get_subtitle_client()
                if client is not None:
                    # Déterminer la langue avec priorité: override > assignment > défaut "fr"
                    lang = step_info.get("language_override")
                    if not lang:
                        assignment = assignments.get(str(sid), {})
                        if isinstance(assignment, dict):
                            lang = assignment.get("language")
                    lang = lang or "fr"
                    try:
                        segments = await asyncio.to_thread(client.transcribe, fpath, lang)
                    except Exception as e:
                        logger.warning(f"Transcription échouée étape {sid}: {e}")
                        segments = None
                    if segments:
                        fmt = req.subtitle_format if req.subtitle_format in {"standard", "word", "shorts", "multiline"} else "standard"
                        gen_method = {
                            "standard": client.generate_srt,
                            "word": client.generate_word_srt,
                            "shorts": client.generate_shorts_srt,
                            "multiline": client.generate_multiline_srt,
                        }[fmt]
                        srt_text = gen_method(segments)
                        srt_path = fpath.rsplit(".", 1)[0] + ".srt"
                        try:
                            with open(srt_path, "w", encoding="utf-8") as srt_f:
                                srt_f.write(srt_text)
                        except OSError as e:
                            logger.warning(f"Écriture SRT échouée étape {sid}: {e}")

            now = time.monotonic()
            if now - last_heartbeat > 15:
                yield {"event": "heartbeat", "data": "{}"}
                last_heartbeat = now

        # Concatenation optionnelle
        if req.make_unique and processed_files:
            yield {"event": "progress", "data": json.dumps({
                "step": "concatenation", "progress": 90,
                "message": f"Concatenation de {len(processed_files)} fichiers..."
            })}
            ext = "mp3" if req.output_format == "mp3" else "wav"
            unique_path = f"{audio_dir}/narration-complete.{ext}"
            if req.output_format == "mp3":
                # Concatener en WAV temporaire puis convertir
                tmp_wav = f"{audio_dir}/narration-complete.tmp.wav"
                await asyncio.to_thread(
                    concatenate_audio, processed_files, tmp_wav,
                    req.silence_duration, audio_config
                )
                ok = await asyncio.to_thread(convert_to_mp3, tmp_wav, unique_path)
                if ok and os.path.exists(unique_path):
                    os.unlink(tmp_wav)
                else:
                    # Fallback : garder le WAV concatene
                    unique_path = tmp_wav
            else:
                await asyncio.to_thread(
                    concatenate_audio, processed_files, unique_path,
                    req.silence_duration, audio_config
                )

        # Documents Markdown
        yield {"event": "progress", "data": json.dumps({
            "step": "documents", "progress": 95,
            "message": "Generation des documents..."
        })}

        with open(f"{export_base}/SCRIPT_PAROLES.md", "w", encoding="utf-8") as f:
            f.write(f"# Script de Paroles — OmniStudio\n\n"
                    f"Date : {datetime.now().strftime('%d/%m/%Y %H:%M')}\n\n---\n\n")
            for s in steps:
                f.write(f"### Etape {s['step_id']}\n\n"
                        f"{s.get('text_tts') or s['text_original']}\n\n")

        with open(f"{export_base}/EQUIVALENCES.md", "w", encoding="utf-8") as f:
            f.write("# Tracabilite technique\n\n---\n\n")
            for item in sorted_generated:
                sid = item["step_id"]
                s = next((s for s in steps if str(s["step_id"]) == str(sid)), {})
                log = next((l for l in cleaning_log
                           if str(l.get("step_id")) == str(sid)), {})
                voice_name = item.get("voice_name") or assignments.get(str(sid), "")
                voice_info = voice_map.get(voice_name, {})
                v_type = voice_info.get("type", "unknown")
                v_source = voice_info.get("source", "unknown")
                instruction = instructions.get(str(sid), "")

                f.write(f"### {item.get('filename', f'etape-{sid}')}\n")
                f.write(f"- **Etape** : {sid}\n")
                f.write(f"- **Voix** : {voice_name} ({v_type}, {v_source})\n")
                if instruction:
                    f.write(f"- **Instruction emotionnelle** : {instruction}\n")
                if s.get("language_override"):
                    f.write(f"- **Langue** : {s['language_override']}\n")
                if s.get("speed_factor") and s["speed_factor"] != 1.0:
                    f.write(f"- **Vitesse** : {s['speed_factor']}\n")
                f.write(f"- **Texte original** : {s.get('text_original', '')}\n")
                f.write(f"- **Texte TTS** : "
                        f"{s.get('text_tts') or s.get('text_original', '')}\n")
                if log:
                    f.write(f"- **Nettoyage** : {log.get('llm_provider')} "
                            f"(t={log.get('temperature', 0.7)}, "
                            f"{str(log.get('timestamp', ''))[:16]})\n")
                try:
                    pfx = f"{int(sid):02d}"
                except (ValueError, TypeError):
                    pfx = str(sid)
                out_ext = "mp3" if req.output_format == "mp3" else "wav"
                fpath = (f"{audio_dir}/etape-{pfx}-"
                         f"{slugify(s.get('text_tts') or s.get('text_original', ''), max_length=40)}.{out_ext}")
                if os.path.exists(fpath):
                    size_kb = round(os.path.getsize(fpath) / 1024)
                    f.write(f"- **Statut** : OK ({size_kb} Ko)\n")
                f.write("\n")

        # ZIP
        yield {"event": "progress", "data": json.dumps({
            "step": "packaging", "progress": 98,
            "message": "Compression ZIP..."
        })}
        zip_path = os.path.abspath(f"export/OmniStudio_Export_{thread_id[:8]}.zip")
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for root, _, files in os.walk(export_base):
                for file in files:
                    fp = os.path.join(root, file)
                    zipf.write(fp, os.path.relpath(fp, export_base))

        zip_size = round(os.path.getsize(zip_path) / 1024)
        await asyncio.to_thread(graph_app.update_state, config, {"export_path": zip_path})

        yield {"event": "done", "data": json.dumps({
            "export_path": "/api/export/download",
            "size_kb": zip_size,
            "files_count": len(processed_files),
            "skipped": skipped
        })}

    async def safe_generator():
        try:
            async for event in event_generator():
                yield event
        finally:
            _unlock(_exporting_locks, thread_id)

    return EventSourceResponse(safe_generator(), headers={
        "X-Accel-Buffering": "no",
        "Cache-Control": "no-cache, no-transform",
    })


@router.get("/api/export/download")
async def download_export(
    request: Request,
    token: str = Query(None),
    tid: str = Query(None),
):
    """Telecharger le ZIP. Auth via header OU query params (pour <a href>)."""
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

    # PRD-031 : verification BOLA (oubli corrige apres revue Codex)
    if user and user.get("user_id"):
        _verify_session_owner(thread_id, user["user_id"])

    # Construction sécurisée du chemin ZIP (thread_id validé par regex ci-dessus)
    export_dir = os.path.abspath("export")
    os.makedirs(export_dir, exist_ok=True)
    zip_name = f"OmniStudio_Export_{thread_id[:8]}.zip"
    zip_path = os.path.join(export_dir, zip_name)
    # Vérifier que le chemin reste dans export/
    if not os.path.abspath(zip_path).startswith(export_dir):
        raise HTTPException(status_code=403, detail="Accès au répertoire refusé")
    if not os.path.exists(zip_path):
        return api_response(
            error={"code": "NOT_FOUND",
                   "message": "ZIP introuvable. Lancez l'export d'abord."},
            status_code=404
        )

    return FileResponse(
        zip_path,
        media_type="application/zip",
        filename=f"OmniStudio_Export_{thread_id[:8]}.zip"
    )
