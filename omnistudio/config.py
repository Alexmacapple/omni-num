"""Configuration serveur OmniStudio DSFR."""
import os

# LLM
LLM_PROVIDER = os.getenv("OMNISTUDIO_LLM_PROVIDER", "Albert Large 120B")
LLM_API_KEY = os.getenv("OPENAI_API_KEY", "")
LLM_TEMPERATURE = float(os.getenv("OMNISTUDIO_LLM_TEMPERATURE", "0.7"))
LLM_MODEL_OVERRIDE = os.getenv("OMNISTUDIO_LLM_MODEL", "")

# Ports
OMNISTUDIO_PORT = int(os.getenv("OMNISTUDIO_PORT", "7870"))
OMNIVOICE_URL = os.getenv("OMNIVOICE_URL", "http://localhost:8070")
KEYCLOAK_URL = os.getenv("KEYCLOAK_URL", "http://localhost:8082")

# Keycloak
KEYCLOAK_REALM = os.getenv("KEYCLOAK_REALM", "harmonia")
KEYCLOAK_CLIENT_ID = os.getenv("KEYCLOAK_CLIENT_ID", "omnistudio")

# Sessions
SESSION_MAX_PER_USER = int(os.getenv("OMNISTUDIO_SESSION_MAX", "50"))
SESSION_PURGE_DAYS = int(os.getenv("OMNISTUDIO_SESSION_PURGE_DAYS", "90"))

# CORS (PRD-026) — inclut les origins Tailscale Funnel publics
CORS_ORIGINS = os.getenv(
    "OMNISTUDIO_CORS_ORIGINS",
    "http://localhost:7870,http://localhost:7443,"
    "https://mac-studio-alex.tail0fc408.ts.net,"
    "https://mac-studio-alex.tail0fc408.ts.net:7443"
).split(",")

# Chemins
DB_PATH = os.getenv("OMNISTUDIO_DB_PATH", "data/omnistudio_checkpoint.db")
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend", "out")
FRONTEND_DIST_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend", "out-dist")
MINIFY = os.getenv("OMNISTUDIO_MINIFY", "false").lower() == "true"
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OMNIVOICE_VOICES_DIR = os.getenv("OMNIVOICE_VOICES_DIR", os.path.join(_PROJECT_ROOT, "OmniVoice", "voices"))

# Voix système versionnées (PRD v1.5 décision 4)
VOICES_SYSTEM_DIR = os.getenv(
    "OMNISTUDIO_VOICES_SYSTEM_DIR",
    os.path.join(_PROJECT_ROOT, "data", "voices-system"),
)
DEFAULT_VOICES_JSON = os.getenv(
    "OMNISTUDIO_DEFAULT_VOICES_JSON",
    os.path.join(_PROJECT_ROOT, "data", "default_voices.json"),
)

# Anti-cascade session stale (PRD v1.5 décision 9, traite PRD-034)
STALE_THRESHOLD_MIN = int(os.getenv("OMNISTUDIO_STALE_THRESHOLD_MIN", "10"))

# Sous-titres SRT (PRD v1.5 décision 16)
WHISPER_MODEL_DIR = os.getenv(
    "OMNISTUDIO_WHISPER_CACHE",
    os.path.join(_PROJECT_ROOT, "data", "models"),
)

# Préchargement modèle OmniVoice (PRD v1.5 décision 17)
PRELOAD_MODEL = os.getenv("OMNISTUDIO_PRELOAD_MODEL", "true").lower() == "true"
