from typing import List, Optional, Tuple

class DungeonCell:
    """Lightweight container for a dungeon grid cell."""
    __slots__ = ("cell_type", "features")
    def __init__(self, cell_type: str, features: Optional[List[str]] = None):
        self.cell_type = cell_type
        self.features = features or []

    def to_dict(self):
        return {"cell_type": self.cell_type, "features": self.features}

Grid3D = List[List[List[DungeonCell]]]
Coord2D = Tuple[int,int]
Size3D = Tuple[int,int,int]
