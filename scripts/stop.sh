#!/bin/bash
# stop.sh — Arrêt propre des services OmniStudio

echo "Arrêt omnistudio (:7870)..."
kill $(lsof -t -i :7870) 2>/dev/null || true

echo "Arrêt OmniVoice (:8070)..."
kill $(lsof -t -i :8070) 2>/dev/null || true

echo "Arrêt Keycloak (Docker)..."
(cd "$HOME/Claude/keycloak" && docker compose down) 2>/dev/null || true

sleep 1
echo ""
echo "État final :"
for port in 7870 8070 8082; do
    if lsof -i :$port >/dev/null 2>&1; then
        echo "  :$port encore actif"
    else
        echo "  :$port libre"
    fi
done
echo "Terminé."
