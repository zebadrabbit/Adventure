-- Enemy Archetype Seed Data
-- Based on enemy_templates.csv from DESIGN.md specification
-- 8 archetypes: Trash, Skirmisher, Brute, Caster, Elite, Champion, Miniboss, Boss

CREATE TABLE IF NOT EXISTS enemy_archetype (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    archetype VARCHAR(40) UNIQUE NOT NULL,
    rank VARCHAR(20) NOT NULL,
    base_hp INTEGER NOT NULL DEFAULT 25,
    hp_per_level REAL NOT NULL DEFAULT 10.0,
    base_damage INTEGER NOT NULL DEFAULT 4,
    damage_per_level REAL NOT NULL DEFAULT 2.0,
    armor_class_base INTEGER NOT NULL DEFAULT 10,
    armor_class_per_level REAL NOT NULL DEFAULT 0.3,
    xp_base INTEGER NOT NULL DEFAULT 15,
    xp_per_level REAL NOT NULL DEFAULT 5.0,
    loot_multiplier REAL NOT NULL DEFAULT 1.0,
    notes TEXT
);

CREATE INDEX IF NOT EXISTS ix_enemy_archetype_archetype ON enemy_archetype(archetype);

-- Clear existing data
DELETE FROM enemy_archetype;

-- Insert 8 enemy archetypes
INSERT INTO enemy_archetype (archetype, rank, base_hp, hp_per_level, base_damage, damage_per_level,
                             armor_class_base, armor_class_per_level, xp_base, xp_per_level,
                             loot_multiplier, notes)
VALUES
    ('Trash', 'Normal', 25, 10, 4, 2, 10, 0.3, 15, 5, 1.0, 'Baseline fodder enemies; appear in groups'),
    ('Skirmisher', 'Normal', 35, 12, 6, 2.5, 11, 0.35, 20, 7, 1.1, 'Fast movers; moderate damage, lower HP'),
    ('Brute', 'Normal', 55, 16, 8, 3, 12, 0.4, 30, 10, 1.2, 'Slow but tanky melee frontliners'),
    ('Caster', 'Normal', 30, 11, 10, 3.5, 10, 0.25, 28, 9, 1.2, 'Low HP, high ranged/magic damage'),
    ('Elite', 'Elite', 120, 30, 16, 5, 13, 0.5, 80, 20, 2.0, 'Upgraded normal archetypes; tinted visuals and extra abilities'),
    ('Champion', 'Elite', 160, 36, 18, 6, 14, 0.6, 110, 25, 2.5, 'Harder elites; occasional mini-encounters'),
    ('Miniboss', 'Boss', 260, 50, 22, 7, 15, 0.7, 200, 40, 3.0, 'Guardians or lieutenants before main boss'),
    ('Boss', 'Boss', 400, 70, 26, 8.5, 16, 0.8, 400, 70, 4.0, 'Main dungeon bosses; unique mechanics');
