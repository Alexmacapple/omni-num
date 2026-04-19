#!/usr/bin/env python3
"""Normalise les instruct dans les meta.json des voix OmniVoice.

Utilise normalize_voice_instruct (core/omnivoice_client.py) qui accepte
un prompt prose EN/FR et extrait les items whitelist OmniVoice (1 par
categorie : gender, age, pitch, accent, special).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "omnistudio"))

from core.omnivoice_client import normalize_voice_instruct  # noqa: E402

VOICES_SYSTEM_DIR = ROOT / "data" / "voices-system"
VOICES_CUSTOM_DIR = ROOT / "OmniVoice" / "voices" / "custom"


def process_meta(path: Path) -> bool:
    """Retourne True si le fichier a ete modifie."""
    meta = json.loads(path.read_text(encoding="utf-8"))
    instruct = meta.get("instruct", "")
    if not instruct:
        return False
    new_instruct = normalize_voice_instruct(instruct)
    if not new_instruct:
        print(f"  ! {path.parent.name:14} instruct vide après normalisation (rejeté: '{instruct[:60]}')")
        return False
    if new_instruct == instruct.strip():
        return False
    meta["instruct"] = new_instruct
    path.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"  ✓ {path.parent.name:14} '{instruct[:40]}...' → '{new_instruct}'")
    return True


def main() -> None:
    print(f"Normalisation voices-system: {VOICES_SYSTEM_DIR}")
    for meta in sorted(VOICES_SYSTEM_DIR.glob("*/meta.json")):
        process_meta(meta)

    if VOICES_CUSTOM_DIR.exists():
        print(f"\nNormalisation voices/custom: {VOICES_CUSTOM_DIR}")
        for meta in sorted(VOICES_CUSTOM_DIR.glob("*/meta.json")):
            process_meta(meta)


if __name__ == "__main__":
    main()
