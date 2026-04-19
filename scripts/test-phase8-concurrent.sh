#!/bin/bash
# test-phase8-concurrent.sh — Smoke test charge 2 users concurrents
#
# PRD-MIGRATION-001 v1.5 Phase 8 / critère #29 (memory_pressure < 0.5).
# Simule 2 requêtes concurrentes sur les endpoints sans auth ou protégés JWT.

set -u
OMNI="https://mac-studio-alex.tail0fc408.ts.net/omni"
OMNI_LOCAL="http://localhost:7870"

echo "=== Phase 8 — Test charge concurrente ==="
echo ""
echo "1) Vérification baseline"
curl -sk -o /dev/null -w "  /api/health local     : HTTP %{http_code} (%{time_total}s)\n" "${OMNI_LOCAL}/api/health"
curl -sk -o /dev/null -w "  /api/health 5G        : HTTP %{http_code} (%{time_total}s)\n" "${OMNI}/api/health"

echo ""
echo "2) Memory pressure baseline (PRD critère #29 : seuil > 50% libre)"
PRESSURE=$(memory_pressure 2>/dev/null | awk '/System-wide memory free/ {gsub(/%/,""); print $NF}')
if [ -n "$PRESSURE" ]; then
    echo "  mémoire libre : ${PRESSURE}%"
    if [ "$PRESSURE" -ge 50 ]; then
        echo "  [OK] au-dessus du seuil PRD"
    else
        echo "  [WARN] sous le seuil PRD (50%)"
    fi
else
    echo "  memory_pressure indisponible"
fi

echo ""
echo "3) 6 requêtes concurrentes vers /api/health (local)"
start=$(date +%s%N)
for i in 1 2 3 4 5 6; do
    curl -sk -o /dev/null -w "    req $i : HTTP %{http_code} (%{time_total}s)\n" "${OMNI_LOCAL}/api/health" &
done
wait
end=$(date +%s%N)
elapsed=$(( (end - start) / 1000000 ))
echo "  ✓ 6 requêtes en ${elapsed}ms (si < 3000ms → OK parallélisation)"

echo ""
echo "4) 6 requêtes concurrentes via Tailscale Funnel /omni/api/health"
start=$(date +%s%N)
for i in 1 2 3 4 5 6; do
    curl -sk -o /dev/null -w "    req $i : HTTP %{http_code} (%{time_total}s)\n" "${OMNI}/api/health" &
done
wait
end=$(date +%s%N)
elapsed=$(( (end - start) / 1000000 ))
echo "  ✓ 6 requêtes 5G en ${elapsed}ms"

echo ""
echo "5) Assets statiques concurrents (stress Tailscale Funnel strip /omni)"
start=$(date +%s%N)
for url in "/omni/" "/omni/js/app.js" "/omni/css/app.css" "/omni/dsfr/dsfr/dsfr.min.css" "/omni/api/health" "/omni/api/voices/templates" "/omni/js/tab-voices.js" "/omni/js/api-client.js"; do
    curl -sk -o /dev/null -w "    %{http_code} %{time_total}s $url\n" "${OMNI}${url}" &
done
wait
end=$(date +%s%N)
elapsed=$(( (end - start) / 1000000 ))
echo "  ✓ 8 assets parallèles en ${elapsed}ms"

echo ""
echo "6) OmniVoice /preset concurrent (2 générations TTS simultanées)"
start=$(date +%s%N)
for voice in Paul Marianne; do
    curl -s -o "/tmp/phase8-${voice}.wav" -w "    ${voice} : HTTP %{http_code} (%{time_total}s, %{size_download} bytes)\n" \
        -X POST "http://localhost:8070/preset" \
        -F "text=Ceci est un test de charge concurrente ${voice}" \
        -F "voice=$voice" -F "language=fr" &
done
wait
end=$(date +%s%N)
elapsed=$(( (end - start) / 1000000 ))
echo "  ✓ 2 TTS parallèles en ${elapsed}ms"

echo ""
echo "7) Memory pressure post-charge"
PRESSURE=$(memory_pressure 2>/dev/null | awk '/System-wide memory free/ {gsub(/%/,""); print $NF}')
echo "  mémoire libre finale : ${PRESSURE:-N/A}%"

echo ""
echo "=== Phase 8 terminée ==="
