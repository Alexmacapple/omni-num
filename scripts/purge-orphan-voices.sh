#!/bin/bash
# purge-orphan-voices.sh — Supprime les voix custom orphelines d'OmniVoice.
#
# Voix orpheline = custom non-système avec owner null/vide dans meta.json.
# Origines typiques :
#   - voix de tests oubliées
#   - voix créées avant PRD-032 (pas d'owner injecté)
#   - voix de VoxStudio clonées massivement (Annexe L) que l'utilisateur
#     n'a pas adoptées
#
# Utilisation :
#   ./scripts/purge-orphan-voices.sh           # affiche la liste et demande confirmation
#   ./scripts/purge-orphan-voices.sh --yes     # purge sans confirmation
#
# Dépendances : OmniVoice doit tourner sur :8070 (sinon rollback impossible).

set -u

OMNIVOICE_URL=${OMNIVOICE_URL:-http://localhost:8070}
AUTO_CONFIRM=${1:-}
ROOT_DIR="$(cd "$(dirname "$(readlink "$0" 2>/dev/null || echo "$0")")/.." && pwd)"
VOICES_DIR="$ROOT_DIR/OmniVoice/voices/custom"
VENV_PY="/Users/alex/Claude/projets-heberges/voice-num/voxstudio/venv/bin/python3"

if ! curl -sf "$OMNIVOICE_URL/" >/dev/null 2>&1; then
    echo "[FAIL] OmniVoice n'est pas joignable à $OMNIVOICE_URL"
    exit 1
fi

echo "=== Détection des voix orphelines ==="
ORPHANS=$("$VENV_PY" - <<EOF
import json
from pathlib import Path
root = Path("$VOICES_DIR")
for vdir in sorted(root.glob('*/')):
    meta_path = vdir / 'meta.json'
    if not meta_path.exists(): continue
    try:
        m = json.load(meta_path.open())
        if not m.get('system', False) and m.get('owner') in (None, '', 'null'):
            print(vdir.name)
    except: pass
EOF
)

if [ -z "$ORPHANS" ]; then
    echo "Aucune voix orpheline trouvée. Rien à faire."
    exit 0
fi

echo "Voix orphelines identifiées :"
for name in $ORPHANS; do
    echo "  - $name"
done
echo ""

if [ "$AUTO_CONFIRM" != "--yes" ]; then
    read -p "Supprimer ces voix ? (oui/non) : " ans
    if [ "$ans" != "oui" ]; then
        echo "Annulé."
        exit 0
    fi
fi

echo ""
echo "=== Suppression ==="
for name in $ORPHANS; do
    code=$(curl -sf -X DELETE "$OMNIVOICE_URL/voices/custom/$name" -o /dev/null -w "%{http_code}" 2>/dev/null || echo "ERR")
    if [ "$code" = "200" ]; then
        echo "  [OK] $name supprimée"
    else
        echo "  [FAIL] $name (HTTP $code)"
    fi
done

echo ""
echo "=== État final ==="
curl -s "$OMNIVOICE_URL/voices/reload" -X POST >/dev/null || true
curl -s "$OMNIVOICE_URL/voices" | "$VENV_PY" -c "
import sys, json
voices = json.load(sys.stdin).get('voices',[])
print(f'Voix restantes : {len(voices)}')
for v in voices:
    print(f'  - {v[\"name\"]}')"
