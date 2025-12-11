Adventure Items Bundle
======================

This bundle defines concrete loot items across major categories for the roguelite "Adventure":

- items_weapons.csv
  Specific named weapons tied to weapon_categories (swords, axes, bows, staves, etc.).
  Includes base rarity, level range, damage bonus, stat hooks, and flavor tags.

- items_armor.csv
  Concrete armor pieces for cloth, leather, mail, plate, and shields.
  Includes armor values, stat hooks, slots, and rarity.

- items_jewelry.csv
  Rings and amulets providing utility, defensive, or progression bonuses.

- items_consumables.csv
  Potions, bombs, scrolls, food, and keys with effect types and scaling formulas.

These are intended as "base items" which can then be modified further by rarity scaling
and procedural affixes (from procedural_affixes.csv). You can expand this library by adding
rows or extending columns as your design evolves.
