# Extraction Mechanics Implementation Summary

## Overview
Implemented a complete extraction mechanics system for the Adventure MUD, including permadeath, locked-in-dungeon states, extraction penalties, and UI.

## Database Changes

### Character Table (Migration: 95ff19b9fe00)
New fields added:
- `locked_in_dungeon` (Boolean): Character is trapped in a specific dungeon
- `locked_dungeon_id` (Integer): FK to dungeon instance where character is locked
- `is_dead` (Boolean): Character died in current dungeon run
- `permadeath` (Boolean): Character permanently died (left behind on extraction)
- `death_count` (Integer): Tracks number of deaths for statistics

### DungeonInstance Table (Migration: 95ff19b9fe00)
New fields added:
- `bosses_defeated` (Integer): Number of bosses killed in this dungeon
- `extraction_available` (Boolean): True when all bosses defeated (Hearthstone Portal active)

## New Services

### `app/services/extraction_service.py`
Complete extraction mechanics service with:
- `check_extraction_available()` - Validates if extraction is possible
- `calculate_extraction_penalties()` - Computes XP/loot penalties for early extraction
- `extract_party()` - Main extraction logic with permadeath handling
- `handle_character_death()` - Marks character as dead and locks to dungeon
- `revive_character()` - Handles resurrection via items/spells/shrines
- `get_extraction_status()` - Returns current extraction state for UI

#### Extraction Penalties (from DESIGN.md)
- **Early Extraction** (before all bosses defeated):
  - -30% XP loss
  - -20% loot quality reduction
- **No penalties** when all bosses defeated (Hearthstone Portal active)

#### Permadeath Rules
- Characters left behind during extraction → **PERMADEATH**
- Dead characters can be revived (items/spells/shrines) during run
- Permadeath characters cannot be revived
- Full party wipe = all characters lost

## New API Endpoints

### `app/routes/extraction_api.py`
Blueprint: `bp_extraction`

#### `GET /api/dungeon/extraction/status`
Returns extraction status for current dungeon:
```json
{
  "extraction_available": true,
  "reason": "Hearthstone Portal is active",
  "all_bosses_defeated": true,
  "bosses_defeated": 1,
  "characters": [
    {
      "id": 1,
      "name": "Thorin",
      "level": 5,
      "is_dead": false,
      "locked_in_dungeon": true,
      "permadeath": false
    }
  ],
  "penalties": {
    "xp_multiplier": 1.0,
    "loot_quality_multiplier": 1.0
  }
}
```

#### `POST /api/dungeon/extraction/extract`
Extract selected characters from dungeon:
```json
{
  "character_ids": [1, 2, 3]  // Characters to extract
}
```
Response:
```json
{
  "success": true,
  "message": "Extracted 3 character(s)",
  "result": {
    "extracted": ["Thorin", "Legolas", "Gimli"],
    "left_behind": [],
    "penalties": {...},
    "early_extraction": false
  }
}
```

#### `POST /api/dungeon/extraction/revive`
Revive a dead character (via item/spell/shrine):
```json
{
  "character_id": 1
}
```

#### `POST /api/dungeon/extraction/boss_defeated`
Mark a boss as defeated (triggers extraction availability check):
```json
{
  "instance_id": 42  // Optional, uses session if omitted
}
```

## UI Components

### Extraction Modal (`adventure.html`)
- **Trigger**: "Hearth" button on adventure screen
- **Features**:
  - Displays all characters in current dungeon
  - Shows dead/alive status for each character
  - Checkbox selection for extraction
  - **Warning**: Characters left behind will suffer PERMADEATH
  - **Penalty Display**: Shows XP loss % and loot quality reduction % for early extraction
  - **Confirm Button**: Validates at least one character selected
  - **Auto-reload**: Refreshes page after successful extraction

### JavaScript Handler
- Fetches extraction status on modal open
- Dynamically builds character selection checkboxes
- Shows/hides penalty warnings based on boss status
- Handles extraction confirmation with validation
- Error handling and user feedback

## Integration Points

### Character Death Flow
1. Character dies in combat → `handle_character_death(char, instance)`
2. Character marked as `is_dead=True`, `locked_in_dungeon=True`
3. Character can be revived during run via items/spells/shrines
4. If party extracts without character → `permadeath=True`

### Boss Defeat Flow
1. Boss defeated in combat → POST `/api/dungeon/extraction/boss_defeated`
2. `bosses_defeated` incremented
3. If `bosses_defeated >= required` → `extraction_available=True`
4. Hearthstone Portal activates (no penalties for extraction)

### Extraction Flow
1. Player clicks "Hearth" button
2. Modal shows extraction status and character list
3. Player selects characters to extract
4. Server applies penalties (if early)
5. Extracted characters: unlocked, revived, XP reduced
6. Left behind characters: `permadeath=True`
7. Page reloads to reflect changes

## Enemy Scaling Integration

### New Spawn Function: `choose_archetype_monster()`
Located in `app/services/spawn_service.py`

#### Parameters
- `level`: Base dungeon level
- `archetype_name`: Specific archetype (Trash, Elite, Boss, etc.) or None for weighted random
- `tier`: Dungeon tier (1-7) - adds monster_level_modifier
- `affix_ids`: List of affix_id strings to apply
- `party_size`: Party size for scaling
- `rng`: Random number generator

#### Scaling Formula
```python
modified_level = level + tier_modifier
stats = archetype.scale_to_level(modified_level)
stats["hp"] *= (1 + (party_size - 1) * 0.5)  # Party scaling
stats["damage"] *= (1 + (party_size - 1) * 0.3)
# Apply affixes
for affix in affixes:
    stats = affix.apply_to_monster_stats(stats)
# Apply tier multipliers
stats["xp"] *= tier_row.xp_multiplier
stats["loot_multiplier"] *= (1.0 + tier_row.loot_quality_bonus)
```

#### Returns
Monster dict with archetype-scaled stats:
```python
{
    "slug": "elite",
    "name": "Elite (L15)",
    "hp": 570,
    "damage": 91,
    "armor_class": 29,
    "xp": 1080,
    "level": 15,
    "rank": "elite",
    "loot_multiplier": 2.4,
    "archetype": "Elite"
}
```

## Updated Models

### Character Model (`app/models/models.py`)
```python
locked_in_dungeon = db.Column(db.Boolean, default=False)
locked_dungeon_id = db.Column(db.Integer, nullable=True)
is_dead = db.Column(db.Boolean, default=False)
permadeath = db.Column(db.Boolean, default=False)
death_count = db.Column(db.Integer, default=0)
```

### DungeonInstance Model (`app/models/dungeon_instance.py`)
```python
tier = db.Column(db.Integer, default=1)
affix_ids = db.Column(db.Text, nullable=True)
bosses_defeated = db.Column(db.Integer, default=0)
extraction_available = db.Column(db.Boolean, default=False)

def get_affixes(self):
    """Parse affix_ids JSON string into list."""

def set_affixes(self, affix_list):
    """Set affix_ids from a list of affix_id strings."""
```

## Testing Recommendations

1. **Character Death**:
   - Verify `is_dead` flag set on combat death
   - Verify `locked_in_dungeon` and `locked_dungeon_id` set correctly
   - Test resurrection mechanics

2. **Extraction**:
   - Test early extraction with penalties applied
   - Test extraction after all bosses defeated (no penalties)
   - Test leaving characters behind → permadeath
   - Test extracting all characters

3. **Boss Defeat**:
   - Test `bosses_defeated` increment
   - Test `extraction_available` flag activation
   - Test multiple bosses (if implemented)

4. **UI**:
   - Test modal display with character list
   - Test checkbox selection validation
   - Test penalty warning display
   - Test permadeath warnings

5. **Enemy Scaling**:
   - Test archetype-based monster spawning
   - Test tier modifiers applied correctly
   - Test affix multipliers stacking
   - Test party size scaling

## Future Enhancements

1. **Resurrection Items**:
   - Implement consumable items that call `revive_character()`
   - Resurrection scrolls, shrines, spells

2. **Extraction Timer**:
   - Optional countdown for extraction portal
   - Timed events (Diablo-style)

3. **Multiple Bosses**:
   - Configure bosses_required based on dungeon tier
   - Boss progression tracking

4. **Character Locking UI**:
   - Dashboard indicator for locked characters
   - Visual distinction for permadeath characters
   - Death count statistics display

5. **Hardcore Mode**:
   - Optional permanent permadeath on any death
   - No resurrection allowed

## Files Modified

### New Files
- `migrations/versions/95ff19b9fe00_add_extraction_and_permadeath_fields_to_character.py`
- `app/services/extraction_service.py`
- `app/routes/extraction_api.py`

### Modified Files
- `app/models/models.py` - Added extraction fields to Character
- `app/models/dungeon_instance.py` - Added extraction and tier fields
- `app/__init__.py` - Registered extraction blueprint
- `app/templates/adventure.html` - Added extraction modal and JS handler
- `app/services/spawn_service.py` - Added archetype integration

## Migrations Applied

1. `b8e4c2f6d9a3` - Enemy scaling system (archetypes, tiers, affixes)
2. `41a271547ca1` - Spawn weight and description for enemy archetypes
3. `95ff19b9fe00` - Extraction and permadeath fields

All migrations successfully applied to database.
