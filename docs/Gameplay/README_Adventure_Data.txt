Adventure Data Bundle
=====================

This bundle contains core CSV data files for the roguelite "Adventure".
They are designed to be consumed by tools like GitHub Copilot, or wired
directly into your game's data-driven systems.

Files:

- enemy_templates.csv
  Archetype-level enemy templates with base stats and scaling coefficients
  for Normal, Elite, and Boss ranks.

- loot_rarities.csv
  Rarity tiers from Common to Mythic, with drop weights, affix counts, and
  value multipliers.

- weapon_categories.csv
  High-level weapon categories (sword, axe, bow, staff, etc.) with base dice,
  stat scaling, tags, and class usage suggestions.

- procedural_affixes.csv
  Diablo-style prefixes and suffixes with affected stats, value ranges,
  rarity weights, and allowed item types.

- xp_table_level_1_to_50.csv
  Unified XP progression from level 1 to 50 with XP-to-next, cumulative XP,
  talent point distribution, and loot-tier scaling hints.

You can safely tweak numbers, add new rows, or extend columns as your
design evolves. Treat these as starting baselines, not rigid rules.
