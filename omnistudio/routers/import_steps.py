"""Routeur Import/Steps — import de fichiers et gestion des etapes (PRD-010, Phase 5).

Endpoints :
- POST /api/import
- POST /api/import/select
- GET /api/steps
- POST /api/steps/add
"""
import asyncio
import os
import re
import shutil
from typing import List

from slugify import slugify

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from pydantic import BaseModel

from auth import get_current_user
from dependencies import (
    _touch_session,
    _verify_session_owner,
    api_error,
    api_response,
    get_thread_id,
    graph_app,
    limiter,
    logger,
)

# Constantes (PRD-016)
ALLOWED_IMPORT_EXT = (".xlsx", ".md", ".csv", ".txt", ".docx", ".pdf")
MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10 Mo

MAGIC_BYTES = {
    ".xlsx": [b"PK"],
    ".docx": [b"PK"],
    ".pdf":  [b"%PDF"],
}

# Regex stricte pour noms de fichiers sûrs (alphanumériques, tirets, points, underscores)
SAFE_FILENAME_RE = re.compile(r"^[a-zA-Z0-9._-]{1,255}$")


def _validate_magic(content: bytes, ext: str) -> bool:
    """Vérifie que le contenu correspond au format déclaré."""
    expected = MAGIC_BYTES.get(ext)
    if not expected:
        return True
    return any(content.startswith(magic) for magic in expected)


def _sanitize_filename(filename: str) -> str:
    """Nettoie et valide le nom de fichier contre les attaques path traversal.

    Bloque :
    - Chemins relatifs (../)
    - Chemins absolus (/)
    - Caractères nulls
    - Noms réservés Windows
    """
    if not filename:
        raise ValueError("Nom de fichier vide")

    # Bloquer les chemins multiples composants
    if "/" in filename or "\\" in filename:
        raise ValueError("Chemins composés refusés")

    # Bloquer les chemins réservés POSIX/Windows
    if filename in {".", "..", "CON", "PRN", "AUX", "NUL"}:
        raise ValueError("Nom de fichier réservé")

    # Ne garder que le nom de base (au cas où un chemin passe)
    safe_name = os.path.basename(filename)

    # Valider avec regex stricte
    if not SAFE_FILENAME_RE.match(safe_name):
        raise ValueError("Caractères non autorisés dans le nom de fichier")

    return safe_name

router = APIRouter()


@router.post("/api/import", responses={
    400: {"description": "Format invalide, fichier trop volumineux, contenu invalide ou import échoué"},
})
@limiter.limit("10/minute")
async def import_file(
    request: Request,
    file: UploadFile = File(...),
    sheet: str = Form("PLAN"),
    mode: str = Form("replace"),
    user=Depends(get_current_user),
    thread_id: str = Depends(get_thread_id),
):
    """Import d'un fichier (Excel, Markdown, CSV, TXT, DOCX)."""
    _verify_session_owner(thread_id, user["user_id"])
    _touch_session(thread_id)

    # Validation extension
    if not file.filename or not file.filename.lower().endswith(ALLOWED_IMPORT_EXT):
        return api_error("INVALID_FORMAT", f"Format non supporté. Acceptés : {', '.join(ALLOWED_IMPORT_EXT)}", 400)

    # Lire et valider la taille
    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        return api_error("FILE_TOO_LARGE", "Fichier trop volumineux (max 10 Mo)", 400)

    # Validation magic bytes (formats binaires)
    ext = os.path.splitext(file.filename)[1].lower()
    if not _validate_magic(content, ext):
        return api_error("INVALID_FILE", f"Le contenu du fichier ne correspond pas au format {ext}.", 400)

    # Sauvegarder le fichier (nom nettoyé — PRD-029)
    upload_dir = os.path.abspath(f"data/uploads/{thread_id}")
    os.makedirs(upload_dir, exist_ok=True)

    # Nettoyer et valider le nom de fichier
    try:
        safe_name = _sanitize_filename(file.filename)
    except ValueError as e:
        return api_error("INVALID_FILENAME", str(e), 400)

    name_part, ext_part = os.path.splitext(safe_name)
    safe_name = f"{slugify(name_part, lowercase=False)}{ext_part}"

    file_path = os.path.join(upload_dir, safe_name)
    # Vérifier que le chemin résultant reste dans upload_dir (sécurité supplémentaire)
    if not os.path.abspath(file_path).startswith(upload_dir):
        return api_error("INVALID_PATH", "Le chemin de fichier dépasse le répertoire autorisé", 403)

    with open(file_path, "wb") as f:
        f.write(content)

    # Detecter les onglets Excel
    sheets = []
    if ext == ".xlsx":
        import openpyxl
        wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
        sheets = wb.sheetnames
        wb.close()

    # Appeler le parser
    config = {"configurable": {"thread_id": thread_id}}
    initial_state = {
        "source_file": os.path.abspath(file_path),
        "source_format": ext.lstrip("."),
        "excel_sheet": sheet,
        "steps": [],
        "iteration_count": 0,
    }

    try:
        from graph.nodes.import_node import import_scenario, ImportError as ParsingImportError
        result = await asyncio.to_thread(import_scenario, initial_state)
        await asyncio.to_thread(graph_app.update_state, config, result)
    except ModuleNotFoundError as e:
        return api_error("IMPORT_FAILED", f"Module import_node indisponible: {e}", 500)
    except ParsingImportError as e:
        # Erreur de parsing du fichier (PDF invalide, format non supporté, etc.)
        return api_error("IMPORT_FAILED", str(e), 400)
    except (ValueError, KeyError, TypeError) as e:
        return api_error("IMPORT_FAILED", f"Erreur lors du parsing du fichier: {e}", 400)
    except Exception as e:
        logger.error(f"Erreur import_scenario pour {thread_id}: {e}", exc_info=True)
        return api_error("IMPORT_FAILED", "Erreur interne lors de l'import", 500)
    finally:
        shutil.rmtree(upload_dir, ignore_errors=True)

    state = await asyncio.to_thread(graph_app.get_state, config)
    steps = state.values.get("steps", []) if state and state.values else []

    return api_response({
        "steps": [{"step_id": s["step_id"], "text_original": s["text_original"]} for s in steps],
        "total": len(steps),
        "sheets": sheets,
        "selected_sheet": sheet,
    })


class SelectRequest(BaseModel):
    step_ids: List[str]


@router.post("/api/import/select")
async def import_select(
    req: SelectRequest,
    request: Request,
    user=Depends(get_current_user),
    thread_id: str = Depends(get_thread_id),
):
    """Filtrer les etapes selectionnees."""
    _verify_session_owner(thread_id, user["user_id"])
    _touch_session(thread_id)

    config = {"configurable": {"thread_id": thread_id}}
    state = await asyncio.to_thread(graph_app.get_state, config)
    steps = state.values.get("steps", []) if state and state.values else []
    total = len(steps)

    selected_set = set(req.step_ids)
    filtered = [s for s in steps if str(s["step_id"]) in selected_set]
    await asyncio.to_thread(graph_app.update_state, config, {"steps": filtered})

    return api_response({"retained": len(filtered), "total": total})


@router.get("/api/steps")
async def get_steps(
    request: Request,
    user=Depends(get_current_user),
    thread_id: str = Depends(get_thread_id),
):
    """Lister les etapes de la session."""
    _verify_session_owner(thread_id, user["user_id"])
    _touch_session(thread_id)

    config = {"configurable": {"thread_id": thread_id}}
    state = await asyncio.to_thread(graph_app.get_state, config)
    steps = state.values.get("steps", []) if state and state.values else []

    return api_response({
        "steps": [{
            "step_id": s["step_id"],
            "text_original": s["text_original"],
            "text_tts": s.get("text_tts", ""),
            "cleaning_status": s.get("cleaning_status", "pending"),
        } for s in steps],
        "total": len(steps),
    })


class AddStepRequest(BaseModel):
    step_id: str
    text_original: str


@router.post("/api/steps/add")
async def add_step(
    req: AddStepRequest,
    request: Request,
    user=Depends(get_current_user),
    thread_id: str = Depends(get_thread_id),
):
    """Ajouter une etape manuellement."""
    _verify_session_owner(thread_id, user["user_id"])
    _touch_session(thread_id)

    config = {"configurable": {"thread_id": thread_id}}
    state = await asyncio.to_thread(graph_app.get_state, config)
    steps = state.values.get("steps", []) if state and state.values else []

    if any(str(s["step_id"]) == req.step_id for s in steps):
        return api_error("STEP_EXISTS", f"L'étape {req.step_id} existe déjà", 409)

    steps.append({
        "step_id": req.step_id,
        "text_original": req.text_original,
        "text_tts": "",
        "cleaning_status": "pending",
    })

    await asyncio.to_thread(graph_app.update_state, config, {"steps": steps})
    return api_response({"step_id": req.step_id, "total": len(steps)})
