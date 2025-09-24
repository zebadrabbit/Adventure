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
