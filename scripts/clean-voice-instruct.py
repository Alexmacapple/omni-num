#!/usr/bin/env python3
"""Nettoie les instruct items non valides dans les meta.json des voix systeme.

OmniVoice (k2-fsa) n'accepte qu'une liste stricte d'items. Les adjectifs
qualitatifs heritages de VoxQwen (calm, gentle, warm and clear, energetic,
assertive, authoritative) sont filtres.
"""
from __future__ import annotations

import json
from pathlib import Path

VOICES_SYSTEM_DIR = Path(__file__).parent.parent / "data" / "voices-system"
VOICES_CUSTOM_DIR = Path(__file__).parent.parent / "OmniVoice" / "voices" / "custom"

VALID_EN_ITEMS = {
    "american accent", "australian accent", "british accent", "canadian accent",
    "child", "chinese accent", "elderly", "female", "high pitch",
    "indian accent", "japanese accent", "korean accent", "low pitch",
    "male", "middle-aged", "moderate pitch", "portuguese accent",
    "russian accent", "teenager", "very high pitch", "very low pitch",
    "whisper", "young adult",
}


def filter_instruct(instruct: str) -> tuple[str, list[str]]:
    """Garde uniquement les items dans VALID_EN_ITEMS. Retourne (filtre, rejetes)."""
    items = [it.strip() for it in instruct.split(",") if it.strip()]
    kept = [it for it in items if it.lower() in VALID_EN_ITEMS]
    dropped = [it for it in items if it.lower() not in VALID_EN_ITEMS]
    return ", ".join(kept), dropped


def process_meta(path: Path) -> bool:
    """Retourne True si le fichier a ete modifie."""
    meta = json.loads(path.read_text(encoding="utf-8"))
    instruct = meta.get("instruct", "")
    if not instruct:
        return False
    new_instruct, dropped = filter_instruct(instruct)
    if not dropped:
        return False
    meta["instruct"] = new_instruct
    path.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"  ✓ {path.parent.name:14} instruct dropped: {dropped}")
    return True


def main() -> None:
    print(f"Nettoyage voices-system: {VOICES_SYSTEM_DIR}")
    for meta in sorted(VOICES_SYSTEM_DIR.glob("*/meta.json")):
        process_meta(meta)

    if VOICES_CUSTOM_DIR.exists():
        print(f"\nNettoyage voices/custom: {VOICES_CUSTOM_DIR}")
        for meta in sorted(VOICES_CUSTOM_DIR.glob("*/meta.json")):
            process_meta(meta)


if __name__ == "__main__":
    main()
