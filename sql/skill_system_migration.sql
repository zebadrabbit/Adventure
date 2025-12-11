-- Skill/Talent Tree System Migration
-- Creates tables for skill trees, skills, and character progression

-- Step 1: Create skill_tree table
CREATE TABLE IF NOT EXISTS skill_tree (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    class_requirement VARCHAR(30),
    description TEXT,
    icon VARCHAR(50),
    max_tier INTEGER DEFAULT 5,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Step 2: Create skill table
CREATE TABLE IF NOT EXISTS skill (
    id SERIAL PRIMARY KEY,
    tree_id INTEGER NOT NULL REFERENCES skill_tree(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    description TEXT NOT NULL,
    tier INTEGER NOT NULL DEFAULT 1,
    position_x INTEGER DEFAULT 0,
    position_y INTEGER DEFAULT 0,
    required_level INTEGER DEFAULT 1,
    required_skill_id INTEGER REFERENCES skill(id) ON DELETE SET NULL,
    cost INTEGER NOT NULL DEFAULT 1,
    effect_json TEXT NOT NULL,
    cooldown INTEGER,
    skill_type VARCHAR(20) NOT NULL DEFAULT 'passive',
    icon VARCHAR(50),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Step 3: Create character_skill table
CREATE TABLE IF NOT EXISTS character_skill (
    id SERIAL PRIMARY KEY,
    character_id INTEGER NOT NULL REFERENCES character(id) ON DELETE CASCADE,
    skill_id INTEGER NOT NULL REFERENCES skill(id) ON DELETE CASCADE,
    unlocked_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    skill_rank INTEGER NOT NULL DEFAULT 1,
    times_used INTEGER DEFAULT 0,
    last_used TIMESTAMP,
    CONSTRAINT unique_character_skill UNIQUE (character_id, skill_id)
);

-- Step 4: Create character_talent_points table
CREATE TABLE IF NOT EXISTS character_talent_points (
    id SERIAL PRIMARY KEY,
    character_id INTEGER NOT NULL REFERENCES character(id) ON DELETE CASCADE UNIQUE,
    total_earned INTEGER NOT NULL DEFAULT 0,
    total_spent INTEGER NOT NULL DEFAULT 0,
    available INTEGER NOT NULL DEFAULT 0,
    last_updated TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Step 5: Create indexes
CREATE INDEX IF NOT EXISTS idx_skill_tree_id ON skill(tree_id);
CREATE INDEX IF NOT EXISTS idx_skill_required ON skill(required_skill_id);
CREATE INDEX IF NOT EXISTS idx_character_skill_char ON character_skill(character_id);
CREATE INDEX IF NOT EXISTS idx_character_skill_skill ON character_skill(skill_id);
CREATE INDEX IF NOT EXISTS idx_talent_points_char ON character_talent_points(character_id);

-- Step 6: Seed starter skill trees (Warrior, Mage, Cleric)
INSERT INTO skill_tree (name, class_requirement, description, icon, max_tier, is_active)
VALUES
    ('Warrior Combat Tree', 'warrior', 'Master the art of melee combat with powerful attacks and defensive abilities', 'crossed-swords', 5, TRUE),
    ('Mage Arcane Tree', 'mage', 'Harness devastating magical powers and arcane knowledge', 'magic-wand', 5, TRUE),
    ('Cleric Divine Tree', 'cleric', 'Channel divine energy to heal allies and smite foes', 'aura', 5, TRUE)
ON CONFLICT DO NOTHING;

-- Step 7: Seed warrior skills
INSERT INTO skill (tree_id, name, description, tier, position_x, position_y, required_level, required_skill_id, cost, effect_json, skill_type, icon)
SELECT
    (SELECT id FROM skill_tree WHERE name = 'Warrior Combat Tree'),
    'Power Strike',
    'Deal 150% weapon damage with your next attack',
    1, 0, 0, 1, NULL, 1,
    '{"damage_multiplier": 1.5, "bonus_damage": 5}',
    'active',
    'sword-clash'
WHERE NOT EXISTS (SELECT 1 FROM skill WHERE name = 'Power Strike');

INSERT INTO skill (tree_id, name, description, tier, position_x, position_y, required_level, required_skill_id, cost, effect_json, skill_type, icon)
SELECT
    (SELECT id FROM skill_tree WHERE name = 'Warrior Combat Tree'),
    'Armor Mastery',
    'Permanently gain +10 defense',
    1, 1, 0, 1, NULL, 1,
    '{"defense_bonus": 10}',
    'passive',
    'shield'
WHERE NOT EXISTS (SELECT 1 FROM skill WHERE name = 'Armor Mastery');

INSERT INTO skill (tree_id, name, description, tier, position_x, position_y, required_level, required_skill_id, cost, effect_json, skill_type, icon)
SELECT
    (SELECT id FROM skill_tree WHERE name = 'Warrior Combat Tree'),
    'Whirlwind',
    'Spin attack hitting all nearby enemies for 80% damage',
    2, 0, 1, 3, (SELECT id FROM skill WHERE name = 'Power Strike'), 2,
    '{"area_damage_multiplier": 0.8, "max_targets": 4}',
    'active',
    'tornado'
WHERE NOT EXISTS (SELECT 1 FROM skill WHERE name = 'Whirlwind');

INSERT INTO skill (tree_id, name, description, tier, position_x, position_y, required_level, required_skill_id, cost, effect_json, skill_type, icon)
SELECT
    (SELECT id FROM skill_tree WHERE name = 'Warrior Combat Tree'),
    'Iron Skin',
    'Reduce all damage taken by 15%',
    2, 1, 1, 3, (SELECT id FROM skill WHERE name = 'Armor Mastery'), 2,
    '{"damage_reduction_percent": 15}',
    'passive',
    'armor'
WHERE NOT EXISTS (SELECT 1 FROM skill WHERE name = 'Iron Skin');

INSERT INTO skill (tree_id, name, description, tier, position_x, position_y, required_level, required_skill_id, cost, effect_json, skill_type, icon)
SELECT
    (SELECT id FROM skill_tree WHERE name = 'Warrior Combat Tree'),
    'Battle Fury',
    'Enter a rage state: +25% damage, +10% critical chance for 10 seconds',
    3, 0, 2, 5, (SELECT id FROM skill WHERE name = 'Whirlwind'), 3,
    '{"damage_bonus_percent": 25, "crit_chance_percent": 10, "duration_seconds": 10}',
    'active',
    'fire'
WHERE NOT EXISTS (SELECT 1 FROM skill WHERE name = 'Battle Fury');

-- Step 8: Seed mage skills
INSERT INTO skill (tree_id, name, description, tier, position_x, position_y, required_level, required_skill_id, cost, effect_json, skill_type, icon)
SELECT
    (SELECT id FROM skill_tree WHERE name = 'Mage Arcane Tree'),
    'Fireball',
    'Hurl a ball of flame dealing 120% spell damage',
    1, 0, 0, 1, NULL, 1,
    '{"spell_damage_multiplier": 1.2, "element": "fire"}',
    'active',
    'flame'
WHERE NOT EXISTS (SELECT 1 FROM skill WHERE name = 'Fireball');

INSERT INTO skill (tree_id, name, description, tier, position_x, position_y, required_level, required_skill_id, cost, effect_json, skill_type, icon)
SELECT
    (SELECT id FROM skill_tree WHERE name = 'Mage Arcane Tree'),
    'Mana Efficiency',
    'Spell costs reduced by 20%',
    1, 1, 0, 1, NULL, 1,
    '{"mana_cost_reduction_percent": 20}',
    'passive',
    'sparkles'
WHERE NOT EXISTS (SELECT 1 FROM skill WHERE name = 'Mana Efficiency');

INSERT INTO skill (tree_id, name, description, tier, position_x, position_y, required_level, required_skill_id, cost, effect_json, skill_type, icon)
SELECT
    (SELECT id FROM skill_tree WHERE name = 'Mage Arcane Tree'),
    'Chain Lightning',
    'Lightning jumps between 3 enemies, 90% damage each',
    2, 0, 1, 3, (SELECT id FROM skill WHERE name = 'Fireball'), 2,
    '{"spell_damage_multiplier": 0.9, "max_jumps": 3, "element": "lightning"}',
    'active',
    'lightning-bolt'
WHERE NOT EXISTS (SELECT 1 FROM skill WHERE name = 'Chain Lightning');

INSERT INTO skill (tree_id, name, description, tier, position_x, position_y, required_level, required_skill_id, cost, effect_json, skill_type, icon)
SELECT
    (SELECT id FROM skill_tree WHERE name = 'Mage Arcane Tree'),
    'Arcane Focus',
    'Permanently increase spell damage by 15%',
    2, 1, 1, 3, (SELECT id FROM skill WHERE name = 'Mana Efficiency'), 2,
    '{"spell_damage_bonus_percent": 15}',
    'passive',
    'target'
WHERE NOT EXISTS (SELECT 1 FROM skill WHERE name = 'Arcane Focus');

INSERT INTO skill (tree_id, name, description, tier, position_x, position_y, required_level, required_skill_id, cost, effect_json, skill_type, icon)
SELECT
    (SELECT id FROM skill_tree WHERE name = 'Mage Arcane Tree'),
    'Meteor Storm',
    'Summon meteors raining down, 200% spell damage in area',
    3, 0, 2, 5, (SELECT id FROM skill WHERE name = 'Chain Lightning'), 3,
    '{"spell_damage_multiplier": 2.0, "area_radius": 5, "element": "fire"}',
    'active',
    'meteor'
WHERE NOT EXISTS (SELECT 1 FROM skill WHERE name = 'Meteor Storm');

-- Step 9: Seed cleric skills
INSERT INTO skill (tree_id, name, description, tier, position_x, position_y, required_level, required_skill_id, cost, effect_json, skill_type, icon)
SELECT
    (SELECT id FROM skill_tree WHERE name = 'Cleric Divine Tree'),
    'Heal',
    'Restore 100 HP to target ally',
    1, 0, 0, 1, NULL, 1,
    '{"heal_amount": 100}',
    'active',
    'health-increase'
WHERE NOT EXISTS (SELECT 1 FROM skill WHERE name = 'Heal');

INSERT INTO skill (tree_id, name, description, tier, position_x, position_y, required_level, required_skill_id, cost, effect_json, skill_type, icon)
SELECT
    (SELECT id FROM skill_tree WHERE name = 'Cleric Divine Tree'),
    'Holy Resistance',
    'Permanently gain +20% resistance to all damage',
    1, 1, 0, 1, NULL, 1,
    '{"damage_resistance_percent": 20}',
    'passive',
    'shield-checkered'
WHERE NOT EXISTS (SELECT 1 FROM skill WHERE name = 'Holy Resistance');

INSERT INTO skill (tree_id, name, description, tier, position_x, position_y, required_level, required_skill_id, cost, effect_json, skill_type, icon)
SELECT
    (SELECT id FROM skill_tree WHERE name = 'Cleric Divine Tree'),
    'Group Heal',
    'Restore 60 HP to all nearby allies',
    2, 0, 1, 3, (SELECT id FROM skill WHERE name = 'Heal'), 2,
    '{"heal_amount": 60, "area_effect": true}',
    'active',
    'hearts'
WHERE NOT EXISTS (SELECT 1 FROM skill WHERE name = 'Group Heal');

INSERT INTO skill (tree_id, name, description, tier, position_x, position_y, required_level, required_skill_id, cost, effect_json, skill_type, icon)
SELECT
    (SELECT id FROM skill_tree WHERE name = 'Cleric Divine Tree'),
    'Divine Shield',
    'Grant ally immunity to next attack',
    2, 1, 1, 3, (SELECT id FROM skill WHERE name = 'Holy Resistance'), 2,
    '{"absorb_hits": 1, "duration_seconds": 30}',
    'active',
    'shield-alt'
WHERE NOT EXISTS (SELECT 1 FROM skill WHERE name = 'Divine Shield');

INSERT INTO skill (tree_id, name, description, tier, position_x, position_y, required_level, required_skill_id, cost, effect_json, skill_type, icon)
SELECT
    (SELECT id FROM skill_tree WHERE name = 'Cleric Divine Tree'),
    'Resurrection',
    'Revive a fallen ally with 50% HP',
    3, 0, 2, 5, (SELECT id FROM skill WHERE name = 'Group Heal'), 3,
    '{"revive_hp_percent": 50}',
    'active',
    'angel'
WHERE NOT EXISTS (SELECT 1 FROM skill WHERE name = 'Resurrection');

-- Step 10: Initialize talent points for existing characters (1 point per level)
INSERT INTO character_talent_points (character_id, total_earned, total_spent, available)
SELECT
    id,
    level,
    0,
    level
FROM character
WHERE id NOT IN (SELECT character_id FROM character_talent_points)
ON CONFLICT DO NOTHING;
