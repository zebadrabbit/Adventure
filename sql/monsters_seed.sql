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

-- Expansion: Additional Monster Families & Tiers
BEGIN TRANSACTION;

-- Additional baseline beasts
INSERT INTO monster_catalog (slug, name, level_min, level_max, base_hp, base_damage, armor, speed, rarity, family, traits, loot_table, xp_base, boss)
VALUES
 ('boar_forest_t1','Forest Boar',1,3,28,6,1,11,'common','beast','charge,thick_hide','beast_basic',22,0),
 ('bear_black_t2','Black Bear',4,6,90,16,3,10,'common','beast','maul,thick_hide','beast_basic',70,0),
 ('bear_cave_t3','Cave Bear',7,9,180,28,5,9,'uncommon','beast','maul,thick_hide','beast_elite',160,0),
 ('hawk_giant_t2','Giant Hawk',4,6,60,14,1,16,'common','beast','flying,dive','beast_basic',62,0);

-- Constructs (defensive, slower)
INSERT INTO monster_catalog (slug, name, level_min, level_max, base_hp, base_damage, armor, speed, rarity, family, traits, loot_table, xp_base, boss)
VALUES
 ('golemClay_t3','Clay Golem',7,9,240,24,10,8,'uncommon','construct','slam,resist_slash','construct_basic',190,0),
 ('golemStone_t4','Stone Golem',10,12,420,38,14,7,'rare','construct','slam,resist_physical','construct_elite',320,0),
 ('golemIron_t5','Iron Golem',13,15,640,54,18,7,'rare','construct','slam,reflect_missile','construct_elite',520,0);

-- Aberrations (odd traits, mixed defenses)
INSERT INTO monster_catalog (slug, name, level_min, level_max, base_hp, base_damage, armor, speed, rarity, family, traits, loot_table, xp_base, boss)
VALUES
 ('mindleech_spawn_t3','Mindleech Spawn',7,9,130,22,4,12,'uncommon','aberration','psychic_bite,aura_fear','aberration_basic',180,0),
 ('eyestalk_watcher_t4','Eyestalk Watcher',10,12,260,36,6,11,'rare','aberration','multi_beam,levitate','aberration_elite',340,0),
 ('void_carapace_t5','Void Carapace',13,15,480,48,12,9,'rare','aberration','phase_shift,psychic_blast','aberration_elite',560,0);

-- Demons (offensive focus, resist fire)
INSERT INTO monster_catalog (slug, name, level_min, level_max, base_hp, base_damage, armor, speed, rarity, family, traits, loot_table, xp_base, boss)
VALUES
 ('imp_brimstone_t2','Brimstone Imp',4,6,70,14,2,14,'common','demon','flying,firebolt,immune_fire','demon_basic',66,0),
 ('fiend_fleshripper_t4','Fleshripper Fiend',10,12,300,44,6,13,'uncommon','demon','bleed_claw,immune_fire','demon_elite',360,0),
 ('demon_infernal_knight_t5','Infernal Knight',13,15,560,62,12,11,'rare','demon','flame_aura,shield','demon_elite',620,0);

-- Mini-bosses (elite rarity, non-boss flag, special drops)
INSERT INTO monster_catalog (slug, name, level_min, level_max, base_hp, base_damage, armor, speed, rarity, family, traits, loot_table, special_drop_slug, xp_base, boss)
VALUES
 ('boar_alpha_t2','Alpha Boar',6,6,160,28,4,12,'elite','beast','charge,thick_hide','beast_named','weapon_spear_l6',240,0),
 ('golemHeart_stone_t4','Heartbound Stone Golem',12,12,520,46,16,7,'elite','construct','slam,core_pulse','construct_named','weapon_mace_l12',480,0),
 ('mindleech_overseer_t4','Mindleech Overseer',12,12,340,50,8,12,'elite','aberration','psychic_blast,aura_fear','aberration_named','weapon_staff_l12',520,0),
 ('infernal_champion_t5','Infernal Champion',15,15,720,74,14,12,'elite','demon','flame_aura,charge,immune_fire','demon_named','weapon_flail_l15',840,0);

-- Additional bosses high tiers (optional, different families)
INSERT INTO monster_catalog (slug, name, level_min, level_max, base_hp, base_damage, armor, speed, rarity, family, traits, loot_table, special_drop_slug, xp_base, boss)
VALUES
 ('golem_core_colossus','Core Colossus',18,18,1500,110,24,8,'boss','construct','core_beam,quake,resist_physical','boss_construct','weapon_mace_l18',3600,1),
 ('void_eye_titan','Void Eye Titan',19,19,1600,118,16,12,'boss','aberration','multi_beam,phase_shift,levitate','boss_aberration','weapon_staff_l19',3800,1),
 ('demon_pit_overlord','Pit Overlord',20,20,2000,140,20,13,'boss','demon','flame_aura,meteor,burning_ground','boss_demon','weapon_flail_l20',4200,1);

COMMIT;

-- Usage:
--   sqlite3 instance/mud.db < sql/monsters_seed.sql
-- Later: add spawn weighting / region mapping referencing monster_catalog.slug.
