# Playtest triage — 2026-07-27 (seed 733064)

First real play session on the multi-floor build. Raw observations from the
player, triaged into bugs / tuning / design work. Nothing here is speculation
about what *might* be wrong: every "bug" below was traced to a line of code
before being written down.

Inspiration set (`~/screenshots/`, 2026-07-27): Gold Box tactical combat
(Pool of Radiance / Curse of the Azure Bonds), Final Fantasy Pixel Remaster
party+enemy group framing, and a Phantasy Star-style panel layout. The common
thread across all three, and the answer to most of the combat feedback:
**the whole party and the whole enemy group are on screen at once, positioned,
with live per-character status and legible hit feedback.**

---

## Fixed in this pass

- **Monsters focused a single character.** `monster_auto_turn`'s basic-attack
  path sorted the party by HP ascending and always swung at the lowest
  (`combat_service.py`, "Prioritize low HP targets"), with two other sites
  hard-coded to `members[0]`. One character absorbed every fight while the rest
  spectated. Replaced with `_pick_monster_target`: weighted random among the
  living, biased toward the wounded (1.0x at full health → 2.0x at death's
  door) but never locked onto them.
- **Downed characters still "took" a turn.** Every action handler refuses to
  act while unconscious, but `_advance_turn` stepped onto downed players
  anyway, so their turn became the *active* turn — the client offered the
  buttons and the player spent a click burning it. `_advance_turn` now steps
  over downed party members.

- **Spells and skills did not scale; attacks did.** Measured through the real
  service functions (`scripts/audit_combat_damage.py`):

  | level | attack | firebolt | lightning | skill (flat base) |
  |------:|-------:|---------:|----------:|------------------:|
  | 1     | 15.2   | 17.4     | 18.4      | 5–22, constant    |
  | 5     | 20.0   | 17.0     | 18.4      | 5–22, constant    |
  | 10    | 25.2   | 17.3     | 19.2      | 5–22, constant    |
  | 20    | **31.8** | 17.8   | 17.4      | 5–22, constant    |

  A weapon swing is `attack ± 25%` where `attack = 8 + STR/2 + level + gear`, so
  it doubles over 20 levels. A spell was `2d8 + 0.6×INT` — no level term at all.
  A skill was the bare constant in its `effect_json`, with no stat input
  whatsoever. By level 5 the free action beat both; by 20 it was nearly double,
  while spells and skills still cost mana and cooldowns.

  The root cause was structural: `_derive_stats` never put `level` in the combat
  party snapshot, so nothing downstream *could* scale by it. Fixed by carrying
  `level` into the snapshot and introducing `_spell_power = 0.6×INT + level`
  (the caster's answer to a weapon user's `attack`). Spells add it to their dice;
  skills add their `effect_json` base on top of `attack` (physical) or
  `_spell_power` (caster); heals add half of it. After:

  | level | attack | firebolt | lightning | skill b5 | skill b22 |
  |------:|-------:|---------:|----------:|---------:|----------:|
  | 1     | 16.4   | 18.5     | 17.9      | 21.0     | 31.0      |
  | 5     | 19.3   | 21.9     | 24.1      | 25.0     | 35.0      |
  | 10    | 23.7   | 25.4     | 26.9      | 30.0     | 40.0      |
  | 20    | 35.8   | 35.6     | 37.5      | 40.0     | 50.0      |

  Ordering is now attack ≤ spell < skill, which matches their costs: an attack
  is free, a spell costs mana and can miss, a skill costs mana plus a cooldown
  and always hits. Note firebolt sits at parity with a free swing at level 20 —
  it is the cheapest spell (5 mana) and its edge is elemental typing against
  resistances, but if it still feels weak in play, its dice are the dial.

## Bugs — confirmed, not yet fixed

- **Party Stash button does nothing.** `adventure-controls.js` literally pops
  `alert('Party Stash feature coming soon!')`.
- **Camping is unlimited.** `dungeon_camp` restores 30% max HP + 50% mana and
  applies a regen buff, with no cost, cooldown or supply. Advancing 8 ticks is
  the only price, and the wandering-monster roll on those ticks is the only
  risk. Proposal: camping supplies as a consumable with charges, plus a
  cooldown, plus a real ambush chance while resting.
- **Floor difficulty rubber-bands upward.** Spawn levels are pinned to the
  party's *average level at the moment a floor is first mapped*
  (`dungeon_api._initialize_spawn_system` → `party_level`), and elites are +1,
  bosses +2. Level up on floor 0 and floor 1 generates harder than it would
  have been — descending after gaining a level makes the world scale with you
  instead of you outgrowing it. This is why level 1 mobs became level 3 and
  wiped the party. Needs an explicit difficulty curve per floor/tier rather
  than "whatever the party is right now".
- **Monster loot tables resolve to nothing.** `loot_table` values
  (`goblin_basic`, `boss_dragon`, …) are parsed by
  `loot_service._parse_loot_table` as a CSV of *item slugs*; items are
  kebab-case (`short-sword`), so every monster's item pool is empty. Monsters
  have never dropped catalogue loot.
- **Catalogue tops out at level 20** while characters can reach 50. Above 20,
  archetype spawns have no identity to borrow and fall back to a bare label.

## Tuning

- **Maze is too maze-y** — too many spiralling corridors. Levers live in
  `DungeonConfig`: `dead_end_keep`, `extra_connection_chance`, `straight_max`,
  and the maze-fill weighting in `connect.fill_maze`. Wants a play-feel pass,
  not a rewrite.
- **Spawn density and group size.** Related to the combat work below: fighting
  one mob at a time is the core complaint, not the number of mobs.
- **Mana economy** (pre-existing TODO): skill costs 4/8/12 vs a +5 mana potion.
- ~~Spells and skills feel weaker than a plain attack~~ — **confirmed and
  fixed**, see above. The player's instinct ("stats aren't applying") was
  right; the snapshot did not carry `level` at all.

## Design work — needs a spec each

### 1. Combat overhaul (the big one)
Current model is one party vs **one** monster, resolved through a log. The
references point at:
- **Enemy groups**: a room's mobs fight together. Requires `CombatSession` to
  hold a monster *list*, initiative across all combatants, and per-enemy
  targeting/health.
- **Positioning grid**: Gold Box-style tactical placement — front/back matters,
  melee reach, ranged and AoE become meaningfully different.
- **Readable feedback**: damage numbers on the actors, hit/miss/crit visible on
  the sprite rather than only as log text.
- **Live party panel**: HP/MP/status per character, always visible, updating.

Big enough to phase: (a) multi-enemy encounters without a grid, (b) grid and
positioning, (c) the visual layer.

### 2. Dungeon map readability
- Walls vs floor are hard to tell apart — darker walls, stronger contrast.
- A lot of empty space; wants props/dressing.
- **Location awareness**: coordinate readout plus current floor ("B2"), so the
  player can note and return to a spot. The minimap alone is not enough.

### 3. Adventure screen UX
- Buttons "feel strange"; the log window is restrictive, especially when
  looting found items — looting deserves a real panel, not log lines.
- Character panels are static; they should react (damage, status, turn).
- **Use D&D lingo throughout** — "Party Stash" is the wrong register.

---

## Suggested order

1. Damage-formula audit (cheap, and it decides whether "spells feel weak" is a
   bug or a tuning problem).
2. Camping supplies + cooldown; floor difficulty curve. Both are small, both
   change the run's shape immediately.
3. Map readability: wall contrast + coordinates/floor indicator. Small, high
   daily value.
4. Maze tuning pass.
5. Combat overhaul, phased. Everything else is smaller than this.
