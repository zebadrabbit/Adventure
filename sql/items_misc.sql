-- Miscellaneous, Crafting, Gems, Scrolls, Tools
-- Non-level or tiered by quality rather than strict 1-20 sequences.
BEGIN TRANSACTION;

DELETE FROM item WHERE slug LIKE 'tool_%';
INSERT INTO item (slug, name, type, description, value_copper) VALUES
('tool_lockpick_basic','Basic Lockpick Set','tool','Opens simple locks (consumable charges TBD).',60),
('tool_lockpick_fine','Fine Lockpick Set','tool','Better success on tougher locks.',180),
('tool_mining_pick','Mining Pick','tool','Allows extraction of ore veins.',120),
('tool_herbal_kit','Herbalist Kit','tool','Enables gathering of rare herbs.',140),
('tool_fishing_rod','Fishing Rod','tool','Catch aquatic ingredients.',90),
('tool_camp_kit','Camping Kit','tool','Set temporary rest site.',200);

DELETE FROM item WHERE slug LIKE 'scroll_%';
INSERT INTO item (slug, name, type, description, value_copper) VALUES
('scroll_identify','Scroll of Identify','scroll','Reveals properties of an item.',160),
('scroll_portal_minor','Minor Portal Scroll','scroll','Opens a short-range portal.',420),
('scroll_recall','Scroll of Recall','scroll','Returns party to entrance.',520),
('scroll_dispel','Scroll of Dispel','scroll','Negates minor magical effects.',480),
('scroll_barrier','Scroll of Barrier','scroll','Creates temporary protective field.',650);

DELETE FROM item WHERE slug LIKE 'gem_%';
INSERT INTO item (slug, name, type, description, value_copper) VALUES
('gem_quartz','Raw Quartz','gem','Common translucent crystal.',80),
('gem_amber','Amber Chunk','gem','Golden fossil resin.',140),
('gem_garnet','Garnet Shard','gem','Deep red crystal.',260),
('gem_sapphire','Sapphire Shard','gem','Blue crystalline fragment.',480),
('gem_emerald','Emerald Shard','gem','Green crystalline fragment.',520),
('gem_ruby','Ruby Shard','gem','Brilliant red fragment.',580),
('gem_diamond','Uncut Diamond','gem','Highly prized gem.',1200),
('gem_starstone','Starstone','gem','Rare stone that glitters with inner light.',1800),
('gem_dragon_eye','Dragon Eye Gem','gem','Legendary gem swirling with power.',2600);

DELETE FROM item WHERE slug LIKE 'material_%';
INSERT INTO item (slug, name, type, description, value_copper) VALUES
('material_iron_ore','Iron Ore Chunk','material','Smeltable iron ore.',40),
('material_mythril_ore','Mythril Ore Chunk','material','Rare light alloy ore.',360),
('material_adamant_ore','Adamant Ore Chunk','material','Dense hard ore.',520),
('material_dragonbone_frag','Dragonbone Fragment','material','Piece of ancient dragonbone.',900),
('material_star_metal','Star Metal Fragment','material','Fallen star alloy piece.',1500);

DELETE FROM item WHERE slug LIKE 'consumable_%';
INSERT INTO item (slug, name, type, description, value_copper) VALUES
('consumable_ration_basic','Basic Rations','consumable','Simple preserved food.',30),
('consumable_ration_hearty','Hearty Rations','consumable','Higher quality preserved food.',70),
('consumable_campfire_kit','Campfire Kit','consumable','Guarantees safe rest once.',160),
('consumable_antidote_universal','Universal Antidote','consumable','Cures most poisons (single use).',340),
('consumable_water_purifier','Water Purifier Tablet','consumable','Purifies tainted water.',120);

DELETE FROM item WHERE slug LIKE 'key_%';
INSERT INTO item (slug, name, type, description, value_copper) VALUES
('key_rusted','Rusted Key','key','Opens a specific old lock.',0),
('key_bronze','Bronze Key','key','Opens a bronze-marked lock.',0),
('key_silver','Silver Key','key','Opens a silver-marked lock.',0),
('key_gold','Gold Key','key','Opens a gold-marked lock.',0),
('key_dragon','Dragon Key','key','Unlocks a draconic seal.',0);

COMMIT;

-- Expansion: Additional Misc / Crafting / Quest Items
BEGIN TRANSACTION;

-- Additional TOOLS
DELETE FROM item WHERE slug LIKE 'tool_alchemy_%';
INSERT INTO item (slug, name, type, description, value_copper) VALUES
('tool_alchemy_basic','Basic Alchemy Kit','tool','Allows brewing minor potions.',240),
('tool_alchemy_advanced','Advanced Alchemy Kit','tool','Enables complex potion crafting.',640);

DELETE FROM item WHERE slug LIKE 'tool_cooking_%';
INSERT INTO item (slug, name, type, description, value_copper) VALUES
('tool_cooking_basic','Camp Cooking Set','tool','Cook simple meals.',160),
('tool_cooking_gourmet','Gourmet Cooking Set','tool','Prepare high-quality feasts.',520);

DELETE FROM item WHERE slug LIKE 'tool_enchant_%';
INSERT INTO item (slug, name, type, description, value_copper) VALUES
('tool_enchant_apprentice','Apprentice Enchanting Kit','tool','Apply minor enchantments.',480),
('tool_enchant_master','Master Enchanting Kit','tool','Apply advanced enchantments.',1400);

-- Additional MATERIAL tiers
DELETE FROM item WHERE slug LIKE 'material_obsidian_%';
INSERT INTO item (slug, name, type, description, value_copper) VALUES
('material_obsidian_fragment','Obsidian Fragment','material','Volcanic glass shard.',260),
('material_obsidian_chunk','Obsidian Chunk','material','Larger glassy shard.',520);

DELETE FROM item WHERE slug LIKE 'material_etheric_%';
INSERT INTO item (slug, name, type, description, value_copper) VALUES
('material_etheric_residue','Etheric Residue','material','Faintly luminous dust.',640),
('material_etheric_core','Etheric Core','material','Condensed planar energy.',1320);

DELETE FROM item WHERE slug LIKE 'material_ancient_%';
INSERT INTO item (slug, name, type, description, value_copper) VALUES
('material_ancient_relic','Ancient Relic Fragment','material','Piece of forgotten device.',980),
('material_ancient_core','Ancient Power Core','material','Arcane-engine node.',1880);

-- GEM expansion (mid-tier variants)
DELETE FROM item WHERE slug LIKE 'gem_opal' OR slug LIKE 'gem_amethyst' OR slug LIKE 'gem_topaz';
INSERT INTO item (slug, name, type, description, value_copper) VALUES
('gem_opal','Opal Shard','gem','Iridescent shifting hues.',380),
('gem_amethyst','Amethyst Shard','gem','Purple crystalline fragment.',300),
('gem_topaz','Topaz Shard','gem','Golden crystalline fragment.',340);

-- SCROLL expansion: teleport & summon & ward
DELETE FROM item WHERE slug LIKE 'scroll_teleport_%';
INSERT INTO item (slug, name, type, description, value_copper) VALUES
('scroll_teleport_minor','Minor Teleport Scroll','scroll','Short-range reposition.',520),
('scroll_teleport_greater','Greater Teleport Scroll','scroll','Longer-range teleport.',1320);

DELETE FROM item WHERE slug LIKE 'scroll_summon_%';
INSERT INTO item (slug, name, type, description, value_copper) VALUES
('scroll_summon_wolf','Scroll of Summon Wolf','scroll','Summons a wolf ally briefly.',680),
('scroll_summon_elemental','Scroll of Summon Elemental','scroll','Summons minor elemental.',1800);

DELETE FROM item WHERE slug LIKE 'scroll_ward_%';
INSERT INTO item (slug, name, type, description, value_copper) VALUES
('scroll_ward_fire','Scroll of Fire Ward','scroll','Applies fire resistance ward.',720),
('scroll_ward_mind','Scroll of Mind Ward','scroll','Applies mental shielding.',900);

-- QUEST / SPECIAL ITEMS
DELETE FROM item WHERE slug LIKE 'quest_%';
INSERT INTO item (slug, name, type, description, value_copper) VALUES
('quest_goblin_totem','Goblin Totem','quest','Totemic carving taken from goblin shaman.',0),
('quest_skeleton_sigil','Skeleton Sigil','quest','Bone sigil radiating undeath.',0),
('quest_dragon_scale','Ancient Dragon Scale','quest','Scale from a legendary wyrm.',0),
('quest_elemental_core','Lesser Elemental Core','quest','Residual elemental essence.',0);

-- KEY expansion (region-coded)
DELETE FROM item WHERE slug LIKE 'key_region_%';
INSERT INTO item (slug, name, type, description, value_copper) VALUES
('key_region_forest','Forest Region Key','key','Opens sealed forest gate.',0),
('key_region_ruins','Ruins Region Key','key','Opens ancient ruin door.',0),
('key_region_depths','Depths Region Key','key','Unlocks lower dungeon access.',0),
('key_region_peak','Peak Region Key','key','Unlocks mountain pass.',0);

COMMIT;
