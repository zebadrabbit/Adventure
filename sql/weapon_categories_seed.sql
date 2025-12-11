-- Weapon Category Seed Data
-- Based on weapon_categories.csv from DESIGN.md specification
-- 12 weapon categories with damage dice, attack speeds, and class restrictions

-- Create weapon_category table
CREATE TABLE IF NOT EXISTS weapon_category (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id VARCHAR(40) UNIQUE NOT NULL,
    name VARCHAR(80) NOT NULL,
    weapon_type VARCHAR(20) NOT NULL,
    hands VARCHAR(10) NOT NULL,
    base_dice_count INTEGER NOT NULL DEFAULT 1,
    base_die INTEGER NOT NULL DEFAULT 6,
    primary_stat VARCHAR(40) NOT NULL,
    crit_multiplier REAL NOT NULL DEFAULT 1.5,
    attack_speed REAL NOT NULL DEFAULT 1.0,
    tags TEXT,
    allowed_classes TEXT,
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_weapon_category_id ON weapon_category(category_id);

-- Clear existing data (for reseeding)
DELETE FROM weapon_category;

-- Insert 12 weapon categories from CSV
INSERT INTO weapon_category (category_id, name, weapon_type, hands, base_dice_count, base_die, primary_stat, crit_multiplier, attack_speed, tags, allowed_classes, notes)
VALUES
    ('sword_1h', 'One-Handed Sword', 'Melee', '1', 1, 8, 'STR/DEX', 1.5, 1.0, 'Versatile;Finesse', 'Fighter;Paladin;Ranger;Rogue;Bard;Warlock', 'Core melee weapon; flexible builds'),
    ('sword_2h', 'Greatsword', 'Melee', '2', 2, 6, 'STR', 1.7, 0.85, 'Heavy;Sweeping', 'Fighter;Barbarian;Paladin', 'Big cleave damage; slower swings'),
    ('axe_1h', 'Hand Axe', 'Melee', '1', 1, 6, 'STR', 1.6, 1.05, 'Thrown;Brutal', 'Fighter;Barbarian;Ranger', 'Can be thrown; slightly higher crit flavor'),
    ('axe_2h', 'Greataxe', 'Melee', '2', 1, 12, 'STR', 1.8, 0.8, 'Heavy;Brutal', 'Fighter;Barbarian;Paladin', 'High variance damage; great with crit builds'),
    ('polearm', 'Halberd', 'Melee', '2', 1, 10, 'STR', 1.6, 0.9, 'Reach;Heavy', 'Fighter;Paladin', 'Extra reach; great frontline zoning'),
    ('dagger', 'Dagger', 'Melee', '1', 1, 4, 'DEX', 1.6, 1.2, 'Finesse;Light;Thrown', 'Rogue;Bard;Wizard;Sorcerer;Warlock', 'Fast, crit-friendly, good off-hand'),
    ('bow', 'Longbow', 'Ranged', '2', 1, 10, 'DEX', 1.5, 1.0, 'Ranged;Two-Handed', 'Ranger;Fighter;Rogue', 'Primary ranged physical damage'),
    ('xbow_light', 'Light Crossbow', 'Ranged', '2', 1, 8, 'DEX', 1.7, 0.9, 'Ranged;Reload', 'Rogue;Wizard;Warlock;Cleric', 'High per-shot damage; slower reloads'),
    ('staff', 'Quarterstaff', 'Melee', '1/2', 1, 6, 'STR/INT/WIS', 1.4, 1.0, 'Focus;Versatile', 'Wizard;Druid;Cleric;Warlock;Sorcerer;Monk', 'Doubles as spellcasting focus'),
    ('wand', 'Wand', 'Magic', '1', 1, 6, 'INT/CHA', 1.5, 1.1, 'Magic;Focus', 'Wizard;Warlock;Sorcerer', 'Amplifies spell-based builds'),
    ('fist', 'Unarmed Strikes', 'Melee', '0', 1, 4, 'DEX/WIS', 1.5, 1.3, 'Finesse;Special', 'Monk', 'Improves with level; ki-scaling'),
    ('shield_bash', 'Shield Bash', 'Melee', '1', 1, 4, 'STR', 1.4, 0.9, 'Defensive;Control', 'Fighter;Paladin;Cleric', 'Secondary attack for shield users');
