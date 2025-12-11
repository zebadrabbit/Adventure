# HP/MP Persistence System

## Overview
The HP/MP persistence system ensures character health and mana values are correctly tracked throughout the entire dungeon exploration and combat flow. This document describes the complete lifecycle of HP/MP values and the fixes applied to ensure proper persistence.

## The Persistence Flow

### 1. Character Creation
When a character is created, their stats are stored in `Character.stats` as JSON:
```json
{
  "str": 14,
  "dex": 12,
  "con": 14,
  "int": 12,
  "hp": 103,  // Current HP
  "current_mana": 44,  // Current mana
  "class": "fighter"
}
```

### 2. Max Value Calculation
Max HP and mana are calculated consistently across the codebase:
- **Max HP**: `50 + CON×2 + level×5`
- **Max Mana**: `20 + INT×2`

These formulas are used in:
- `combat_service._derive_stats()` (line 82-85)
- `dashboard_helpers.build_party_payload()` (line 210-213)
- `dungeon_api.dungeon_state()` (line 1086-1089)

### 3. Dungeon Exploration
During exploration, HP/MP values are read from `Character.stats`:
- `/api/dungeon/state` returns party array with current HP/MP
- Dashboard shows current values (not max)
- Values persist across movement, camping, and other non-combat actions

### 4. Combat Entry
When combat starts via `combat_service.start_session()`:
1. Calls `_derive_stats()` for each character
2. Reads `stats['hp']` for current HP (falls back to max HP if not set)
3. Reads `stats['current_mana']` for current mana
4. Creates `party_snapshot_json` with these values

**Fixed**: Previously always used max HP, now reads persisted current HP.

### 5. During Combat
Combat modifies HP/MP in `party_snapshot_json`:
- Damage reduces HP: `member['hp'] -= damage`
- Healing restores HP: `member['hp'] = min(max_hp, hp + heal_amount)`
- Spells consume mana: `member['mana'] -= spell_cost`
- Potions restore both

### 6. Combat Completion
When combat ends, `_persist_party_resources()` saves values back:
```python
stats_obj['hp'] = int(m.get('hp', ...))
stats_obj['current_mana'] = int(m.get('mana', ...))
row.stats = json.dumps(stats_obj)
db.session.add(row)
```

This ensures damaged characters stay damaged after combat.

### 7. Camping
The `/api/dungeon/camp` endpoint restores HP/MP:
- Reads current values from `Character.stats`
- Restores 30% max HP, 50% max mana
- Writes updated values back to `Character.stats`

### 8. Extraction
Final HP/MP values persist through extraction. Characters retain their state for future dungeon runs.

## Key Components

### combat_service._derive_stats()
**Location**: `app/services/combat_service.py:64`

**Purpose**: Convert Character model to combat-ready stats dict

**Fixed Logic**:
```python
# Read persisted current HP (line 88-93)
hp_source = base.get("hp", max_hp)
try:
    hp = int(hp_source)
except Exception:
    hp = max_hp
hp = max(0, min(hp, max_hp))  # Clamp to valid range

return {
    "hp": hp,  # Uses persisted value
    "max_hp": max_hp,
    "mana": mana,  # Already read from current_mana
    "mana_max": mana_max,
}
```

**Before**: Always returned max HP, ignoring persisted values.

**After**: Reads `stats['hp']`, falls back to max HP only for new characters.

### dashboard_helpers.build_party_payload()
**Location**: `app/routes/dashboard_helpers.py:197`

**Purpose**: Build party data for dashboard display

**Fixed Logic**:
```python
# Read actual current HP/MP from stats (line 218-219)
hp = int(s.get("hp", hp_max))  # Default to full if not set
mana = int(s.get("current_mana", s.get("mana", mana_max)))
```

**Before**: Hardcoded `hp = hp_max` and `mana = mana_max` (always full).

**After**: Reads actual persisted values, shows real state.

### dungeon_api.dungeon_state()
**Location**: `app/routes/dungeon_api.py:1026`

**Purpose**: Return current dungeon state including party info

**Added**:
```python
# Add party HP/MP for UI display (lines 1086-1127)
party_chars = Character.query.filter_by(user_id=current_user.id).limit(4).all()
party_data = []
for char in party_chars:
    stats = json.loads(char.stats)
    # Calculate max values
    max_hp = 50 + con * 2 + level * 5
    max_mana = 20 + intelligence * 2
    # Read current values
    hp = int(stats.get("hp", max_hp))
    mana = int(stats.get("current_mana", stats.get("mana", max_mana)))
    party_data.append({
        "char_id": char.id,
        "name": char.name,
        "hp": hp,
        "max_hp": max_hp,
        "mana": mana,
        "max_mana": max_mana,
    })
resp["party"] = party_data
```

**Before**: API didn't include party HP/MP at all.

**After**: Frontend can display accurate HP/MP bars during exploration.

### combat_service._persist_party_resources()
**Location**: `app/services/combat_service.py:665`

**Status**: Already working correctly

**Logic**:
```python
stats_obj["hp"] = int(m.get("hp", stats_obj.get("hp", 0)))
stats_obj["current_mana"] = int(m.get("mana", ...))
row.stats = json.dumps(stats_obj)
db.session.add(row)
db.session.commit()
```

This function correctly writes combat HP/MP back to Character.stats.

## Testing HP/MP Persistence

### Manual Test Scenario
1. Create character with specific HP (e.g., 50/100)
2. Enter combat → verify party_snapshot has hp=50
3. Take damage in combat → verify hp decreases
4. Complete combat → verify Character.stats['hp'] updated
5. Move around dungeon → verify HP persists
6. Enter new combat → verify starts with reduced HP (not full)
7. Camp → verify HP restored by 30%
8. Check dashboard → verify shows actual HP values

### Automated Testing
Run HP/MP persistence tests:
```bash
pytest tests/test_combat_persistence.py -v
```

These tests verify:
- HP persists after monster defeat
- HP persists after player flee
- Mana persists through combat actions

### Diagnostic Script
Use the diagnostic script to analyze the flow:
```bash
python3 scripts/diagnose_hp_mp.py
```

This shows all key locations where HP/MP is read/written.

## Common Issues and Solutions

### Issue: Combat starts with full HP every time
**Cause**: `_derive_stats()` returning max HP instead of reading persisted value

**Fix**: Applied in this update - now reads `stats['hp']`

### Issue: Dashboard shows full HP after combat damage
**Cause**: `build_party_payload()` hardcoding `hp = hp_max`

**Fix**: Applied in this update - now reads `stats['hp']`

### Issue: Frontend can't display HP bars during exploration
**Cause**: `/api/dungeon/state` didn't include party data

**Fix**: Applied in this update - now includes party array

### Issue: HP resets after camping
**Cause**: Camp endpoint not reading current values

**Fix**: Already working - camp correctly reads and writes

## Data Model

### Character.stats Structure
```json
{
  // Core Stats (uppercase or lowercase)
  "str": 14, "STR": 14,
  "dex": 12, "DEX": 12,
  "con": 14, "CON": 14,
  "int": 12, "INT": 12,
  "wis": 10, "WIS": 10,
  "cha": 10, "CHA": 10,

  // Resource Tracking
  "hp": 75,  // Current HP (0 to max_hp)
  "current_mana": 30,  // Current mana (0 to max_mana)
  "mana": 30,  // Legacy key (prefer current_mana)

  // Character Info
  "class": "fighter",
  "level": 5,

  // Calculated at runtime (not stored):
  // max_hp = 50 + CON*2 + level*5
  // max_mana = 20 + INT*2
}
```

### Combat Session party_snapshot_json
```json
{
  "members": [
    {
      "char_id": 123,
      "name": "TestHero",
      "char_class": "fighter",
      "hp": 75,  // Current HP during combat
      "max_hp": 103,
      "mana": 30,  // Current mana during combat
      "mana_max": 44,
      "attack": 18,
      "defense": 9,
      "speed": 14,
      "defending": false,
      "buffs": []
    }
  ],
  "item_counts": {
    "potion-healing": 3
  }
}
```

## Migration Notes

### Existing Characters
Characters created before this fix may not have `hp` or `current_mana` keys in their stats. The system handles this gracefully:
- Missing `hp`: defaults to max HP
- Missing `current_mana`: defaults to max mana or legacy `mana` key

### Database Schema
No schema changes required. All HP/MP data stored in `Character.stats` TEXT column (JSON).

## Performance Considerations

### Calculation Frequency
Max HP/mana calculated:
- When entering combat (_derive_stats)
- When displaying dashboard (build_party_payload)
- When returning dungeon state (dungeon_state)

**Optimization**: Values could be cached in stats JSON, but recalculation is cheap and ensures consistency if level/stats change.

### Query Efficiency
`dungeon_state` now loads party characters:
```python
party_chars = Character.query.filter_by(user_id=current_user.id).limit(4).all()
```

**Impact**: Adds one extra query per state check, but only retrieves 4 rows max.

## Related Documentation
- [Combat System](../README.md#combat-system) - Overall combat flow
- [Combat Effects](COMBAT_EFFECTS.md) - Visual damage/healing effects
- [Locked Doors](LOCKED_DOORS.md) - Door unlock mechanics (related to HP/MP management during exploration)

## Changelog Reference
See `CHANGELOG.md` [Unreleased] section:
- HP/MP Persistence Fixes
- Combat Bug Fixes (dead character handling)
