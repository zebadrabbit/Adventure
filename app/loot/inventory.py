# app/loot/inventory.py
"""Helpers to merge generated gear instances into a character's JSON inventory."""

from __future__ import annotations

import json


def add_gear_to_character(character, instances: list[dict]) -> None:
    """Append gear instances to character.items (JSON list), preserving existing."""
    try:
        items = json.loads(character.items) if character.items else []
        if not isinstance(items, list):
            items = []
    except Exception:
        items = []
    for inst in instances or []:
        if isinstance(inst, dict) and inst.get("uid"):
            items.append(inst)
    character.items = json.dumps(items)
