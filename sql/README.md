# Item Seed SQL Files

This directory contains SQL seed data for the `item` table. The current schema (see `app/models/models.py`) defines:
```
item(id INTEGER PK, slug TEXT UNIQUE, name TEXT, type TEXT, description TEXT, value_copper INTEGER)
```

## Files
- `items_weapons.sql` – Level 1-20 progression for eight weapon classes (sword, axe, spear/halberd, bow, dagger, staff, mace, wand). Value scaling uses roughly quadratic growth with thematic rarity boosts.
- `items_armor.sql` – Level 1-20 sets for armor slots (head, chest, legs, hands, feet) plus belt, cloak, shield, rings, amulets.
- `items_potions.sql` – Healing & mana potions (levels 1-20), offensive/defensive/speed buff elixirs, antidotes, elemental resistance potions (sparse tier milestones).
- `items_misc.sql` – Tools, scrolls, gems, crafting materials, consumables, and generic keys used for future locked/secret door mechanics.
- `monsters_seed.sql` – Catalog of monsters (common, named elite, bosses) with level bands, base stats, rarity tiers, and optional special drops referencing existing item slugs.

## Conventions
- Slug pattern: `<category>_<subcat>_l<level>` for level-scaled gear; non-leveled utility items drop the `_l<level>` suffix.
- Value units: `value_copper` is the full integer price in copper coins (future formatting can derive silver/gold).
- All gear is currently cross-class usable; specialization (e.g., class restrictions) can be introduced later by adding a column or a join table.
- Deletion guards: Each file begins by `DELETE`ing existing rows for its slug pattern to allow idempotent re-seeding.
- Transactions: Wrapped in `BEGIN TRANSACTION; ... COMMIT;` for atomic loading.

## Loading
From project root in an environment with the SQLite DB (`instance/mud.db` by default):
```bash
sqlite3 instance/mud.db < sql/items_weapons.sql
sqlite3 instance/mud.db < sql/items_armor.sql
sqlite3 instance/mud.db < sql/items_potions.sql
sqlite3 instance/mud.db < sql/items_misc.sql
sqlite3 instance/mud.db < sql/monsters_seed.sql
```
(Adjust path if using a different DB URI.)

## Future Enhancements
- Add rarity tiers (common/uncommon/rare/epic/legendary) via new column.
- Introduce `stat_mods` JSON column for storing per-item bonuses.
- Normalize accessories into their own table if complexity grows.
- Add spawn weight tables to tune dungeon / shop distribution probabilities.
- Add localization keys for names & descriptions.
- Link monsters to region/biome spawn tables referencing `monster_catalog.slug`.
- Add `resistances` and `damage_types` JSON columns to monster schema.
- Introduce procedural affixes that modify base monster rows at runtime.

## Testing Hooks
For deterministic test fixtures you can load only a minimal subset (e.g., level 1 and level 10 rows) or create a dedicated `items_test.sql` containing a smaller pool.

## Monster Scaling Overview
The monster catalog uses tiered level bands:
T1 (1-3), T2 (4-6), T3 (7-9), T4 (10-12), T5 (13-15), T6 (16-18), T7 (19-20).

Base stat guidelines:
- HP: `~ level * (8 + tier_mod)` (tier_mod increases by ~2–4 each band)
- Damage: `~ level * (1 + tier_mod/10)`
- Armor: Increases modestly for undead/elemental defenders, lower for beasts/goblins.
- Speed: Baseline 10, faster for agile (goblins, wolves), slower for heavy elementals.

Rarity influences expected spawn frequency (logic to be added) and suggested XP reward. `boss=1` rows represent end-of-region landmarks and include a `special_drop_slug` guaranteeing (or heavily weighting) a unique drop.

Example integration pseudocode (future):
```python
# choose monster for region level L
candidates = [m for m in monsters if m.level_min <= L <= m.level_max]
# weight by rarity -> common:1, uncommon:0.6, rare:0.3, elite:0.15, boss:0.02
```

Import command (idempotent):
```bash
sqlite3 instance/mud.db < sql/monsters_seed.sql
```

Re-importing will replace prior rows because the file issues a DELETE on the table first.
