# Dungeon Generation Fixes

## Fix 1: Corridor Gap Repair - Seed 177545

### Issue
At seed 177545, position (30, 20) showed a Cave tile when there should have been a Tunnel connecting to a nearby room. The tunnel was supposed to bridge from a vertical corridor to the room's wall/door.

## Root Cause
The `_repair_corridor_gaps()` method in `app/dungeon/dungeon.py` was missing a pattern:
- **Tunnel → Cave → Wall/Door** alignment where the cave should become a tunnel to properly connect the corridor to the room entrance

This pattern occurs when:
1. A tunnel approaches a room
2. Caves fill the gap before the wall/door
3. The corridor generation logic stops before completing the connection

## Fix Applied
Added **Pattern 4** to `_repair_corridor_gaps()`:

```python
# Pattern 4: Tunnel-to-Wall gap (T-C-W/D/S pattern)
# This handles cases where a tunnel approaches a room but caves fill the gap before the wall/door
if tunnels >= 1 and walls_or_doors >= 1 and rooms == 0:
    # Verify there's a linear alignment: tunnel on one side, wall/door on opposite side
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        tx, ty = x - dx, y - dy  # Tunnel position (opposite direction)
        wx, wy = x + dx, y + dy  # Wall/door position
        if (0 <= tx < w and 0 <= ty < h and self.grid[tx][ty] == TUNNEL and
            0 <= wx < w and 0 <= wy < h and self.grid[wx][wy] in (WALL, DOOR, SECRET_DOOR, LOCKED_DOOR)):
            to_fill.append((x, y))
            break
```

## Results
### Before Fix:
```
   67890123
24 CCCCCCCC
23 CCCCCCCC
22 CCCCCCCC
21 CCCCCCCC
20 CCCCCCCC  <- No tunnel at x=29
19 WWWSWWWW
18 RRRRRRRR
```

### After Fix:
```
   67890123
24 CCCTCCCC
23 CCCTCCCC
22 CCCTCCCC
21 CCCTCCCC
20 CCCTCCCC  <- Tunnel now at (29, 20)
19 WWWSWWWW  <- Connects to Secret Door at (29, 19)
18 RRRRRRRR
```

The fix properly connects the vertical tunnel at x=29 through position (29, 20) down to the secret door at (29, 19), which leads into the room below.

## Testing
- Existing test `test_corridor_gap_repair.py` continues to pass
- Created verification script `quick_test_177545.py` to validate the specific seed
- All corridor gap repair invariants maintained:
  - No adjacent doors
  - No walls with 2+ tunnel neighbors
  - Tunnel spans >=4 exist

## Files Modified
- `app/dungeon/dungeon.py` - Enhanced `_repair_corridor_gaps()` method

---

## Fix 2: Secret Door Rendering - Seed 354321

### Issue
At seed 354321, position (42, 49) contained a Secret Door ('S') but was **rendering as a cave** in the game UI. This violated the design rule that "caves should never touch rooms" and made secret doors indistinguishable from caves.

### Root Cause
Two missing mappings:
1. **Backend**: `char_to_type()` in `app/dungeon/api_helpers/tiles.py` didn't handle 'S' (SECRET_DOOR) or 'L' (LOCKED_DOOR), defaulting them to "cave"
2. **Frontend**: `adventure.js` tile renderer had no color definitions for `secret_door` or `locked_door` tile types

### Fix Applied
**Backend** - Added Secret Door and Locked Door mappings:
```python
# app/dungeon/api_helpers/tiles.py
from app.dungeon.dungeon import SECRET_DOOR, LOCKED_DOOR

def char_to_type(ch: str) -> str:
    # ... existing mappings ...
    if ch == SECRET_DOOR:
        return "secret_door"
    if ch == LOCKED_DOOR:
        return "locked_door"
    return "cave"
```

**Frontend** - Added appropriate colors for new tile types:
```javascript
// app/static/js/adventure.js (line ~956)
cell.cell_type === 'secret_door' ? '#3d2a1f' :  // dark brown (wall-like, unrevealed)
cell.cell_type === 'locked_door' ? '#664466' :  // darker purple (door variant)
```

### Color Choices
- **Secret Door** (`#3d2a1f`): Dark brown, similar to walls - visually blends with wall rings since secret doors should appear as walls until revealed
- **Locked Door** (`#664466`): Darker purple, variant of regular door color (`#551455`) - indicates it's a special door type

### Results
- Secret doors now render with wall-like appearance (dark brown) instead of cave black
- Locked doors render with distinct darker purple color
- Both tile types are now properly distinguished from caves in the UI
- No cave-room adjacency violations (walls/doors properly separate all caves from rooms)

### Testing
```
Seed 354321, position (42, 49):
  Raw tile: 'S'
  Mapped to: 'secret_door'
  Status: ✓ FIXED
```

## Files Modified (Fix 2)
- `app/dungeon/api_helpers/tiles.py` - Added SECRET_DOOR and LOCKED_DOOR mappings
- `app/static/js/adventure.js` - Added color definitions for secret_door and locked_door tiles
