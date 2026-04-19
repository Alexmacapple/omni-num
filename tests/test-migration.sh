#!/bin/bash
# tests/test-migration.sh — Tests automatises migration DSFR
# Usage : ./tests/test-migration.sh [prd-001|prd-002|prd-003|prd-004|prd-005|all]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PASS=0; FAIL=0; WARN=0

ok()   { echo "  [OK] $1"; PASS=$((PASS + 1)); }
fail() { echo "  [FAIL] $1"; FAIL=$((FAIL + 1)); }
warn() { echo "  [WARN] $1"; WARN=$((WARN + 1)); }

# --- PRD-001 : Architecture ---
test_prd_001() {
    echo "=== PRD-001 : Architecture ==="

    # Keycloak
    curl -sf http://localhost:8082/realms/harmonia >/dev/null 2>&1 \
        && ok "Keycloak realm harmonia accessible" \
        || warn "Keycloak realm harmonia inaccessible (serveur non lance ?)"

    # server.py existe
    [ -f "$SCRIPT_DIR/voxstudio/server.py" ] \
        && ok "server.py existe" \
        || fail "server.py introuvable"

    # auth.py existe
    [ -f "$SCRIPT_DIR/voxstudio/auth.py" ] \
        && ok "auth.py existe" \
        || fail "auth.py introuvable"

    # config.py existe
    [ -f "$SCRIPT_DIR/voxstudio/config.py" ] \
        && ok "config.py existe" \
        || fail "config.py introuvable"

    # Frontend DSFR
    [ -f "$SCRIPT_DIR/voxstudio/frontend/out/index.html" ] \
        && ok "index.html existe" \
        || fail "index.html introuvable"

    # DSFR self-hosted
    [ -d "$SCRIPT_DIR/voxstudio/frontend/out/dsfr" ] \
        && ok "DSFR self-hosted present" \
        || fail "DSFR self-hosted manquant"

    # dom-utils.js
    [ -f "$SCRIPT_DIR/voxstudio/frontend/out/js/dom-utils.js" ] \
        && ok "dom-utils.js existe" \
        || fail "dom-utils.js introuvable"

    # Tous les modules JS
    for f in app.js api-client.js auth.js toast.js audio-player.js theme-init.js; do
        [ -f "$SCRIPT_DIR/voxstudio/frontend/out/js/$f" ] \
            && ok "$f existe" \
            || fail "$f introuvable"
    done

    # 6 tab modules
    for f in tab-import.js tab-clean.js tab-voices.js tab-assign.js tab-generate.js tab-export.js; do
        [ -f "$SCRIPT_DIR/voxstudio/frontend/out/js/$f" ] \
            && ok "$f existe" \
            || fail "$f introuvable"
    done

    # CSS
    [ -f "$SCRIPT_DIR/voxstudio/frontend/out/css/app.css" ] \
        && ok "app.css existe" \
        || fail "app.css introuvable"

    # API status (si serveur lance)
    if curl -sf "http://localhost:7861/api/status" >/dev/null 2>&1; then
        ok "API status repond sur :7861"
    elif curl -sf "http://localhost:7860/api/status" >/dev/null 2>&1; then
        ok "API status repond sur :7860"
    else
        warn "API VoxStudio ne repond pas (serveur non lance ?)"
    fi

    # JWT protection
    local HTTP_CODE
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:7861/api/steps" 2>/dev/null) || true
    case "$HTTP_CODE" in
        401) ok "Endpoint protege retourne 401 sans token" ;;
        000) warn "Serveur non lance, impossible de tester JWT" ;;
        *)   fail "Endpoint /api/steps retourne $HTTP_CODE au lieu de 401" ;;
    esac

    # start.sh et stop.sh
    [ -f "$SCRIPT_DIR/start.sh" ] && ok "start.sh existe" || fail "start.sh introuvable"
    [ -f "$SCRIPT_DIR/stop.sh" ] && ok "stop.sh existe" || fail "stop.sh introuvable"
}

# --- PRD-002 : Import + Preparation ---
test_prd_002() {
    echo "=== PRD-002 : Import + Preparation ==="

    [ -f "$SCRIPT_DIR/voxstudio/frontend/out/js/tab-import.js" ] \
        && ok "tab-import.js existe" \
        || fail "tab-import.js introuvable"

    [ -f "$SCRIPT_DIR/voxstudio/frontend/out/js/tab-clean.js" ] \
        && ok "tab-clean.js existe" \
        || fail "tab-clean.js introuvable"

    # Verifier que escapeHtml n'est pas declare localement
    if grep -q "function escapeHtml" "$SCRIPT_DIR/voxstudio/frontend/out/js/tab-import.js" 2>/dev/null; then
        fail "tab-import.js contient une declaration locale de escapeHtml"
    else
        ok "tab-import.js importe escapeHtml depuis dom-utils.js"
    fi

    if grep -q "function escapeHtml" "$SCRIPT_DIR/voxstudio/frontend/out/js/tab-clean.js" 2>/dev/null; then
        fail "tab-clean.js contient une declaration locale de escapeHtml"
    else
        ok "tab-clean.js importe escapeHtml depuis dom-utils.js"
    fi

    # Verifier que index.html contient les elements du panel import
    grep -q 'id="import-file"' "$SCRIPT_DIR/voxstudio/frontend/out/index.html" 2>/dev/null \
        && ok "index.html contient input import-file" \
        || fail "index.html manque input import-file"

    grep -q 'id="import-table-container"' "$SCRIPT_DIR/voxstudio/frontend/out/index.html" 2>/dev/null \
        && ok "index.html contient import-table-container" \
        || fail "index.html manque import-table-container"

    # Verifier les elements du panel clean
    grep -q 'id="clean-glossary"' "$SCRIPT_DIR/voxstudio/frontend/out/index.html" 2>/dev/null \
        && ok "index.html contient clean-glossary" \
        || fail "index.html manque clean-glossary"

    grep -q 'id="clean-progress-bar"' "$SCRIPT_DIR/voxstudio/frontend/out/index.html" 2>/dev/null \
        && ok "index.html contient clean-progress-bar" \
        || fail "index.html manque clean-progress-bar"

    grep -q 'id="clean-diff-accordion"' "$SCRIPT_DIR/voxstudio/frontend/out/index.html" 2>/dev/null \
        && ok "index.html contient clean-diff-accordion" \
        || fail "index.html manque clean-diff-accordion"

    grep -q 'id="clean-resume"' "$SCRIPT_DIR/voxstudio/frontend/out/index.html" 2>/dev/null \
        && ok "index.html contient clean-resume" \
        || fail "index.html manque clean-resume"

    # Verifier les classes CSS PRD-002
    grep -q "vx-diff-del" "$SCRIPT_DIR/voxstudio/frontend/out/css/app.css" 2>/dev/null \
        && ok "app.css contient vx-diff-del" \
        || fail "app.css manque vx-diff-del"

    grep -q "vx-diff-ins" "$SCRIPT_DIR/voxstudio/frontend/out/css/app.css" 2>/dev/null \
        && ok "app.css contient vx-diff-ins" \
        || fail "app.css manque vx-diff-ins"

    grep -q "vx-progress" "$SCRIPT_DIR/voxstudio/frontend/out/css/app.css" 2>/dev/null \
        && ok "app.css contient vx-progress" \
        || fail "app.css manque vx-progress"

    grep -q "vx-tts-edit" "$SCRIPT_DIR/voxstudio/frontend/out/css/app.css" 2>/dev/null \
        && ok "app.css contient vx-tts-edit" \
        || fail "app.css manque vx-tts-edit"

    # Verifier syntaxe Python server.py
    python3 -c "import ast; ast.parse(open('$SCRIPT_DIR/voxstudio/server.py').read())" 2>/dev/null \
        && ok "server.py syntaxe valide" \
        || fail "server.py erreur de syntaxe"

    # Verifier que server.py contient les endpoints PRD-002
    grep -q '/api/import' "$SCRIPT_DIR/voxstudio/server.py" 2>/dev/null \
        && ok "server.py contient /api/import" \
        || fail "server.py manque /api/import"

    grep -q '/api/clean' "$SCRIPT_DIR/voxstudio/server.py" 2>/dev/null \
        && ok "server.py contient /api/clean" \
        || fail "server.py manque /api/clean"

    grep -q '/api/clean/validate' "$SCRIPT_DIR/voxstudio/server.py" 2>/dev/null \
        && ok "server.py contient /api/clean/validate" \
        || fail "server.py manque /api/clean/validate"

    grep -q '/api/clean/diff' "$SCRIPT_DIR/voxstudio/server.py" 2>/dev/null \
        && ok "server.py contient /api/clean/diff" \
        || fail "server.py manque /api/clean/diff"

    # Verifier que fetchSSE gere onAbort
    grep -q "onAbort" "$SCRIPT_DIR/voxstudio/frontend/out/js/api-client.js" 2>/dev/null \
        && ok "api-client.js gere onAbort" \
        || fail "api-client.js manque onAbort"

    # Verifier uploadFile dans api-client.js
    grep -q "uploadFile" "$SCRIPT_DIR/voxstudio/frontend/out/js/api-client.js" 2>/dev/null \
        && ok "api-client.js contient uploadFile" \
        || fail "api-client.js manque uploadFile"

    # Verifier eventBus dans app.js
    grep -q "eventBus" "$SCRIPT_DIR/voxstudio/frontend/out/js/app.js" 2>/dev/null \
        && ok "app.js contient eventBus" \
        || fail "app.js manque eventBus"
}

# --- PRD-003 : Voix ---
test_prd_003() {
    echo "=== PRD-003 : Voix ==="

    [ -f "$SCRIPT_DIR/voxstudio/frontend/out/js/tab-voices.js" ] \
        && ok "tab-voices.js existe" \
        || fail "tab-voices.js introuvable"

    # Verifier que escapeHtml et escapeAttr sont importes depuis dom-utils
    if grep -q "function escapeHtml" "$SCRIPT_DIR/voxstudio/frontend/out/js/tab-voices.js" 2>/dev/null; then
        fail "tab-voices.js contient une declaration locale de escapeHtml"
    else
        ok "tab-voices.js importe escapeHtml depuis dom-utils.js"
    fi

    grep -q "escapeAttr" "$SCRIPT_DIR/voxstudio/frontend/out/js/tab-voices.js" 2>/dev/null \
        && ok "tab-voices.js utilise escapeAttr" \
        || fail "tab-voices.js manque escapeAttr"

    # Verifier que index.html contient les elements du panel voix
    grep -q 'id="voice-test-text"' "$SCRIPT_DIR/voxstudio/frontend/out/index.html" 2>/dev/null \
        && ok "index.html contient voice-test-text" \
        || fail "index.html manque voice-test-text"

    grep -q 'id="sub-panel-library"' "$SCRIPT_DIR/voxstudio/frontend/out/index.html" 2>/dev/null \
        && ok "index.html contient sub-panel-library" \
        || fail "index.html manque sub-panel-library"

    grep -q 'id="sub-panel-design"' "$SCRIPT_DIR/voxstudio/frontend/out/index.html" 2>/dev/null \
        && ok "index.html contient sub-panel-design" \
        || fail "index.html manque sub-panel-design"

    grep -q 'id="sub-panel-clone"' "$SCRIPT_DIR/voxstudio/frontend/out/index.html" 2>/dev/null \
        && ok "index.html contient sub-panel-clone" \
        || fail "index.html manque sub-panel-clone"

    grep -q 'id="design-lock-btn"' "$SCRIPT_DIR/voxstudio/frontend/out/index.html" 2>/dev/null \
        && ok "index.html contient design-lock-btn" \
        || fail "index.html manque design-lock-btn"

    grep -q 'id="clone-btn"' "$SCRIPT_DIR/voxstudio/frontend/out/index.html" 2>/dev/null \
        && ok "index.html contient clone-btn" \
        || fail "index.html manque clone-btn"

    # Verifier les endpoints dans server.py
    grep -q '/api/voices/design-flow' "$SCRIPT_DIR/voxstudio/server.py" 2>/dev/null \
        && ok "server.py contient /api/voices/design-flow" \
        || fail "server.py manque /api/voices/design-flow"

    grep -q '/api/voices/explore' "$SCRIPT_DIR/voxstudio/server.py" 2>/dev/null \
        && ok "server.py contient /api/voices/explore" \
        || fail "server.py manque /api/voices/explore"

    grep -q '/api/voices/lock' "$SCRIPT_DIR/voxstudio/server.py" 2>/dev/null \
        && ok "server.py contient /api/voices/lock" \
        || fail "server.py manque /api/voices/lock"

    grep -q '/api/voices/clone' "$SCRIPT_DIR/voxstudio/server.py" 2>/dev/null \
        && ok "server.py contient /api/voices/clone" \
        || fail "server.py manque /api/voices/clone"

    grep -q '/api/voices/preview' "$SCRIPT_DIR/voxstudio/server.py" 2>/dev/null \
        && ok "server.py contient /api/voices/preview" \
        || fail "server.py manque /api/voices/preview"

    grep -q '/api/voices/export' "$SCRIPT_DIR/voxstudio/server.py" 2>/dev/null \
        && ok "server.py contient /api/voices/export" \
        || fail "server.py manque /api/voices/export"

    grep -q '/api/voices/import' "$SCRIPT_DIR/voxstudio/server.py" 2>/dev/null \
        && ok "server.py contient /api/voices/import" \
        || fail "server.py manque /api/voices/import"

    # Verifier apiDelete dans api-client.js
    grep -q "apiDelete" "$SCRIPT_DIR/voxstudio/frontend/out/js/api-client.js" 2>/dev/null \
        && ok "api-client.js contient apiDelete" \
        || fail "api-client.js manque apiDelete"

    # Verifier CSS spinner
    grep -q "vx-spin" "$SCRIPT_DIR/voxstudio/frontend/out/css/app.css" 2>/dev/null \
        && ok "app.css contient vx-spin" \
        || fail "app.css manque vx-spin"

    # VoxQwen accessible
    curl -sf http://localhost:8060/voices >/dev/null 2>&1 \
        && ok "VoxQwen /voices accessible" \
        || warn "VoxQwen non lance"

    # Proxy voix
    local VOICES_CODE
    VOICES_CODE=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:7861/api/voices" -H "Authorization: Bearer test" 2>/dev/null) || true
    case "$VOICES_CODE" in
        401|200) ok "Endpoint /api/voices repond ($VOICES_CODE)" ;;
        000) warn "Serveur non lance" ;;
        *) fail "/api/voices retourne $VOICES_CODE" ;;
    esac
}

# --- PRD-004 : Assignation + Generation + Export ---
test_prd_004() {
    echo "=== PRD-004 : Assignation + Generation + Export ==="

    # --- Fichiers JS ---
    [ -f "$SCRIPT_DIR/voxstudio/frontend/out/js/tab-assign.js" ] \
        && ok "tab-assign.js existe" \
        || fail "tab-assign.js introuvable"

    [ -f "$SCRIPT_DIR/voxstudio/frontend/out/js/tab-generate.js" ] \
        && ok "tab-generate.js existe" \
        || fail "tab-generate.js introuvable"

    [ -f "$SCRIPT_DIR/voxstudio/frontend/out/js/tab-export.js" ] \
        && ok "tab-export.js existe" \
        || fail "tab-export.js introuvable"

    # audio-player.js
    [ -f "$SCRIPT_DIR/voxstudio/frontend/out/js/audio-player.js" ] \
        && ok "audio-player.js existe" \
        || fail "audio-player.js introuvable"

    # --- JS : imports corrects (dom-utils, api-client, app) ---
    grep -q "from './dom-utils.js'" "$SCRIPT_DIR/voxstudio/frontend/out/js/tab-assign.js" \
        && ok "tab-assign.js importe dom-utils.js" \
        || fail "tab-assign.js n'importe pas dom-utils.js"

    grep -q "escapeAttr" "$SCRIPT_DIR/voxstudio/frontend/out/js/tab-assign.js" \
        && ok "tab-assign.js utilise escapeAttr" \
        || fail "tab-assign.js n'utilise pas escapeAttr"

    grep -q "from './api-client.js'" "$SCRIPT_DIR/voxstudio/frontend/out/js/tab-generate.js" \
        && ok "tab-generate.js importe api-client.js" \
        || fail "tab-generate.js n'importe pas api-client.js"

    grep -q "fetchSSE" "$SCRIPT_DIR/voxstudio/frontend/out/js/tab-generate.js" \
        && ok "tab-generate.js utilise fetchSSE" \
        || fail "tab-generate.js n'utilise pas fetchSSE"

    grep -q "fetchSSE" "$SCRIPT_DIR/voxstudio/frontend/out/js/tab-export.js" \
        && ok "tab-export.js utilise fetchSSE" \
        || fail "tab-export.js n'utilise pas fetchSSE"

    grep -q "eventBus" "$SCRIPT_DIR/voxstudio/frontend/out/js/tab-assign.js" \
        && ok "tab-assign.js utilise eventBus" \
        || fail "tab-assign.js n'utilise pas eventBus"

    # --- JS : pas de declaration locale escapeHtml ---
    ! grep -q "^function escapeHtml\|^const escapeHtml" "$SCRIPT_DIR/voxstudio/frontend/out/js/tab-assign.js" \
        && ok "tab-assign.js pas de escapeHtml local" \
        || fail "tab-assign.js a un escapeHtml local"

    ! grep -q "^function escapeHtml\|^const escapeHtml" "$SCRIPT_DIR/voxstudio/frontend/out/js/tab-generate.js" \
        && ok "tab-generate.js pas de escapeHtml local" \
        || fail "tab-generate.js a un escapeHtml local"

    # --- JS : NATIVE_VOICES dans tab-assign.js ---
    grep -q "NATIVE_VOICES" "$SCRIPT_DIR/voxstudio/frontend/out/js/tab-assign.js" \
        && ok "tab-assign.js a NATIVE_VOICES" \
        || fail "tab-assign.js manque NATIVE_VOICES"

    # --- JS : pagination dans tab-generate.js ---
    grep -q "ITEMS_PER_PAGE" "$SCRIPT_DIR/voxstudio/frontend/out/js/tab-generate.js" \
        && ok "tab-generate.js a ITEMS_PER_PAGE (pagination)" \
        || fail "tab-generate.js manque ITEMS_PER_PAGE"

    # --- HTML : panels 4-5-6 complets ---
    HTML="$SCRIPT_DIR/voxstudio/frontend/out/index.html"

    grep -q 'id="assign-table"' "$HTML" \
        && ok "HTML : tableau assign-table present" \
        || fail "HTML : tableau assign-table absent"

    grep -q 'id="assign-voice"' "$HTML" \
        && ok "HTML : select assign-voice present" \
        || fail "HTML : select assign-voice absent"

    grep -q 'id="assign-apply-all-btn"' "$HTML" \
        && ok "HTML : bouton assign-apply-all-btn present" \
        || fail "HTML : bouton assign-apply-all-btn absent"

    grep -q 'id="gen-start-btn"' "$HTML" \
        && ok "HTML : bouton gen-start-btn present" \
        || fail "HTML : bouton gen-start-btn absent"

    grep -q 'id="gen-resume-btn"' "$HTML" \
        && ok "HTML : bouton gen-resume-btn present" \
        || fail "HTML : bouton gen-resume-btn absent"

    grep -q 'id="gen-progress-bar"' "$HTML" \
        && ok "HTML : progress gen-progress-bar present" \
        || fail "HTML : progress gen-progress-bar absent"

    grep -q 'id="gen-pagination"' "$HTML" \
        && ok "HTML : pagination gen-pagination presente" \
        || fail "HTML : pagination gen-pagination absente"

    grep -q 'id="export-btn"' "$HTML" \
        && ok "HTML : bouton export-btn present" \
        || fail "HTML : bouton export-btn absent"

    grep -q 'id="export-download-link"' "$HTML" \
        && ok "HTML : lien export-download-link present" \
        || fail "HTML : lien export-download-link absent"

    grep -q 'id="export-normalize"' "$HTML" \
        && ok "HTML : checkbox export-normalize presente" \
        || fail "HTML : checkbox export-normalize absente"

    grep -q 'name="export-depth"' "$HTML" \
        && ok "HTML : radio export-depth present" \
        || fail "HTML : radio export-depth absent"

    grep -q 'id="export-silence"' "$HTML" \
        && ok "HTML : range export-silence present" \
        || fail "HTML : range export-silence absent"

    # --- HTML : plus de stubs PRD-004 ---
    ! grep -q "Implementation dans PRD-004" "$HTML" \
        && ok "HTML : plus de stubs PRD-004" \
        || fail "HTML : stubs PRD-004 encore presents"

    # --- server.py : endpoints reels (pas NOT_IMPLEMENTED) ---
    SRV="$SCRIPT_DIR/voxstudio/server.py"

    grep -q "NATIVE_VOICE_NAMES" "$SRV" \
        && ok "server.py : NATIVE_VOICE_NAMES present" \
        || fail "server.py : NATIVE_VOICE_NAMES absent"

    grep -q "_generating_locks" "$SRV" \
        && ok "server.py : _generating_locks present" \
        || fail "server.py : _generating_locks absent"

    grep -q "_exporting_locks" "$SRV" \
        && ok "server.py : _exporting_locks present" \
        || fail "server.py : _exporting_locks absent"

    grep -q "class AssignRequest" "$SRV" \
        && ok "server.py : AssignRequest present" \
        || fail "server.py : AssignRequest absent"

    grep -q "class GenerateRequest" "$SRV" \
        && ok "server.py : GenerateRequest present" \
        || fail "server.py : GenerateRequest absent"

    grep -q "class ExportRequest" "$SRV" \
        && ok "server.py : ExportRequest present" \
        || fail "server.py : ExportRequest absent"

    grep -q "from slugify import slugify" "$SRV" \
        && ok "server.py : import slugify present" \
        || fail "server.py : import slugify absent"

    grep -q "from core.audio import process_audio" "$SRV" \
        && ok "server.py : import process_audio present" \
        || fail "server.py : import process_audio absent"

    grep -q "safe_generator" "$SRV" \
        && ok "server.py : safe_generator (verrous SSE)" \
        || fail "server.py : safe_generator absent"

    grep -q "batch_preset" "$SRV" \
        && ok "server.py : batch_preset (generation batch)" \
        || fail "server.py : batch_preset absent"

    grep -q "SCRIPT_PAROLES.md" "$SRV" \
        && ok "server.py : SCRIPT_PAROLES.md dans export" \
        || fail "server.py : SCRIPT_PAROLES.md absent"

    grep -q "EQUIVALENCES.md" "$SRV" \
        && ok "server.py : EQUIVALENCES.md dans export" \
        || fail "server.py : EQUIVALENCES.md absent"

    # --- server.py : endpoints non-stub ---
    ! grep -q "NOT_IMPLEMENTED.*PRD-004" "$SRV" \
        && ok "server.py : plus de stubs NOT_IMPLEMENTED PRD-004" \
        || fail "server.py : stubs PRD-004 encore presents"

    # --- CSS : styles onglets 4-5-6 ---
    CSS="$SCRIPT_DIR/voxstudio/frontend/out/css/app.css"

    grep -q "vx-assign-speed" "$CSS" \
        && ok "CSS : vx-assign-speed present" \
        || fail "CSS : vx-assign-speed absent"

    grep -q "#assign-table-container" "$CSS" \
        && ok "CSS : #assign-table-container present" \
        || fail "CSS : #assign-table-container absent"

    grep -q "#gen-results-list" "$CSS" \
        && ok "CSS : #gen-results-list present" \
        || fail "CSS : #gen-results-list absent"

    # --- Syntaxe Python ---
    python3 -c "import py_compile; py_compile.compile('$SRV', doraise=True)" 2>/dev/null \
        && ok "server.py : syntaxe Python valide" \
        || fail "server.py : erreur de syntaxe Python"

    # --- Syntaxe JS ---
    node --check "$SCRIPT_DIR/voxstudio/frontend/out/js/tab-assign.js" 2>/dev/null \
        && ok "tab-assign.js : syntaxe JS valide" \
        || fail "tab-assign.js : erreur de syntaxe JS"

    node --check "$SCRIPT_DIR/voxstudio/frontend/out/js/tab-generate.js" 2>/dev/null \
        && ok "tab-generate.js : syntaxe JS valide" \
        || fail "tab-generate.js : erreur de syntaxe JS"

    node --check "$SCRIPT_DIR/voxstudio/frontend/out/js/tab-export.js" 2>/dev/null \
        && ok "tab-export.js : syntaxe JS valide" \
        || fail "tab-export.js : erreur de syntaxe JS"
}

# --- PRD-005 : Nettoyage ---
test_prd_005() {
    echo "=== PRD-005 : Nettoyage ==="

    # --- Suppressions Gradio ---
    [ ! -f "$SCRIPT_DIR/voxstudio/main.py" ] \
        && ok "main.py supprime" \
        || fail "main.py encore present"

    [ ! -d "$SCRIPT_DIR/voxstudio/ui" ] \
        && ok "ui/ supprime" \
        || fail "ui/ encore present"

    [ ! -d "$SCRIPT_DIR/voxstudio/voxstudio" ] \
        && ok "voxstudio/voxstudio/ artefact supprime" \
        || fail "voxstudio/voxstudio/ encore present"

    [ ! -f "$SCRIPT_DIR/voxstudio/data/last_session.txt" ] \
        && ok "data/last_session.txt supprime" \
        || fail "data/last_session.txt encore present"

    # --- requirements.txt ---
    if grep -q "gradio" "$SCRIPT_DIR/voxstudio/requirements.txt" 2>/dev/null; then
        fail "gradio encore dans requirements.txt"
    else
        ok "gradio supprime de requirements.txt"
    fi

    if grep -q "nest_asyncio" "$SCRIPT_DIR/voxstudio/requirements.txt" 2>/dev/null; then
        fail "nest_asyncio encore dans requirements.txt"
    else
        ok "nest_asyncio supprime de requirements.txt"
    fi

    grep -q "sse-starlette" "$SCRIPT_DIR/voxstudio/requirements.txt" 2>/dev/null \
        && ok "sse-starlette dans requirements.txt" \
        || fail "sse-starlette manquant"

    grep -q "python-jose" "$SCRIPT_DIR/voxstudio/requirements.txt" 2>/dev/null \
        && ok "python-jose dans requirements.txt" \
        || fail "python-jose manquant"

    grep -q "fastapi" "$SCRIPT_DIR/voxstudio/requirements.txt" 2>/dev/null \
        && ok "fastapi dans requirements.txt" \
        || fail "fastapi manquant"

    grep -q "uvicorn" "$SCRIPT_DIR/voxstudio/requirements.txt" 2>/dev/null \
        && ok "uvicorn dans requirements.txt" \
        || fail "uvicorn manquant"

    # --- config.py : port 7860, base unique ---
    grep -q '"7860"' "$SCRIPT_DIR/voxstudio/config.py" \
        && ok "config.py : port 7860" \
        || fail "config.py : port pas 7860"

    grep -q "voxstudio_checkpoint.db" "$SCRIPT_DIR/voxstudio/config.py" \
        && ok "config.py : base unique voxstudio_checkpoint.db" \
        || fail "config.py : base pas voxstudio_checkpoint.db"

    ! grep -q "dsfr_checkpoint" "$SCRIPT_DIR/voxstudio/config.py" \
        && ok "config.py : plus de reference dsfr_checkpoint" \
        || fail "config.py : reference dsfr_checkpoint encore presente"

    # --- security.py simplifie ---
    grep -q "os.getenv" "$SCRIPT_DIR/voxstudio/core/security.py" \
        && ok "security.py : utilise os.getenv" \
        || fail "security.py : n'utilise pas os.getenv"

    ! grep -q "_api_key_cache" "$SCRIPT_DIR/voxstudio/core/security.py" \
        && ok "security.py : cache memoire supprime" \
        || fail "security.py : cache memoire encore present"

    ! grep -q "threading" "$SCRIPT_DIR/voxstudio/core/security.py" \
        && ok "security.py : threading supprime" \
        || fail "security.py : threading encore present"

    # --- start.sh : version finale ---
    grep -q "server.py" "$SCRIPT_DIR/start.sh" \
        && ok "start.sh : lance server.py" \
        || fail "start.sh : ne lance pas server.py"

    # main.py dans le contexte VoxStudio (pas VoxQwen qui a aussi un main.py)
    ! grep -q "voxstudio.*main.py\|Gradio.*main.py" "$SCRIPT_DIR/start.sh" \
        && ok "start.sh : plus de reference voxstudio/main.py" \
        || fail "start.sh : reference voxstudio/main.py encore presente"

    ! grep -q "7861" "$SCRIPT_DIR/start.sh" \
        && ok "start.sh : plus de port 7861" \
        || fail "start.sh : port 7861 encore present"

    ! grep -q "Gradio" "$SCRIPT_DIR/start.sh" \
        && ok "start.sh : plus de reference Gradio" \
        || fail "start.sh : reference Gradio encore presente"

    # --- stop.sh : version finale ---
    ! grep -q "7861" "$SCRIPT_DIR/stop.sh" \
        && ok "stop.sh : plus de port 7861" \
        || fail "stop.sh : port 7861 encore present"

    # --- test-smoke.sh : verifie server.py pas main.py ---
    grep -q "server.py" "$SCRIPT_DIR/test-smoke.sh" \
        && ok "test-smoke.sh : verifie server.py" \
        || fail "test-smoke.sh : ne verifie pas server.py"

    ! grep -q "from ui\." "$SCRIPT_DIR/test-smoke.sh" \
        && ok "test-smoke.sh : plus d'imports Gradio" \
        || fail "test-smoke.sh : imports Gradio encore presents"

    # --- Port 7860 (si serveur lance) ---
    local PORT_CODE
    PORT_CODE=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:7860/api/status" 2>/dev/null || echo "000")
    if [ "$PORT_CODE" = "200" ]; then
        ok "API sur port 7860"
    elif [ "$PORT_CODE" = "000" ]; then
        warn "Serveur non lance"
    else
        warn "API retourne $PORT_CODE sur 7860"
    fi

    # --- dom-utils.js : pas de declaration locale ---
    local LOCAL_ESCAPE
    LOCAL_ESCAPE=$(grep -rl "function escapeHtml" "$SCRIPT_DIR/voxstudio/frontend/out/js/" 2>/dev/null | grep -v dom-utils.js || true)
    if [ -z "$LOCAL_ESCAPE" ]; then
        ok "escapeHtml uniquement dans dom-utils.js"
    else
        fail "escapeHtml declare localement dans : $LOCAL_ESCAPE"
    fi

    # --- Syntaxe Python config.py + security.py ---
    python3 -c "import py_compile; py_compile.compile('$SCRIPT_DIR/voxstudio/config.py', doraise=True)" 2>/dev/null \
        && ok "config.py : syntaxe Python valide" \
        || fail "config.py : erreur de syntaxe Python"

    python3 -c "import py_compile; py_compile.compile('$SCRIPT_DIR/voxstudio/core/security.py', doraise=True)" 2>/dev/null \
        && ok "security.py : syntaxe Python valide" \
        || fail "security.py : erreur de syntaxe Python"
}

# --- Execution ---
TARGET=${1:-all}

case "$TARGET" in
    prd-001) test_prd_001 ;;
    prd-002) test_prd_001; test_prd_002 ;;
    prd-003) test_prd_001; test_prd_002; test_prd_003 ;;
    prd-004) test_prd_001; test_prd_002; test_prd_003; test_prd_004 ;;
    prd-005) test_prd_001; test_prd_002; test_prd_003; test_prd_004; test_prd_005 ;;
    all)     test_prd_001; test_prd_002; test_prd_003; test_prd_004; test_prd_005 ;;
    *) echo "Usage : $0 [prd-001|prd-002|prd-003|prd-004|prd-005|all]"; exit 1 ;;
esac

echo ""
echo "=== Resultats ==="
echo "  OK   : $PASS"
echo "  FAIL : $FAIL"
echo "  WARN : $WARN"

[ "$FAIL" -eq 0 ] && echo "  -> SUCCES" || echo "  -> ECHEC ($FAIL tests echoues)"
exit $FAIL
