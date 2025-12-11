-- Achievement System Migration
-- Creates tables for achievements, progress tracking, and rewards

-- Step 1: Create achievement table
CREATE TABLE IF NOT EXISTS achievement (
    id SERIAL PRIMARY KEY,
    slug VARCHAR(100) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    description TEXT NOT NULL,
    category VARCHAR(30) NOT NULL,
    icon VARCHAR(50),
    points INTEGER DEFAULT 10,
    hidden BOOLEAN DEFAULT FALSE,
    requirement_type VARCHAR(50) NOT NULL,
    requirement_value INTEGER DEFAULT 1,
    requirement_data TEXT,
    reward_gold INTEGER DEFAULT 0,
    reward_items TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Step 2: Create character_achievement table
CREATE TABLE IF NOT EXISTS character_achievement (
    id SERIAL PRIMARY KEY,
    character_id INTEGER NOT NULL REFERENCES character(id) ON DELETE CASCADE,
    achievement_id INTEGER NOT NULL REFERENCES achievement(id) ON DELETE CASCADE,
    progress INTEGER DEFAULT 0,
    unlocked BOOLEAN NOT NULL DEFAULT FALSE,
    unlocked_at TIMESTAMP,
    notified BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT unique_character_achievement UNIQUE (character_id, achievement_id)
);

-- Step 3: Create achievement_category table
CREATE TABLE IF NOT EXISTS achievement_category (
    id SERIAL PRIMARY KEY,
    slug VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    icon VARCHAR(50),
    display_order INTEGER DEFAULT 0
);

-- Step 4: Create indexes
CREATE INDEX IF NOT EXISTS idx_achievement_category ON achievement(category);
CREATE INDEX IF NOT EXISTS idx_achievement_slug ON achievement(slug);
CREATE INDEX IF NOT EXISTS idx_char_achievement_char ON character_achievement(character_id);
CREATE INDEX IF NOT EXISTS idx_char_achievement_ach ON character_achievement(achievement_id);
CREATE INDEX IF NOT EXISTS idx_char_achievement_unlocked ON character_achievement(unlocked);

-- Step 5: Seed achievement categories
INSERT INTO achievement_category (slug, name, description, icon, display_order)
VALUES
    ('combat', 'Combat', 'Achievements for defeating enemies and winning battles', 'sword', 1),
    ('exploration', 'Exploration', 'Achievements for discovering dungeons and exploring the world', 'map', 2),
    ('progression', 'Progression', 'Achievements for character growth and advancement', 'trophy', 3),
    ('collection', 'Collection', 'Achievements for gathering items and equipment', 'box', 4),
    ('social', 'Social', 'Achievements for party activities and cooperation', 'people', 5),
    ('special', 'Special', 'Rare and unique achievements', 'star', 6)
ON CONFLICT (slug) DO NOTHING;

-- Step 6: Seed starter achievements

-- Combat Achievements
INSERT INTO achievement (slug, name, description, category, icon, points, requirement_type, requirement_value, reward_gold)
SELECT 'first-blood', 'First Blood', 'Defeat your first enemy', 'combat', 'sword-clash', 10, 'enemy_kills', 1, 50
WHERE NOT EXISTS (SELECT 1 FROM achievement WHERE slug = 'first-blood');

INSERT INTO achievement (slug, name, description, category, icon, points, requirement_type, requirement_value, reward_gold)
SELECT 'slayer', 'Slayer', 'Defeat 25 enemies', 'combat', 'crossed-swords', 25, 'enemy_kills', 25, 200
WHERE NOT EXISTS (SELECT 1 FROM achievement WHERE slug = 'slayer');

INSERT INTO achievement (slug, name, description, category, icon, points, requirement_type, requirement_value, reward_gold)
SELECT 'executioner', 'Executioner', 'Defeat 100 enemies', 'combat', 'skull', 50, 'enemy_kills', 100, 500
WHERE NOT EXISTS (SELECT 1 FROM achievement WHERE slug = 'executioner');

INSERT INTO achievement (slug, name, description, category, icon, points, requirement_type, requirement_value, reward_gold)
SELECT 'boss-hunter', 'Boss Hunter', 'Defeat 5 boss enemies', 'combat', 'dragon', 50, 'boss_kills', 5, 1000
WHERE NOT EXISTS (SELECT 1 FROM achievement WHERE slug = 'boss-hunter');

-- Exploration Achievements
INSERT INTO achievement (slug, name, description, category, icon, points, requirement_type, requirement_value, reward_gold)
SELECT 'explorer', 'Explorer', 'Complete your first dungeon', 'exploration', 'map', 15, 'dungeons_completed', 1, 100
WHERE NOT EXISTS (SELECT 1 FROM achievement WHERE slug = 'explorer');

INSERT INTO achievement (slug, name, description, category, icon, points, requirement_type, requirement_value, reward_gold)
SELECT 'adventurer', 'Adventurer', 'Complete 10 dungeons', 'exploration', 'compass', 30, 'dungeons_completed', 10, 300
WHERE NOT EXISTS (SELECT 1 FROM achievement WHERE slug = 'adventurer');

INSERT INTO achievement (slug, name, description, category, icon, points, requirement_type, requirement_value, reward_gold)
SELECT 'dungeon-master', 'Dungeon Master', 'Complete 50 dungeons', 'exploration', 'castle', 100, 'dungeons_completed', 50, 1500
WHERE NOT EXISTS (SELECT 1 FROM achievement WHERE slug = 'dungeon-master');

-- Progression Achievements
INSERT INTO achievement (slug, name, description, category, icon, points, requirement_type, requirement_value, reward_gold)
SELECT 'level-up', 'Level Up!', 'Reach level 5', 'progression', 'arrow-up', 15, 'level_reached', 5, 100
WHERE NOT EXISTS (SELECT 1 FROM achievement WHERE slug = 'level-up');

INSERT INTO achievement (slug, name, description, category, icon, points, requirement_type, requirement_value, reward_gold)
SELECT 'veteran', 'Veteran', 'Reach level 10', 'progression', 'shield-check', 40, 'level_reached', 10, 500
WHERE NOT EXISTS (SELECT 1 FROM achievement WHERE slug = 'veteran');

INSERT INTO achievement (slug, name, description, category, icon, points, requirement_type, requirement_value, reward_gold)
SELECT 'legendary', 'Legendary', 'Reach level 20', 'progression', 'crown', 100, 'level_reached', 20, 2000
WHERE NOT EXISTS (SELECT 1 FROM achievement WHERE slug = 'legendary');

-- Collection Achievements
INSERT INTO achievement (slug, name, description, category, icon, points, requirement_type, requirement_value, reward_gold)
SELECT 'treasure-hunter', 'Treasure Hunter', 'Collect 1000 gold', 'collection', 'coin', 20, 'gold_earned', 1000, 100
WHERE NOT EXISTS (SELECT 1 FROM achievement WHERE slug = 'treasure-hunter');

INSERT INTO achievement (slug, name, description, category, icon, points, requirement_type, requirement_value, reward_gold)
SELECT 'merchant-prince', 'Merchant Prince', 'Collect 10000 gold', 'collection', 'gem', 50, 'gold_earned', 10000, 1000
WHERE NOT EXISTS (SELECT 1 FROM achievement WHERE slug = 'merchant-prince');

INSERT INTO achievement (slug, name, description, category, icon, points, requirement_type, requirement_value, reward_gold)
SELECT 'equipped', 'Fully Equipped', 'Have all equipment slots filled', 'collection', 'armor-helmet', 30, 'full_equipment', 1, 250
WHERE NOT EXISTS (SELECT 1 FROM achievement WHERE slug = 'equipped');

-- Social Achievements
INSERT INTO achievement (slug, name, description, category, icon, points, requirement_type, requirement_value, reward_gold)
SELECT 'team-player', 'Team Player', 'Join a party', 'social', 'people-fill', 10, 'party_joined', 1, 50
WHERE NOT EXISTS (SELECT 1 FROM achievement WHERE slug = 'team-player');

INSERT INTO achievement (slug, name, description, category, icon, points, requirement_type, requirement_value, reward_gold)
SELECT 'generous', 'Generous Soul', 'Trade 10 items with merchants', 'social', 'gift', 25, 'trades_completed', 10, 200
WHERE NOT EXISTS (SELECT 1 FROM achievement WHERE slug = 'generous');

-- Special Achievements
INSERT INTO achievement (slug, name, description, category, icon, points, hidden, requirement_type, requirement_value, reward_gold)
SELECT 'lucky', 'Lucky Strike', 'Get a critical hit', 'special', 'lightning-bolt', 15, TRUE, 'critical_hits', 1, 100
WHERE NOT EXISTS (SELECT 1 FROM achievement WHERE slug = 'lucky');

INSERT INTO achievement (slug, name, description, category, icon, points, hidden, requirement_type, requirement_value, reward_gold)
SELECT 'survivor', 'Survivor', 'Win a battle with 1 HP remaining', 'special', 'heart-pulse', 50, TRUE, 'survived_low_hp', 1, 500
WHERE NOT EXISTS (SELECT 1 FROM achievement WHERE slug = 'survivor');

INSERT INTO achievement (slug, name, description, category, icon, points, hidden, requirement_type, requirement_value, reward_gold)
SELECT 'perfectionist', 'Perfectionist', 'Complete a dungeon without taking damage', 'special', 'shield-fill', 75, TRUE, 'flawless_dungeon', 1, 1000
WHERE NOT EXISTS (SELECT 1 FROM achievement WHERE slug = 'perfectionist');
