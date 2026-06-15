-- Procedural Affix Seed Data
-- Schema: procedural_affix table for stat modifiers
-- Data source: docs/Gameplay/procedural_affixes.csv

BEGIN TRANSACTION;

CREATE TABLE IF NOT EXISTS procedural_affix (
    id INTEGER PRIMARY KEY,
    affix_id TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    slot TEXT NOT NULL,
    affected_stat TEXT NOT NULL,
    min_value REAL NOT NULL,
    max_value REAL NOT NULL,
    scaling_per_level REAL NOT NULL DEFAULT 0.0,
    rarity_weight INTEGER NOT NULL DEFAULT 100,
    allowed_item_types TEXT,
    tags TEXT,
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_affix_id ON procedural_affix(affix_id);

-- Defensive Affixes
INSERT INTO procedural_affix (affix_id, name, slot, affected_stat, min_value, max_value, scaling_per_level, rarity_weight, allowed_item_types, tags, notes)
VALUES
 ('hp_flat', 'of Vitality', 'Suffix', 'MaxHP', 10, 50, 2, 120, 'Armor;Jewelry', 'Defensive', 'Flat HP increase'),
 ('hp_pct', 'of the Bear', 'Suffix', 'MaxHPPercent', 3, 12, 0.2, 80, 'Armor;Jewelry', 'Defensive', '% max HP increase'),
 ('armor_flat', 'of Guarding', 'Suffix', 'Armor', 5, 25, 1, 110, 'Armor;Shield', 'Defensive', 'Flat armor bonus'),
 ('res_all', 'of Warding', 'Suffix', 'AllResist', 3, 15, 0.3, 90, 'Armor;Jewelry', 'Defensive;Elemental', 'All-element resistance boost')
ON CONFLICT (affix_id) DO NOTHING;

-- Stat Boost Affixes
INSERT INTO procedural_affix (affix_id, name, slot, affected_stat, min_value, max_value, scaling_per_level, rarity_weight, allowed_item_types, tags, notes)
VALUES
 ('str_flat', 'Brutal', 'Prefix', 'STR', 2, 10, 0.3, 100, 'Weapon;Armor', 'Offensive;Melee', 'Flat Strength increase'),
 ('dex_flat', 'Nimble', 'Prefix', 'DEX', 2, 10, 0.3, 100, 'Weapon;Armor', 'Offensive;Ranged', 'Flat Dexterity increase'),
 ('int_flat', 'Sage''s', 'Prefix', 'INT', 2, 10, 0.3, 100, 'Weapon;Jewelry', 'Offensive;Caster', 'Flat Intelligence increase'),
 ('wis_flat', 'Insightful', 'Prefix', 'WIS', 2, 10, 0.3, 100, 'Armor;Jewelry', 'Utility;Caster', 'Flat Wisdom increase'),
 ('cha_flat', 'Charismatic', 'Prefix', 'CHA', 2, 10, 0.3, 90, 'Jewelry;Armor', 'Utility;Caster', 'Flat Charisma increase')
ON CONFLICT (affix_id) DO NOTHING;

-- Offensive Affixes
INSERT INTO procedural_affix (affix_id, name, slot, affected_stat, min_value, max_value, scaling_per_level, rarity_weight, allowed_item_types, tags, notes)
VALUES
 ('crit_chance', 'of Precision', 'Suffix', 'CritChancePercent', 2, 8, 0.15, 70, 'Weapon;Jewelry', 'Offensive;Crit', 'Crit chance increase'),
 ('crit_damage', 'of Carnage', 'Suffix', 'CritDamagePercent', 10, 35, 0.4, 60, 'Weapon;Jewelry', 'Offensive;Crit', 'Critical damage multiplier'),
 ('lifesteal', 'of the Leech', 'Suffix', 'LifeStealPercent', 2, 6, 0.1, 50, 'Weapon', 'Offensive;Sustain', 'Life on hit')
ON CONFLICT (affix_id) DO NOTHING;

-- Elemental Damage Affixes
INSERT INTO procedural_affix (affix_id, name, slot, affected_stat, min_value, max_value, scaling_per_level, rarity_weight, allowed_item_types, tags, notes)
VALUES
 ('damage_ele_fire', 'Flaming', 'Prefix', 'FireDamageFlat', 3, 15, 0.4, 95, 'Weapon', 'Offensive;Elemental', 'Adds fire damage to attacks'),
 ('damage_ele_cold', 'Freezing', 'Prefix', 'ColdDamageFlat', 3, 15, 0.4, 95, 'Weapon', 'Offensive;Elemental', 'Adds cold damage to attacks'),
 ('damage_ele_lightning', 'Shocking', 'Prefix', 'LightningDamageFlat', 3, 15, 0.4, 95, 'Weapon', 'Offensive;Elemental', 'Adds lightning damage to attacks')
ON CONFLICT (affix_id) DO NOTHING;

-- Utility Affixes
INSERT INTO procedural_affix (affix_id, name, slot, affected_stat, min_value, max_value, scaling_per_level, rarity_weight, allowed_item_types, tags, notes)
VALUES
 ('movespeed', 'Fleetfoot', 'Prefix', 'MoveSpeedPercent', 3, 10, 0.2, 85, 'Boots;Armor', 'Utility', 'Movement speed bonus'),
 ('mana_regen', 'of Clarity', 'Suffix', 'ManaRegen', 1, 5, 0.15, 90, 'Jewelry;Armor', 'Caster', 'Mana regeneration increase'),
 ('cooldown_reduction', 'of Reprieve', 'Suffix', 'CooldownReductionPercent', 4, 15, 0.25, 55, 'Jewelry;Armor', 'Caster;Utility', 'Reduces ability cooldowns')
ON CONFLICT (affix_id) DO NOTHING;

-- Special Affixes
INSERT INTO procedural_affix (affix_id, name, slot, affected_stat, min_value, max_value, scaling_per_level, rarity_weight, allowed_item_types, tags, notes)
VALUES
 ('thorns', 'of Thorns', 'Suffix', 'ThornsDamage', 5, 30, 0.6, 75, 'Armor;Shield', 'Reactive', 'Reflects damage back to attackers'),
 ('xp_bonus', 'of Learning', 'Suffix', 'XPBonusPercent', 3, 12, 0.25, 40, 'Jewelry', 'Progression', 'Bonus XP from kills')
ON CONFLICT (affix_id) DO NOTHING;

-- Item Affix Instance Table (links items to their rolled affixes)
CREATE TABLE IF NOT EXISTS item_affix (
    id INTEGER PRIMARY KEY,
    item_id INTEGER NOT NULL,
    affix_id TEXT NOT NULL,
    rolled_value REAL NOT NULL,
    dungeon_seed INTEGER,
    x INTEGER,
    y INTEGER,
    z INTEGER,
    FOREIGN KEY (item_id) REFERENCES item(id),
    FOREIGN KEY (affix_id) REFERENCES procedural_affix(affix_id)
);

CREATE INDEX IF NOT EXISTS idx_item_affix_item ON item_affix(item_id);
CREATE INDEX IF NOT EXISTS idx_item_affix_seed ON item_affix(dungeon_seed);

COMMIT;
