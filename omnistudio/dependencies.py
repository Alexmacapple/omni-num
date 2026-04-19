"""Dependances partagees OmniStudio (PRD-010, Phase 0).

Centralise les objets utilises par 2+ routeurs :
- Singletons (graph_app, design_app, vox_client)
- Helpers transversaux (api_response, api_error, get_thread_id)
- Sessions SQLite (init, verify, touch, purge)
- Verrous SSE (cleaning, generating, exporting)
- Proxy OmniVoice (httpx AsyncClient)
"""
import logging
import os
import re
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from typing import Dict

import httpx
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

from config import (
    DB_PATH,
    SESSION_MAX_PER_USER,
    SESSION_PURGE_DAYS,
    OMNIVOICE_URL,
)
from graph.workflow import create_workflow
from graph.subgraphs.design_loop import create_design_subgraph
from core.omnivoice_client import OmniVoiceClient

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
from logging.handlers import RotatingFileHandler


def _setup_logging():
    """Configure le logging avec rotation fichier + console."""
    log_dir = os.path.join(os.path.dirname(__file__), "logs")
    os.makedirs(log_dir, exist_ok=True)

    json_formatter = logging.Formatter(
        '{"ts":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","msg":"%(message)s"}'
    )
    console_formatter = logging.Formatter(
        "%(asctime)s [%(name)s] %(levelname)s %(message)s"
    )

    file_handler = RotatingFileHandler(
        os.path.join(log_dir, "omnistudio.log"),
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(json_formatter)
    file_handler.setLevel(logging.INFO)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(console_formatter)
    console_handler.setLevel(logging.INFO)

    omnistudio_logger = logging.getLogger("omnistudio")
    omnistudio_logger.setLevel(logging.INFO)
    omnistudio_logger.addHandler(file_handler)
    omnistudio_logger.addHandler(console_handler)

    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    return omnistudio_logger


logger = _setup_logging()

# ---------------------------------------------------------------------------
# Repertoires de travail
# ---------------------------------------------------------------------------
os.makedirs("voice", exist_ok=True)
os.makedirs("export", exist_ok=True)
os.makedirs("data", exist_ok=True)
os.makedirs("temp", exist_ok=True)

# ---------------------------------------------------------------------------
# LangGraph workflow + OmniVoice client (singletons)
# ---------------------------------------------------------------------------
graph_app = create_workflow(db_path=DB_PATH)
design_app = create_design_subgraph()
vox_client = OmniVoiceClient(base_url=OMNIVOICE_URL)

# ---------------------------------------------------------------------------
# Verrous de concurrence SSE (thread_id -> timestamp)
# Timeout auto : si un verrou depasse 10 min, il est considere comme orphelin
# ---------------------------------------------------------------------------
_LOCK_TIMEOUT = 600  # 10 minutes
_cleaning_locks: Dict[str, datetime] = {}
_generating_locks: Dict[str, datetime] = {}
_exporting_locks: Dict[str, datetime] = {}


# =============================================================================
# Isolation multi-user des voix custom (PRD v1.5 décision 7, traite PRD-032)
# =============================================================================

def filter_voices_for_user(all_voices: list, user_sub: str) -> list:
    """Filtre la liste des voix visibles par un utilisateur.

    Règle : owner == user_sub OR system == true.
    """
    return [
        v for v in all_voices
        if v.get("system") is True or v.get("owner") == user_sub
    ]


def check_voice_ownership(voice_meta: dict, user_sub: str) -> bool:
    """Vérifie si l'utilisateur peut modifier/supprimer cette voix.

    Règle : owner == user_sub ET system == false.
    Les voix système ne sont jamais modifiables.
    """
    if voice_meta.get("system") is True:
        return False
    return voice_meta.get("owner") == user_sub


# =============================================================================
# Anti-cascade session stale (PRD v1.5 décision 9, traite PRD-034)
# =============================================================================

def is_session_stale(last_activity: datetime) -> bool:
    """Retourne True si la session est obsolète (dernière activité > seuil).

    Seuil configurable via env var OMNISTUDIO_STALE_THRESHOLD_MIN (défaut 10).
    """
    threshold_min = int(os.getenv("OMNISTUDIO_STALE_THRESHOLD_MIN", "10"))
    # Normaliser en UTC-aware
    if last_activity.tzinfo is None:
        last_activity = last_activity.replace(tzinfo=timezone.utc)
    age = datetime.now(timezone.utc) - last_activity
    return age > timedelta(minutes=threshold_min)


def release_stale_locks():
    """Libère les verrous SSE dont l'ancienneté dépasse le seuil.

    Appelé au démarrage de chaque SSE pour éviter les verrous orphelins.
    """
    for locks in (_cleaning_locks, _generating_locks, _exporting_locks):
        stale_keys = [k for k, ts in locks.items() if is_session_stale(ts)]
        for key in stale_keys:
            logger.info("Verrou stale libéré : %s", key)
            del locks[key]


def _is_locked(locks: Dict[str, datetime], thread_id: str) -> bool:
    """Verifie si un verrou est actif (avec nettoyage auto des verrous orphelins).

    Anti-cascade session stale (PRD v1.5 décision 9) : libère si > _LOCK_TIMEOUT secondes.
    Tolère un float timestamp (héritage / tests) en plus d'un datetime.
    """
    if thread_id not in locks:
        return False
    locked_at = locks[thread_id]
    # Compat : certains tests ou versions antérieures stockent un float (time.time())
    if isinstance(locked_at, (int, float)):
        locked_at = datetime.fromtimestamp(locked_at, tz=timezone.utc)
    elif locked_at.tzinfo is None:
        locked_at = locked_at.replace(tzinfo=timezone.utc)
    age_seconds = (datetime.now(timezone.utc) - locked_at).total_seconds()
    if age_seconds > _LOCK_TIMEOUT:
        logger.warning("Verrou orphelin detecte pour %s, liberation automatique", thread_id)
        del locks[thread_id]
        return False
    return True


def _lock(locks: Dict[str, datetime], thread_id: str):
    locks[thread_id] = datetime.now(timezone.utc)


def _unlock(locks: Dict[str, datetime], thread_id: str):
    locks.pop(thread_id, None)


# ---------------------------------------------------------------------------
# Table user_sessions (SQLite)
# ---------------------------------------------------------------------------
_BASE_DIR = os.path.dirname(__file__)
_sessions_db_path = os.path.join(_BASE_DIR, "data", "omnistudio_dsfr_sessions.db")


def _init_sessions_db():
    conn = sqlite3.connect(_sessions_db_path)
    # WAL mode for better concurrency (PRD-026)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS user_sessions (
            thread_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            label TEXT
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_user_sessions_user ON user_sessions(user_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_user_sessions_updated ON user_sessions(updated_at)")
    conn.commit()
    conn.close()


def _purge_old_sessions():
    """Supprime les sessions inactives > SESSION_PURGE_DAYS jours et les checkpoints associes."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=SESSION_PURGE_DAYS)).isoformat()
    conn = sqlite3.connect(_sessions_db_path)

    # Recuperer les thread_ids a purger AVANT de les supprimer
    old_ids = conn.execute(
        "SELECT thread_id FROM user_sessions WHERE updated_at < ?", (cutoff,)
    ).fetchall()

    conn.execute("DELETE FROM user_sessions WHERE updated_at < ?", (cutoff,))
    conn.commit()
    conn.close()

    # Purger les checkpoints LangGraph associes (tables checkpoints + writes)
    if old_ids:
        try:
            cp_conn = sqlite3.connect(DB_PATH)
            cp_conn.execute("PRAGMA busy_timeout=5000")
            for (tid,) in old_ids:
                cp_conn.execute("DELETE FROM checkpoints WHERE thread_id = ?", (tid,))
                cp_conn.execute("DELETE FROM writes WHERE thread_id = ?", (tid,))
            cp_conn.commit()
            cp_conn.execute("VACUUM")
            cp_conn.close()
            logger.info("Purge checkpoints : %d sessions (tables checkpoints + writes) supprimees", len(old_ids))
        except Exception as e:
            logger.warning("Erreur purge checkpoints : %s", e)

    logger.info("Purge des sessions anterieures a %s", cutoff)


def _purge_temp_files():
    """Supprime les fichiers temporaires orphelins au demarrage (PRD-015)."""
    import glob
    import shutil

    purged = 0
    for directory in ["temp", "voice", "export", os.path.join("data", "voices")]:
        if not os.path.isdir(directory):
            continue
        for f in glob.glob(os.path.join(directory, "*")):
            if os.path.isfile(f):
                os.remove(f)
                purged += 1
            elif os.path.isdir(f):
                shutil.rmtree(f, ignore_errors=True)
                purged += 1
    if purged:
        logger.info("Purge : %d fichiers/dossiers temporaires supprimes", purged)


def _touch_session(thread_id: str):
    """Met a jour updated_at."""
    conn = sqlite3.connect(_sessions_db_path)
    conn.execute(
        "UPDATE user_sessions SET updated_at = ? WHERE thread_id = ?",
        (datetime.now(timezone.utc).isoformat(), thread_id),
    )
    conn.commit()
    conn.close()


def _verify_session_owner(thread_id: str, user_id: str):
    """Verifie que le thread_id appartient au user_id."""
    conn = sqlite3.connect(_sessions_db_path)
    row = conn.execute(
        "SELECT user_id FROM user_sessions WHERE thread_id = ?", (thread_id,)
    ).fetchone()
    conn.close()
    if row is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "SESSION_NOT_FOUND", "message": "Session introuvable"},
        )
    if row[0] != user_id:
        raise HTTPException(
            status_code=403,
            detail={"code": "FORBIDDEN", "message": "Session non autorisee"},
        )


# ---------------------------------------------------------------------------
# Helpers : reponse uniforme
# ---------------------------------------------------------------------------
def api_response(data=None, error=None, status_code=200):
    return JSONResponse({"data": data, "error": error}, status_code=status_code)


def api_error(code: str, message: str, status_code: int = 400):
    return api_response(error={"code": code, "message": message}, status_code=status_code)


# ---------------------------------------------------------------------------
# Helper : thread_id depuis les headers
# ---------------------------------------------------------------------------
THREAD_ID_RE = re.compile(r"^[a-zA-Z0-9\-_]{1,64}$")


def get_thread_id(request: Request) -> str:
    thread_id = request.headers.get("X-Thread-Id", "").strip()
    if not thread_id or not THREAD_ID_RE.match(thread_id):
        raise HTTPException(status_code=400, detail={"code": "INVALID_THREAD_ID", "message": "Header X-Thread-Id invalide (alphanumérique, 1-64 caractères)"})
    return thread_id


# ---------------------------------------------------------------------------
# Rate limiting (PRD-011)
# ---------------------------------------------------------------------------
from slowapi import Limiter


def _get_real_ip(request: Request) -> str:
    """Extrait l'IP reelle du client (supporte Tailscale Funnel proxy)."""
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


limiter = Limiter(key_func=_get_real_ip)


# ---------------------------------------------------------------------------
# OmniVoice client (proxy httpx)
# ---------------------------------------------------------------------------
def _check_disk_quota(warn_gb: int = 10):
    """Verifie l'espace disque utilise par les fichiers audio."""
    voices_dir = os.path.join("data", "voices")
    if not os.path.isdir(voices_dir):
        return
    total_size = 0
    for root, dirs, files in os.walk(voices_dir):
        for f in files:
            total_size += os.path.getsize(os.path.join(root, f))
    size_gb = total_size / (1024 * 1024 * 1024)
    if size_gb > warn_gb:
        logger.warning("Espace audio : %.1f Go (seuil %d Go). Purge recommandee.", size_gb, warn_gb)
    else:
        logger.info("Espace audio : %.1f Go", size_gb)


def _purge_stale_exports(max_age_hours: int = 72):
    """Supprime les ZIP d'export de plus de 72h."""
    import glob
    export_dir = "export"
    if not os.path.isdir(export_dir):
        return
    cutoff = time.time() - (max_age_hours * 3600)
    purged = 0
    for f in glob.glob(os.path.join(export_dir, "*.zip")):
        if os.path.getmtime(f) < cutoff:
            os.remove(f)
            purged += 1
    if purged:
        logger.info("Purge exports : %d ZIP de plus de %dh supprimes", purged, max_age_hours)


def _purge_orphan_voices(max_age_hours: int = 48):
    """Supprime les dossiers voix orphelins (session inexistante + > 48h)."""
    import shutil
    voices_dir = os.path.join("data", "voices")
    if not os.path.isdir(voices_dir):
        return
    cutoff = time.time() - (max_age_hours * 3600)
    purged = 0
    for d in os.listdir(voices_dir):
        full_path = os.path.join(voices_dir, d)
        if not os.path.isdir(full_path):
            continue
        if os.path.getmtime(full_path) > cutoff:
            continue
        # Check if session still exists
        conn = sqlite3.connect(_sessions_db_path)
        row = conn.execute("SELECT 1 FROM user_sessions WHERE thread_id = ?", (d,)).fetchone()
        conn.close()
        if not row:
            shutil.rmtree(full_path, ignore_errors=True)
            purged += 1
    if purged:
        logger.info("Purge voix orphelines : %d dossiers de plus de %dh supprimes", purged, max_age_hours)


# ---------------------------------------------------------------------------
# OmniVoice client (proxy httpx)
# ---------------------------------------------------------------------------
_omnivoice_client = httpx.AsyncClient(base_url=OMNIVOICE_URL, timeout=300.0)


async def _close_resources():
    """Ferme les connexions au shutdown."""
    try:
        await _omnivoice_client.aclose()
        logger.info("Client OmniVoice ferme")
    except Exception as e:
        logger.warning(f"Erreur fermeture client OmniVoice: {e}")


async def _proxy_omnivoice(method: str, path: str, **kwargs):
    """Proxy vers OmniVoice avec gestion d'erreur."""
    try:
        response = await _omnivoice_client.request(method, path, **kwargs)
        return response
    except (httpx.ConnectError, httpx.TimeoutException) as exc:
        code = 504 if isinstance(exc, httpx.TimeoutException) else 502
        raise HTTPException(
            status_code=code,
            detail={"code": "OMNIVOICE_UNAVAILABLE", "message": f"Service TTS indisponible ({type(exc).__name__})"},
        )
