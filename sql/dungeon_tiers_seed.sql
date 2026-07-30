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
-- Rescaled to the level-20 cap (2026-07-30). These tiers used to span 1-50,
-- which put Expert/Master/Heroic/Mythic at levels 22-50 -- unreachable now, and
-- already non-functional before, since the monster catalogue stops at 20 and
-- every spawn up there was a clamped level-20 monster.
--
-- The bands overlap by one level on purpose, exactly as the 1-50 ladder did: a
-- character sitting on a boundary can choose the safer tier or the greedier one
-- (each step up carries a real monster_level_modifier, loot bonus and xp
-- multiplier). Mythic sits at the cap alone and is the endgame tier -- the
-- "rift" the depth is supposed to come from, rather than more level numbers.
INSERT INTO dungeon_tier (tier, name, min_level, max_level, monster_level_modifier, loot_quality_bonus, xp_multiplier, description)
VALUES
    (1, 'Novice', 1, 5, 0, 0.0, 1.0, 'Entry-level dungeons for beginners'),
    (2, 'Apprentice', 4, 8, 1, 0.05, 1.1, 'Moderate challenge with improved rewards'),
    (3, 'Adept', 7, 11, 2, 0.1, 1.2, 'Seasoned adventurers face tougher foes'),
    (4, 'Expert', 10, 14, 3, 0.15, 1.3, 'High-level content with rare loot'),
    (5, 'Master', 13, 17, 4, 0.2, 1.4, 'Elite dungeons for veteran players'),
    (6, 'Heroic', 16, 20, 5, 0.25, 1.5, 'Legendary challenges await'),
    (7, 'Mythic', 20, 20, 6, 0.3, 1.6, 'The ultimate test of skill and power -- the endgame tier, run at the cap');
