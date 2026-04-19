#!/bin/bash
# start.sh — OmniStudio (Keycloak 8082 + OmniVoice 8070 + omnistudio 7870)
# PRD-MIGRATION-001 Phase 6 / décision 17 (preload models au boot)

set -e

REAL_SCRIPT="$(readlink "$0" 2>/dev/null || echo "$0")"
SCRIPT_DIR="$(cd "$(dirname "$REAL_SCRIPT")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

# Venv partagé avec voice-num (pas de venv dédié omni-num — cf session-context)
VENV_PY="/Users/alex/Claude/projets-heberges/voice-num/voxstudio/venv/bin/python3"
if [ ! -x "$VENV_PY" ]; then
    echo "ERREUR : venv introuvable à $VENV_PY"
    echo "Créer un venv omni-num ou ajuster VENV_PY dans ce script."
    exit 1
fi

OMNIVOICE_PID=""
OMNISTUDIO_PID=""

cleanup() {
    echo ""
    echo "Interruption — arrêt des processus lancés..."
    [[ -n "$OMNISTUDIO_PID" ]] && kill "$OMNISTUDIO_PID" 2>/dev/null || true
    [[ -n "$OMNIVOICE_PID" ]] && kill "$OMNIVOICE_PID" 2>/dev/null || true
}
trap cleanup INT TERM

echo "=== OmniStudio — démarrage ==="

# 0. Clé Albert (LLM pour voice design)
CRED_FILE="$HOME/Claude/config-claude/credentials.json"
if [ -z "${OPENAI_API_KEY:-}" ] && [ -f "$CRED_FILE" ]; then
    ALBERT_KEY=$("$VENV_PY" -c "import json; d=json.load(open('$CRED_FILE')); print(d.get('albert',{}).get('api_key',''))" 2>/dev/null || echo "")
    if [ -n "$ALBERT_KEY" ]; then
        export OPENAI_API_KEY="$ALBERT_KEY"
        echo "Clé Albert chargée."
    else
        echo "Clé Albert absente dans credentials.json — design voice tombera en fallback parser (sans LLM)."
    fi
fi

# 1. Keycloak (Docker partagé avec voice-num / harmonia)
if ! curl -s http://localhost:8082/ >/dev/null 2>&1; then
    echo "Démarrage Keycloak..."
    (cd "$HOME/Claude/keycloak" && docker compose up -d)
    for i in $(seq 1 30); do
        curl -s http://localhost:8082/ >/dev/null 2>&1 && break
        sleep 2
    done
    echo "Keycloak prêt."
else
    echo "Keycloak déjà actif sur :8082."
fi

# 2. OmniVoice (Python natif, MPS)
if ! curl -s http://localhost:8070/ >/dev/null 2>&1; then
    echo "Démarrage OmniVoice..."
    cd "$ROOT_DIR/OmniVoice"
    if [ -x "./venv/bin/python3" ]; then
        OMNIVOICE_PY="./venv/bin/python3"
    else
        OMNIVOICE_PY="$VENV_PY"
    fi
    "$OMNIVOICE_PY" main.py >> "$ROOT_DIR/logs/omnivoice.log" 2>&1 &
    OMNIVOICE_PID=$!
    echo -n "Attente OmniVoice :8070..."
    for i in $(seq 1 60); do
        curl -s http://localhost:8070/ >/dev/null 2>&1 && echo " OK" && break
        echo -n "."
        sleep 1
        if [ $i -eq 60 ]; then echo " TIMEOUT"; exit 1; fi
    done
else
    echo "OmniVoice déjà actif sur :8070."
fi

# 3. Seed voix système si dossier custom vide (PRD décision 6)
CUSTOM_DIR="$ROOT_DIR/OmniVoice/voices/custom"
if [ -d "$ROOT_DIR/data/voices-system" ] && [ -z "$(ls -A "$CUSTOM_DIR" 2>/dev/null)" ]; then
    echo "Seed des voix système dans $CUSTOM_DIR..."
    cp -r "$ROOT_DIR/data/voices-system/"* "$CUSTOM_DIR/"
    curl -s -X POST http://localhost:8070/voices/reload >/dev/null || true
    echo "Seed terminé (6 voix système)."
fi

# 4. omnistudio FastAPI (port 7870)
if ! curl -s http://localhost:7870/api/health >/dev/null 2>&1; then
    echo "Démarrage omnistudio..."
    mkdir -p "$ROOT_DIR/logs"
    cd "$ROOT_DIR/omnistudio"
    "$VENV_PY" server.py >> "$ROOT_DIR/logs/omnistudio.log" 2>&1 &
    OMNISTUDIO_PID=$!
    echo -n "Attente omnistudio :7870..."
    for i in $(seq 1 30); do
        curl -s http://localhost:7870/api/health >/dev/null 2>&1 && echo " OK" && break
        echo -n "."
        sleep 1
        if [ $i -eq 30 ]; then echo " TIMEOUT"; exit 1; fi
    done
else
    echo "omnistudio déjà actif sur :7870."
fi

# 5. Preload modèles OmniVoice (PRD décision 17 — évite latence premier appel)
echo "Préchargement modèles OmniVoice (design + preset + clone_1_7b)..."
curl -s -X POST http://localhost:8070/models/preload \
    --data-urlencode "design=true" \
    --data-urlencode "preset=true" \
    --data-urlencode "clone_1_7b=true" \
    -o /dev/null -w "  → HTTP %{http_code}\n" || true

echo ""
echo "=== OmniStudio prêt ==="
echo "  Local   : http://localhost:7870"
echo "  5G      : https://mac-studio-alex.tail0fc408.ts.net/omni/"
echo "  Logs    : $ROOT_DIR/logs/"
echo ""
echo "Ctrl+C pour détacher ce script (services restent actifs)."
echo "Arrêter les services : ./scripts/stop.sh"

# Ne pas kill les services quand le script se termine
trap - INT TERM
wait
