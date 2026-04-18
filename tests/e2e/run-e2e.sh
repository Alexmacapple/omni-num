#!/bin/bash
# run-e2e.sh — Lance les tests E2E VoxStudio (Playwright)
#
# Prerequis :
#   pip install -r tests/e2e/requirements.txt
#   playwright install chromium
#   ./start.sh  (serveur VoxStudio actif)
#
# Usage :
#   ./tests/e2e/run-e2e.sh                    # Headless (defaut)
#   ./tests/e2e/run-e2e.sh --headed           # Voir le navigateur
#   ./tests/e2e/run-e2e.sh --slow             # Ralenti (500ms entre actions)
#   ./tests/e2e/run-e2e.sh --skip-tts         # Sans generation TTS
#   ./tests/e2e/run-e2e.sh --headed --slow    # Combiner les options

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"

# Mot de passe Keycloak (demander si pas defini)
if [ -z "${E2E_PASSWORD:-}" ]; then
    echo -n "Mot de passe Keycloak (utilisateur ${E2E_USERNAME:-alex}) : "
    read -s E2E_PASSWORD
    echo ""
    export E2E_PASSWORD
fi

# Options
for arg in "$@"; do
    case $arg in
        --headed)    export E2E_HEADLESS=0 ;;
        --slow)      export E2E_SLOW_MO=500 ;;
        --skip-tts)  export E2E_SKIP_TTS=1 ;;
    esac
done

# Verifier que le serveur tourne
if ! curl -s "http://localhost:7860/api/status" >/dev/null 2>&1; then
    echo "[ERREUR] VoxStudio ne repond pas sur localhost:7860"
    echo "Lancez ./start.sh avant de lancer les tests E2E."
    exit 1
fi

echo "=== Tests E2E VoxStudio ==="
echo "URL   : ${E2E_BASE_URL:-http://localhost:7860}"
echo "User  : ${E2E_USERNAME:-alex}"
echo "Mode  : $([ "${E2E_HEADLESS:-1}" = "1" ] && echo "headless" || echo "headed")"
echo ""

cd "$ROOT_DIR"
python3 -m pytest tests/e2e/ -v --timeout=120 "$@" 2>&1 | grep -v "^$"
