"""Resolves what a potion slug does. The single place a slug becomes an effect.

Before this module existed, three code paths each guessed independently at
what a potion slug meant. combat_service.player_use_item matched three
hyphenated slugs by exact equality. inventory_api.consume_item matched
unanchored substrings -- "regen", then "healing", then "mana" -- against slugs
the catalogue actually spells "heal", not "healing", so all twenty
potion_heal_lN entries fell through every branch, were removed from the bag,
and granted zero HP: 127 of the catalogue's 154 potions consumed and destroyed
for nothing. The two paths also disagreed on magnitude for the one slug they
shared -- potion-healing healed 25 in combat, 5 out of it.

This module is the only place a slug becomes an effect. No new substring
matching belongs anywhere else in the codebase; adding a tiered family here is
one table entry plus a handler function.

Pure module: importable with no Flask app context. No db, no models, no
current_app, no imports from app.routes or app.services.combat_service.
"""

from __future__ import annotations

import copy
import re
from typing import Callable, Dict, Optional

# The player-facing refusal used by both call sites (combat and out-of-combat)
# when a slug names no implemented effect. Prose, not a machine code -- a
# player reads this sentence.
REFUSAL_NO_EFFECT = "That draught has no effect you can call upon yet."

# Distinct from the above: the slug resolved, the effect was applied, and only
# then did removing the potion from the bag fail -- a genuine race or bug, not
# a normal refusal path, so the message must not claim the draught did nothing.
# Lives here rather than in either caller because combat and out-of-combat both
# say it, and both used to define it verbatim, which is exactly the drift this
# module exists to prevent.
REFUSAL_ITEM_REMOVAL_FAILED = "Something went wrong reaching for that potion. Try again."

# Anchor the parse on the "_l<digits>" suffix at the end of the slug, not on a
# fixed split index: a family may itself contain underscores (buff_attack,
# resist_fire, group_battle), so `slug.split("_")[n]` would cut a family name
# in half. `.+` is greedy, so it backtracks from the end of the string to find
# the *last* "_l<digits>" run, which is always the tier suffix here since no
# family name in the catalogue itself ends in "_l<digits>".
_TIERED_SLUG_RE = re.compile(r"potion_(?P<family>.+)_l(?P<tier>\d+)")


def _heal(tier: int) -> dict:
    return {"kind": "restore_hp", "amount": 5 * (tier + 1)}


def _mana(tier: int) -> dict:
    return {"kind": "restore_mp", "amount": 2 * (tier + 1)}


# Families live in one table, mapping a family name to a handler that takes
# the parsed tier and returns a fresh descriptor dict. This is the extension
# point: adding a new tiered family (say, buff_attack, once a combat mechanic
# exists for it) is one entry here plus a handler function above -- no other
# file needs to change. A family absent from this table resolves to None:
# refused, never guessed at.
_FAMILY_HANDLERS: Dict[str, Callable[[int], dict]] = {
    "heal": _heal,
    "mana": _mana,
}

# Legacy hyphenated slugs predate the tiered catalogue and carry no tier of
# their own, so they get their own small flat map rather than a handler.
# potion_regen_lN deliberately has no handler above -- the regen buff's
# duration and multipliers are already duplicated literal-for-literal in four
# other places in the codebase, and tiering it now would create a fifth. The
# legacy potion-regen slug below keeps working as-is until those are folded
# together.
_LEGACY_SLUGS: Dict[str, dict] = {
    "potion-healing": {"kind": "restore_hp", "amount": 25},
    "potion-mana": {"kind": "restore_mp", "amount": 5},
    "potion-regen": {
        "kind": "status",
        "name": "regen_buff",
        "ticks": 5,
        "data": {"hp_mult": 3.0, "mp_mult": 3.0},
    },
}


def resolve_potion_effect(slug: Optional[str]) -> Optional[dict]:
    """Return the effect a potion slug grants, or None if none is implemented.

    Never raises, regardless of input shape. Matching is exact and
    case-sensitive: the catalogue is lower-case, so a slug differing in case
    is not a slug in this catalogue and is refused like any other unrecognised
    string -- the input is never lower-cased before matching.

    Returns a fresh dict on every call; callers are free to mutate what they
    get back without affecting the next caller.
    """
    if not isinstance(slug, str) or not slug:
        return None

    legacy = _LEGACY_SLUGS.get(slug)
    if legacy is not None:
        return copy.deepcopy(legacy)

    match = _TIERED_SLUG_RE.fullmatch(slug)
    if not match:
        return None

    handler = _FAMILY_HANDLERS.get(match.group("family"))
    if handler is None:
        return None

    return handler(int(match.group("tier")))
