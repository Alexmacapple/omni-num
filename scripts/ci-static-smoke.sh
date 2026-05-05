#!/usr/bin/env bash
# ci-static-smoke.sh — validations statiques CI sans services externes.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
FRONTEND_DIR="$ROOT_DIR/omnistudio/frontend/out"
INDEX_HTML="$FRONTEND_DIR/index.html"
SERVER_PY="$ROOT_DIR/omnistudio/server.py"

ok() { echo "  [OK] $*"; }
fail() { echo "  [FAIL] $*"; exit 1; }

echo "=== Smoke statique CI OmniStudio ==="

[ -f "$INDEX_HTML" ] || fail "index.html absent: $INDEX_HTML"
[ -f "$SERVER_PY" ] || fail "server.py absent: $SERVER_PY"

grep -q '<base href="/omni/">' "$INDEX_HTML" \
    && ok '<base href="/omni/"> present' \
    || fail '<base href="/omni/"> manquant dans index.html'

if grep -Eq 'root_path\s*=\s*["'\'']/omni/?["'\'']' "$SERVER_PY"; then
    fail 'root_path="/omni" detecte dans FastAPI()'
fi
ok 'FastAPI sans root_path="/omni" statique'

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
