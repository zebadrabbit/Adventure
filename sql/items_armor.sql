-- Armor & Accessories Seed Data (Levels 1-20)
-- Slots: head, chest, legs, hands, feet, belt, cloak, ring, amulet, shield
-- Slug pattern: armor_<slot>_l<level> or accessory_<type>_l<level>
-- All type column set to 'armor' except accessories use 'armor' as well for now (schema simple)
BEGIN TRANSACTION;

-- HEAD
DELETE FROM item WHERE slug LIKE 'armor_head_l%';
INSERT INTO item (slug, name, type, description, value_copper) VALUES
('armor_head_l1','Cloth Hood','armor','Simple cloth head covering.',24),
('armor_head_l2','Padded Hood','armor','Light cushioning.',40),
('armor_head_l3','Leather Cap','armor','Basic leather protection.',62),
('armor_head_l4','Reinforced Cap','armor','Studded reinforcement.',88),
('armor_head_l5','Iron Helm','armor','Metal dome helmet.',120),
('armor_head_l6','Steel Helm','armor','Standard steel helm.',156),
('armor_head_l7','Visored Helm','armor','Face protection added.',198),
('armor_head_l8','Masterwork Helm','armor','Optimized weight distribution.',246),
('armor_head_l9','Runed Helm','armor','Subtle warding glyphs.',300),
('armor_head_l10','Mythril Helm','armor','Light, resilient alloy.',360),
('armor_head_l11','Adamant Helm','armor','Heavy adamant shell.',426),
('armor_head_l12','Adamantine Helm','armor','Near unbreakable dome.',498),
('armor_head_l13','Celestial Helm','armor','Halo-like rim.',576),
('armor_head_l14','Eclipse Helm','armor','Shadow-lined interior.',660),
('armor_head_l15','Dragonbone Helm','armor','Bone ridge crest.',750),
('armor_head_l16','Runebound Helm','armor','Runic cage reinforcement.',846),
('armor_head_l17','Voidforged Helm','armor','Absorbs glare.',948),
('armor_head_l18','Starshard Helm','armor','Embedded star fragment.',1056),
('armor_head_l19','Empyreal Helm','armor','Radiant sigils.',1170),
('armor_head_l20','Transcendent Helm','armor','Reality-thin barrier.',1290);

-- CHEST
DELETE FROM item WHERE slug LIKE 'armor_chest_l%';
INSERT INTO item (slug, name, type, description, value_copper) VALUES
('armor_chest_l1','Cloth Tunic','armor','Simple woven tunic.',30),
('armor_chest_l2','Padded Jerkin','armor','Layered cloth padding.',50),
('armor_chest_l3','Leather Jerkin','armor','Flexible leather torso.',78),
('armor_chest_l4','Studded Leather','armor','Riveted studs for defense.',112),
('armor_chest_l5','Iron Cuirass','armor','Metal breastplate.',152),
('armor_chest_l6','Steel Cuirass','armor','Standard plate body.',198),
('armor_chest_l7','Riveted Cuirass','armor','Extra reinforcement seams.',250),
('armor_chest_l8','Masterwork Cuirass','armor','Refined balancing.',308),
('armor_chest_l9','Runed Cuirass','armor','Glyph lattice inside.',372),
('armor_chest_l10','Mythril Cuirass','armor','Exceptional weight savings.',442),
('armor_chest_l11','Adamant Cuirass','armor','Heavy protection.',518),
('armor_chest_l12','Adamantine Cuirass','armor','Superior hardness.',600),
('armor_chest_l13','Celestial Cuirass','armor','Radiant plating.',688),
('armor_chest_l14','Eclipse Cuirass','armor','Inner shadow weave.',782),
('armor_chest_l15','Dragonbone Cuirass','armor','Bone plate segments.',882),
('armor_chest_l16','Runebound Cuirass','armor','Interlocked rune mesh.',988),
('armor_chest_l17','Voidforged Cuirass','armor','Dark mirror surface.',1100),
('armor_chest_l18','Starshard Cuirass','armor','Starmetal inlays.',1218),
('armor_chest_l19','Empyreal Cuirass','armor','Emits faint warmth.',1342),
('armor_chest_l20','Transcendent Cuirass','armor','Near intangible plating.',1472);

-- LEGS
DELETE FROM item WHERE slug LIKE 'armor_legs_l%';
INSERT INTO item (slug, name, type, description, value_copper) VALUES
('armor_legs_l1','Cloth Pants','armor','Simple woven pants.',22),
('armor_legs_l2','Padded Pants','armor','Layered cloth padding.',38),
('armor_legs_l3','Leather Greaves','armor','Basic leather legs.',60),
('armor_legs_l4','Reinforced Greaves','armor','Studded leather legs.',86),
('armor_legs_l5','Iron Greaves','armor','Metal lower leg guards.',118),
('armor_legs_l6','Steel Greaves','armor','Standard plate legs.',154),
('armor_legs_l7','Riveted Greaves','armor','Reinforced joints.',196),
('armor_legs_l8','Masterwork Greaves','armor','Weight-optimized.',244),
('armor_legs_l9','Runed Greaves','armor','Subtle ward glyphs.',298),
('armor_legs_l10','Mythril Greaves','armor','Light, durable.',358),
('armor_legs_l11','Adamant Greaves','armor','Heavy resilience.',424),
('armor_legs_l12','Adamantine Greaves','armor','Supreme hardness.',496),
('armor_legs_l13','Celestial Greaves','armor','Radiant sheen.',574),
('armor_legs_l14','Eclipse Greaves','armor','Shadow muffle.',658),
('armor_legs_l15','Dragonbone Greaves','armor','Bone plate arcs.',748),
('armor_legs_l16','Runebound Greaves','armor','Rune mesh joints.',844),
('armor_legs_l17','Voidforged Greaves','armor','Dark reflective.',946),
('armor_legs_l18','Starshard Greaves','armor','Inlaid star pieces.',1054),
('armor_legs_l19','Empyreal Greaves','armor','Faint aura.',1168),
('armor_legs_l20','Transcendent Greaves','armor','Half-ethereal.',1288);

-- HANDS
DELETE FROM item WHERE slug LIKE 'armor_hands_l%';
INSERT INTO item (slug, name, type, description, value_copper) VALUES
('armor_hands_l1','Cloth Gloves','armor','Simple gloves.',14),
('armor_hands_l2','Padded Gloves','armor','Lightly cushioned.',24),
('armor_hands_l3','Leather Gloves','armor','Basic handguards.',36),
('armor_hands_l4','Reinforced Gloves','armor','Studded knuckles.',50),
('armor_hands_l5','Iron Gauntlets','armor','Metal hand armor.',68),
('armor_hands_l6','Steel Gauntlets','armor','Standard plate hands.',90),
('armor_hands_l7','Riveted Gauntlets','armor','Joint reinforcement.',114),
('armor_hands_l8','Masterwork Gauntlets','armor','Ergonomic shaping.',142),
('armor_hands_l9','Runed Gauntlets','armor','Warding glyphs inside.',174),
('armor_hands_l10','Mythril Gauntlets','armor','Light protective.',210),
('armor_hands_l11','Adamant Gauntlets','armor','Heavy resilience.',250),
('armor_hands_l12','Adamantine Gauntlets','armor','Superior hardness.',294),
('armor_hands_l13','Celestial Gauntlets','armor','Soft glow.',342),
('armor_hands_l14','Eclipse Gauntlets','armor','Shadow lining.',394),
('armor_hands_l15','Dragonbone Gauntlets','armor','Bone plating.',450),
('armor_hands_l16','Runebound Gauntlets','armor','Runic mesh.',510),
('armor_hands_l17','Voidforged Gauntlets','armor','Matte dark.',574),
('armor_hands_l18','Starshard Gauntlets','armor','Star flecks.',642),
('armor_hands_l19','Empyreal Gauntlets','armor','Halo traces.',714),
('armor_hands_l20','Transcendent Gauntlets','armor','Phase-shift feel.',790);

-- FEET
DELETE FROM item WHERE slug LIKE 'armor_feet_l%';
INSERT INTO item (slug, name, type, description, value_copper) VALUES
('armor_feet_l1','Cloth Shoes','armor','Soft cloth footwear.',16),
('armor_feet_l2','Padded Boots','armor','Light padding.',28),
('armor_feet_l3','Leather Boots','armor','Basic leather boots.',42),
('armor_feet_l4','Reinforced Boots','armor','Studded ankle guards.',60),
('armor_feet_l5','Iron Sabatons','armor','Metal foot guards.',82),
('armor_feet_l6','Steel Sabatons','armor','Standard plate feet.',108),
('armor_feet_l7','Riveted Sabatons','armor','Joint reinforcement.',138),
('armor_feet_l8','Masterwork Sabatons','armor','Weight-balanced.',172),
('armor_feet_l9','Runed Sabatons','armor','Warding glyphs.',210),
('armor_feet_l10','Mythril Sabatons','armor','Light resilient.',252),
('armor_feet_l11','Adamant Sabatons','armor','Heavy plating.',298),
('armor_feet_l12','Adamantine Sabatons','armor','Superior hardness.',348),
('armor_feet_l13','Celestial Sabatons','armor','Radiant glow.',402),
('armor_feet_l14','Eclipse Sabatons','armor','Shadow muffling.',460),
('armor_feet_l15','Dragonbone Sabatons','armor','Bone arches.',522),
('armor_feet_l16','Runebound Sabatons','armor','Rune mesh arcs.',588),
('armor_feet_l17','Voidforged Sabatons','armor','Dim sheen.',658),
('armor_feet_l18','Starshard Sabatons','armor','Star motes.',732),
('armor_feet_l19','Empyreal Sabatons','armor','Faint aura.',810),
('armor_feet_l20','Transcendent Sabatons','armor','Ethereal step.',892);

-- BELT
DELETE FROM item WHERE slug LIKE 'armor_belt_l%';
INSERT INTO item (slug, name, type, description, value_copper) VALUES
('armor_belt_l1','Simple Belt','armor','Plain leather.',10),
('armor_belt_l2','Stitched Belt','armor','Extra stitching.',18),
('armor_belt_l3','Reinforced Belt','armor','Metal buckle plates.',28),
('armor_belt_l4','Studded Belt','armor','Defense studs.',40),
('armor_belt_l5','Ironclasp Belt','armor','Iron clasp core.',54),
('armor_belt_l6','Steelclasp Belt','armor','Steel reinforced.',70),
('armor_belt_l7','Runed Belt','armor','Minor glyphs.',88),
('armor_belt_l8','Masterwork Belt','armor','Optimized support.',108),
('armor_belt_l9','Mythrilclasp Belt','armor','Light metal clasp.',130),
('armor_belt_l10','Adamant Belt','armor','Adamant buckle.',154),
('armor_belt_l11','Adamantine Belt','armor','Exceptional hardness.',180),
('armor_belt_l12','Celestial Belt','armor','Luminous trim.',208),
('armor_belt_l13','Eclipse Belt','armor','Shadow-lined.',238),
('armor_belt_l14','Dragonbone Belt','armor','Bone segments.',270),
('armor_belt_l15','Runebound Belt','armor','Runic filaments.',304),
('armor_belt_l16','Voidforged Belt','armor','Absorbs glare.',340),
('armor_belt_l17','Starshard Belt','armor','Star flecks.',378),
('armor_belt_l18','Empyreal Belt','armor','Radiant trace.',418),
('armor_belt_l19','Transcendent Belt','armor','Phasing weave.',460),
('armor_belt_l20','Paragon Belt','armor','Perfect balance.',504);

-- CLOAK
DELETE FROM item WHERE slug LIKE 'armor_cloak_l%';
INSERT INTO item (slug, name, type, description, value_copper) VALUES
('armor_cloak_l1','Worn Cloak','armor','Frayed at edges.',14),
('armor_cloak_l2','Travel Cloak','armor','Weather resistant.',24),
('armor_cloak_l3','Lined Cloak','armor','Insulated lining.',36),
('armor_cloak_l4','Reinforced Cloak','armor','Leather patched.',50),
('armor_cloak_l5','Ward Cloak','armor','Minor protective charm.',68),
('armor_cloak_l6','Runed Cloak','armor','Glyph-lined hem.',90),
('armor_cloak_l7','Masterwork Cloak','armor','Optimized drape.',114),
('armor_cloak_l8','Mythrilthread Cloak','armor','Filaments woven in.',142),
('armor_cloak_l9','Adamantthread Cloak','armor','Resist tearing.',174),
('armor_cloak_l10','Celestial Cloak','armor','Faint soft glow.',210),
('armor_cloak_l11','Eclipse Cloak','armor','Shadows cling.',250),
('armor_cloak_l12','Dragonbone Weave Cloak','armor','Bone filament traces.',294),
('armor_cloak_l13','Runebound Cloak','armor','Runic mesh aura.',342),
('armor_cloak_l14','Voidshroud Cloak','armor','Light-dampening.',394),
('armor_cloak_l15','Starshard Cloak','armor','Star motes sewn.',450),
('armor_cloak_l16','Empyreal Cloak','armor','Radiant aura.',510),
('armor_cloak_l17','Transcendent Cloak','armor','Shifting fabric.',574),
('armor_cloak_l18','Paragon Cloak','armor','Peak craftsmanship.',642),
('armor_cloak_l19','Mythic Cloak','armor','Legendary weave.',714),
('armor_cloak_l20','Ascendant Cloak','armor','Near intangible.',790);

-- SHIELD
DELETE FROM item WHERE slug LIKE 'armor_shield_l%';
INSERT INTO item (slug, name, type, description, value_copper) VALUES
('armor_shield_l1','Wooden Buckler','armor','Small wood shield.',26),
('armor_shield_l2','Reinforced Buckler','armor','Metal rim added.',44),
('armor_shield_l3','Iron Shield','armor','Basic iron shield.',68),
('armor_shield_l4','Steel Shield','armor','Standard defense.',96),
('armor_shield_l5','Kite Shield','armor','Elongated coverage.',130),
('armor_shield_l6','Tower Shield','armor','Large frontal wall.',170),
('armor_shield_l7','Runed Shield','armor','Protective glyphs.',216),
('armor_shield_l8','Masterwork Shield','armor','Optimized weight.',268),
('armor_shield_l9','Mythril Shield','armor','Light superior metal.',326),
('armor_shield_l10','Adamant Shield','armor','Heavy resilient.',390),
('armor_shield_l11','Adamantine Shield','armor','Near unbreakable.',460),
('armor_shield_l12','Celestial Shield','armor','Radiant pulses.',536),
('armor_shield_l13','Eclipse Shield','armor','Shadow film.',618),
('armor_shield_l14','Dragonbone Shield','armor','Bone core plating.',706),
('armor_shield_l15','Runebound Shield','armor','Runic lattice.',800),
('armor_shield_l16','Voidforged Shield','armor','Light-absorbing.',900),
('armor_shield_l17','Starshard Shield','armor','Star inlays.',1006),
('armor_shield_l18','Empyreal Shield','armor','Holy resonance.',1118),
('armor_shield_l19','Transcendent Shield','armor','Phase barrier.',1236),
('armor_shield_l20','Paragon Shield','armor','Ultimate guardian.',1360);

-- RINGS
DELETE FROM item WHERE slug LIKE 'accessory_ring_l%';
INSERT INTO item (slug, name, type, description, value_copper) VALUES
('accessory_ring_l1','Copper Ring','armor','Simple copper band.',18),
('accessory_ring_l2','Bronze Ring','armor','Sturdy bronze band.',30),
('accessory_ring_l3','Silver Ring','armor','Polished silver.',46),
('accessory_ring_l4','Garnet Ring','armor','Garnet-set band.',66),
('accessory_ring_l5','Runed Ring','armor','Minor glyph engraving.',90),
('accessory_ring_l6','Mythril Ring','armor','Light alloy.',118),
('accessory_ring_l7','Adamant Ring','armor','Hard metal band.',150),
('accessory_ring_l8','Adamantine Ring','armor','Superior hardness.',186),
('accessory_ring_l9','Celestial Ring','armor','Soft aura.',226),
('accessory_ring_l10','Eclipse Ring','armor','Shadow trace.',270),
('accessory_ring_l11','Dragonbone Ring','armor','Bone carved.',318),
('accessory_ring_l12','Runebound Ring','armor','Runic micro lattice.',370),
('accessory_ring_l13','Voidforged Ring','armor','Light absorbing.',426),
('accessory_ring_l14','Starshard Ring','armor','Tiny star fragment.',486),
('accessory_ring_l15','Empyreal Ring','armor','Glows faintly.',550),
('accessory_ring_l16','Transcendent Ring','armor','Reality-thin band.',618),
('accessory_ring_l17','Paragon Ring','armor','Peak purity.',690),
('accessory_ring_l18','Mythic Ring','armor','Legend tier.',766),
('accessory_ring_l19','Ascendant Ring','armor','Ascendant aura.',846),
('accessory_ring_l20','Eternal Ring','armor','Timeless artifact.',930);

-- AMULETS
DELETE FROM item WHERE slug LIKE 'accessory_amulet_l%';
INSERT INTO item (slug, name, type, description, value_copper) VALUES
('accessory_amulet_l1','Bone Pendant','armor','Carved bone charm.',20),
('accessory_amulet_l2','Copper Pendant','armor','Copper disk.',34),
('accessory_amulet_l3','Silver Pendant','armor','Silver medallion.',52),
('accessory_amulet_l4','Garnet Amulet','armor','Garnet gem focus.',74),
('accessory_amulet_l5','Runed Amulet','armor','Glyph etched.',100),
('accessory_amulet_l6','Mythril Amulet','armor','Light alloy focus.',130),
('accessory_amulet_l7','Adamant Amulet','armor','Hard protective core.',164),
('accessory_amulet_l8','Adamantine Amulet','armor','Superior hardness.',202),
('accessory_amulet_l9','Celestial Amulet','armor','Radiant pulse.',244),
('accessory_amulet_l10','Eclipse Amulet','armor','Shadow veil.',290),
('accessory_amulet_l11','Dragonbone Amulet','armor','Bone rune matrix.',340),
('accessory_amulet_l12','Runebound Amulet','armor','Dense rune mesh.',394),
('accessory_amulet_l13','Voidforged Amulet','armor','Absorbs stray energy.',452),
('accessory_amulet_l14','Starshard Amulet','armor','Star fragment.',514),
('accessory_amulet_l15','Empyreal Amulet','armor','Divine resonance.',580),
('accessory_amulet_l16','Transcendent Amulet','armor','Phase-shifted focus.',650),
('accessory_amulet_l17','Paragon Amulet','armor','Peak purity.',724),
('accessory_amulet_l18','Mythic Amulet','armor','Legend tier focus.',802),
('accessory_amulet_l19','Ascendant Amulet','armor','Ascendant aura.',884),
('accessory_amulet_l20','Eternal Amulet','armor','Timeless artifact.',970);

COMMIT;
