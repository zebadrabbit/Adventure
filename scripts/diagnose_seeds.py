#!/usr/bin/env python3
"""Dungeon structural diagnostics for specific seeds.

Usage:
  DUNGEON_DISABLE_CACHE=1 python scripts/diagnose_seeds.py 292372 730727

If no seeds are provided as CLI args, a default list is used.
Exits with non-zero status if structural issues are detected.
"""

from __future__ import annotations

import json
import os
import sys
from typing import List

# Ensure project root on path if executed directly
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app.dungeon.debug_checks import analyze  # noqa: E402 import after path fix
from app.dungeon.pipeline import Dungeon  # type: ignore  # noqa: E402 import after path fix

DEFAULT_SEEDS = [292372, 730727]


def run_for_seed(seed: int) -> dict:
    os.environ["DUNGEON_DISABLE_CACHE"] = "1"
    os.environ["DUNGEON_SEED"] = str(seed)
    d = Dungeon(seed=seed, size=(75, 75, 1))
    res = analyze(d)
    issues = {
        "unreachable_rooms": len(res["unreachable_rooms"]),
        "split_tunnel_candidates": len(res["split_tunnel_candidates"]),
        "room_tunnel_walls": len(res["wall_between_room_tunnel"]),
        "demoted_tunnels_doors": d.metrics.get("demoted_tunnels_doors", 0),
    }
    return {"seed": seed, "issues": issues, "ok": all(v == 0 for v in issues.values())}


def main(argv: List[str]) -> int:
    seeds = [int(a) for a in argv] if argv else DEFAULT_SEEDS
    results = [run_for_seed(s) for s in seeds]
    print(json.dumps({"results": results}, indent=2))
    # Non-zero exit if any failure
    if not all(r["ok"] for r in results):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
