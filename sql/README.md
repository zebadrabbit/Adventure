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
```
(Adjust path if using a different DB URI.)

## Future Enhancements
- Add rarity tiers (common/uncommon/rare/epic/legendary) via new column.
- Introduce `stat_mods` JSON column for storing per-item bonuses.
- Normalize accessories into their own table if complexity grows.
- Add spawn weight tables to tune dungeon / shop distribution probabilities.
- Add localization keys for names & descriptions.

## Testing Hooks
For deterministic test fixtures you can load only a minimal subset (e.g., level 1 and level 10 rows) or create a dedicated `items_test.sql` containing a smaller pool.
