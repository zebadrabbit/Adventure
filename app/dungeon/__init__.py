"""Dungeon generation package (modularized from former monolithic dungeon.py).

Public entry point: import Dungeon from app.dungeon (re-export from pipeline).
"""
"""Public exports for dungeon generation package.

External code should import Dungeon and DungeonCell from here to remain
stable while internal implementation is refactored.
"""

from .pipeline import Dungeon
from .cells import DungeonCell

__all__ = ["Dungeon", "DungeonCell"]

__all__ = ["Dungeon", "DungeonCell"]
