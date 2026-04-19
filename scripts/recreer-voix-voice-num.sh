#!/bin/bash
# recreer-voix-voice-num.sh — Annexe L du PRD-MIGRATION-001 v1.5.
#
# Recrée les 4 voix historiques de voice-num (alexandra, frederique,
# stephanie, vieux) en voix custom OmniVoice via clone. Le prompt.pt de
# VoxQwen n'est pas compatible : il faut un WAV de référence + transcription.
#
# Prérequis :
# - OmniVoice actif sur :8070
# - (optionnel) voxstudio actif sur :7860 pour régénérer les WAV source
# - WAV source (~30 s) pour chaque voix à cloner

set -u

OMNIVOICE_URL=${OMNIVOICE_URL:-http://localhost:8070}
ROOT_DIR="$(cd "$(dirname "$(readlink "$0" 2>/dev/null || echo "$0")")/.." && pwd)"

clone_voice() {
    local name=$1
    local wav=$2
    local transcription=$3

    if [ ! -f "$wav" ]; then
        echo "  [SKIP] $name — WAV introuvable : $wav"
        echo "         Générer un preview 30s via voxstudio puis relancer."
        return 1
    fi

    echo "  [EN COURS] $name ← $wav"
    response=$(curl -s -w "\n%{http_code}" -X POST "$OMNIVOICE_URL/voices/custom" \
        -F "name=$name" \
        -F "source=clone" \
        -F "model=1.7B" \
        -F "language=fr" \
        -F "reference_audio=@$wav" \
        -F "reference_text=$transcription")
    code=$(echo "$response" | tail -1)
    body=$(echo "$response" | sed '$d')

    if [ "$code" = "200" ] || [ "$code" = "201" ]; then
        echo "  [OK]   $name créé"
        # Injecter owner=null (voix système)
        meta="$ROOT_DIR/OmniVoice/voices/custom/$name/meta.json"
        if [ -f "$meta" ]; then
            # Pas besoin d'injection owner ici : laissé à null pour accès global
            echo "       meta: $meta"
        fi
    else
        echo "  [FAIL] $name : HTTP $code — $body"
    fi
}

# Source WAV par défaut : prendre les samples voxstudio existants
find_wav() {
    local name=$1
    find /Users/alex/Claude/projets-heberges/voice-num -name "${name}_*.wav" \
        -not -path '*/node_modules/*' 2>/dev/null | head -1
}

echo "=== Recréation voix voice-num dans OmniVoice ==="

# Transcription standard voxstudio preview (cf. test-smoke.sh voxstudio)
TRANSCRIPTION_DEFAULT="Bonjour, bienvenue sur Voxstudio. Voici un extrait de ma voix pour vous aider à choisir."

for voice in alexandra frederique stephanie vieux; do
    wav=$(find_wav "$voice")
    if [ -n "$wav" ]; then
        clone_voice "$voice" "$wav" "$TRANSCRIPTION_DEFAULT" || true
    else
        echo "  [TODO] $voice — générer WAV via voxstudio puis relancer ce script"
    fi
done

echo ""
echo "=== Reload voix OmniVoice ==="
curl -s -X POST "$OMNIVOICE_URL/voices/reload" | head -c 100; echo

echo ""
echo "Voix finales :"
curl -s "$OMNIVOICE_URL/voices" | /Users/alex/Claude/projets-heberges/voice-num/voxstudio/venv/bin/python3 -c "
import sys, json
voices = json.load(sys.stdin).get('voices', [])
for v in voices:
    print(f'  - {v.get(\"name\",\"?\")} ({v.get(\"source\",\"?\")})')"
