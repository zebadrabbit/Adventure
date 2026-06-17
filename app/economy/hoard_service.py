"""Operations that move value between a character's at-risk run state and the Hoard.

Reuses the canonical inventory format and helpers from app.inventory.utils so the
hoard, character bags, and trading all speak the same shape:
  - stacks:    {"slug": str, "qty": int}
  - instances: {"uid": str, ...}  (procedural gear)
"""

from __future__ import annotations

import json
from typing import List

from app.inventory.utils import (
    add_item,
    find_instance,
    load_inventory,
    remove_instance,
    remove_one,
)
from app.models.hoard import Hoard
from app.models.models import Character


def _load(raw: str | None) -> List[dict]:
    return load_inventory(raw)


def deposit_items(hoard: Hoard, entries: List[dict]) -> None:
    """Merge a list of canonical entries (stacks and/or instances) into the hoard."""
    items = _load(hoard.items_json)
    for entry in entries or []:
        if entry.get("uid"):
            items.append(entry)
        elif entry.get("slug"):
            add_item(items, entry["slug"], int(entry.get("qty", 1)))
    hoard.items_json = json.dumps(items)


def deposit_copper(hoard: Hoard, amount: int) -> None:
    hoard.copper = (hoard.copper or 0) + max(0, int(amount))


def withdraw_to_character(
    hoard: Hoard, character: Character, *, slug: str | None = None, uid: str | None = None
) -> bool:
    """Move one stack-unit (by slug) or one instance (by uid) from hoard to a bag.

    Returns False if the item is not in the hoard.
    """
    hoard_items = _load(hoard.items_json)
    bag = _load(character.items)
    if uid:
        inst = find_instance(hoard_items, uid)
        if not inst:
            return False
        remove_instance(hoard_items, uid)
        bag.append(inst)
    elif slug:
        if not remove_one(hoard_items, slug):
            return False
        add_item(bag, slug, 1)
    else:
        return False
    hoard.items_json = json.dumps(hoard_items)
    character.items = json.dumps(bag)
    return True


def pool_run_haul(hoard: Hoard, character: Character) -> dict:
    """Move a character's entire bag + run-purse into the hoard, then zero them.

    Returns {"copper": int, "items": int} — what was moved, for caller-side reporting.
    """
    bag = _load(character.items)
    copper = character.gold or 0
    deposit_items(hoard, bag)
    deposit_copper(hoard, copper)
    character.items = "[]"
    character.gold = 0
    return {"copper": copper, "items": len(bag)}
