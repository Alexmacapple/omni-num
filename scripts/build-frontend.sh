#!/bin/bash
# build-frontend.sh — Bundle et minifie les assets frontend (PRD-028)
#
# Produit : omnistudio/frontend/out-dist/
#   - js/app.min.js (14 modules -> 1 bundle minifie)
#   - css/app.min.css (CSS minifie)
#   - index.html (chemins reecris avec hash)
#   - dsfr/ (copie tel quel)
#   - js/theme-init.js (copie, charge separement)
#
# Usage :
#   ./scripts/build-frontend.sh

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
SRC_DIR="$ROOT_DIR/omnistudio/frontend/out"
DIST_DIR="$ROOT_DIR/omnistudio/frontend/out-dist"

# Verifier esbuild
if ! command -v esbuild >/dev/null 2>&1; then
    echo "[ERREUR] esbuild non installe. Installer avec : npm install -g esbuild"
    exit 1
fi

# Verifier les sources
[ -f "$SRC_DIR/js/app.js" ] || { echo "[ERREUR] $SRC_DIR/js/app.js introuvable"; exit 1; }

echo "=== Build frontend OmniStudio ==="

# Nettoyer
rm -rf "$DIST_DIR"
mkdir -p "$DIST_DIR/js" "$DIST_DIR/css"

# 1. Bundle + minify JS
echo "  JS : bundling + minification..."
esbuild "$SRC_DIR/js/app.js" \
    --bundle \
    --minify \
    --sourcemap \
    --format=esm \
    --outfile="$DIST_DIR/js/app.min.js"

# 2. Minify CSS (pas de --bundle : app.css n'a aucun @import)
echo "  CSS : minification..."
esbuild "$SRC_DIR/css/app.css" \
    --minify \
    --sourcemap \
    --outfile="$DIST_DIR/css/app.min.css"

# 3. Copier theme-init.js (charge separement, avant le CSS)
cp "$SRC_DIR/js/theme-init.js" "$DIST_DIR/js/theme-init.js"

# 3bis. Copier les assets racine referencés par index.html
[ -f "$SRC_DIR/favicon.svg" ] && cp "$SRC_DIR/favicon.svg" "$DIST_DIR/favicon.svg"

# 4. Copier DSFR (inchange)
cp -r "$SRC_DIR/dsfr" "$DIST_DIR/dsfr"

# 5. Cache busting : hash du contenu
if command -v md5sum >/dev/null 2>&1; then
    HASH=$(md5sum "$DIST_DIR/js/app.min.js" | cut -c1-8)
else
    HASH=$(md5 -r "$DIST_DIR/js/app.min.js" | cut -c1-8)
fi

# 6. Reecrire index.html avec les chemins minifies + hash.
# Les chemins doivent rester relatifs pour que <base href="/omni/"> continue
# de normaliser correctement les requetes via Tailscale Funnel.
sed \
    -e "s|href=\"css/app\.css[^\"]*\"|href=\"css/app.min.css?v=$HASH\"|g" \
    -e "s|src=\"js/app\.js[^\"]*\"|src=\"js/app.min.js?v=$HASH\"|g" \
    "$SRC_DIR/index.html" > "$DIST_DIR/index.html"

# 7. Smoke test
[ -s "$DIST_DIR/js/app.min.js" ] || { echo "[ERREUR] Bundle JS vide"; exit 1; }
[ -s "$DIST_DIR/css/app.min.css" ] || { echo "[ERREUR] Bundle CSS vide"; exit 1; }
grep -q '<base href="/omni/">' "$DIST_DIR/index.html" || { echo "[ERREUR] <base href=\"/omni/\"> absent du build prod"; exit 1; }
grep -q 'href="css/app.min.css?v=' "$DIST_DIR/index.html" || { echo "[ERREUR] index.html n'utilise pas app.min.css"; exit 1; }
grep -q 'src="js/app.min.js?v=' "$DIST_DIR/index.html" || { echo "[ERREUR] index.html n'utilise pas app.min.js"; exit 1; }
if rg -q 'VoxStudio|vx_access_token|vx-login-screen|data-vx-active' "$DIST_DIR/index.html" "$DIST_DIR/css/app.min.css" "$DIST_DIR/js/app.min.js"; then
    echo "[ERREUR] Bundle prod stale detecte (restes VoxStudio)"
    exit 1
fi

JS_SIZE=$(wc -c < "$DIST_DIR/js/app.min.js")
CSS_SIZE=$(wc -c < "$DIST_DIR/css/app.min.css")
echo ""
echo "  Build termine :"
echo "    JS  : $(echo "$JS_SIZE / 1024" | bc) Ko ($(wc -c < "$SRC_DIR/js/app.js" | xargs echo) -> $JS_SIZE octets)"
echo "    CSS : $(echo "$CSS_SIZE / 1024" | bc) Ko"
echo "    Hash : $HASH"
echo "    Dist : $DIST_DIR"
