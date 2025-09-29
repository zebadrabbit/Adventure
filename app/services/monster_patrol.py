"""Monster patrol movement helper.

Responsibility: lightweight, opt-in wandering for non-combat monsters.

Design goals:
 - Pure function style: accepts a monster dict (mutable) and a dungeon-like object.
 - Reads global config (GameConfig key 'monster_ai') for patrol knobs:
       patrol_enabled (bool) gate
       patrol_step_chance (float 0-1) probability this tick
       patrol_radius (int) max Chebyshev distance from origin (x0,y0)
 - Records monster['patrol_origin'] = (x0,y0) the first time it is invoked.
 - Avoids stepping onto DOOR or TELEPORT tiles (tactical limitation requirement).
 - Never leaves patrol_radius boundary; if all candidate tiles outside radius or blocked, no-op.

Integration expectations:
 - Caller (e.g., dungeon tick / player movement hook) invokes maybe_patrol(monster, dungeon).
 - Caller persists updated monster JSON if return value is True (movement occurred).
 - Function is intentionally defensive; if anything unexpected arises it returns False silently.

Test strategy (see tests/test_monster_patrol.py):
 - Disabled gate -> no movement even with 100% chance.
 - Forced move with 100% chance -> coordinates change and remain within radius.
 - Door / teleport tiles excluded from candidate set.
"""

from __future__ import annotations

import json
import random
from typing import Any, Dict, Iterable, List, Optional, Tuple

from app.models import GameConfig

try:  # tile constants (best-effort import; tolerate absence during certain test contexts)
    from app.dungeon.tiles import DOOR, TELEPORT
except Exception:  # pragma: no cover - fallback values
    DOOR, TELEPORT = "D", "P"


Coord = Tuple[int, int]


def _cfg() -> Dict[str, Any]:
    try:
        raw = GameConfig.get("monster_ai")
        if raw:
            if isinstance(raw, str):
                return json.loads(raw)
            if isinstance(raw, dict):
                return raw
    except Exception:
        pass
    return {}


def _neighbors(x: int, y: int) -> Iterable[Coord]:
    # 4-way movement (N,E,S,W) keeps pathing simple and readable on ASCII map.
    yield (x + 1, y)
    yield (x - 1, y)
    yield (x, y + 1)
    yield (x, y - 1)


def maybe_patrol(monster: Dict[str, Any], dungeon: Any, *, rng: Optional[random.Random] = None) -> bool:
    """Attempt a single patrol step for monster.

    Returns True if movement occurred, else False.
    The dungeon object must expose: grid (2D list-like), width, height.
    Monster dict must contain integer 'x','y'. These are updated in-place.
    """
    r = rng or random
    try:
        cfg = _cfg()
        if not bool(cfg.get("patrol_enabled", False)):
            return False
        step_chance = float(cfg.get("patrol_step_chance", 0.1))
        if r.random() >= step_chance:
            return False
        if "x" not in monster or "y" not in monster:
            return False
        x, y = int(monster["x"]), int(monster["y"])
        # Establish origin if first time
        if "patrol_origin" not in monster:
            monster["patrol_origin"] = [x, y]
        ox, oy = monster.get("patrol_origin", [x, y])
        radius = max(0, int(cfg.get("patrol_radius", 5)))
        width = getattr(dungeon, "width", len(getattr(dungeon, "grid", [])))
        height = getattr(dungeon, "height", len(getattr(dungeon, "grid", [[]])))
        grid = getattr(dungeon, "grid", None)
        if grid is None:
            return False
        candidates: List[Coord] = []
        for nx, ny in _neighbors(x, y):
            if nx < 0 or ny < 0 or nx >= width or ny >= height:
                continue
            # Enforce patrol radius via Chebyshev distance (max-axis difference)
            if max(abs(nx - ox), abs(ny - oy)) > radius:
                continue
            tile = grid[nx][ny]
            # Skip restricted traversals (door/teleport). Additional restrictions can be appended.
            if tile in (DOOR, TELEPORT):
                continue
            # Treat walls/unknown as blocked: only move if not wall-ish. We'll assume uppercase letters W = wall.
            if tile == "W":
                continue
            candidates.append((nx, ny))
        if not candidates:
            return False
        nx, ny = r.choice(candidates)
        monster["x"], monster["y"] = nx, ny
        return True
    except Exception:  # pragma: no cover - safety net
        return False


__all__ = ["maybe_patrol"]
