"""Feature assignment for dungeon cells (loot, spawns, decor, etc.).

Placeholder module to receive migrated logic from monolith.
"""
from __future__ import annotations
from typing import Dict, Any, List
import random

SPECIAL_ROOM_TYPES = ['jail', 'barracks', 'common', 'water', 'treasure']

def _spread_water(dungeon: "Dungeon", cx: int, cy: int, radius: int = 1) -> None:
    x,y,_ = dungeon.size
    for dx in range(-radius, radius+1):
        for dy in range(-radius, radius+1):
            nx,ny = cx+dx, cy+dy
            if 0 <= nx < x and 0 <= ny < y and dungeon.grid[nx][ny][0].cell_type == 'room':
                if 'water' not in dungeon.grid[nx][ny][0].features:
                    dungeon.grid[nx][ny][0].features.append('water')

def assign_features(dungeon: "Dungeon", metrics: Dict[str, Any]) -> None:
    """Assign gameplay/features to dungeon after structural completion.

    Logic (approx migrated):
      * First room: ensure 'entrance' already placed by pipeline.
      * Last room: ensure 'boss'.
      * Intermediate rooms: probabilistically assign a special tag.
      * Water rooms spread 'water' to surrounding tiles in radius 1 (legacy cosmetic water pool effect).
    """
    rooms = getattr(dungeon, 'rooms', [])
    if not rooms:
        return
    x,y,_ = dungeon.size
    # Ensure entrance & boss tags present (pipeline already set, idempotent safety)
    first = rooms[0]; last = rooms[-1]
    fx, fy = first.x + first.w//2, first.y + first.h//2
    if 'entrance' not in dungeon.grid[fx][fy][0].features:
        dungeon.grid[fx][fy][0].features.append('entrance')
        dungeon.entrance_pos = (fx,fy,0)
    lx, ly = last.x + last.w//2, last.y + last.h//2
    if (lx,ly)!=(fx,fy) and 'boss' not in dungeon.grid[lx][ly][0].features:
        dungeon.grid[lx][ly][0].features.append('boss')
    # Intermediate special assignment
    for i, r in enumerate(rooms[1:-1], start=1):
        rx, ry, rw, rh = r.x, r.y, r.w, r.h
        cx, cy = rx + rw//2, ry + rh//2
        cell = dungeon.grid[cx][cy][0]
        if 'entrance' in cell.features or 'boss' in cell.features:
            continue
        if random.random() < 0.7:
            tag = random.choice(SPECIAL_ROOM_TYPES)
            cell.features.append(tag)
            if tag == 'water':
                _spread_water(dungeon, cx, cy, radius=1)
    # (Optional future) metrics: count each special type
    if dungeon.enable_metrics is True:
        from collections import Counter
        counts = Counter()
        for r in rooms:
            cx = r.x + r.w//2; cy = r.y + r.h//2
            feats = dungeon.grid[cx][cy][0].features
            for f in feats:
                if f in SPECIAL_ROOM_TYPES or f in {'entrance','boss'}:
                    counts[f]+=1
        for k,v in counts.items():
            metrics[f'feature_{k}_rooms'] = v
