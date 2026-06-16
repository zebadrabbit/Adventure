"""Currency formatting (B-lite: copper internal, 3-tier display).

All money in the game is stored internally as **copper** — the single smallest
unit (e.g. ``Character.gold`` is reinterpreted as a copper balance, no schema
change). Display is a pure presentation concern:

    100 copper = 1 silver
    100 silver = 1 gold

Use :func:`format_copper` for human-readable strings and :func:`split_copper`
when the frontend needs the individual tier values.
"""

from __future__ import annotations

from typing import Dict

COPPER_PER_SILVER = 100
SILVER_PER_GOLD = 100
COPPER_PER_GOLD = COPPER_PER_SILVER * SILVER_PER_GOLD


def split_copper(copper: int) -> Dict[str, int]:
    """Split a copper amount into gold / silver / copper tiers.

    Negative inputs are clamped to zero. Returns a dict with integer
    ``gold``, ``silver`` and ``copper`` keys.
    """
    total = max(0, int(copper))
    gold, rem = divmod(total, COPPER_PER_GOLD)
    silver, copper_rem = divmod(rem, COPPER_PER_SILVER)
    return {"gold": gold, "silver": silver, "copper": copper_rem}


def format_copper(copper: int) -> str:
    """Format a copper amount as a tiered string, omitting zero tiers.

    Examples::

        format_copper(0)      -> "0c"
        format_copper(150)    -> "1s 50c"
        format_copper(10000)  -> "1g"
        format_copper(120505) -> "12g 5s 5c"

    Always shows at least ``"0c"`` for an empty balance.
    """
    tiers = split_copper(copper)
    parts = []
    if tiers["gold"]:
        parts.append(f"{tiers['gold']}g")
    if tiers["silver"]:
        parts.append(f"{tiers['silver']}s")
    if tiers["copper"]:
        parts.append(f"{tiers['copper']}c")
    return " ".join(parts) if parts else "0c"
