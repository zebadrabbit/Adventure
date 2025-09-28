-- Monster seed data
-- Schema creation (idempotent). This creates a generic monster catalog table.
-- Stats are intentionally coarse; detailed combat math can derive secondary values later.
-- Difficulty scaling: base_hp ~ level * (8 + tier_modifier), base_damage ~ level * (1 + tier_mod/10).

BEGIN TRANSACTION;

CREATE TABLE IF NOT EXISTS monster_catalog (
    id INTEGER PRIMARY KEY,
    slug TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    level_min INTEGER NOT NULL DEFAULT 1,
    level_max INTEGER NOT NULL DEFAULT 1,
    base_hp INTEGER NOT NULL,
    base_damage INTEGER NOT NULL,
    armor INTEGER NOT NULL DEFAULT 0,
    speed INTEGER NOT NULL DEFAULT 10,
    rarity TEXT NOT NULL DEFAULT 'common',        -- common | uncommon | rare | elite | boss
    family TEXT NOT NULL,                        -- grouping: undead, beast, humanoid, construct, elemental, aberration
    traits TEXT,                                 -- CSV or JSON (future migration to join table)
    loot_table TEXT,                             -- key referencing loot logic (e.g., 'undead_basic', 'boss_dragon')
    special_drop_slug TEXT,                      -- optional guaranteed / high-chance special item slug
    xp_base INTEGER NOT NULL,                    -- base XP before scaling curve
    boss INTEGER NOT NULL DEFAULT 0              -- 0/1 flag
);

-- Helper conventions:
--  * Slugs: family_name_tier (e.g., skeleton_warrior_t1, goblin_scout_t1)
--  * Level bands: T1 (1-3), T2 (4-6), T3 (7-9), T4 (10-12), T5 (13-15), T6 (16-18), T7 (19-20)
--  * Bosses sit at upper edge of their intended band and may exceed base ranges.
--  * Named monsters have rarity 'elite' but boss=0, using special_drop_slug for unique loot.

-- Wipe existing to allow re-import updates while preserving unrelated tables.
DELETE FROM monster_catalog;

-- Common / baseline creatures (goblins, skeletons, wolves)
INSERT INTO monster_catalog (slug, name, level_min, level_max, base_hp, base_damage, armor, speed, rarity, family, traits, loot_table, xp_base, boss)
VALUES
 ('goblin_scout_t1', 'Goblin Scout', 1, 2, 18, 4, 0, 12, 'common', 'humanoid', 'nimble,low_light_vision', 'goblin_basic', 15, 0),
 ('goblin_raider_t2', 'Goblin Raider', 4, 5, 52, 10, 2, 12, 'common', 'humanoid', 'aggressive,pack_tactics', 'goblin_basic', 40, 0),
 ('goblin_champion_t3', 'Goblin Champion', 7, 8, 110, 18, 4, 11, 'uncommon', 'humanoid', 'leader,pack_tactics', 'goblin_elite', 120, 0),
 ('skeleton_shambler_t1', 'Skeleton Shambler', 1, 3, 22, 5, 1, 10, 'common', 'undead', 'resist_pierce,vulnerable_bludgeon', 'undead_basic', 20, 0),
 ('skeleton_archer_t2', 'Skeleton Archer', 4, 6, 60, 12, 1, 11, 'common', 'undead', 'ranged,resist_pierce', 'undead_basic', 55, 0),
 ('skeleton_knight_t3', 'Skeleton Knight', 7, 9, 125, 20, 6, 9, 'uncommon', 'undead', 'shielded,resist_pierce', 'undead_elite', 140, 0),
 ('wolf_gray_t1', 'Gray Wolf', 1, 2, 20, 6, 0, 14, 'common', 'beast', 'pack_tactics,scent', 'beast_basic', 18, 0),
 ('wolf_dire_t3', 'Dire Wolf', 7, 9, 140, 22, 2, 14, 'uncommon', 'beast', 'pack_tactics,scent', 'beast_elite', 150, 0);

-- Elementals (mid/high-tier scaling)
INSERT INTO monster_catalog (slug, name, level_min, level_max, base_hp, base_damage, armor, speed, rarity, family, traits, loot_table, xp_base, boss)
VALUES
 ('fire_elemental_minor_t3', 'Minor Fire Elemental', 7, 9, 130, 24, 3, 12, 'uncommon', 'elemental', 'burn_aura,immune_fire,vulnerable_cold', 'elemental_basic', 160, 0),
 ('fire_elemental_greater_t5', 'Greater Fire Elemental', 13, 15, 340, 48, 6, 12, 'rare', 'elemental', 'burn_aura,immune_fire,vulnerable_cold', 'elemental_elite', 420, 0),
 ('earth_elemental_minor_t3', 'Minor Earth Elemental', 7, 9, 180, 20, 10, 8, 'uncommon', 'elemental', 'resist_slash,slow', 'elemental_basic', 170, 0),
 ('earth_elemental_greater_t5', 'Greater Earth Elemental', 13, 15, 400, 42, 14, 8, 'rare', 'elemental', 'resist_slash,slow', 'elemental_elite', 440, 0);

-- Named (elite, non-boss) with special drops
INSERT INTO monster_catalog (slug, name, level_min, level_max, base_hp, base_damage, armor, speed, rarity, family, traits, loot_table, special_drop_slug, xp_base, boss)
VALUES
 ('grimtooth_goblin_chief', 'Grimtooth, Goblin Chief', 8, 8, 180, 26, 5, 12, 'elite', 'humanoid', 'leader,pack_tactics,strategist', 'goblin_named', 'short-sword', 300, 0),
 ('sir_rattleborne', 'Sir Rattleborne', 9, 9, 210, 30, 8, 9, 'elite', 'undead', 'shielded,aura_fear,resist_pierce', 'undead_named', 'wooden-shield', 340, 0),
 ('embermane', 'Embermane', 14, 14, 460, 58, 6, 15, 'elite', 'beast', 'burn_aura,charge', 'beast_named', 'hunting-bow', 620, 0);

-- Boss monsters (end-of-region / dungeon terminus)
INSERT INTO monster_catalog (slug, name, level_min, level_max, base_hp, base_damage, armor, speed, rarity, family, traits, loot_table, special_drop_slug, xp_base, boss)
VALUES
 ('necromancer_overlord', 'Necromancer Overlord', 10, 10, 600, 55, 8, 11, 'boss', 'humanoid', 'spellcaster,summoner,aura_fear', 'boss_necromancer', 'oak-staff', 1200, 1),
 ('wyrm_of_ashen_gate', 'Wyrm of the Ashen Gate', 15, 15, 1200, 92, 14, 12, 'boss', 'dragon', 'flying,breath_fire,frightful_presence', 'boss_dragon', 'leather-armor', 2400, 1),
 ('primordial_flame', 'Primordial Flame', 20, 20, 1800, 120, 10, 13, 'boss', 'elemental', 'burn_aura,regenerate_fire,immune_fire', 'boss_primordial', 'potion-mana', 4000, 1);

COMMIT;

-- Usage:
--   sqlite3 instance/mud.db < sql/monsters_seed.sql
-- Later: add spawn weighting / region mapping referencing monster_catalog.slug.
