#!/usr/bin/env bash
# verify-assets-prefix.sh — Audit des chemins absolus dans le frontend
#
# Inventaire des chemins absolus (/css/, /js/, /dsfr/, /api/, /auth/,
# /fonts/, /images/) dans le frontend OmniStudio. Le script sort en erreur
# si un chemin absolu reste dans le frontend audité.
#
# Usage :
#   ./scripts/verify-assets-prefix.sh [chemin_frontend]
#
# Sans argument, audite omnistudio/frontend/out/ et omnistudio/frontend/out-dist/
# (si présents). Pour auditer un autre frontend, passer le chemin en argument.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
OMNISTUDIO_FRONTEND="${ROOT_DIR}/omnistudio/frontend/out"
OMNISTUDIO_FRONTEND_DIST="${ROOT_DIR}/omnistudio/frontend/out-dist"

TARGETS=()
if [ -n "${1:-}" ]; then
    TARGETS+=("$1")
else
    [ -d "$OMNISTUDIO_FRONTEND" ] && TARGETS+=("$OMNISTUDIO_FRONTEND")
    [ -d "$OMNISTUDIO_FRONTEND_DIST" ] && TARGETS+=("$OMNISTUDIO_FRONTEND_DIST")
fi

if [ ${#TARGETS[@]} -eq 0 ]; then
    echo "Aucun frontend trouvé. Usage : $0 [chemin]"
    exit 1
fi

OVERALL_TOTAL=0

count_lines() {
    wc -l | tr -d ' '
}

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
    grep -rEn 'href="/[a-zA-Z]' "$TARGET" --include='*.html' 2>/dev/null | grep -v 'href="/$' | grep -v '<base ' | head -20 || echo "  (aucun)"

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
    HTML_HREF=$( { grep -rEn 'href="/[a-zA-Z]' "$TARGET" --include='*.html' 2>/dev/null | grep -v 'href="/$' | grep -v '<base ' || true; } | count_lines )
    HTML_SRC=$( { grep -rEn 'src="/[a-zA-Z]' "$TARGET" --include='*.html' 2>/dev/null || true; } | count_lines )
    HTML_ACTION=$( { grep -rEn 'action="/[a-zA-Z]' "$TARGET" --include='*.html' 2>/dev/null || true; } | count_lines )
    JS_FETCH=$( { grep -rEn "fetch\([\"']/[a-zA-Z]" "$TARGET" --include='*.js' 2>/dev/null || true; } | count_lines )
    JS_URL=$( { grep -rEn "new URL\([\"']/[a-zA-Z]" "$TARGET" --include='*.js' 2>/dev/null || true; } | count_lines )
    JS_LOCATION=$( { grep -rEn "location\.(href|replace|assign)\s*=\s*[\"']/[a-zA-Z]" "$TARGET" --include='*.js' 2>/dev/null || true; } | count_lines )
    CSS_URL=$( { grep -rEn "url\([\"']?/[a-zA-Z]" "$TARGET" --include='*.css' 2>/dev/null || true; } | count_lines )

    echo "  HTML href=    : $HTML_HREF"
    echo "  HTML src=     : $HTML_SRC"
    echo "  HTML action=  : $HTML_ACTION"
    echo "  JS fetch()    : $JS_FETCH"
    echo "  JS new URL()  : $JS_URL"
    echo "  JS location   : $JS_LOCATION"
    echo "  CSS url()     : $CSS_URL"

    TOTAL=$((HTML_HREF + HTML_SRC + HTML_ACTION + JS_FETCH + JS_URL + JS_LOCATION + CSS_URL))
    OVERALL_TOTAL=$((OVERALL_TOTAL + TOTAL))
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

echo ""
if [ "$OVERALL_TOTAL" -eq 0 ]; then
    echo "Résultat : OK — aucun chemin absolu détecté."
    exit 0
fi

echo "Résultat : ECHEC — $OVERALL_TOTAL chemin(s) absolu(s) détecté(s)."
exit 1
