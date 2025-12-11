-- Party Management System Migration
-- Creates tables for party formations, shared inventory, and party buffs

-- Step 1: Create party table
CREATE TABLE IF NOT EXISTS party (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    leader_id INTEGER REFERENCES character(id) ON DELETE SET NULL,
    formation_json TEXT DEFAULT '{}',
    shared_gold INTEGER NOT NULL DEFAULT 0,
    party_level INTEGER DEFAULT 1,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_active TIMESTAMP
);

-- Step 2: Create party_member table
CREATE TABLE IF NOT EXISTS party_member (
    id SERIAL PRIMARY KEY,
    party_id INTEGER NOT NULL REFERENCES party(id) ON DELETE CASCADE,
    character_id INTEGER NOT NULL REFERENCES character(id) ON DELETE CASCADE,
    role VARCHAR(20) DEFAULT 'dps',
    position VARCHAR(20) DEFAULT 'middle',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    joined_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_party_character UNIQUE (party_id, character_id)
);

-- Step 3: Create party_buff table
CREATE TABLE IF NOT EXISTS party_buff (
    id SERIAL PRIMARY KEY,
    party_id INTEGER NOT NULL REFERENCES party(id) ON DELETE CASCADE,
    buff_type VARCHAR(30) NOT NULL,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    effect_json TEXT NOT NULL,
    duration INTEGER,
    expires_at TIMESTAMP,
    source VARCHAR(100),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Step 4: Create party_shared_inventory table
CREATE TABLE IF NOT EXISTS party_shared_inventory (
    id SERIAL PRIMARY KEY,
    party_id INTEGER NOT NULL REFERENCES party(id) ON DELETE CASCADE,
    item_slug VARCHAR(100) NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 1,
    added_by INTEGER REFERENCES character(id) ON DELETE SET NULL,
    added_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_party_item UNIQUE (party_id, item_slug)
);

-- Step 5: Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_party_member_party ON party_member(party_id);
CREATE INDEX IF NOT EXISTS idx_party_member_character ON party_member(character_id);
CREATE INDEX IF NOT EXISTS idx_party_buff_party ON party_buff(party_id);
CREATE INDEX IF NOT EXISTS idx_party_shared_inventory_party ON party_shared_inventory(party_id);

-- Step 6: Seed a default party for existing characters
INSERT INTO party (name, shared_gold, party_level, is_active, created_at)
VALUES ('Default Party', 50, 1, TRUE, CURRENT_TIMESTAMP)
ON CONFLICT DO NOTHING;

-- Add all existing characters to the default party
INSERT INTO party_member (party_id, character_id, role, position, joined_at)
SELECT
    (SELECT id FROM party WHERE name = 'Default Party' LIMIT 1),
    id,
    CASE
        WHEN character_class = 'warrior' THEN 'tank'
        WHEN character_class = 'mage' THEN 'dps'
        WHEN character_class = 'cleric' THEN 'healer'
        ELSE 'dps'
    END,
    CASE
        WHEN character_class = 'warrior' THEN 'front'
        WHEN character_class = 'mage' THEN 'back'
        WHEN character_class = 'cleric' THEN 'middle'
        ELSE 'middle'
    END,
    CURRENT_TIMESTAMP
FROM character
WHERE id NOT IN (SELECT character_id FROM party_member)
ON CONFLICT DO NOTHING;

-- Set the first character as party leader
UPDATE party
SET leader_id = (SELECT MIN(id) FROM character)
WHERE name = 'Default Party' AND leader_id IS NULL;

-- Add a starter leadership buff
INSERT INTO party_buff (party_id, buff_type, name, description, effect_json, source, created_at)
SELECT
    id,
    'leadership',
    'United Front',
    'Party members gain +5% damage when fighting together',
    '{"damage_bonus_percent": 5, "applies_to": "all"}',
    'default',
    CURRENT_TIMESTAMP
FROM party
WHERE name = 'Default Party'
ON CONFLICT DO NOTHING;
