# Locked Door System

Complete implementation of locked doors with key items and rogue lockpicking abilities.

## Overview

Locked doors (`L`) block passage until unlocked using either:
1. **Key items** (consumable, found as loot)
2. **Rogue lockpicking** (skill check, requires lockpicks tool)

## Key Items

Three types of keys are available:

| Item | Rarity | Value | Description |
|------|--------|-------|-------------|
| `rusty-key` | Common | 50cp | Opens simple locked doors |
| `master-key` | Rare | 500cp | Opens any locked door |
| `boss-key` | Epic | 1000cp | Opens boss chamber doors |

### Key Sources

- **Boss drops**: Every boss drops one key (33% rusty, 50% master, 17% boss-key)
- **Treasure loot**: Keys can appear in treasure caches
- **Monster drops**: Elite monsters may drop keys

## Rogue Lockpicking

### Requirements

1. Character must be a **Rogue** (DEX >= other stats, CHA < 14)
2. Must have **lockpicks** tool in inventory
3. Must be within 1 tile of the locked door

### Skill Check

```
DC = 10 + (dungeon_tier × 2)
Roll = 1d20 + DEX_modifier
Success if Roll >= DC
```

### Outcomes

- **Success** (roll >= DC): Door unlocks permanently
- **Failure** (roll < DC): Door remains locked
- **Critical Failure** (roll = 1): Lockpicks break and are consumed

### Example DCs

| Dungeon Tier | DC | DEX Needed (50% chance) |
|--------------|-----|-------------------------|
| 1 | 12 | 14 (+2) |
| 2 | 14 | 16 (+3) |
| 3 | 16 | 18 (+4) |
| 5 | 20 | 22 (+6) |

## API Endpoints

### Unlock Door

```http
POST /api/dungeon/unlock
Content-Type: application/json

{
  "x": 42,
  "y": 50,
  "method": "key",        // "key" or "lockpick"
  "key_slug": "rusty-key" // optional, auto-detects if omitted
}
```

**Success Response (Key)**:
```json
{
  "unlocked": true,
  "method": "key",
  "key_used": "rusty-key"
}
```

**Success Response (Lockpick)**:
```json
{
  "unlocked": true,
  "method": "lockpick",
  "roll": 15,
  "total": 18,
  "dc": 14
}
```

**Error Responses**:
```json
{ "error": "Too far" }           // Distance > 1 tile
{ "error": "Not locked" }         // Not a locked door tile
{ "error": "Already unlocked" }   // Door previously unlocked
{ "error": "No key" }             // No valid key in inventory
{ "error": "Not rogue" }          // Character isn't a rogue
{ "error": "No lockpicks" }       // Missing lockpicks tool
{ "error": "Lockpick failed", "broken": true, "roll": 1 }  // Critical failure
{ "error": "Lockpick failed", "broken": false, "roll": 8 } // Normal failure
```

### Dungeon State

The `/api/dungeon/state` endpoint now includes:

```json
{
  "pos": [42, 50, 0],
  "desc": "You are in a room. Exits: North, East.",
  "exits": ["n", "e"],
  "unlocked_doors": [[42, 51], [43, 50]]
}
```

## Database Schema

### DungeonInstance Model

New column:
```python
unlocked_doors_json = db.Column(db.Text, nullable=True)
```

Stores JSON array of `[x, y]` coordinates:
```json
[[42, 51], [43, 50], [44, 52]]
```

### Helper Methods

```python
instance.get_unlocked_doors()      # Returns set of (x,y) tuples
instance.unlock_door(x, y)         # Mark door as unlocked
instance.is_door_unlocked(x, y)    # Check if door is unlocked
```

## Movement System

### Walkability Changes

The `Dungeon.is_walkable()` method now accepts an optional `unlocked_doors` parameter:

```python
def is_walkable(self, x: int, y: int, unlocked_doors=None) -> bool:
    cell = self.grid[x][y]
    if cell == LOCKED_DOOR:
        if unlocked_doors is None:
            return False
        return (x, y) in unlocked_doors
    return cell in (ROOM, TUNNEL, DOOR, TELEPORT)
```

### Movement Helpers

All movement helpers in `app/dungeon/api_helpers/movement.py` updated:
- `normalize_position()` - passes unlocked_doors to is_walkable
- `attempt_move()` - checks unlocked_doors before allowing movement
- `describe_cell_and_exits()` - filters exits by unlocked status

## Frontend Integration

### Basic Example

```javascript
// Check if tile is a locked door
if (cell.cell_type === 'locked_door') {
    // Show unlock button if adjacent
    const dist = Math.max(
        Math.abs(cell.x - player.pos[0]),
        Math.abs(cell.y - player.pos[1])
    );

    if (dist === 1) {
        showUnlockButton(cell.x, cell.y);
    }
}

// Attempt unlock
async function unlockDoor(x, y, method) {
    const response = await fetch('/api/dungeon/unlock', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ x, y, method })
    });

    const result = await response.json();

    if (result.unlocked) {
        if (method === 'lockpick') {
            console.log(`Lockpick: rolled ${result.roll}+${result.total-result.roll} = ${result.total} vs DC ${result.dc}`);
        }
        // Refresh map to show unlocked door
        refreshDungeonState();
    } else {
        alert(result.error);
        if (result.broken) {
            alert('Your lockpicks broke!');
        }
    }
}
```

## Game Balance

### Key Economy

- **Scarcity**: Keys are relatively rare, making lockpicking valuable
- **Consumable**: Using a key removes it from inventory
- **Boss reward**: Killing bosses always provides keys for progression

### Rogue Utility

- **Non-consumable**: Lockpicking doesn't consume keys
- **Risk/reward**: Can fail and break lockpicks
- **Scaling difficulty**: Higher tier dungeons are harder to pick
- **Class identity**: Gives rogues unique utility beyond combat

### Door Placement

Locked doors spawn on:
- **Boss room entrances**: 1 guaranteed locked door per boss room
- **Treasure rooms**: Sometimes locked (via secret door logic)
- **Random rooms**: Probabilistic generation

## Testing

### Manual Test Flow

1. Create rogue character with lockpicks
2. Enter dungeon, find locked door (look for boss room)
3. Move adjacent to locked door (within 1 tile)
4. Attempt lockpick: `POST /api/dungeon/unlock {"x": X, "y": Y, "method": "lockpick"}`
5. Verify success/failure based on roll
6. Try to move through door - should work if unlocked

### Test with Keys

1. Kill a boss to get a key drop
2. Find another locked door
3. Use key: `POST /api/dungeon/unlock {"x": X, "y": Y, "method": "key"}`
4. Verify key consumed from inventory
5. Door should unlock and remain unlocked

## Future Enhancements

- **Key durability**: Rusty keys might break after use
- **Door difficulty**: Different lock types requiring specific keys
- **Lockpick quality**: Better lockpicks give bonuses
- **Perks/skills**: Rogue skill tree for lockpicking bonuses
- **Trap detection**: Locked doors might have traps
- **Sound effects**: Audio feedback for lockpicking attempts
