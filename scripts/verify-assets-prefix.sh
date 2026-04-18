#!/usr/bin/env bash
# verify-assets-prefix.sh — Audit des chemins absolus dans le frontend
#
# Phase 0bis étape 2 : inventaire des chemins absolus (/css/, /js/, /dsfr/,
# /api/, /auth/, /fonts/, /images/) dans HTML et JS, pour décider la stratégie
# assets (Option A <base href> / B esbuild prefix / C runtime).
#
# Usage :
#   ./scripts/verify-assets-prefix.sh [chemin_frontend]
#
# Sans argument, audite voxstudio/frontend/out/ (source du fork) puis
# omnistudio/frontend/out/ (cible, si existe).

set -e

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VOXSTUDIO_FRONTEND="${ROOT_DIR}/../voice-num/voxstudio/frontend/out"
OMNISTUDIO_FRONTEND="${ROOT_DIR}/omnistudio/frontend/out"

TARGETS=()
if [ -n "$1" ]; then
    TARGETS+=("$1")
else
    [ -d "$VOXSTUDIO_FRONTEND" ] && TARGETS+=("$VOXSTUDIO_FRONTEND")
    [ -d "$OMNISTUDIO_FRONTEND" ] && TARGETS+=("$OMNISTUDIO_FRONTEND")
fi

if [ ${#TARGETS[@]} -eq 0 ]; then
    echo "Aucun frontend trouvé. Usage : $0 [chemin]"
    exit 1
fi

for TARGET in "${TARGETS[@]}"; do
    echo ""
    echo "================================================================"
    echo "Audit : $TARGET"
    echo "================================================================"

    if [ ! -d "$TARGET" ]; then
        echo "  [SKIP] dossier inexistant"
        continue
    fi

    echo ""
    echo "--- HTML : href=\"/... attributes absolus ---"
    grep -rEn 'href="/[a-zA-Z]' "$TARGET" --include='*.html' 2>/dev/null | grep -v 'href="/$' | head -20 || echo "  (aucun)"

    echo ""
    echo "--- HTML : src=\"/... attributes absolus ---"
    grep -rEn 'src="/[a-zA-Z]' "$TARGET" --include='*.html' 2>/dev/null | head -20 || echo "  (aucun)"

    echo ""
    echo "--- HTML : action=\"/... (formulaires) ---"
    grep -rEn 'action="/[a-zA-Z]' "$TARGET" --include='*.html' 2>/dev/null | head -10 || echo "  (aucun)"

    echo ""
    echo "--- JS : fetch('/...') absolus ---"
    grep -rEn "fetch\([\"']/[a-zA-Z]" "$TARGET" --include='*.js' 2>/dev/null | head -20 || echo "  (aucun)"

    echo ""
    echo "--- JS : new URL('/...') absolus ---"
    grep -rEn "new URL\([\"']/[a-zA-Z]" "$TARGET" --include='*.js' 2>/dev/null | head -10 || echo "  (aucun)"

    echo ""
    echo "--- JS : window.location.href = '/...' ---"
    grep -rEn "location\.(href|replace|assign)\s*=\s*[\"']/[a-zA-Z]" "$TARGET" --include='*.js' 2>/dev/null | head -10 || echo "  (aucun)"

    echo ""
    echo "--- CSS : url('/...') absolus ---"
    grep -rEn "url\([\"']?/[a-zA-Z]" "$TARGET" --include='*.css' 2>/dev/null | head -10 || echo "  (aucun)"

    echo ""
    echo "--- Comptage par catégorie ---"
    HTML_HREF=$(grep -rEn 'href="/[a-zA-Z]' "$TARGET" --include='*.html' 2>/dev/null | grep -v 'href="/$' | wc -l | tr -d ' ')
    HTML_SRC=$(grep -rEn 'src="/[a-zA-Z]' "$TARGET" --include='*.html' 2>/dev/null | wc -l | tr -d ' ')
    HTML_ACTION=$(grep -rEn 'action="/[a-zA-Z]' "$TARGET" --include='*.html' 2>/dev/null | wc -l | tr -d ' ')
    JS_FETCH=$(grep -rEn "fetch\([\"']/[a-zA-Z]" "$TARGET" --include='*.js' 2>/dev/null | wc -l | tr -d ' ')
    JS_URL=$(grep -rEn "new URL\([\"']/[a-zA-Z]" "$TARGET" --include='*.js' 2>/dev/null | wc -l | tr -d ' ')
    JS_LOCATION=$(grep -rEn "location\.(href|replace|assign)\s*=\s*[\"']/[a-zA-Z]" "$TARGET" --include='*.js' 2>/dev/null | wc -l | tr -d ' ')
    CSS_URL=$(grep -rEn "url\([\"']?/[a-zA-Z]" "$TARGET" --include='*.css' 2>/dev/null | wc -l | tr -d ' ')

    echo "  HTML href=    : $HTML_HREF"
    echo "  HTML src=     : $HTML_SRC"
    echo "  HTML action=  : $HTML_ACTION"
    echo "  JS fetch()    : $JS_FETCH"
    echo "  JS new URL()  : $JS_URL"
    echo "  JS location   : $JS_LOCATION"
    echo "  CSS url()     : $CSS_URL"

    TOTAL=$((HTML_HREF + HTML_SRC + HTML_ACTION + JS_FETCH + JS_URL + JS_LOCATION + CSS_URL))
    echo "  ---"
    echo "  TOTAL absolus : $TOTAL"
done

echo ""
echo "================================================================"
echo "Recommandation"
echo "================================================================"
echo ""
echo "Si TOTAL > 0 : Option A <base href=\"/omni/\"> dans index.html résout"
echo "automatiquement les chemins relatifs et ne nécessite aucune modif"
echo "du code existant (voxstudio → omnistudio)."
echo ""
echo "Les absolus qui restent (fetch('/api/...'), new URL('/...'))"
echo "ne sont pas affectés par <base href>. Pour ceux-ci :"
echo "  - fetch('api/...') (relatif) → sera résolu via <base href>"
echo "  - fetch('/api/...') (absolu) → à remplacer par fetch('api/...')"
