#!/usr/bin/env bash
# ci-static-smoke.sh — validations statiques CI sans services externes.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
FRONTEND_DIR="$ROOT_DIR/omnistudio/frontend/out"
INDEX_HTML="$FRONTEND_DIR/index.html"
SERVER_PY="$ROOT_DIR/omnistudio/server.py"
STUB_SERVER_PY="$ROOT_DIR/omnistudio/stub_server.py"
PACKAGE_JSON="$ROOT_DIR/package.json"
PACKAGE_LOCK="$ROOT_DIR/package-lock.json"
BUILD_FRONTEND="$ROOT_DIR/scripts/build-frontend.sh"

ok() { echo "  [OK] $*"; }
fail() { echo "  [FAIL] $*"; exit 1; }

echo "=== Smoke statique CI OmniStudio ==="

[ -f "$INDEX_HTML" ] || fail "index.html absent: $INDEX_HTML"
[ -f "$SERVER_PY" ] || fail "server.py absent: $SERVER_PY"
[ -f "$STUB_SERVER_PY" ] || fail "stub_server.py absent: $STUB_SERVER_PY"
[ -f "$PACKAGE_JSON" ] || fail "package.json absent: $PACKAGE_JSON"
[ -f "$PACKAGE_LOCK" ] || fail "package-lock.json absent: $PACKAGE_LOCK"

grep -q '<base href="/omni/">' "$INDEX_HTML" \
    && ok '<base href="/omni/"> present' \
    || fail '<base href="/omni/"> manquant dans index.html'

for app_file in "$SERVER_PY" "$STUB_SERVER_PY"; do
    if grep -Eq 'root_path\s*=\s*["'\'']/omni/?["'\'']' "$app_file"; then
        fail "root_path=\"/omni\" detecte dans $app_file"
    fi
    if grep -Eq 'root_path\s*=\s*os\.getenv' "$app_file"; then
        fail "root_path configurable par environnement detecte dans $app_file"
    fi
    if grep -q 'OMNISTUDIO_ROOT_PATH' "$app_file"; then
        fail "OMNISTUDIO_ROOT_PATH ne doit pas piloter FastAPI: $app_file"
    fi
    if ! grep -Eq 'root_path\s*=\s*["'\'']{2}' "$app_file"; then
        fail "root_path vide explicite absent dans $app_file"
    fi
done
ok 'FastAPI root_path force a vide'

PACKAGE_JSON="$PACKAGE_JSON" PACKAGE_LOCK="$PACKAGE_LOCK" python3 - <<'PY'
import json
import os
import sys
from pathlib import Path

package = json.loads(Path(os.environ["PACKAGE_JSON"]).read_text(encoding="utf-8"))
lock = json.loads(Path(os.environ["PACKAGE_LOCK"]).read_text(encoding="utf-8"))

declared = package.get("devDependencies", {}).get("esbuild")
locked = lock.get("packages", {}).get("node_modules/esbuild", {}).get("version")
if not declared:
    print("esbuild absent de devDependencies", file=sys.stderr)
    sys.exit(1)
if not locked:
    print("esbuild absent du package-lock.json", file=sys.stderr)
    sys.exit(1)
if declared != locked:
    print(f"Version esbuild non verrouillee: package.json={declared}, lock={locked}", file=sys.stderr)
    sys.exit(1)

print(f"  [OK] esbuild local verrouille ({locked})")
PY

if grep -Eq '^[[:space:]]*(command -v esbuild|esbuild[[:space:]])|npm install -g esbuild' "$BUILD_FRONTEND"; then
    fail "build-frontend.sh ne doit pas dépendre d'un esbuild global"
fi
grep -q 'node_modules/.bin/esbuild' "$BUILD_FRONTEND" \
    && ok 'build frontend utilise esbuild local' \
    || fail 'build-frontend.sh ne référence pas node_modules/.bin/esbuild'

FRONTEND_DIR="$FRONTEND_DIR" python3 - <<'PY'
import os
import re
import sys
from pathlib import Path

frontend = Path(os.environ["FRONTEND_DIR"])
index = frontend / "index.html"
html = index.read_text(encoding="utf-8")

missing = []
for attr in ("href", "src"):
    for raw in re.findall(rf'{attr}="([^"#?]+)(?:\?[^"]*)?"', html):
        if raw.startswith(("http://", "https://", "data:", "mailto:", "#")):
            continue
        if raw == "./":
            continue
        if not raw.endswith((".css", ".js", ".svg", ".woff", ".woff2")):
            continue
        rel = raw.lstrip("/")
        if not (frontend / rel).is_file():
            missing.append(raw)

if missing:
    print("Assets references introuvables dans index.html:", file=sys.stderr)
    for path in missing:
        print(f"  - {path}", file=sys.stderr)
    sys.exit(1)

print("  [OK] assets index.html presents")
PY

echo "=== Smoke statique CI OK ==="
