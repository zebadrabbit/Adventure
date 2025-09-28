-- Weapon Items Seed Data
-- Levels 1-20, covering common fantasy archetypes.
-- Value curve: base_copper = tier_multiplier * level^2 + rarity kicker.
-- Slug pattern: weapon_<type>_l<level>
-- Type column uses 'weapon'.
-- All items are generic cross-class unless class-specific variants introduced later.

BEGIN TRANSACTION;

-- Swords (balanced damage)
-- (Removed legacy malformed single-row INSERT for weapon_sword_l1)
-- Using a compound statement style for readability; each block ends with semicolon.

DELETE FROM item WHERE slug LIKE 'weapon_sword_l%';
INSERT INTO item (slug, name, type, description, value_copper) VALUES
-- Swords
('weapon_sword_l1','Rusty Shortsword','weapon','A worn but serviceable blade.',35),
('weapon_sword_l2','Iron Shortsword','weapon','Reliable iron construction.',60),
('weapon_sword_l3','Steel Shortsword','weapon','Sharper tempered steel blade.',95),
('weapon_sword_l4','Steel Longsword','weapon','Standard issue adventurer blade.',140),
('weapon_sword_l5','Knight Longsword','weapon','Well-balanced knightly steel.',200),
('weapon_sword_l6','Fine Longsword','weapon','Expertly honed edge.',280),
('weapon_sword_l7','Tempered Longsword','weapon','Resists wear in long battles.',380),
('weapon_sword_l8','Masterwork Longsword','weapon','A craftsman''s flawless creation.',510),
('weapon_sword_l9','Runed Longsword','weapon','Etched with faint glowing runes.',670),
('weapon_sword_l10','Mythril Longsword','weapon','Light and incredibly sharp.',860),
('weapon_sword_l11','Mythril Greatsword','weapon','Two-handed mythril devastation.',1080),
('weapon_sword_l12','Enchanted Greatsword','weapon','Arcane edge hums softly.',1320),
('weapon_sword_l13','Runed Greatsword','weapon','Runes pulse with latent power.',1600),
('weapon_sword_l14','Adamant Greatsword','weapon','Near unbreakable adamant alloy.',1925),
('weapon_sword_l15','Adamantine Greatsword','weapon','Refined adamantine slaughter blade.',2300),
('weapon_sword_l16','Celestial Greatsword','weapon','Radiant alloy channels light.',2720),
('weapon_sword_l17','Eclipse Greatsword','weapon','Blade drinks ambient light.',3190),
('weapon_sword_l18','Dragonbone Greatsword','weapon','Forged around dragonbone core.',3710),
('weapon_sword_l19','Runebound Greatsword','weapon','Runic lattice amplifies strikes.',4280),
('weapon_sword_l20','Transcendent Blade','weapon','Edge warps reality itself.',4900);

-- Axes (higher damage, heavier)
DELETE FROM item WHERE slug LIKE 'weapon_axe_l%';
INSERT INTO item (slug, name, type, description, value_copper) VALUES
('weapon_axe_l1','Chipped Handaxe','weapon','A small axe with nicks.',32),
('weapon_axe_l2','Iron Handaxe','weapon','Reliable sidearm.',58),
('weapon_axe_l3','Steel Handaxe','weapon','Balanced throwing weight.',92),
('weapon_axe_l4','Steel Battleaxe','weapon','Heavier head for brutal chops.',138),
('weapon_axe_l5','War Battleaxe','weapon','Favored by seasoned warriors.',198),
('weapon_axe_l6','Fine Battleaxe','weapon','Precision forged edge.',276),
('weapon_axe_l7','Reinforced Battleaxe','weapon','Riveted spine for durability.',374),
('weapon_axe_l8','Masterwork Battleaxe','weapon','Keen, perfectly balanced.',504),
('weapon_axe_l9','Runed Battleaxe','weapon','Glyphs sharpen each blow.',664),
('weapon_axe_l10','Mythril Battleaxe','weapon','Light for its size.',854),
('weapon_axe_l11','Mythril Greataxe','weapon','Massive sweeping arcs.',1074),
('weapon_axe_l12','Enchanted Greataxe','weapon','Crackles faintly on impact.',1314),
('weapon_axe_l13','Runed Greataxe','weapon','Blood channels carved in runes.',1592),
('weapon_axe_l14','Adamant Greataxe','weapon','Shatters lesser steel.',1914),
('weapon_axe_l15','Adamantine Greataxe','weapon','Edge holds near indefinitely.',2288),
('weapon_axe_l16','Celestial Greataxe','weapon','Radiant crescents cleave dark.',2708),
('weapon_axe_l17','Eclipse Greataxe','weapon','Absorbs faint warmth.',3176),
('weapon_axe_l18','Dragonbone Greataxe','weapon','Dragonbone core channels force.',3696),
('weapon_axe_l19','Runebound Greataxe','weapon','Rune cage amplifies momentum.',4268),
('weapon_axe_l20','Titan Cleaver','weapon','Splits armor like bark.',4890);

-- Spears (reach / precision)
DELETE FROM item WHERE slug LIKE 'weapon_spear_l%';
INSERT INTO item (slug, name, type, description, value_copper) VALUES
('weapon_spear_l1','Wooden Spear','weapon','Simple sharpened tip.',30),
('weapon_spear_l2','Iron Spear','weapon','Iron tip adds penetration.',55),
('weapon_spear_l3','Steel Spear','weapon','Reliable infantry weapon.',88),
('weapon_spear_l4','Steel Partisan','weapon','Winged blade prevents over-thrust.',132),
('weapon_spear_l5','Refined Partisan','weapon','Balanced for drill precision.',188),
('weapon_spear_l6','Fine Partisan','weapon','Polished and honed.',264),
('weapon_spear_l7','Tempered Partisan','weapon','Maintains edge in campaigns.',360),
('weapon_spear_l8','Masterwork Partisan','weapon','Exquisite balance.',486),
('weapon_spear_l9','Runed Partisan','weapon','Runes stabilize thrust.',642),
('weapon_spear_l10','Mythril Partisan','weapon','Featherweight control.',828),
('weapon_spear_l11','Mythril Halberd','weapon','Axe + hook versatility.',1044),
('weapon_spear_l12','Enchanted Halberd','weapon','Arc sparks on sweep.',1280),
('weapon_spear_l13','Runed Halberd','weapon','Glyph lattice along shaft.',1554),
('weapon_spear_l14','Adamant Halberd','weapon','Nearly unstoppable impact.',1868),
('weapon_spear_l15','Adamantine Halberd','weapon','Edge remains pristine.',2224),
('weapon_spear_l16','Celestial Halberd','weapon','Light-conductive shaft.',2624),
('weapon_spear_l17','Eclipse Halberd','weapon','Shadow halo on swings.',3070),
('weapon_spear_l18','Dragonbone Halberd','weapon','Bone core vibrates faintly.',3564),
('weapon_spear_l19','Runebound Halberd','weapon','Runes resonate at contact.',4108),
('weapon_spear_l20','Starlance Halberd','weapon','Tip trails starlight.',4700);

-- Bows (ranged)
DELETE FROM item WHERE slug LIKE 'weapon_bow_l%';
INSERT INTO item (slug, name, type, description, value_copper) VALUES
('weapon_bow_l1','Crude Shortbow','weapon','Basic flexible wood.',34),
('weapon_bow_l2','Elm Shortbow','weapon','Stronger limb tension.',60),
('weapon_bow_l3','Oak Shortbow','weapon','Improved draw strength.',94),
('weapon_bow_l4','Oak Longbow','weapon','Longer draw arc.',140),
('weapon_bow_l5','Refined Longbow','weapon','Carefully tillered limbs.',200),
('weapon_bow_l6','Yew Longbow','weapon','Classic war bow.',280),
('weapon_bow_l7','Composite Longbow','weapon','Horn & sinew layers.',380),
('weapon_bow_l8','Masterwork Longbow','weapon','Perfect release feel.',512),
('weapon_bow_l9','Runed Longbow','weapon','Glyphs steady the aim.',676),
('weapon_bow_l10','Mythril Longbow','weapon','Mythril reinforced nocks.',872),
('weapon_bow_l11','Mythril Warbow','weapon','High draw weight.',1100),
('weapon_bow_l12','Enchanted Warbow','weapon','Arrows spark faintly.',1350),
('weapon_bow_l13','Runed Warbow','weapon','Runes correct wind.',1638),
('weapon_bow_l14','Adamant Warbow','weapon','Frame resists torsion.',1968),
('weapon_bow_l15','Adamantine Warbow','weapon','Unyielding under stress.',2340),
('weapon_bow_l16','Celestial Warbow','weapon','String shimmers faintly.',2756),
('weapon_bow_l17','Eclipse Warbow','weapon','Arrows leave dark trail.',3218),
('weapon_bow_l18','Dragonbone Warbow','weapon','Bone core stores energy.',3730),
('weapon_bow_l19','Runebound Warbow','weapon','Runes guide trajectory.',4294),
('weapon_bow_l20','Starfall Warbow','weapon','Shots streak like meteors.',4910);

-- Daggers (fast / light)
DELETE FROM item WHERE slug LIKE 'weapon_dagger_l%';
INSERT INTO item (slug, name, type, description, value_copper) VALUES
('weapon_dagger_l1','Rusty Dagger','weapon','Pitted but sharp enough.',28),
('weapon_dagger_l2','Iron Dagger','weapon','Simple iron blade.',50),
('weapon_dagger_l3','Steel Dagger','weapon','Reliable sidearm.',80),
('weapon_dagger_l4','Fine Dagger','weapon','Honed for precision.',120),
('weapon_dagger_l5','Twinsteel Dagger','weapon','Dual-layer steel.',170),
('weapon_dagger_l6','Tempered Dagger','weapon','Holds edge well.',230),
('weapon_dagger_l7','Masterwork Dagger','weapon','Perfect balance.',300),
('weapon_dagger_l8','Runed Dagger','weapon','Runes dampen vibration.',380),
('weapon_dagger_l9','Mythril Dagger','weapon','Featherlight thrusts.',470),
('weapon_dagger_l10','Enchanted Dagger','weapon','Arcane sharpness.',570),
('weapon_dagger_l11','Adamant Dagger','weapon','Near chip-proof.',680),
('weapon_dagger_l12','Adamantine Dagger','weapon','Unbending spine.',800),
('weapon_dagger_l13','Celestial Dagger','weapon','Radiant glint.',930),
('weapon_dagger_l14','Eclipse Dagger','weapon','Edge darkens slightly.',1070),
('weapon_dagger_l15','Dragonbone Dagger','weapon','Bone infill core.',1220),
('weapon_dagger_l16','Runebound Dagger','weapon','Runes amplify strikes.',1380),
('weapon_dagger_l17','Voidglass Dagger','weapon','Glasslike translucent edge.',1550),
('weapon_dagger_l18','Starshard Dagger','weapon','Embedded star fragment.',1730),
('weapon_dagger_l19','Nightveil Dagger','weapon','Swallows reflections.',1920),
('weapon_dagger_l20','Transcendent Dagger','weapon','Reality-shearing point.',2120);

-- Staves (caster focus)
DELETE FROM item WHERE slug LIKE 'weapon_staff_l%';
INSERT INTO item (slug, name, type, description, value_copper) VALUES
('weapon_staff_l1','Crooked Staff','weapon','Knotted wood focus.',34),
('weapon_staff_l2','Oak Staff','weapon','Sturdy base focus.',58),
('weapon_staff_l3','Ash Staff','weapon','Resonant grain.',90),
('weapon_staff_l4','Runed Staff','weapon','Minor etched sigils.',134),
('weapon_staff_l5','Channeling Staff','weapon','Guides arcane flow.',190),
('weapon_staff_l6','Focus Staff','weapon','Enhanced conduit core.',260),
('weapon_staff_l7','Adept Staff','weapon','Responds to will.',350),
('weapon_staff_l8','Masterwork Staff','weapon','Minimizes mana loss.',462),
('weapon_staff_l9','Mythril Filigree Staff','weapon','Mythril veins pulse.',596),
('weapon_staff_l10','Enchanted Staff','weapon','Constant low hum.',752),
('weapon_staff_l11','Runed Focus Staff','weapon','Glyphs self-align.',930),
('weapon_staff_l12','Adamant Core Staff','weapon','Dense anchoring core.',1130),
('weapon_staff_l13','Celestial Staff','weapon','Radiates faint light.',1352),
('weapon_staff_l14','Eclipse Staff','weapon','Dark aura sheath.',1596),
('weapon_staff_l15','Dragonbone Staff','weapon','Bone amplifies spells.',1862),
('weapon_staff_l16','Runebound Staff','weapon','Runic lattice web.',2150),
('weapon_staff_l17','Voidbound Staff','weapon','Absorbs stray magic.',2460),
('weapon_staff_l18','Starforge Staff','weapon','Inlaid star-metal.',2792),
('weapon_staff_l19','Empyreal Staff','weapon','Celestial resonance.',3146),
('weapon_staff_l20','Transcendent Conduit','weapon','Pure arcane channel.',3522);

-- Maces (crushing)
DELETE FROM item WHERE slug LIKE 'weapon_mace_l%';
INSERT INTO item (slug, name, type, description, value_copper) VALUES
('weapon_mace_l1','Dentd Mace','weapon','Head is uneven.',30),
('weapon_mace_l2','Iron Mace','weapon','Solid iron head.',54),
('weapon_mace_l3','Steel Mace','weapon','Weighted for impact.',86),
('weapon_mace_l4','Flanged Mace','weapon','Flanges bite armor.',130),
('weapon_mace_l5','War Mace','weapon','Battle-hardened design.',186),
('weapon_mace_l6','Fine War Mace','weapon','Expert forging.',254),
('weapon_mace_l7','Reinforced War Mace','weapon','Ribbed core.',344),
('weapon_mace_l8','Masterwork War Mace','weapon','Optimized momentum.',456),
('weapon_mace_l9','Runed War Mace','weapon','Runes concentrate force.',590),
('weapon_mace_l10','Mythril War Mace','weapon','Light but deadly.',746),
('weapon_mace_l11','Adamant War Mace','weapon','Adamant cap.',924),
('weapon_mace_l12','Adamantine War Mace','weapon','Edge-resistant flanges.',1124),
('weapon_mace_l13','Celestial War Mace','weapon','Radiant shock on hit.',1346),
('weapon_mace_l14','Eclipse War Mace','weapon','Shadow ripple.',1590),
('weapon_mace_l15','Dragonbone War Mace','weapon','Bone shock core.',1856),
('weapon_mace_l16','Runebound War Mace','weapon','Runic energy shell.',2144),
('weapon_mace_l17','Voidforged War Mace','weapon','Echo absorbs sound.',2454),
('weapon_mace_l18','Starhammer Mace','weapon','Star-metal studs.',2786),
('weapon_mace_l19','Empyreal War Mace','weapon','Divine resonance.',3140),
('weapon_mace_l20','Transcendent War Mace','weapon','Reality-thumping blow.',3516);

-- Wands (light magic focus / offhand alt to staff)
DELETE FROM item WHERE slug LIKE 'weapon_wand_l%';
INSERT INTO item (slug, name, type, description, value_copper) VALUES
('weapon_wand_l1','Twig Wand','weapon','Barely stable focus.',22),
('weapon_wand_l2','Carved Wand','weapon','Simple carvings.',40),
('weapon_wand_l3','Runed Wand','weapon','Minor runic etchings.',62),
('weapon_wand_l4','Channel Wand','weapon','Improved mana flow.',86),
('weapon_wand_l5','Adept Wand','weapon','Responsive focus.',112),
('weapon_wand_l6','Fine Wand','weapon','Minimizes resonance loss.',140),
('weapon_wand_l7','Masterwork Wand','weapon','Highly efficient core.',170),
('weapon_wand_l8','Enchanted Wand','weapon','Stable arcane field.',202),
('weapon_wand_l9','Runed Focus Wand','weapon','Runes self-sustain.',236),
('weapon_wand_l10','Mythril Wand','weapon','Mythril filigree.',272),
('weapon_wand_l11','Adamant Wand','weapon','Rigid channel stability.',310),
('weapon_wand_l12','Adamantine Wand','weapon','Superior arc conduction.',350),
('weapon_wand_l13','Celestial Wand','weapon','Soft glow aura.',392),
('weapon_wand_l14','Eclipse Wand','weapon','Shadow core.',436),
('weapon_wand_l15','Dragonbone Wand','weapon','Bone resonance.',482),
('weapon_wand_l16','Runebound Wand','weapon','Dense rune network.',530),
('weapon_wand_l17','Voidglass Wand','weapon','Translucent void core.',580),
('weapon_wand_l18','Starshard Wand','weapon','Embedded star fragment.',632),
('weapon_wand_l19','Empyreal Wand','weapon','Divine-laced focus.',686),
('weapon_wand_l20','Transcendent Wand','weapon','Perfect mana conduit.',742);

COMMIT;
