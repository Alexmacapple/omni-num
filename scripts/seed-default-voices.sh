#!/usr/bin/env bash
# seed-default-voices.sh — Seed idempotent des 6 voix système (PRD v1.5 décision 4).
#
# Stratégie validée en Phase 0bis : les 6 voix sont versionnées dans
# data/voices-system/ (cf. RUNBOOK-DEPLOYMENT.md). Ce script fait un cp
# déterministe vers OmniVoice/voices/custom/ puis POST /voices/reload.
#
# Si data/voices-system/ est vide (première install, pas encore committé),
# le script fait fallback sur une génération via POST /voices/custom avec
# les instructions de data/default_voices.json.
#
# Usage :
#   ./scripts/seed-default-voices.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

VOICES_SYSTEM_DIR="$ROOT_DIR/data/voices-system"
OMNIVOICE_VOICES_DIR="$ROOT_DIR/OmniVoice/voices/custom"
DEFAULT_JSON="$ROOT_DIR/data/default_voices.json"
OMNIVOICE_URL="${OMNIVOICE_URL:-http://localhost:8070}"

EXPECTED_VOICES=("Marianne" "Lea" "Sophie" "Jean" "Paul" "Thomas")

echo "=== Seed voix système omnistudio ==="
echo ""

# Vérifier OmniVoice up
if ! curl -s -o /dev/null -w "%{http_code}" "$OMNIVOICE_URL/" 2>/dev/null | grep -q "200"; then
    echo "ERROR: OmniVoice ne répond pas sur $OMNIVOICE_URL"
    exit 1
fi

# Vérifier si les voix sont déjà présentes (idempotence)
all_present=true
for name in "${EXPECTED_VOICES[@]}"; do
    if [ ! -d "$OMNIVOICE_VOICES_DIR/$name" ]; then
        all_present=false
        break
    fi
done

if [ "$all_present" = true ]; then
    echo "Les 6 voix système sont déjà présentes dans OmniVoice/voices/custom/. Rien à faire."
    exit 0
fi

# Mode 1 : copie depuis data/voices-system/ si versionné
if [ -d "$VOICES_SYSTEM_DIR" ] && [ -n "$(ls -A "$VOICES_SYSTEM_DIR" 2>/dev/null)" ]; then
    echo "Mode copie : data/voices-system/ → OmniVoice/voices/custom/"
    mkdir -p "$OMNIVOICE_VOICES_DIR"
    cp -R "$VOICES_SYSTEM_DIR"/* "$OMNIVOICE_VOICES_DIR/"
    echo "6 voix copiées."
else
    # Mode 2 : génération via POST /voices/custom (premier boot sur machine de référence)
    echo "Mode génération : data/voices-system/ vide, génération via POST /voices/custom..."
    echo "(Rappel : après génération, committer data/voices-system/ pour les prochaines installs)"
    echo ""

    if [ ! -f "$DEFAULT_JSON" ]; then
        echo "ERROR: $DEFAULT_JSON introuvable"
        exit 1
    fi

    python3 << PYEOF
import json
import os
import sys
import time
import urllib.request
import urllib.parse
import http.client

voices = json.load(open("$DEFAULT_JSON"))
url = "$OMNIVOICE_URL"

for v in voices:
    name = v["name"]
    print(f"  Génération {name}...")
    # POST multipart/form-data vers /voices/custom
    boundary = "----OmniStudioSeedBoundary"
    body = []
    for key in ("name", "source", "language", "description"):
        body.append(f"--{boundary}".encode())
        body.append(f'Content-Disposition: form-data; name="{key}"'.encode())
        body.append(b"")
        body.append(str(v.get(key, "")).encode())
    body.append(f"--{boundary}".encode())
    body.append(b'Content-Disposition: form-data; name="voice_description"')
    body.append(b"")
    body.append(v["instruct"].encode())
    body.append(f"--{boundary}--".encode())
    body.append(b"")
    data = b"\r\n".join(body)

    req = urllib.request.Request(
        f"{url}/voices/custom",
        data=data,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            status = resp.status
            if status in (200, 201):
                print(f"    ✓ créée (status {status})")
            else:
                print(f"    ✗ erreur status {status}")
                sys.exit(1)
    except Exception as e:
        print(f"    ✗ exception : {e}")
        sys.exit(1)
    time.sleep(1)

print("\\n6 voix générées. Copie vers data/voices-system/ pour versionner :")
print(f"  cp -R {'$OMNIVOICE_VOICES_DIR'}/* {'$VOICES_SYSTEM_DIR'}/")
PYEOF
fi

# Reload OmniVoice (rescan des voix custom depuis disque)
echo ""
echo "=== Reload OmniVoice ==="
curl -s -X POST "$OMNIVOICE_URL/voices/reload" > /dev/null && echo "OK" || echo "Warning: reload échoué (non-critique)"

echo ""
echo "Seed terminé."
