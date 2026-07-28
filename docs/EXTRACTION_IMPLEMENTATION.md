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

#### Extraction Penalties
- **Early Extraction** (before all bosses defeated):
  - -20% of the XP **earned during that run**, plus the same cut on the
    extraction bonus. Career XP is never touched.
  - -20% of the copper that reaches the Hoard. Items are never skimmed — only
    coin, applied to the deposit itself and to the reported total.
- **No penalties** when all bosses defeated (Hearthstone Portal active)

The XP rate is tunable: **Admin → Dungeon Settings → Early Exit XP Penalty (%)**,
which mirrors into `GameConfig["progression"]["early_extraction_xp_penalty"]` (a
0..1 share) — the key `app/services/progression.py` actually reads. See
"Admin settings" below for why the mirror is needed.

The run baseline comes from `instance.dungeon_metadata["xp_at_entry"]`, written
by `dashboard.commit_party_to_run()` — the one place every entry path (Start
Adventure and Continue Adventure alike) binds a party to a run. No baseline
(older instances) means no deduction — it never falls back to docking career XP,
which is what the -30% rule used to do.

Baseline entries are only ever added, never rewritten. Re-entering a live run
must not re-mark it, or a player could bank a run's XP by bouncing off the
dashboard before extracting.

#### Permadeath Rules
- Characters left behind during extraction → **PERMADEATH**
- Dead characters can be revived (items/spells/shrines) during run
- Permadeath characters cannot be revived
- Full party wipe = all characters lost

## Ways a Run Ends

A run starts when the dashboard creates (or resumes) the `DungeonInstance`.
Both the `start_adventure` and `continue_adventure` forms then call
`commit_party_to_run()`, which sets `locked_dungeon_id = instance.id` on every
party member and records the XP baseline. `extraction_service` selects the party
by that column, so the lock is what makes any of the three exits below possible —
any future entry path owes the run the same call.

| Exit | Endpoint | Characters | Haul | Dungeon |
|------|----------|-----------|------|---------|
| **Extract** | `POST /api/dungeon/extraction/extract` | Released; left-behind members permadeath | Pooled into the Hoard (full-clear bonus if cleared, -20% copper if early) | Instance kept until deleted by the caller |
| **Hearthstone (abandon)** | `POST /api/dungeon/hearth` | All released, no deaths, no penalty | Kept as-is in their bags | Instance **deleted** — the next trip is a fresh dungeon |
| **Wipe** | (no endpoint — resolved in combat) | All dead + `permadeath`, locks cleared | Lost with them; never pooled | Instance **deleted**, session pointer cleared |

Hearthstone is no-fault: the player had to stop, not lose. It applies no XP or
loot penalty. (It used to halve each character's *lifetime* XP, which was both
punitive and a bug — the penalty was never scoped to the run.)

A wipe is terminal and resets the world: `combat_service.resolve_party_defeat_if_any`
permadeaths every member, clears their dungeon locks, deletes the instance and
drops `session['dungeon_instance_id']`. The player must create or recruit new
characters, and starts a brand-new dungeon when they do.

Deleting an instance cascades to its `DungeonEntity` rows via the
`DungeonInstance.entities` relationship — without that cascade the DELETE fails on
`dungeon_entity`'s foreign key.

## Kill Tracking

`bosses_defeated` / `elites_defeated` / `monsters_defeated` are incremented in
`combat_service._check_end` when a monster dies. It finds the instance through the
combat session's `dungeon_snapshot_json` (written by `start_session`), and reads
the archetype off the monster payload — which `trigger_collision_combat` copies
wholesale from the spawn's stored `data`. Break either link and kill tracking
silently stops: no extraction unlock, no quest progress.

## Admin Settings

The admin panel's five settings pages each persist their own JSON blob
(`dungeon_settings`, `combat_settings`, `loot_settings`, `progression_settings`,
`fog_settings`). **No gameplay module reads any of them.** The engine reads a
different, smaller set of `GameConfig` keys:

| Engine key | Read by |
|---|---|
| `monster_ai` | `services/monster_ai.py`, `services/monster_patrol.py`, `combat_service.start_session` |
| `progression` | `services/progression.py` |
| `floor_loot` | `loot/generator.py` |
| `rarity_weights` | `services/spawn_service.py` (**monster** rarity, not item) |
| `regen_rates`, `tick_costs`, `durability`, `trading` | status effects, time, durability, merchant seeding |

`admin_new._mirror_to_engine()` copies the wired-up fields across on save:

| Page field | Engine key |
|---|---|
| Dungeon → Early Exit XP Penalty | `progression.early_extraction_xp_penalty` |
| Combat → Ambush Chance | `monster_ai.ambush_chance` |
| Combat → Monster Spell Chance | `monster_ai.spell_chance` |
| Combat → Monster Flee HP Threshold | `monster_ai.flee_threshold` |
| Combat → Monster Help Chance | `monster_ai.help_chance` |
| Loot → Rarity Weights | `floor_loot.rarity_weights` |

Everything else on those pages is still inert, and each page carries a banner
saying so. To wire a new knob: give it a consumer in the engine, mirror it here,
and make the page's default match the engine's default so that saving the page
untouched is a no-op (`test_admin_settings_reach_gameplay.py` asserts this).

Two traps worth remembering:

* Percent vs share — the pages work in whole percent, the engine in 0..1.
* `rarity_weights` means two different things. The Loot page's weights are
  *item* rarity and mirror to `floor_loot.rarity_weights`; the top-level
  `rarity_weights` key weights *monster* rarity in spawn_service. Mirroring the
  first onto the second would silently reweight every spawn.

## Monsters, Archetypes and Identity

Two systems feed a spawn, and both must be seeded or spawns degrade silently:

* `monster_catalog` (105 rows, `sql/monsters_seed.sql`) — who a creature *is*:
  name, family, level band, traits, loot table.
* `enemy_archetype` (8 rows, `sql/enemy_archetypes_seed.sql`) — how a set piece
  *scales*: Trash/Skirmisher/Brute/Caster/Elite/Champion/Miniboss/Boss, each with
  per-level HP, damage, AC and XP curves that tier and affixes modify.

Ambient spawns come straight from the catalogue. Elite and boss spawns take
their stats from the archetype and their identity from the catalogue
(`spawn_service._identity_for_archetype`), preferring the dungeon's own
`monster_family` and only widening if that family has nothing at the level.
Ordinary ranks may never borrow a catalogued boss's identity — a Trash mob
wearing a boss's name would read as the dungeon boss to `boss_abilities.is_boss`
and unlock extraction.

If either table is unseeded, `populate_spawn_stats` falls back to a bare
`"<Archetype> Monster"` with `hp = level * 20` and no loot table. That fallback
now logs `spawn_stats_fallback`; it used to be silent, which is how an empty
`enemy_archetype` table went unnoticed in a live database.

Known gaps: the catalogue covers levels 1–20 while characters can reach 50, and
`loot_table` values (`goblin_basic`, `boss_dragon`, …) are parsed by
`loot_service._parse_loot_table` as **CSV item slugs**, so they resolve to
nothing — every monster's item pool is currently empty.

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
- **Trigger**: "Extract" button (hotkey `E`) on the adventure screen. The "Hearth"
  button (hotkey `H`) sits next to it and abandons the run instead — the two used
  to share `#btn-hearth`, so opening the modal also fired the abandon request.
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
1. Boss defeated in combat → `combat_service._check_end` increments
   `bosses_defeated` (see Kill Tracking above). `POST /api/dungeon/extraction/boss_defeated`
   does the same thing and exists for clients that resolve a boss out of band.
2. If `bosses_defeated >= bosses_total` → `extraction_available=True`
3. The sealed loot room's locked doors open (`effective_unlocked_doors`) and the
   exit portal at its center becomes reachable

### Extraction Flow
1. Player clicks "Extract" (hotkey `E`)
2. Modal shows extraction status and character list
3. Player selects characters to extract
4. Server applies penalties (if early)
5. Extracted characters: unlocked, revived, haul pooled into the Hoard
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

## Testing

`tests/test_full_run_e2e.py` plays whole runs through the real HTTP endpoints —
entry, exploration, collision combat, stairs both ways, boss kill, loot claim,
portal, extraction, plus a wipe run and a hearthstone run. It exists because the
unit-level tests around extraction all fabricate the win state on the instance row
(`bosses_defeated = 1`, `extraction_available = True`) and call the service
directly, which meant nothing exercised kill tracking, the party lock, or instance
deletion. Every one of those was broken.

Keep at least one test that reaches the win state by *playing* rather than by
setting columns.

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
