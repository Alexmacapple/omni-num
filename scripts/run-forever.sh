#!/bin/bash
# run-forever.sh — Relance OmniStudio si crash
#
# Usage :
#   ./scripts/run-forever.sh              # Foreground
#   nohup ./scripts/run-forever.sh &      # Background
#
# Arreter :
#   kill $(cat /tmp/omnistudio-supervisor.pid)

set -u
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
MAX_RESTARTS=10
RESTART_DELAY=5
CRASH_WINDOW=300  # Si 10 crashes en 5 min, abandon
LOG_FILE="/tmp/omnistudio-supervisor.log"
PID_FILE="/tmp/omnistudio-supervisor.pid"

echo $$ > "$PID_FILE"
restarts=0
window_start=$(date +%s)

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

cleanup() {
    log "Supervision arretee (SIGTERM/SIGINT)"
    kill $(lsof -t -i :7870) 2>/dev/null || true
    rm -f "$PID_FILE"
    exit 0
}
trap cleanup SIGTERM SIGINT

log "Supervision OmniStudio demarree (max $MAX_RESTARTS restarts en ${CRASH_WINDOW}s)"

while true; do
    log "Demarrage OmniStudio (restart #$restarts)"
    cd "$ROOT_DIR/omnistudio"
    ./venv/bin/python3 server.py >> "$LOG_FILE" 2>&1
    EXIT_CODE=$?

    if [ $EXIT_CODE -eq 0 ]; then
        log "Arret propre (code 0)"
        break
    fi

    restarts=$((restarts + 1))
    now=$(date +%s)
    elapsed=$((now - window_start))

    # Reset le compteur si on est hors de la fenetre de crash
    if [ $elapsed -gt $CRASH_WINDOW ]; then
        restarts=1
        window_start=$now
    fi

    if [ $restarts -ge $MAX_RESTARTS ]; then
        log "ERREUR CRITIQUE : $MAX_RESTARTS crashes en ${elapsed}s, abandon"
        exit 1
    fi

    log "Crash (code $EXIT_CODE), redemarrage dans ${RESTART_DELAY}s... ($restarts/$MAX_RESTARTS)"
    sleep $RESTART_DELAY
done

rm -f "$PID_FILE"
