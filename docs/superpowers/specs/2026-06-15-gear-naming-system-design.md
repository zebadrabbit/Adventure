# Gear & Naming System — Design

**Date:** 2026-06-15
**Status:** Approved (design); pending implementation plan
**Branch:** `gear-system`

## 1. Goal

Turn finite data tables into endless, build-defining loot. Every drop is a base
*archetype* rolled up with a *rarity*, optional *prefix*, and optional themed
*suffix* → a composed display name plus real stat bonuses that matter in combat.
The aim is to make a one-shot dungeon run feel rewarding and worth coming back to,
WoW/Diablo-style, where a name like "… of the Hawk" implies a stat package.

### Approved decisions (from brainstorming)

| Decision | Choice |
|---|---|
| Affix model | **Hybrid**: themed stat-package *suffixes* (`of the Hawk` = DEX+CON) + single-stat *prefixes* (`Brutal` = +damage) |
| Mechanics | **Affixes modify combat stats** (gear matters; equipped affixes feed stat derivation) |
| Data authorship | **Author a deep set now** in code-defined data modules (not the hasty old-manual SQL) |
| Item architecture | **Procedural from archetypes** (replace the hand-tiered `weapon_*_l1..l20` catalog) |
| Loot determinism | **Random each run** (no seed/coord derivation needed) |
| Equipment slots | **Moderate set (8)**: Weapon, Offhand, Head, Chest, Hands, Feet, Ring, Amulet |
| Sequencing | **Infra first** (item-seed bug + Postgres), then the gear system |
| Data tables | **Code-defined** (Python/JSON modules), not DB-seeded affixes |
| Item storage | **Self-contained JSON item instances** in existing columns (no new tables) |
| Tiered catalog | **Removed** in favor of archetypes |

### Context: current state of the codebase

- A half-built procedural affix system exists but is **dormant**:
  - `ProceduralAffix` + `ItemAffix` models, ~20 seeded affixes, and
    `app/loot/affix_generator.py` (`apply_procedural_affixes`).
  - The real drop path (`app/services/loot_service.py::roll_loot`, used by combat
    and treasure) **ignores affixes** — affixes never reach gameplay.
  - There is **no name composition** (prefix + base + suffix → display name).
- **Equipped gear has zero combat effect today**: `combat_service._derive_stats`
  reads only `character.stats`, never `character.gear`.
- Items are stored as JSON in text columns: `character.items` (slug list),
  `character.gear` (`{}`), `character.stats`. The `Item` model is a flat catalog
  (`slug, name, type, level NOT NULL, rarity, weight, value_copper`).
- A pre-existing seed bug (`NOT NULL constraint failed: item.level`) blocks loading
  `items_weapons.sql` on a fresh DB.
- Existing item/affix data was "hastily pulled together from old manuals" and is
  **not** treated as authoritative.

## 2. Phase 0 — Infra first

### 2.1 Fix the item-seed bug
`reseed-items` fails on a fresh DB with `NOT NULL constraint failed: item.level`.
The seed pipeline (`app/seed_items.py`) only augments `level` for certain insert
shapes. Fix so every `INSERT INTO item` path supplies a `level` (default 0), and
verify `reseed-items` loads clean on **both SQLite and PostgreSQL**. Because the
hand-tiered weapon/armor/jewelry catalog is being removed in favor of archetypes
(§3), the remaining seeded `Item` rows are primarily **consumables** (potions,
keys, tools); the fix keeps those loading cleanly.

### 2.2 Postgres setup
Stand up the app on PostgreSQL using the running docker container:
- Point the app at a clean `adventure` database (resolve the `.env` /
  `localhost:5433` target; create DB/user as needed).
- Run schema (`create_all`) + migrations + seeds against it.
- Update `.env` / `docs/TESTING.md` and add a **one-command bootstrap script**
  (e.g. `scripts/bootstrap_db.sh` or a `run.py` subcommand) that creates,
  migrates, and seeds the DB repeatably for dev and CI.
- Confirm the full test suite stays green on Postgres.

## 3. Data model (code-defined)

Four small, version-controlled data tables live as Python/JSON data modules under
`app/loot/data/` (easy to extend; the user can add entries). They replace the
hasty SQL data.

### 3.1 Archetypes (base items)
Each archetype defines: `key`, display `base_name`, `slot`, `category`,
base `damage`/`armor` range, `attack_speed` (weapons), and `affinity` (which
attribute themes fit, used to weight affix eligibility).

- **Weapons:** Dagger, Shortsword, Longsword, Greatsword, Mace, Warhammer,
  Greataxe, Spear, Bow, Crossbow, Staff, Wand.
- **Offhand:** Shield (armor), Tome (caster), Orb (caster).
- **Armor** (material drives base armor — cloth/leather/mail/plate):
  Head, Chest, Hands, Feet.
- **Jewelry** (pure affix carriers, no base armor): Ring, Amulet.

### 3.2 Prefixes (single-stat, tiered)
Examples: `Sharp → Keen → Brutal → Savage → Cruel` (+flat damage),
`Sturdy/Reinforced` (+armor), `Flaming/Frozen/Shocking` (+elemental),
`Quick` (+speed), `Vampiric` (lifesteal). Tier scales with item level/rarity.
Each prefix declares `affected_stat`, value range, scaling, allowed slots/categories,
and a rarity-weight.

### 3.3 Suffixes (themed stat *packages*)
The "of the X" model: one suffix → a small set of `(stat, weight)` pairs with a
flavor name. ~40–60 entries mapping to the six attributes (STR, DEX, INT, WIS, CON,
CHA) plus a few derived stats (crit, resist, mana). Examples:
`of the Hawk` (DEX+CON), `of the Bear` (STR+CON), `of the Eagle` (INT+CON),
`of the Owl` (INT+WIS), `of the Tiger` (STR+DEX), `of the Whale` (big CON/HP),
`of the Wolf` (DEX+WIS), `of the Gorilla` (STR+INT), `of the Sorcerer` (INT+crit).

### 3.4 Rarities
`common → uncommon → rare → epic → legendary → mythic`, each with an affix-count
range and a UI color. Higher rarity = more affixes and higher value.

| Rarity | Affixes | Color |
|---|---|---|
| common | 0–1 | grey |
| uncommon | 1–2 | green |
| rare | 2–3 | blue |
| epic | 3–4 | purple |
| legendary | 3–5 | orange |
| mythic | 4–6 | red/gold |

## 4. Roll engine

Build on `app/loot/affix_generator.py`. Core entry point:

```
generate_item(level: int, rarity: str | None = None, slot: str | None = None,
              rng: random.Random | None = None) -> dict  # item instance
```

Algorithm:
1. Roll or accept `rarity` → affix-count range.
2. Pick a base archetype (respecting `slot` and `level`).
3. Roll N affixes (prefix and/or themed suffix) eligible for that archetype's
   slot/category/affinity, no duplicates, weighted by rarity-weight.
4. Roll each affix value, scaled by item level.
5. Compose the name (§5) and compute a gold value (base value + affix value).

Loot is **random each run** — no seed/coordinate derivation. RNG is injectable for
deterministic tests.

## 5. Name composition

`[Prefix] <Base> [of <Suffix>]`:
- "Brutal Shortsword of the Hawk"
- "Reinforced Plate Helm of the Whale"
- "Oak Wand of the Owl"
- bare commons → just "Shortsword"

Rarity drives display color in the UI.

## 6. Item instances & storage

Each rolled item is a **self-contained JSON instance** (no join schema, fits the
existing JSON-in-column convention):

```json
{
  "uid": "…",
  "base": "shortsword",
  "slot": "weapon",
  "name": "Brutal Shortsword of the Hawk",
  "rarity": "rare",
  "ilvl": 7,
  "affixes": [
    {"stat": "damage", "val": 4},
    {"stat": "dex", "val": 8},
    {"stat": "con", "val": 5}
  ],
  "value": 240
}
```

- `character.items` → list of these instances. Stackable consumables remain
  `{slug, qty}` and continue to resolve against the `Item` catalog.
- `character.gear` → `{slot: instance}` for the 8 slots.
- Gear is *generated*, not seeded, so this sidesteps new tables/migrations and the
  item-seed bug entirely for gear. Potions/consumables stay in the `Item` catalog.

The dormant `ProceduralAffix` / `ItemAffix` DB tables are superseded by code-defined
data + JSON instances; remove or leave inert (decided in the plan, default: remove
to avoid confusion, consistent with deleting the tiered catalog).

## 7. Stat application

Add `gear_bonuses(character) -> dict[str, number]` that sums equipped affixes into
a stat dict (str/dex/int/wis/con/cha + derived: damage, armor, crit, resist, speed,
mana, max_hp). Fold it into:
- `combat_service._derive_stats` (combat read path), and
- the dashboard party payload / `serialize_character_list` (display read path).

One clean seam, applied in both places, so `of the Hawk` on a bow really raises DEX
→ better hit/damage rolls in combat and accurate dashboard numbers.

## 8. Loot integration

`roll_loot` (the real drop path for monsters and treasure) calls `generate_item(...)`
to produce instances instead of bare slugs, scaled to monster/dungeon level; bosses
roll higher rarity / more drops. The treasure-claim and combat-reward flows store
instances into `character.items`. Equip/inventory APIs (`inventory_api.py`,
`loot_api.py`) updated to handle instances and the 8 slots.

## 9. UI (light touch)

- Item names colored by rarity; tooltip lists affixes.
- Equip into the 8 slots (paper-doll). Full visual polish deferred (pairs naturally
  with the future three.js work).

## 10. Testing

- Roll engine: rarity → affix counts, archetype/affix eligibility, value scaling,
  name composition (deterministic under seeded RNG).
- Stat application math (`gear_bonuses` sums + combat read).
- Loot integration (drops produce valid instances; bosses skew rarity).
- Suite stays green on PostgreSQL.

## 11. Out of scope (future)

Set bonuses, seed-deterministic loot, sockets/gems, admin-tunable affix DB, and the
**three.js** experience upgrade — revisit once this system is functional.
