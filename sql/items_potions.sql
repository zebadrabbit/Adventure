-- Potions & Consumables (Levels 1-20)
-- Types kept as 'potion' for schema simplicity; could be split later.
-- Healing / Mana / Buff / Utility tiers scale roughly quadratically with level for value.
BEGIN TRANSACTION;

DELETE FROM item WHERE slug LIKE 'potion_heal_l%';
INSERT INTO item (slug, name, type, description, value_copper, level, rarity, weight) VALUES
('potion_heal_l1','Minor Healing Potion','potion','Restores a small amount of health.',18, 1, 'common', 1.0),
('potion_heal_l2','Lesser Healing Potion','potion','Restores modest health.',28, 2, 'common', 1.0),
('potion_heal_l3','Standard Healing Potion','potion','Restores a fair amount of health.',40, 3, 'common', 1.0),
('potion_heal_l4','Improved Healing Potion','potion','Restores significant health.',56, 4, 'common', 1.0),
('potion_heal_l5','Greater Healing Potion','potion','Restores large health.',76, 5, 'uncommon', 1.0),
('potion_heal_l6','Superior Healing Potion','potion','Restores very large health.',100, 6, 'uncommon', 1.0),
('potion_heal_l7','Major Healing Potion','potion','Major health restoration.',128, 7, 'uncommon', 1.0),
('potion_heal_l8','Potent Healing Potion','potion','High potency recovery.',160, 8, 'uncommon', 1.0),
('potion_heal_l9','Grand Healing Potion','potion','Grand restorative.',196, 9, 'uncommon', 1.0),
('potion_heal_l10','Mighty Healing Potion','potion','Mighty restorative.',236, 10, 'rare', 1.0),
('potion_heal_l11','Royal Healing Elixir','potion','Royal grade healing.',280, 11, 'rare', 1.0),
('potion_heal_l12','Sacred Healing Elixir','potion','Sacred infused healing.',328, 12, 'rare', 1.0),
('potion_heal_l13','Mythic Healing Elixir','potion','Mythic scale healing.',380, 13, 'rare', 1.0),
('potion_heal_l14','Empyreal Healing Elixir','potion','Empyreal potent healing.',436, 14, 'rare', 1.0),
('potion_heal_l15','Transcendent Healing Elixir','potion','Transcendent restoration.',496, 15, 'epic', 1.0),
('potion_heal_l16','Paragon Healing Elixir','potion','Peak tier restoration.',560, 16, 'epic', 1.0),
('potion_heal_l17','Ascendant Healing Elixir','potion','Ascendant vitality.',628, 17, 'epic', 1.0),
('potion_heal_l18','Eternal Healing Elixir','potion','Enduring supreme healing.',700, 18, 'epic', 1.0),
('potion_heal_l19','Legendary Healing Elixir','potion','Legend-tier restoration.',776, 19, 'legendary', 1.0),
('potion_heal_l20','Ultimate Healing Elixir','potion','Maximum possible restoration.',856, 20, 'legendary', 1.0);

DELETE FROM item WHERE slug LIKE 'potion_mana_l%';
INSERT INTO item (slug, name, type, description, value_copper, level, rarity, weight) VALUES
('potion_mana_l1','Minor Mana Potion','potion','Restores a small amount of mana.',18, 1, 'common', 1.0),
('potion_mana_l2','Lesser Mana Potion','potion','Restores modest mana.',28, 2, 'common', 1.0),
('potion_mana_l3','Standard Mana Potion','potion','Restores a fair amount of mana.',40, 3, 'common', 1.0),
('potion_mana_l4','Improved Mana Potion','potion','Restores significant mana.',56, 4, 'common', 1.0),
('potion_mana_l5','Greater Mana Potion','potion','Restores large mana.',76, 5, 'uncommon', 1.0),
('potion_mana_l6','Superior Mana Potion','potion','Restores very large mana.',100, 6, 'uncommon', 1.0),
('potion_mana_l7','Major Mana Potion','potion','Major mana restoration.',128, 7, 'uncommon', 1.0),
('potion_mana_l8','Potent Mana Potion','potion','High potency mana.',160, 8, 'uncommon', 1.0),
('potion_mana_l9','Grand Mana Potion','potion','Grand mana restorative.',196, 9, 'uncommon', 1.0),
('potion_mana_l10','Mighty Mana Potion','potion','Mighty mana restorative.',236, 10, 'rare', 1.0),
('potion_mana_l11','Royal Mana Elixir','potion','Royal grade mana.',280, 11, 'rare', 1.0),
('potion_mana_l12','Sacred Mana Elixir','potion','Sacred infused mana.',328, 12, 'rare', 1.0),
('potion_mana_l13','Mythic Mana Elixir','potion','Mythic scale mana.',380, 13, 'rare', 1.0),
('potion_mana_l14','Empyreal Mana Elixir','potion','Empyreal potent mana.',436, 14, 'rare', 1.0),
('potion_mana_l15','Transcendent Mana Elixir','potion','Transcendent mana.',496, 15, 'epic', 1.0),
('potion_mana_l16','Paragon Mana Elixir','potion','Peak tier mana.',560, 16, 'epic', 1.0),
('potion_mana_l17','Ascendant Mana Elixir','potion','Ascendant mana.',628, 17, 'epic', 1.0),
('potion_mana_l18','Eternal Mana Elixir','potion','Enduring supreme mana.',700, 18, 'epic', 1.0),
('potion_mana_l19','Legendary Mana Elixir','potion','Legend-tier mana.',776, 19, 'legendary', 1.0),
('potion_mana_l20','Ultimate Mana Elixir','potion','Maximum possible mana.',856, 20, 'legendary', 1.0);

-- Buff Potions (Attack, Defense, Speed) cycles; value set slightly above raw heal equivalent due to strategic utility.
DELETE FROM item WHERE slug LIKE 'potion_buff_attack_l%';
INSERT INTO item (slug, name, type, description, value_copper, level, rarity, weight) VALUES
('potion_buff_attack_l1','Minor Attack Draught','potion','Slightly increases attack briefly.',22, 1, 'common', 1.0),
('potion_buff_attack_l2','Lesser Attack Draught','potion','Modest attack increase.',34, 2, 'common', 1.0),
('potion_buff_attack_l3','Standard Attack Draught','potion','Fair attack increase.',48, 3, 'common', 1.0),
('potion_buff_attack_l4','Improved Attack Draught','potion','Notable attack increase.',64, 4, 'common', 1.0),
('potion_buff_attack_l5','Greater Attack Draught','potion','Large attack increase.',84, 5, 'uncommon', 1.0),
('potion_buff_attack_l6','Superior Attack Draught','potion','Very large attack increase.',108, 6, 'uncommon', 1.0),
('potion_buff_attack_l7','Major Attack Draught','potion','Major attack surge.',136, 7, 'uncommon', 1.0),
('potion_buff_attack_l8','Potent Attack Draught','potion','High potency attack boost.',168, 8, 'uncommon', 1.0),
('potion_buff_attack_l9','Grand Attack Elixir','potion','Grand attack empowerment.',204, 9, 'uncommon', 1.0),
('potion_buff_attack_l10','Mighty Attack Elixir','potion','Mighty attack empowerment.',244, 10, 'rare', 1.0),
('potion_buff_attack_l11','Royal Attack Elixir','potion','Royal-grade attack boost.',288, 11, 'rare', 1.0),
('potion_buff_attack_l12','Sacred Attack Elixir','potion','Sacred attack infusion.',336, 12, 'rare', 1.0),
('potion_buff_attack_l13','Mythic Attack Elixir','potion','Mythic attack power.',388, 13, 'rare', 1.0),
('potion_buff_attack_l14','Empyreal Attack Elixir','potion','Empyreal attack resonance.',444, 14, 'rare', 1.0),
('potion_buff_attack_l15','Transcendent Attack Elixir','potion','Transcendent attack force.',504, 15, 'epic', 1.0),
('potion_buff_attack_l16','Paragon Attack Elixir','potion','Peak attack empowerment.',568, 16, 'epic', 1.0),
('potion_buff_attack_l17','Ascendant Attack Elixir','potion','Ascendant attack zeal.',636, 17, 'epic', 1.0),
('potion_buff_attack_l18','Eternal Attack Elixir','potion','Enduring attack power.',708, 18, 'epic', 1.0),
('potion_buff_attack_l19','Legendary Attack Elixir','potion','Legend-tier attack force.',784, 19, 'legendary', 1.0),
('potion_buff_attack_l20','Ultimate Attack Elixir','potion','Maximum attack surge.',864, 20, 'legendary', 1.0);

DELETE FROM item WHERE slug LIKE 'potion_buff_defense_l%';
INSERT INTO item (slug, name, type, description, value_copper, level, rarity, weight) VALUES
('potion_buff_defense_l1','Minor Defense Draught','potion','Slightly increases defense briefly.',22, 1, 'common', 1.0),
('potion_buff_defense_l2','Lesser Defense Draught','potion','Modest defense increase.',34, 2, 'common', 1.0),
('potion_buff_defense_l3','Standard Defense Draught','potion','Fair defense increase.',48, 3, 'common', 1.0),
('potion_buff_defense_l4','Improved Defense Draught','potion','Notable defense increase.',64, 4, 'common', 1.0),
('potion_buff_defense_l5','Greater Defense Draught','potion','Large defense increase.',84, 5, 'uncommon', 1.0),
('potion_buff_defense_l6','Superior Defense Draught','potion','Very large defense increase.',108, 6, 'uncommon', 1.0),
('potion_buff_defense_l7','Major Defense Draught','potion','Major defense surge.',136, 7, 'uncommon', 1.0),
('potion_buff_defense_l8','Potent Defense Draught','potion','High potency defense boost.',168, 8, 'uncommon', 1.0),
('potion_buff_defense_l9','Grand Defense Elixir','potion','Grand defense empowerment.',204, 9, 'uncommon', 1.0),
('potion_buff_defense_l10','Mighty Defense Elixir','potion','Mighty defense empowerment.',244, 10, 'rare', 1.0),
('potion_buff_defense_l11','Royal Defense Elixir','potion','Royal-grade defense boost.',288, 11, 'rare', 1.0),
('potion_buff_defense_l12','Sacred Defense Elixir','potion','Sacred defense infusion.',336, 12, 'rare', 1.0),
('potion_buff_defense_l13','Mythic Defense Elixir','potion','Mythic defense power.',388, 13, 'rare', 1.0),
('potion_buff_defense_l14','Empyreal Defense Elixir','potion','Empyreal defense resonance.',444, 14, 'rare', 1.0),
('potion_buff_defense_l15','Transcendent Defense Elixir','potion','Transcendent defense force.',504, 15, 'epic', 1.0),
('potion_buff_defense_l16','Paragon Defense Elixir','potion','Peak defense empowerment.',568, 16, 'epic', 1.0),
('potion_buff_defense_l17','Ascendant Defense Elixir','potion','Ascendant defensive zeal.',636, 17, 'epic', 1.0),
('potion_buff_defense_l18','Eternal Defense Elixir','potion','Enduring defense power.',708, 18, 'epic', 1.0),
('potion_buff_defense_l19','Legendary Defense Elixir','potion','Legend-tier defense force.',784, 19, 'legendary', 1.0),
('potion_buff_defense_l20','Ultimate Defense Elixir','potion','Maximum defense surge.',864, 20, 'legendary', 1.0);

DELETE FROM item WHERE slug LIKE 'potion_buff_speed_l%';
INSERT INTO item (slug, name, type, description, value_copper, level, rarity, weight) VALUES
('potion_buff_speed_l1','Minor Swiftness Draught','potion','Slightly increases speed briefly.',22, 1, 'common', 1.0),
('potion_buff_speed_l2','Lesser Swiftness Draught','potion','Modest speed increase.',34, 2, 'common', 1.0),
('potion_buff_speed_l3','Standard Swiftness Draught','potion','Fair speed increase.',48, 3, 'common', 1.0),
('potion_buff_speed_l4','Improved Swiftness Draught','potion','Notable speed increase.',64, 4, 'common', 1.0),
('potion_buff_speed_l5','Greater Swiftness Draught','potion','Large speed increase.',84, 5, 'uncommon', 1.0),
('potion_buff_speed_l6','Superior Swiftness Draught','potion','Very large speed increase.',108, 6, 'uncommon', 1.0),
('potion_buff_speed_l7','Major Swiftness Draught','potion','Major speed surge.',136, 7, 'uncommon', 1.0),
('potion_buff_speed_l8','Potent Swiftness Draught','potion','High potency speed boost.',168, 8, 'uncommon', 1.0),
('potion_buff_speed_l9','Grand Swiftness Elixir','potion','Grand speed empowerment.',204, 9, 'uncommon', 1.0),
('potion_buff_speed_l10','Mighty Swiftness Elixir','potion','Mighty speed empowerment.',244, 10, 'rare', 1.0),
('potion_buff_speed_l11','Royal Swiftness Elixir','potion','Royal-grade speed boost.',288, 11, 'rare', 1.0),
('potion_buff_speed_l12','Sacred Swiftness Elixir','potion','Sacred speed infusion.',336, 12, 'rare', 1.0),
('potion_buff_speed_l13','Mythic Swiftness Elixir','potion','Mythic speed power.',388, 13, 'rare', 1.0),
('potion_buff_speed_l14','Empyreal Swiftness Elixir','potion','Empyreal speed resonance.',444, 14, 'rare', 1.0),
('potion_buff_speed_l15','Transcendent Swiftness Elixir','potion','Transcendent speed force.',504, 15, 'epic', 1.0),
('potion_buff_speed_l16','Paragon Swiftness Elixir','potion','Peak speed empowerment.',568, 16, 'epic', 1.0),
('potion_buff_speed_l17','Ascendant Swiftness Elixir','potion','Ascendant velocity zeal.',636, 17, 'epic', 1.0),
('potion_buff_speed_l18','Eternal Swiftness Elixir','potion','Enduring speed power.',708, 18, 'epic', 1.0),
('potion_buff_speed_l19','Legendary Swiftness Elixir','potion','Legend-tier speed force.',784, 19, 'legendary', 1.0),
('potion_buff_speed_l20','Ultimate Swiftness Elixir','potion','Maximum speed surge.',864, 20, 'legendary', 1.0);

-- Utility / Resistance
DELETE FROM item WHERE slug LIKE 'potion_antidote_l%';
INSERT INTO item (slug, name, type, description, value_copper, level, rarity, weight) VALUES
('potion_antidote_l1','Minor Antidote','potion','Cures minor poisons.',26, 1, 'common', 1.0),
('potion_antidote_l5','Greater Antidote','potion','Cures potent poisons.',86, 5, 'uncommon', 1.0),
('potion_antidote_l10','Superior Antidote','potion','Cures virulent poisons.',236, 10, 'rare', 1.0),
('potion_antidote_l15','Transcendent Antidote','potion','Purges nearly all toxins.',504, 15, 'epic', 1.0),
('potion_antidote_l20','Ultimate Antidote','potion','Universal toxin purge.',856, 20, 'legendary', 1.0);

DELETE FROM item WHERE slug LIKE 'potion_resist_fire_l%';
INSERT INTO item (slug, name, type, description, value_copper, level, rarity, weight) VALUES
('potion_resist_fire_l1','Minor Fire Resist Potion','potion','Slightly reduces fire damage.',30, 1, 'common', 1.0),
('potion_resist_fire_l5','Greater Fire Resist Potion','potion','Large fire resistance.',96, 5, 'uncommon', 1.0),
('potion_resist_fire_l10','Superior Fire Resist Potion','potion','High fire resistance.',270, 10, 'rare', 1.0),
('potion_resist_fire_l15','Transcendent Fire Resist Potion','potion','Near-immune to fire.',580, 15, 'epic', 1.0),
('potion_resist_fire_l20','Ultimate Fire Resist Potion','potion','Brief fire immunity.',990, 20, 'legendary', 1.0);

COMMIT;

-- Expansion: Additional Potion Categories
BEGIN TRANSACTION;

-- STAMINA / ENERGY (parallel to heal/mana pricing)
DELETE FROM item WHERE slug LIKE 'potion_stamina_l%';
INSERT INTO item (slug, name, type, description, value_copper, level, rarity, weight) VALUES
('potion_stamina_l1','Minor Stamina Potion','potion','Restores a small amount of stamina.',18, 1, 'common', 1.0),
('potion_stamina_l5','Greater Stamina Potion','potion','Restores large stamina.',76, 5, 'uncommon', 1.0),
('potion_stamina_l10','Mighty Stamina Potion','potion','Mighty stamina restorative.',236, 10, 'rare', 1.0),
('potion_stamina_l15','Transcendent Stamina Elixir','potion','Transcendent stamina regeneration.',496, 15, 'epic', 1.0),
('potion_stamina_l20','Ultimate Stamina Elixir','potion','Maximum stamina restoration.',856, 20, 'legendary', 1.0);

-- INVISIBILITY (rarer, higher premium value tiers)
DELETE FROM item WHERE slug LIKE 'potion_invis_l%';
INSERT INTO item (slug, name, type, description, value_copper, level, rarity, weight) VALUES
('potion_invis_l5','Lesser Invisibility Potion','potion','Short partial invisibility.',180, 5, 'uncommon', 1.0),
('potion_invis_l10','Invisibility Potion','potion','Full temporary invisibility.',420, 10, 'rare', 1.0),
('potion_invis_l15','Greater Invisibility Potion','potion','Extended invisibility duration.',880, 15, 'epic', 1.0),
('potion_invis_l20','Ultimate Invisibility Elixir','potion','Near-perfect invisibility.',1600, 20, 'legendary', 1.0);

-- REGENERATION (continuous heal effect)
DELETE FROM item WHERE slug LIKE 'potion_regen_l%';
INSERT INTO item (slug, name, type, description, value_copper, level, rarity, weight) VALUES
('potion_regen_l5','Lesser Regeneration Potion','potion','Gradually restores health.',190, 5, 'uncommon', 1.0),
('potion_regen_l10','Regeneration Potion','potion','Moderate regeneration effect.',440, 10, 'rare', 1.0),
('potion_regen_l15','Greater Regeneration Potion','potion','Strong regeneration.',920, 15, 'epic', 1.0),
('potion_regen_l20','Ultimate Regeneration Elixir','potion','Maximum regeneration potency.',1680, 20, 'legendary', 1.0);

-- PERCEPTION (improved detection, vision)
DELETE FROM item WHERE slug LIKE 'potion_perception_l%';
INSERT INTO item (slug, name, type, description, value_copper, level, rarity, weight) VALUES
('potion_perception_l1','Minor Perception Draught','potion','Slightly heightens senses.',24, 1, 'common', 1.0),
('potion_perception_l5','Greater Perception Draught','potion','Large perception boost.',90, 5, 'uncommon', 1.0),
('potion_perception_l10','Superior Perception Elixir','potion','High sensory enhancement.',210, 10, 'rare', 1.0),
('potion_perception_l15','Transcendent Perception Elixir','potion','Near-omniscient awareness.',500, 15, 'epic', 1.0),
('potion_perception_l20','Ultimate Perception Elixir','potion','Peak sensory clarity.',900, 20, 'legendary', 1.0);

-- LUCK (affects loot RNG - conceptual)
DELETE FROM item WHERE slug LIKE 'potion_luck_l%';
INSERT INTO item (slug, name, type, description, value_copper, level, rarity, weight) VALUES
('potion_luck_l5','Lesser Fortune Draught','potion','Slightly increases fortune.',200, 5, 'uncommon', 1.0),
('potion_luck_l10','Fortune Elixir','potion','Improves luck noticeably.',460, 10, 'rare', 1.0),
('potion_luck_l15','Greater Fortune Elixir','potion','Large fortune increase.',940, 15, 'epic', 1.0),
('potion_luck_l20','Transcendent Fortune Elixir','potion','Peak fortune boost.',1700, 20, 'legendary', 1.0);

-- ELEMENTAL RESISTS (cold, lightning, poison) mirroring fire pattern
DELETE FROM item WHERE slug LIKE 'potion_resist_cold_l%';
INSERT INTO item (slug, name, type, description, value_copper, level, rarity, weight) VALUES
('potion_resist_cold_l1','Minor Cold Resist Potion','potion','Slightly reduces cold damage.',30, 1, 'common', 1.0),
('potion_resist_cold_l5','Greater Cold Resist Potion','potion','Large cold resistance.',96, 5, 'uncommon', 1.0),
('potion_resist_cold_l10','Superior Cold Resist Potion','potion','High cold resistance.',270, 10, 'rare', 1.0),
('potion_resist_cold_l15','Transcendent Cold Resist Potion','potion','Near-immune to cold.',580, 15, 'epic', 1.0),
('potion_resist_cold_l20','Ultimate Cold Resist Potion','potion','Brief cold immunity.',990, 20, 'legendary', 1.0);

DELETE FROM item WHERE slug LIKE 'potion_resist_lightning_l%';
INSERT INTO item (slug, name, type, description, value_copper, level, rarity, weight) VALUES
('potion_resist_lightning_l1','Minor Lightning Resist Potion','potion','Slightly reduces lightning damage.',34, 1, 'common', 1.0),
('potion_resist_lightning_l5','Greater Lightning Resist Potion','potion','Large lightning resistance.',104, 5, 'uncommon', 1.0),
('potion_resist_lightning_l10','Superior Lightning Resist Potion','potion','High lightning resistance.',288, 10, 'rare', 1.0),
('potion_resist_lightning_l15','Transcendent Lightning Resist Potion','potion','Near-immune to lightning.',600, 15, 'epic', 1.0),
('potion_resist_lightning_l20','Ultimate Lightning Resist Potion','potion','Brief lightning immunity.',1020, 20, 'legendary', 1.0);

DELETE FROM item WHERE slug LIKE 'potion_resist_poison_l%';
INSERT INTO item (slug, name, type, description, value_copper, level, rarity, weight) VALUES
('potion_resist_poison_l1','Minor Poison Resist Potion','potion','Slightly reduces poison damage.',28, 1, 'common', 1.0),
('potion_resist_poison_l5','Greater Poison Resist Potion','potion','Large poison resistance.',90, 5, 'uncommon', 1.0),
('potion_resist_poison_l10','Superior Poison Resist Potion','potion','High poison resistance.',260, 10, 'rare', 1.0),
('potion_resist_poison_l15','Transcendent Poison Resist Potion','potion','Near-immune to poison.',560, 15, 'epic', 1.0),
('potion_resist_poison_l20','Ultimate Poison Resist Potion','potion','Brief poison immunity.',960, 20, 'legendary', 1.0);

-- GROUP BUFF (party-wide) - premium cost scaling
DELETE FROM item WHERE slug LIKE 'potion_group_battle_l%';
INSERT INTO item (slug, name, type, description, value_copper, level, rarity, weight) VALUES
('potion_group_battle_l5','Lesser Battle Elixir','potion','Minor party combat buffs.',300, 5, 'uncommon', 1.0),
('potion_group_battle_l10','Battle Elixir','potion','Moderate party combat buffs.',660, 10, 'rare', 1.0),
('potion_group_battle_l15','Greater Battle Elixir','potion','Strong party combat buffs.',1240, 15, 'epic', 1.0),
('potion_group_battle_l20','Ultimate Battle Elixir','potion','Peak party combat buffs.',2100, 20, 'legendary', 1.0);

COMMIT;
