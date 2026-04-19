#!/bin/bash
# monitor.sh — Vérifie la santé d'OmniStudio (PRD critère #29)
#
# Usage :
#   ./scripts/monitor.sh               # Check unique
#   watch -n 60 ./scripts/monitor.sh   # Toutes les minutes
#
# Cron (toutes les 5 min) :
#   */5 * * * * /path/to/scripts/monitor.sh >> /tmp/omnistudio-monitor.log 2>&1

set -u
LOG_PREFIX="[$(date '+%Y-%m-%d %H:%M:%S')]"

check() {
    local name=$1
    local url=$2
    local timeout=${3:-5}
    local code
    code=$(curl -s -o /dev/null -w "%{http_code}" --max-time "$timeout" "$url" 2>/dev/null)
    if [ "$code" = "200" ]; then
        echo "$LOG_PREFIX OK   $name ($url)"
        return 0
    fi
    echo "$LOG_PREFIX FAIL $name ($url) → HTTP $code"
    return 1
}

ERRORS=0

check "Keycloak          " "http://localhost:8082/" 5 || ERRORS=$((ERRORS+1))
check "OmniVoice health  " "http://localhost:8070/" 5 || ERRORS=$((ERRORS+1))
check "OmniVoice /models  " "http://localhost:8070/models/status" 5 || ERRORS=$((ERRORS+1))
check "omnistudio /health " "http://localhost:7870/api/health" 10 || ERRORS=$((ERRORS+1))

# Pression mémoire (PRD critère #29 — seuil 0.5)
MEM_PRESSURE=$(memory_pressure 2>/dev/null | awk '/System-wide memory free/ {print $NF}' | tr -d '%')
if [ -n "$MEM_PRESSURE" ]; then
    # memory_pressure reporte le free pct. Pression = 100 - free. Seuil : free > 50%.
    FREE_PCT=$MEM_PRESSURE
    if [ "$FREE_PCT" -ge 50 ] 2>/dev/null; then
        echo "$LOG_PREFIX OK   mémoire libre ${FREE_PCT}%"
    else
        echo "$LOG_PREFIX WARN mémoire libre ${FREE_PCT}% (<50%, seuil PRD)"
        ERRORS=$((ERRORS+1))
    fi
else
    echo "$LOG_PREFIX --   mémoire (memory_pressure indisponible)"
fi

# Espace disque data/voices
VOICES_DIR="$HOME/Claude/projets-heberges/omni-num/data/voices"
if [ -d "$VOICES_DIR" ]; then
    USAGE=$(du -sh "$VOICES_DIR" 2>/dev/null | awk '{print $1}')
    echo "$LOG_PREFIX INFO data/voices = $USAGE"
fi

# Funnel Tailscale (si `tailscale` est installé)
if command -v tailscale >/dev/null 2>&1; then
    if tailscale funnel status 2>/dev/null | grep -q "/omni"; then
        echo "$LOG_PREFIX OK   Funnel /omni actif"
    else
        echo "$LOG_PREFIX WARN Funnel /omni absent (exposition 5G KO)"
    fi
fi

echo ""
if [ $ERRORS -eq 0 ]; then
    echo "$LOG_PREFIX RESULT : OK"
    exit 0
fi
echo "$LOG_PREFIX RESULT : $ERRORS erreur(s)"
exit 1
