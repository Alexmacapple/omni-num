#!/usr/bin/env bash
# security-smoke.sh — scan statique sécurité sans services externes.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

ok() { echo "  [OK] $*"; }

failures=0

fail_matches() {
    local label="$1"
    local matches="$2"
    echo "  [FAIL] $label"
    echo "$matches" | sed -n '1,40p'
    if [ "$(echo "$matches" | wc -l | tr -d ' ')" -gt 40 ]; then
        echo "  ... sortie tronquee"
    fi
    failures=$((failures + 1))
}

check_no_matches() {
    local label="$1"
    local pattern="$2"
    shift 2

    local matches=""
    if matches=$(git grep -nI -E "$pattern" -- "$@" 2>/dev/null); then
        fail_matches "$label" "$matches"
    else
        ok "$label"
    fi
}

echo "=== Smoke sécurité OmniStudio ==="

# Secrets haute confiance. Les fichiers documentaires peuvent mentionner les noms
# de variables ; ce scan cible les valeurs commitées accidentellement.
check_no_matches \
    "aucune clé privée versionnée" \
    'BEGIN ((RSA|OPENSSH|EC|DSA) )?PRIVATE KEY' \
    ':!package-lock.json' \
    ':!omnistudio/frontend/out/dsfr/**' \
    ':!omnistudio/frontend/out-dist/**'

check_no_matches \
    "aucun token haute confiance versionné" \
    '(AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9_]{20,}|xox[baprs]-[A-Za-z0-9-]{20,}|sk-[A-Za-z0-9_-]{20,})' \
    ':!package-lock.json' \
    ':!omnistudio/frontend/out/dsfr/**' \
    ':!omnistudio/frontend/out-dist/**'

check_no_matches \
    "aucune valeur de secret sensible codée en dur" \
    '(OPENAI_API_KEY|KEYCLOAK_ADMIN_PASSWORD|ACCESS_TOKEN|REFRESH_TOKEN|CLIENT_SECRET|API_SECRET)[[:space:]]*[:=][[:space:]]*["'\''"]?[A-Za-z0-9_./+=-]{20,}' \
    ':!package-lock.json' \
    ':!omnistudio/frontend/out/dsfr/**' \
    ':!omnistudio/frontend/out-dist/**'

# Patterns d'exécution dynamiques.
check_no_matches \
    "aucun eval/exec/new Function dans les sources applicatives" \
    '(^|[^A-Za-z0-9_])eval[[:space:]]*\(|(^|[^A-Za-z0-9_])exec[[:space:]]*\(|new[[:space:]]+Function[[:space:]]*\(' \
    '*.py' '*.js' 'scripts/*' \
    ':!package-lock.json' \
    ':!omnistudio/frontend/out/dsfr/**' \
    ':!omnistudio/frontend/out-dist/**' \
    ':!scripts/security-smoke.sh'

check_no_matches \
    "aucun document.write dans le frontend applicatif" \
    'document\.write[[:space:]]*\(' \
    '*.js' '*.html' \
    ':!omnistudio/frontend/out/dsfr/**' \
    ':!omnistudio/frontend/out-dist/**' \
    ':!scripts/security-smoke.sh'

# Invariants Omni/Funnel : FastAPI doit rester sans root_path dynamique ou /omni.
check_no_matches \
    "root_path FastAPI non configurable et jamais /omni" \
    'root_path[[:space:]]*=[[:space:]]*["'\''"]/omni/?["'\''"]|root_path[[:space:]]*=[[:space:]]*os\.getenv|OMNISTUDIO_ROOT_PATH' \
    '*.py' '.github/**' 'scripts/*' \
    ':!tests/**' \
    ':!scripts/ci-static-smoke.sh' \
    ':!scripts/security-smoke.sh'

# Build frontend : esbuild doit venir de node_modules, pas d'un binaire global.
check_no_matches \
    "build frontend sans esbuild global" \
    '^[[:space:]]*(command -v esbuild|esbuild[[:space:]])|npm install -g esbuild' \
    'scripts/build-frontend.sh'

# Le stub public de test ne doit pas réintroduire de sinks HTML ni logs debug.
check_no_matches \
    "stub frontend sans innerHTML ni logs console" \
    '\.innerHTML[[:space:]]*=|console\.(log|debug|info|warn|error)' \
    'omnistudio/frontend/out-stub/js/test.js'

if [ "$failures" -ne 0 ]; then
    echo "=== Smoke sécurité ECHEC ($failures catégorie(s)) ==="
    exit 1
fi

echo "=== Smoke sécurité OK ==="
