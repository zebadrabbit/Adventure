# Monster AI & Configuration

This document describes the monster behavior system, configuration keys, and feature flags.

## Overview
Monsters now support modular behaviors:
- Ambush pre-combat surprise strike
- Spell casting (currently Firebolt) with accuracy/crit/resistance logic
- Fleeing when low HP
- Calling for help (log only placeholder)
- Action cooldown between turns
- Status effects (poison, stun) via generic effects list
- Vulnerabilities & resistances (damage multipliers)

All new behaviors are opt-in via monster flags and governed by server-wide probabilities stored in the `GameConfig` row with key `monster_ai`.

## Monster Flags (per-monster JSON fields)
| Field | Type | Description |
|-------|------|-------------|
| `ai_enabled` | bool | Enables AI decision delegation (otherwise legacy basic attack). |
| `enable_monster_spells` | bool | Allows spell decisions (requires `spells` list). |
| `enable_monster_flee` | bool | Permits flee attempts under threshold conditions. |
| `enable_monster_help` | bool | Permits help call attempt. |
| `enable_ambush` | bool | Monster may ambush on encounter start. |
| `spells` | list[str] | Known spell identifiers (currently supports `firebolt`). |
| `resistances` | dict[str,float] | Damage type multipliers (<1 resist, >1 vulnerability). |

## Global Configuration (`GameConfig` key `monster_ai`)
Store a JSON object. All keys optional; unspecified keys fall back to internal defaults.

| Key | Default | Meaning |
|-----|---------|---------|
| `ambush_chance` | 0.5 | Chance an ambush-enabled monster succeeds (0-1). |
| `spell_chance` | 0.4 | Chance to cast a spell (per eligible turn). |
| `flee_threshold` | 0.2 | HP% (0-1) below which flee logic may trigger. |
| `flee_chance` | 0.3 | Chance to actually flee when under threshold. |
| `help_threshold` | 0.5 | HP% below which help call considered. |
| `help_chance` | 0.2 | Chance to log help call when under threshold. |
| `cooldown_turns` | 0 | Minimum turns to wait between monster actions (turn-based throttle). |
| `patrol_enabled` | false | Enable simple wandering for idle monsters (non-combat loop integration required). |
| `patrol_step_chance` | 0.1 | Probability a patrol-enabled monster takes a 1-tile step on a patrol tick. |
| `patrol_radius` | 5 | Max Chebyshev distance from initial patrol origin (x0,y0). |

Example row value:
```json
{
  "ambush_chance": 0.35,
  "spell_chance": 0.5,
  "flee_threshold": 0.25,
  "flee_chance": 0.4,
  "help_threshold": 0.4,
  "help_chance": 0.15,
  "cooldown_turns": 0
}
```
Insert/update via:
```python
from app.models.models import GameConfig, json
GameConfig.set("monster_ai", json.dumps({...}))
```

## Status Effects
Effects live under `participant['effects']` list with schema:
```json
{"name":"poison","remaining":3,"data":{"damage":5}}
```
Supported:
- `poison` (start-of-turn damage)
- `stun` (pre-action veto one turn per remaining)

Add new effects by extending maps in `app/services/status_effects.py`.

## Damage Types & Vulnerabilities
`apply_resistances(base, [types], resistances)` applies multipliers.
- Values <1 reduce damage, >1 increase (vulnerability) — already supported; no extra code needed.

## Cooldown Logic
If `cooldown_turns` > 0, a monster that acted on turn `T` will skip acting again until `combat_turn >= T + cooldown_turns` (logging a cooldown wait message).

## Ambush Sequence
1. Encounter starts (session created, initiative rolled).
2. If monster has `enable_ambush` and random roll < `ambush_chance`, it performs one surprise basic attack before normal turn order begins.

## Testing Summary
`tests/test_monster_ai.py` covers:
- Flee gating when flag disabled
- Guaranteed spell cast when spell chance forced to 1.0
- Cooldown preventing consecutive actions
- Vulnerability increasing damage

## Adding New Behaviors
1. Add config knobs to `monster_ai` JSON (document defaults).
2. Extend `monster_ai.select_action` to produce new action type.
3. Handle new action branch inside `combat_service.monster_auto_turn`.
4. Gate via per-monster flag to preserve backwards compatibility.
5. Add focused tests with probability forcing (mock `random.random`).

## Iconography
Assign monster icon slugs referencing SVG assets (tooling TBD). Suggest adding a `icon_slug` field in monster definitions; UI layer can map to `static/icons/<slug>.svg`.

## Future Enhancements
- Patrol movement & room boundary logic
- Door / teleport restrictions enforcement
- Multi-target spells & AoE status effects
- Dynamic difficulty scaling using party composite level & gear score

Patrol keys defined (see table) and module `app/services/monster_patrol.py` implements `maybe_patrol`. Integrate by calling it during world ticks / player movement events and persisting updated monster state when it returns True.

---
Maintainers: update this document when adding new AI keys or effect types to keep gameplay tuning transparent.
