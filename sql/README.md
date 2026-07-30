# Item Seed SQL Files

This directory contains SQL seed data for the `item` table. The current schema (see `app/models/models.py`) defines:
```
item(id INTEGER PK, slug TEXT UNIQUE, name TEXT, type TEXT, description TEXT, value_copper INTEGER)
```

## Files
- `items_weapons.sql` – **Missing from this directory.** Documented as level 1-20 progression for eight weapon classes (sword, axe, spear/halberd, bow, dagger, staff, mace, wand), with roughly quadratic value scaling and thematic rarity boosts. The file has never been committed; weapons currently come from the seed data in `app/server.py` and the procedural generator.
- `items_armor.sql` – **Missing from this directory.** Documented as level 1-20 sets for the armor slots (head, chest, hands, feet) plus offhand/shield, rings and amulets. Armor currently comes from the same places as weapons. Note there is no `legs` slot: the canonical vocabulary is the eight names in `app/loot/data/archetypes.py` (`SLOTS`), and D&D-style body armour is one piece, so leg armour is part of the chest piece.
- `items_potions.sql` – Healing & mana potions (levels 1-20), offensive/defensive/speed buff elixirs, antidotes, elemental resistance potions (sparse tier milestones).
- `items_misc.sql` – Tools, scrolls, gems, crafting materials, consumables, and generic keys used for future locked/secret door mechanics.
- `monsters_seed.sql` – Catalog of monsters (common, named elite, bosses) with level bands, base stats, rarity tiers, and optional special drops referencing existing item slugs.
- `dungeon_tiers_seed.sql` – Creates `dungeon_tier` and seeds the seven difficulty tiers (Novice → Mythic) with level bands, monster level modifiers, loot quality bonuses, and XP multipliers.
- `dungeon_affixes_seed.sql` – Creates `dungeon_affix` and seeds ten run modifiers (Frenzied, Bolstered, Volcanic, …) with HP/damage/speed multipliers, a player damage-taken multiplier, and a `special_effect` JSON blob.
- `enemy_archetypes_seed.sql` – Creates `enemy_archetype` and seeds the eight combat roles (Trash → Boss) with base and per-level HP, damage, armor class, XP, and a loot multiplier.
- `weapon_categories_seed.sql` – Creates `weapon_category` and seeds twelve weapon families with damage dice, primary stat, crit multiplier, attack speed, tags, and allowed classes.
- `achievement_system_migration.sql` – Creates `achievement`, `character_achievement`, and `achievement_category` plus their indexes, then seeds six categories and eighteen starter achievements.
- `skill_system_migration.sql` – Creates `skill_tree`, `skill`, `character_skill`, and `character_talent_points` plus their indexes, then seeds the Warrior/Mage/Cleric trees with five skills each across tiers 1-3.
- `party_system_migration.sql` – Creates `party`, `party_member`, `party_buff`, and `party_shared_inventory` plus their indexes, then seeds one default party from the existing characters.
- `trading_system_migration.sql` – Adds `character.gold` and creates `merchant`, `merchant_stock`, and `trade_transaction` plus their indexes, then seeds three starter merchants (general, weapons, armor).

The four `*_migration.sql` files are Postgres dialect (`SERIAL`, `ON CONFLICT`, `ADD COLUMN IF NOT EXISTS`) and are applied with `psql` — each system's doc under `docs/` gives the exact command. The `*_seed.sql` files above them are SQLite dialect (`AUTOINCREMENT`), so the two sets are not interchangeable and neither loads cleanly under the other engine.

## Conventions
- Slug pattern: `<category>_<subcat>_l<level>` for level-scaled gear; non-leveled utility items drop the `_l<level>` suffix.
- Value units: `value_copper` is the full integer price in copper coins (future formatting can derive silver/gold).
- All gear is currently cross-class usable; specialization (e.g., class restrictions) can be introduced later by adding a column or a join table.
- Deletion guards: Each file begins by `DELETE`ing existing rows for its slug pattern to allow idempotent re-seeding.
- Transactions: Wrapped in `BEGIN TRANSACTION; ... COMMIT;` for atomic loading.

## Loading
From project root in an environment with the SQLite DB (`instance/mud.db` by default):
```bash
sqlite3 instance/mud.db < sql/items_potions.sql
sqlite3 instance/mud.db < sql/items_misc.sql
sqlite3 instance/mud.db < sql/monsters_seed.sql
```
(Adjust path if using a different DB URI. `items_weapons.sql` and `items_armor.sql`
are described above but are not in this directory, so they cannot be loaded.)

## Future Enhancements
The following ideas extend the now-implemented monster + loot systems:
- Introduce `stat_mods` JSON column for storing per-item bonuses.
- Normalize accessories into their own table if complexity grows.
- Add spawn weight override tables (region/biome specific) referencing `monster_catalog.slug`.
- Add localization keys for names & descriptions.
- Procedural affixes that modify monster instances at runtime (prefix/suffix system) producing variant slugs.
- Elite pack generation & multi-monster formations.
- XP & drop analytics for balancing.

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

## Implemented Monster & Loot Integration (Summary)
- Runtime encounter spawning hooked into `/api/dungeon/move` with weighted rarity selection and midpoint bias.
- Monster scaling: HP +15%, Damage +10%, XP +20% per additional party member beyond one.
- Caching: eligible monster query results are cached in-memory for 30s to reduce DB load.
- Loot tables: `loot_table` column accepts CSV / JSON list / JSON object (weights); `special_drop_slug` grants a 25% drop chance unless suffixed with `!guaranteed` in the table.
- Resistance support: optional `resistances` (JSON mapping) and `damage_types` columns added by migration helper; helper `apply_resistances` in `app/services/combat_utils.py` ready for combat integration.
- Admin endpoints: `/api/admin/monsters` (filtered catalog listing) and `/api/admin/force_spawn` (scaled encounter + loot preview) facilitate balancing.
