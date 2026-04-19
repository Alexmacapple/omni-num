#!/bin/bash
# test-smoke.sh — Smoke test OmniStudio (~10s)
#
# WARN_AS_ERROR=1 (default) : warnings → exit 1
# WARN_AS_ERROR=0 : warnings → exit 0

set -euo pipefail

REAL="$(readlink "$0" 2>/dev/null || echo "$0")"
ROOT_DIR="$(cd "$(dirname "$(dirname "$REAL")")" && pwd)"
OMNIVOICE_PORT=${OMNIVOICE_PORT:-8070}
OMNISTUDIO_PORT=${OMNISTUDIO_PORT:-7870}
WARN_AS_ERROR=${WARN_AS_ERROR:-1}

warn_count=0
ok()   { echo "  [OK] $*"; }
warn() { echo "  [WARN] $*"; warn_count=$((warn_count+1)); }
fail() { echo "  [FAIL] $*"; exit 1; }

command -v curl >/dev/null 2>&1 || fail "curl manquant"
command -v python3 >/dev/null 2>&1 || fail "python3 manquant"

echo "=== Smoke test OmniStudio ==="

# 1. Prérequis audio
echo "  --- Prérequis ---"
command -v sox >/dev/null 2>&1 && ok "sox" || warn "sox manquant (concat WAV)"
command -v ffmpeg >/dev/null 2>&1 && ok "ffmpeg" || warn "ffmpeg manquant (fallback concat + post-traitement)"

# 2. Services HTTP
echo "  --- Services ---"
curl -s -f "http://localhost:8082/" >/dev/null && ok "Keycloak :8082" || warn "Keycloak :8082 down"

if curl -s -f "http://localhost:${OMNIVOICE_PORT}/" >/dev/null; then
    ok "OmniVoice :${OMNIVOICE_PORT}"
    # Modèles chargés ?
    if curl -s "http://localhost:${OMNIVOICE_PORT}/models/status" | grep -q '"model_loaded": *true'; then
        ok "OmniVoice modèles chargés"
    else
        warn "OmniVoice modèles non préchargés (lancer /models/preload)"
    fi
else
    fail "OmniVoice :${OMNIVOICE_PORT} down"
fi

if curl -s -f "http://localhost:${OMNISTUDIO_PORT}/api/health" >/dev/null; then
    ok "omnistudio :${OMNISTUDIO_PORT}/api/health"
else
    fail "omnistudio :${OMNISTUDIO_PORT}/api/health down"
fi

# 3. Assets statiques (cause historique des 404 sous /omni)
echo "  --- Assets ---"
# Localhost direct (sans /omni/ prefix car root_path retiré)
for path in "" "js/app.js" "css/app.css" "dsfr/dsfr/dsfr.min.css"; do
    code=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:${OMNISTUDIO_PORT}/${path}")
    if [ "$code" = "200" ]; then
        ok "/${path} HTTP ${code}"
    else
        warn "/${path} HTTP ${code}"
    fi
done

# 4. Voix système seedées
echo "  --- Voix système ---"
VOICES_JSON=$(curl -s "http://localhost:${OMNIVOICE_PORT}/voices" || echo "")
for voix in Marianne Paul Lea Jean Sophie Thomas; do
    if echo "$VOICES_JSON" | grep -q "\"${voix}\""; then
        ok "voix ${voix} chargée"
    else
        warn "voix ${voix} absente (lancer seed ou start.sh)"
    fi
done

# 5. Instruct items normalisés (régression whitelist)
echo "  --- Instruct items voix système ---"
for voix in Marianne Paul Lea Jean Sophie Thomas; do
    meta="$ROOT_DIR/OmniVoice/voices/custom/${voix}/meta.json"
    if [ -f "$meta" ]; then
        # Un item invalide = présence d'un des mots bloqués
        if grep -qE 'energetic|warm and clear|gentle|calm|assertive|authoritative' "$meta"; then
            warn "${voix}/meta.json a encore des items invalides (lancer scripts/clean-voice-instruct.py)"
        else
            ok "${voix}/meta.json items valides"
        fi
    fi
done

# 6. Bilan
echo ""
echo "=== Résultat : $warn_count warning(s) ==="
if [ "$warn_count" -gt 0 ] && [ "$WARN_AS_ERROR" = "1" ]; then
    exit 1
fi
exit 0
