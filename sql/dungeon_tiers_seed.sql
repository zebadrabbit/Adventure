-- Dungeon Tier Seed Data
-- 7 tiers from novice to mythic difficulty

CREATE TABLE IF NOT EXISTS dungeon_tier (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tier INTEGER UNIQUE NOT NULL,
    name VARCHAR(40) NOT NULL,
    min_level INTEGER NOT NULL,
    max_level INTEGER NOT NULL,
    monster_level_modifier INTEGER NOT NULL DEFAULT 0,
    loot_quality_bonus REAL NOT NULL DEFAULT 0.0,
    xp_multiplier REAL NOT NULL DEFAULT 1.0,
    description TEXT
);

CREATE INDEX IF NOT EXISTS ix_dungeon_tier_tier ON dungeon_tier(tier);

-- Clear existing data
DELETE FROM dungeon_tier;

-- Insert 7 dungeon tiers
INSERT INTO dungeon_tier (tier, name, min_level, max_level, monster_level_modifier, loot_quality_bonus, xp_multiplier, description)
VALUES
    (1, 'Novice', 1, 10, 0, 0.0, 1.0, 'Entry-level dungeons for beginners'),
    (2, 'Apprentice', 8, 18, 1, 0.05, 1.1, 'Moderate challenge with improved rewards'),
    (3, 'Adept', 15, 25, 2, 0.1, 1.2, 'Seasoned adventurers face tougher foes'),
    (4, 'Expert', 22, 32, 3, 0.15, 1.3, 'High-level content with rare loot'),
    (5, 'Master', 28, 38, 4, 0.2, 1.4, 'Elite dungeons for veteran players'),
    (6, 'Heroic', 35, 45, 5, 0.25, 1.5, 'Legendary challenges await'),
    (7, 'Mythic', 42, 50, 6, 0.3, 1.6, 'The ultimate test of skill and power');
