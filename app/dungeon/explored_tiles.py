"""Helper functions for managing explored tiles persistence.

Handles loading, updating, and saving explored tiles to the user's profile.
"""

from __future__ import annotations

import json as _json
from typing import Set, Tuple

from flask import session
from flask_login import current_user

from app import db
from app.models.models import User


def load_explored_tiles(seed: int) -> Set[Tuple[int, int]]:
    """Load explored tiles for the given seed from the current user's profile.

    Returns:
        Set of (x, y) coordinates that have been explored
    """
    if not current_user or not current_user.is_authenticated:
        # Fall back to session-only storage for non-logged-in users
        session_key = f"explored_tiles:{seed}"
        tiles_str = session.get(session_key, "")
        if tiles_str:
            return _parse_tiles_string(tiles_str)
        return set()

    user = db.session.get(User, current_user.id)
    if not user or not user.explored_tiles:
        return set()

    try:
        all_explored = _json.loads(user.explored_tiles)
        if not isinstance(all_explored, dict):
            return set()

        seed_key = str(seed)
        if seed_key not in all_explored:
            return set()

        tiles_str = all_explored[seed_key]
        return _parse_tiles_string(tiles_str)
    except Exception:
        return set()


def save_explored_tiles(seed: int, tiles: Set[Tuple[int, int]]):
    """Save explored tiles for the given seed to the current user's profile.

    Args:
        seed: Dungeon seed
        tiles: Set of (x, y) coordinates that have been explored
    """
    if not current_user or not current_user.is_authenticated:
        # Fall back to session-only storage
        session_key = f"explored_tiles:{seed}"
        session[session_key] = _encode_tiles_set(tiles)
        return

    user = db.session.get(User, current_user.id)
    if not user:
        return

    try:
        # Load existing explored tiles
        if user.explored_tiles:
            all_explored = _json.loads(user.explored_tiles)
            if not isinstance(all_explored, dict):
                all_explored = {}
        else:
            all_explored = {}

        # Update for this seed
        seed_key = str(seed)
        all_explored[seed_key] = _encode_tiles_set(tiles)

        # Save back to user
        user.explored_tiles = _json.dumps(all_explored)
        db.session.commit()
    except Exception:
        db.session.rollback()


def update_explored_tiles(seed: int, new_tiles: Set[Tuple[int, int]]):
    """Add new tiles to the explored set for the given seed.

    Args:
        seed: Dungeon seed
        new_tiles: Set of (x, y) coordinates newly explored
    """
    existing = load_explored_tiles(seed)
    existing.update(new_tiles)
    save_explored_tiles(seed, existing)


def _parse_tiles_string(tiles_str: str) -> Set[Tuple[int, int]]:
    """Parse a tiles string like 'x1,y1;x2,y2;...' into a set of coordinates."""
    if not tiles_str:
        return set()

    result = set()
    for pair in tiles_str.split(";"):
        if not pair:
            continue
        try:
            x_str, y_str = pair.split(",")
            result.add((int(x_str), int(y_str)))
        except Exception:
            continue

    return result


def _encode_tiles_set(tiles: Set[Tuple[int, int]]) -> str:
    """Encode a set of coordinates into a string like 'x1,y1;x2,y2;...'"""
    if not tiles:
        return ""

    return ";".join(f"{x},{y}" for x, y in sorted(tiles))
