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
 ('goblin_scout_t1', 'Goblin Scout', 1, 2, 18, 4, 0, 12, 'common', 'humanoid', 'nimble,low_light_vision', 'goblin_basic', 15, false),
 ('goblin_raider_t2', 'Goblin Raider', 4, 5, 52, 10, 2, 12, 'common', 'humanoid', 'aggressive,pack_tactics', 'goblin_basic', 40, false),
 ('goblin_champion_t3', 'Goblin Champion', 7, 8, 110, 18, 4, 11, 'uncommon', 'humanoid', 'leader,pack_tactics', 'goblin_elite', 120, false),
 ('skeleton_shambler_t1', 'Skeleton Shambler', 1, 3, 22, 5, 1, 10, 'common', 'undead', 'resist_pierce,vulnerable_bludgeon', 'undead_basic', 20, false),
 ('skeleton_archer_t2', 'Skeleton Archer', 4, 6, 60, 12, 1, 11, 'common', 'undead', 'ranged,resist_pierce', 'undead_basic', 55, false),
 ('skeleton_knight_t3', 'Skeleton Knight', 7, 9, 125, 20, 6, 9, 'uncommon', 'undead', 'shielded,resist_pierce', 'undead_elite', 140, false),
 ('wolf_gray_t1', 'Gray Wolf', 1, 2, 20, 6, 0, 14, 'common', 'beast', 'pack_tactics,scent', 'beast_basic', 18, false),
 ('wolf_dire_t3', 'Dire Wolf', 7, 9, 140, 22, 2, 14, 'uncommon', 'beast', 'pack_tactics,scent', 'beast_elite', 150, false);

-- Elementals (mid/high-tier scaling)
INSERT INTO monster_catalog (slug, name, level_min, level_max, base_hp, base_damage, armor, speed, rarity, family, traits, loot_table, xp_base, boss)
VALUES
 ('spark_wisp_t1', 'Spark Wisp', 1, 3, 17, 4, 0, 15, 'common', 'elemental', 'shock_touch,evasive', 'elemental_basic', 16, false),
 ('gust_elemental_t2', 'Gust Elemental', 4, 6, 65, 12, 1, 16, 'common', 'elemental', 'gust,evasive', 'elemental_basic', 60, false),
 ('fire_elemental_minor_t3', 'Minor Fire Elemental', 7, 9, 130, 24, 3, 12, 'uncommon', 'elemental', 'burn_aura,immune_fire,vulnerable_cold', 'elemental_basic', 160, false),
 ('fire_elemental_greater_t5', 'Greater Fire Elemental', 13, 15, 340, 48, 6, 12, 'rare', 'elemental', 'burn_aura,immune_fire,vulnerable_cold', 'elemental_elite', 420, false),
 ('earth_elemental_minor_t3', 'Minor Earth Elemental', 7, 9, 180, 20, 10, 8, 'uncommon', 'elemental', 'resist_slash,slow', 'elemental_basic', 170, false),
 ('earth_elemental_greater_t5', 'Greater Earth Elemental', 13, 15, 400, 42, 14, 8, 'rare', 'elemental', 'resist_slash,slow', 'elemental_elite', 440, false);

-- Named (elite, non-boss) with special drops
INSERT INTO monster_catalog (slug, name, level_min, level_max, base_hp, base_damage, armor, speed, rarity, family, traits, loot_table, special_drop_slug, xp_base, boss)
VALUES
 ('grimtooth_goblin_chief', 'Grimtooth, Goblin Chief', 8, 8, 180, 26, 5, 12, 'elite', 'humanoid', 'leader,pack_tactics,strategist', 'goblin_named', 'short-sword', 300, false),
 ('sir_rattleborne', 'Sir Rattleborne', 9, 9, 210, 30, 8, 9, 'elite', 'undead', 'shielded,aura_fear,resist_pierce', 'undead_named', 'wooden-shield', 340, false),
 ('embermane', 'Embermane', 14, 14, 460, 58, 6, 15, 'elite', 'beast', 'burn_aura,charge', 'beast_named', 'hunting-bow', 620, false);

-- Boss monsters (end-of-region / dungeon terminus)
INSERT INTO monster_catalog (slug, name, level_min, level_max, base_hp, base_damage, armor, speed, rarity, family, traits, loot_table, special_drop_slug, xp_base, boss)
VALUES
 ('necromancer_overlord', 'Necromancer Overlord', 10, 10, 600, 55, 8, 11, 'boss', 'humanoid', 'spellcaster,summoner,aura_fear', 'boss_necromancer', 'oak-staff', 1200, true),
 ('wyrm_of_ashen_gate', 'Wyrm of the Ashen Gate', 15, 15, 1200, 92, 14, 12, 'boss', 'dragon', 'flying,breath_fire,frightful_presence', 'boss_dragon', 'leather-armor', 2400, true),
 ('primordial_flame', 'Primordial Flame', 20, 20, 1800, 120, 10, 13, 'boss', 'elemental', 'burn_aura,regenerate_fire,immune_fire', 'boss_primordial', 'potion-mana', 4000, true);

-- ===========================================================================
-- Compendium expansion (2026-07-27): SRD-derived, reflavoured to house style.
--
-- Stat blocks are adapted from the D&D 5e SRD 5.1 (CC BY 4.0, Wizards of the
-- Coast) -- challenge ratings remapped onto this game's own HP/damage/XP curve
-- rather than imported raw, and every creature renamed into this world's voice
-- to match the original 45 entries. No non-SRD creatures are referenced.
--
-- Fills the family x level-band gaps: dragons had a single entry, undead and
-- humanoids stopped at level 9-10, and nothing above 15 outside a few bosses.
-- Curve reference (common tier): L1-3 ~17-28 hp / 4-6 dmg / 15-22 xp;
-- L4-6 ~52-90 / 10-16 / 40-70; L7-9 ~110-190 / 18-28 / 120-190;
-- L10-12 ~260-420 / 36-46 / 320-360; L13-15 ~340-640 / 42-64 / 420-640;
-- L16-18 ~820-950 / 84-98 / 1250-1450. Elites run ~1.8x hp and ~3x xp of
-- their band; bosses ~3-4x hp and ~6-10x xp.
-- ===========================================================================

-- Dragons: a full line from hatchling to wyrm (previously one L15 boss).
INSERT INTO monster_catalog (slug, name, level_min, level_max, base_hp, base_damage, armor, speed, rarity, family, traits, loot_table, xp_base, boss)
VALUES
 ('dragon_cinder_hatchling_t1','Cinder Hatchling',1,3,25,6,2,12,'common','dragon','breath_fire,flying','dragon_basic',22, false),
 ('dragon_ember_whelp_t1','Ember Whelp',2,3,30,7,3,13,'common','dragon','breath_fire,flying','dragon_basic',26, false),
 ('dragon_scalewing_skitter_t2','Scalewing Skitter',4,6,78,15,4,15,'common','dragon','flying,pounce','dragon_basic',68, false),
 ('dragon_bog_drake_t3','Bog Drake',7,9,165,26,6,12,'uncommon','dragon','breath_acid,thick_hide','dragon_basic',175, false),
 ('dragon_stormwing_drake_t3','Stormwing Drake',7,9,150,28,4,16,'uncommon','dragon','flying,breath_lightning','dragon_basic',180, false),
 ('dragon_frost_serpent_t4','Frost Serpent',10,12,380,42,10,11,'rare','dragon','breath_frost,immune_cold','dragon_elite',350, false),
 ('dragon_gilded_tyrant_t4','Gilded Tyrant',12,12,520,52,12,12,'elite','dragon','breath_fire,frightful_presence,flying','dragon_named',560, false),
 ('dragon_verdant_ancient_t5','Verdant Ancient',16,18,900,92,16,11,'elite','dragon','breath_acid,thick_hide,frightful_presence','dragon_named',1400, false),
 ('dragon_stormcrown_wyrm','Stormcrown Wyrm',20,20,1900,132,18,14,'boss','dragon','breath_lightning,flying,frightful_presence,tail_sweep','boss_dragon',4100, true);

-- Undead: the line stopped at level 9; wights, wraiths and worse now follow.
INSERT INTO monster_catalog (slug, name, level_min, level_max, base_hp, base_damage, armor, speed, rarity, family, traits, loot_table, xp_base, boss)
VALUES
 ('undead_rot_shambler_t1','Rot Shambler',1,3,26,5,1,8,'common','undead','undead_fortitude,slow','undead_basic',19, false),
 ('undead_carrion_ghoul_t2','Carrion Ghoul',4,6,62,12,1,13,'common','undead','paralyzing_touch,pack_tactics','undead_basic',58, false),
 ('undead_grave_hound_t2','Grave Hound',4,6,55,13,2,15,'common','undead','pack_tactics,scent','undead_basic',56, false),
 ('undead_barrow_warden_t3','Barrow Warden',8,10,190,26,7,10,'uncommon','undead','life_drain,resist_slash','undead_basic',185, false),
 ('undead_hollow_wraith_t4','Hollow Wraith',10,12,270,40,4,14,'rare','undead','incorporeal,life_drain,aura_fear','undead_elite',345, false),
 ('undead_bandaged_king_t4','Bandaged King',12,12,400,46,10,8,'elite','undead','aura_fear,curse_touch,resist_physical','undead_named',530, false),
 ('undead_gravecall_lich_t5','Gravecall Lich',13,15,520,58,8,11,'rare','undead','summon_minor,life_drain,magic_resistance','undead_elite',600, false),
 ('undead_bone_choir_t5','Bone Choir',16,18,820,84,12,9,'elite','undead','aura_fear,summon_minor,resist_slash','undead_named',1300, false),
 ('undead_hollow_crown','The Hollow Crown',19,19,1700,124,16,10,'boss','undead','life_drain,summon_minor,aura_fear,phase_shift','boss_undead',3900, true);

-- Humanoids: previously goblins-only above level 4, and nothing past 10.
INSERT INTO monster_catalog (slug, name, level_min, level_max, base_hp, base_damage, armor, speed, rarity, family, traits, loot_table, xp_base, boss)
VALUES
 ('humanoid_marsh_stalker_t1','Marsh Stalker',1,3,24,5,1,12,'common','humanoid','nimble,poison_bite','humanoid_basic',18, false),
 ('humanoid_ridge_brute_t2','Ridge Brute',4,6,85,15,3,10,'common','humanoid','maul,thick_hide','humanoid_basic',68, false),
 ('humanoid_fen_hexer_t2','Fen Hexer',4,6,58,14,1,12,'common','humanoid','firebolt,curse_touch','humanoid_basic',60, false),
 ('humanoid_ashen_zealot_t3','Ashen Zealot',7,9,135,24,4,12,'uncommon','humanoid','firebolt,leader','humanoid_basic',165, false),
 ('humanoid_crag_giant_t4','Crag Giant',10,12,400,44,8,10,'rare','humanoid','boulder_throw,thick_hide','humanoid_elite',355, false),
 ('humanoid_iron_warlord_t4','Iron Warlord',12,12,380,48,14,11,'elite','humanoid','leader,shielded,charge','humanoid_named',540, false),
 ('humanoid_frostbound_jarl_t5','Frostbound Jarl',13,15,600,60,12,10,'rare','humanoid','frost_aura,maul,immune_cold','humanoid_elite',610, false),
 ('humanoid_pale_tyrant','The Pale Tyrant',16,18,1400,104,18,11,'boss','humanoid','leader,summon_minor,aura_fear','boss_humanoid',3400, true);

-- Beasts: nothing stalked the deep floors above level 14.
INSERT INTO monster_catalog (slug, name, level_min, level_max, base_hp, base_damage, armor, speed, rarity, family, traits, loot_table, xp_base, boss)
VALUES
 ('beast_burrow_ravager_t2','Burrow Ravager',4,6,72,14,4,11,'common','beast','burrow,acid_spray','beast_basic',64, false),
 ('beast_thicket_maul_t3','Thicket Maul',7,9,175,25,3,11,'uncommon','beast','maul,thick_hide,scent','beast_basic',170, false),
 ('beast_chasm_lurker_t4','Chasm Lurker',10,12,300,40,6,12,'rare','beast','web,poison_bite,ambusher','beast_elite',340, false),
 ('beast_skyrend_raptor_t4','Skyrend Raptor',10,12,280,42,5,17,'rare','beast','flying,charge,dive','beast_elite',350, false),
 ('beast_three_maw_t5','Three-Maw',13,15,560,64,8,13,'elite','beast','breath_fire,maul,flying','beast_named',640, false),
 ('beast_tidefall_roc_t5','Tidefall Roc',16,18,880,88,10,16,'elite','beast','flying,grapple,dive','beast_named',1250, false);

-- Demons: filled the 7-9 hole and the long gap above 15.
INSERT INTO monster_catalog (slug, name, level_min, level_max, base_hp, base_damage, armor, speed, rarity, family, traits, loot_table, xp_base, boss)
VALUES
 ('demon_gnashing_dretch_t3','Gnashing Dretch',7,9,145,22,3,11,'uncommon','demon','pack_tactics,rot_cloud','demon_basic',155, false),
 ('demon_abyssal_maulape_t3','Abyssal Maulape',7,9,190,26,4,13,'uncommon','demon','maul,leap','demon_basic',175, false),
 ('demon_carrion_shrieker_t4','Carrion Shrieker',10,12,320,42,6,14,'rare','demon','flying,spores,aura_fear','demon_elite',350, false),
 ('demon_bloatgut_fiend_t5','Bloatgut Fiend',13,15,620,58,10,9,'rare','demon','rot_cloud,thick_hide,immune_poison','demon_elite',580, false),
 ('demon_six_blade_dancer_t5','Six-Blade Dancer',16,18,950,98,12,15,'elite','demon','multi_strike,evasive,resist_slash','demon_named',1450, false),
 ('demon_gloom_prince','Gloom Prince',19,19,1750,128,16,12,'boss','demon','aura_fear,summon_minor,flame_aura','boss_demon',3900, true);

-- Elementals: adds the cold/water line and the missing 10-12 and 16-19 bands.
INSERT INTO monster_catalog (slug, name, level_min, level_max, base_hp, base_damage, armor, speed, rarity, family, traits, loot_table, xp_base, boss)
VALUES
 ('elemental_frost_mote_t1','Frost Mote',1,3,19,5,1,12,'common','elemental','frost_aura,vulnerable_fire','elemental_basic',17, false),
 ('elemental_tide_wisp_t2','Tide Wisp',4,6,66,12,2,13,'common','elemental','engulf,resist_physical','elemental_basic',58, false),
 ('elemental_glacier_maw_t4','Glacier Maw',10,12,360,40,10,9,'rare','elemental','immune_cold,frost_aura,slam','elemental_elite',345, false),
 ('elemental_stormcaller_t4','Stormcaller',10,12,290,46,4,16,'rare','elemental','breath_lightning,levitate,evasive','elemental_elite',350, false),
 ('elemental_riptide_colossus_t5','Riptide Colossus',16,18,900,86,14,10,'elite','elemental','engulf,slam,resist_physical','elemental_named',1300, false),
 ('elemental_hoarfrost_sovereign','Hoarfrost Sovereign',19,19,1650,120,14,11,'boss','elemental','immune_cold,frost_aura,blizzard','boss_elemental',3850, true);

-- Constructs: mid-band filler plus the missing 16-18 and a capstone boss.
INSERT INTO monster_catalog (slug, name, level_min, level_max, base_hp, base_damage, armor, speed, rarity, family, traits, loot_table, xp_base, boss)
VALUES
 ('construct_scrap_swarm_t1','Scrap Swarm',1,3,22,5,2,12,'common','construct','swarm,evasive','construct_basic',18, false),
 ('construct_clay_sentinel_t2','Clay Sentinel',4,6,80,12,5,8,'common','construct','slam,slow','construct_basic',64, false),
 ('construct_helmed_watcher_t3','Helmed Watcher',7,9,160,22,8,10,'uncommon','construct','shielded,magic_resistance','construct_basic',165, false),
 ('construct_bound_guardian_t4','Bound Guardian',10,12,390,40,12,9,'rare','construct','shielded,slam,regeneration','construct_elite',350, false),
 ('construct_brass_inquisitor_t5','Brass Inquisitor',16,18,950,84,20,8,'elite','construct','slam,burn_aura,resist_physical','construct_named',1350, false),
 ('construct_worldforge_engine','Worldforge Engine',20,20,1950,130,22,7,'boss','construct','slam,burning_ground,resist_physical','boss_construct',4150, true);

-- Aberrations: the 16-18 band and a capstone to sit beside the Void Eye Titan.
INSERT INTO monster_catalog (slug, name, level_min, level_max, base_hp, base_damage, armor, speed, rarity, family, traits, loot_table, xp_base, boss)
VALUES
 ('aberration_gutter_chuul_t3','Gutter Chuul',7,9,170,24,7,10,'uncommon','aberration','grapple,paralyzing_touch','aberration_basic',170, false),
 ('aberration_refuse_maw_t4','Refuse Maw',10,12,340,40,6,9,'rare','aberration','grapple,rot_cloud,swallow','aberration_elite',345, false),
 ('aberration_shroud_drifter_t5','Shroud Drifter',13,15,500,54,8,13,'rare','aberration','phase_shift,aura_fear,psychic_blast','aberration_elite',590, false),
 ('aberration_hook_tyrant_t5','Hook Tyrant',16,18,870,86,14,8,'elite','aberration','grapple,psychic_blast,thick_hide','aberration_named',1300, false),
 ('aberration_deep_mind','The Deep Mind',20,20,1850,126,14,10,'boss','aberration','psychic_blast,dominate,phase_shift','boss_aberration',4050, true);

COMMIT;

-- Expansion: Additional Monster Families & Tiers
BEGIN TRANSACTION;

-- Additional baseline beasts
INSERT INTO monster_catalog (slug, name, level_min, level_max, base_hp, base_damage, armor, speed, rarity, family, traits, loot_table, xp_base, boss)
VALUES
 ('boar_forest_t1','Forest Boar',1,3,28,6,1,11,'common','beast','charge,thick_hide','beast_basic',22, false),
 ('bear_black_t2','Black Bear',4,6,90,16,3,10,'common','beast','maul,thick_hide','beast_basic',70, false),
 ('bear_cave_t3','Cave Bear',7,9,180,28,5,9,'uncommon','beast','maul,thick_hide','beast_elite',160, false),
 ('hawk_giant_t2','Giant Hawk',4,6,60,14,1,16,'common','beast','flying,dive','beast_basic',62, false);

-- Constructs (defensive, slower)
INSERT INTO monster_catalog (slug, name, level_min, level_max, base_hp, base_damage, armor, speed, rarity, family, traits, loot_table, xp_base, boss)
VALUES
 ('rubble_construct_t1','Rubble Construct',1,3,26,5,4,7,'common','construct','slam,resist_slash','construct_basic',18, false),
 ('animated_armor_t2','Animated Armor',4,6,75,13,6,9,'common','construct','slam,resist_slash','construct_basic',65, false),
 ('golemClay_t3','Clay Golem',7,9,240,24,10,8,'uncommon','construct','slam,resist_slash','construct_basic',190, false),
 ('golemStone_t4','Stone Golem',10,12,420,38,14,7,'rare','construct','slam,resist_physical','construct_elite',320, false),
 ('golemIron_t5','Iron Golem',13,15,640,54,18,7,'rare','construct','slam,reflect_missile','construct_elite',520, false);

-- Aberrations (odd traits, mixed defenses)
INSERT INTO monster_catalog (slug, name, level_min, level_max, base_hp, base_damage, armor, speed, rarity, family, traits, loot_table, xp_base, boss)
VALUES
 ('spore_crawler_t1','Spore Crawler',1,3,20,5,0,9,'common','aberration','psychic_bite,spores','aberration_basic',17, false),
 ('gloom_tendril_t2','Gloom Tendril',4,6,68,13,2,10,'common','aberration','psychic_bite,aura_fear','aberration_basic',62, false),
 ('mindleech_spawn_t3','Mindleech Spawn',7,9,130,22,4,12,'uncommon','aberration','psychic_bite,aura_fear','aberration_basic',180, false),
 ('eyestalk_watcher_t4','Eyestalk Watcher',10,12,260,36,6,11,'rare','aberration','multi_beam,levitate','aberration_elite',340, false),
 ('void_carapace_t5','Void Carapace',13,15,480,48,12,9,'rare','aberration','phase_shift,psychic_blast','aberration_elite',560, false);

-- Demons (offensive focus, resist fire)
INSERT INTO monster_catalog (slug, name, level_min, level_max, base_hp, base_damage, armor, speed, rarity, family, traits, loot_table, xp_base, boss)
VALUES
 ('imp_lesser_t1','Lesser Imp',1,3,17,4,0,13,'common','demon','flying,firebolt','demon_basic',15, false),
 ('imp_brimstone_t2','Brimstone Imp',4,6,70,14,2,14,'common','demon','flying,firebolt,immune_fire','demon_basic',66, false),
 ('fiend_fleshripper_t4','Fleshripper Fiend',10,12,300,44,6,13,'uncommon','demon','bleed_claw,immune_fire','demon_elite',360, false),
 ('demon_infernal_knight_t5','Infernal Knight',13,15,560,62,12,11,'rare','demon','flame_aura,shield','demon_elite',620, false);

-- Mini-bosses (elite rarity, non-boss flag, special drops)
INSERT INTO monster_catalog (slug, name, level_min, level_max, base_hp, base_damage, armor, speed, rarity, family, traits, loot_table, special_drop_slug, xp_base, boss)
VALUES
 ('boar_alpha_t2','Alpha Boar',6,6,160,28,4,12,'elite','beast','charge,thick_hide','beast_named','weapon_spear_l6',240, false),
 ('golemHeart_stone_t4','Heartbound Stone Golem',12,12,520,46,16,7,'elite','construct','slam,core_pulse','construct_named','weapon_mace_l12',480, false),
 ('mindleech_overseer_t4','Mindleech Overseer',12,12,340,50,8,12,'elite','aberration','psychic_blast,aura_fear','aberration_named','weapon_staff_l12',520, false),
 ('infernal_champion_t5','Infernal Champion',15,15,720,74,14,12,'elite','demon','flame_aura,charge,immune_fire','demon_named','weapon_flail_l15',840, false);

-- Additional bosses high tiers (optional, different families)
INSERT INTO monster_catalog (slug, name, level_min, level_max, base_hp, base_damage, armor, speed, rarity, family, traits, loot_table, special_drop_slug, xp_base, boss)
VALUES
 ('golem_core_colossus','Core Colossus',18,18,1500,110,24,8,'boss','construct','core_beam,quake,resist_physical','boss_construct','weapon_mace_l18',3600, true),
 ('void_eye_titan','Void Eye Titan',19,19,1600,118,16,12,'boss','aberration','multi_beam,phase_shift,levitate','boss_aberration','weapon_staff_l19',3800, true),
 ('demon_pit_overlord','Pit Overlord',20,20,2000,140,20,13,'boss','demon','flame_aura,meteor,burning_ground','boss_demon','weapon_flail_l20',4200, true);

-- Top band (19-20) held nothing but bosses, so ordinary spawns at max depth had
-- no catalogue identity to borrow and fell back to a bare "Trash (L19)" label.
INSERT INTO monster_catalog (slug, name, level_min, level_max, base_hp, base_damage, armor, speed, rarity, family, traits, loot_table, xp_base, boss)
VALUES
 ('undead_dread_sentinel_t6','Dread Sentinel',19,20,1050,96,16,10,'elite','undead','aura_fear,life_drain,resist_slash','undead_named',1650, false),
 ('demon_ruin_harbinger_t6','Ruin Harbinger',19,20,1120,104,14,13,'elite','demon','flame_aura,multi_strike,resist_slash','demon_named',1700, false),
 ('construct_adamant_warden_t6','Adamant Warden',19,20,1300,92,24,7,'elite','construct','slam,shielded,resist_physical','construct_named',1600, false),
 ('beast_worldscar_behemoth_t6','Worldscar Behemoth',19,20,1250,108,12,11,'elite','beast','maul,charge,thick_hide','beast_named',1720, false),
 ('humanoid_ashen_conqueror_t6','Ashen Conqueror',19,20,1000,100,18,12,'elite','humanoid','leader,charge,shielded','humanoid_named',1680, false);

COMMIT;

-- Usage:
--   sqlite3 instance/mud.db < sql/monsters_seed.sql
-- Later: add spawn weighting / region mapping referencing monster_catalog.slug.
