-- Dungeon Affix Seed Data
-- Modifiers that change dungeon difficulty and monster behavior

CREATE TABLE IF NOT EXISTS dungeon_affix (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    affix_id VARCHAR(40) UNIQUE NOT NULL,
    name VARCHAR(80) NOT NULL,
    description TEXT,
    monster_hp_multiplier REAL NOT NULL DEFAULT 1.0,
    monster_damage_multiplier REAL NOT NULL DEFAULT 1.0,
    monster_speed_multiplier REAL NOT NULL DEFAULT 1.0,
    player_damage_taken_multiplier REAL NOT NULL DEFAULT 1.0,
    special_effect TEXT,
    color VARCHAR(20)
);

CREATE INDEX IF NOT EXISTS ix_dungeon_affix_affix_id ON dungeon_affix(affix_id);

-- Clear existing data
DELETE FROM dungeon_affix;

-- Insert dungeon affixes
INSERT INTO dungeon_affix (affix_id, name, description, monster_hp_multiplier, monster_damage_multiplier,
                          monster_speed_multiplier, player_damage_taken_multiplier, special_effect, color)
VALUES
    ('frenzied', 'Frenzied', 'Monsters attack 30% faster', 1.0, 1.0, 1.3, 1.0, '{"effect":"attack_speed_bonus"}', '#ff6b6b'),
    ('bolstered', 'Bolstered', 'Monsters have double HP', 2.0, 1.0, 1.0, 1.0, '{"effect":"hp_bonus"}', '#4ecdc4'),
    ('volcanic', 'Volcanic', 'Monsters deal 25% more damage and inflict burning', 1.0, 1.25, 1.0, 1.0, '{"effect":"fire_damage","dot":"burning"}', '#ff8c42'),
    ('necrotic', 'Necrotic', 'Monsters drain life and resist healing', 1.2, 1.15, 1.0, 1.0, '{"effect":"life_drain","healing_reduction":0.5}', '#9b59b6'),
    ('fortified', 'Fortified', 'Monsters have 50% more armor', 1.5, 1.0, 1.0, 1.0, '{"effect":"armor_bonus","armor_multiplier":1.5}', '#95a5a6'),
    ('enraged', 'Enraged', 'Monsters deal 40% more damage', 1.0, 1.4, 1.0, 1.0, '{"effect":"damage_bonus"}', '#e74c3c'),
    ('shadowed', 'Shadowed', 'Monsters have increased evasion and stealth', 1.0, 1.0, 1.0, 1.0, '{"effect":"evasion_bonus","stealth":true}', '#34495e'),
    ('corrupted', 'Corrupted', 'Players take 20% more damage', 1.1, 1.1, 1.0, 1.2, '{"effect":"vulnerability"}', '#8e44ad'),
    ('swarming', 'Swarming', 'More monsters spawn in groups', 1.0, 1.0, 1.0, 1.0, '{"effect":"spawn_multiplier","multiplier":1.5}', '#f39c12'),
    ('chaotic', 'Chaotic', 'Random elemental damage types', 1.0, 1.2, 1.1, 1.0, '{"effect":"random_elements"}', '#e67e22');
