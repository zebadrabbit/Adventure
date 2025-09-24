-- Potions & Consumables (Levels 1-20)
-- Types kept as 'potion' for schema simplicity; could be split later.
-- Healing / Mana / Buff / Utility tiers scale roughly quadratically with level for value.
BEGIN TRANSACTION;

DELETE FROM item WHERE slug LIKE 'potion_heal_l%';
INSERT INTO item (slug, name, type, description, value_copper) VALUES
('potion_heal_l1','Minor Healing Potion','potion','Restores a small amount of health.',18),
('potion_heal_l2','Lesser Healing Potion','potion','Restores modest health.',28),
('potion_heal_l3','Standard Healing Potion','potion','Restores a fair amount of health.',40),
('potion_heal_l4','Improved Healing Potion','potion','Restores significant health.',56),
('potion_heal_l5','Greater Healing Potion','potion','Restores large health.',76),
('potion_heal_l6','Superior Healing Potion','potion','Restores very large health.',100),
('potion_heal_l7','Major Healing Potion','potion','Major health restoration.',128),
('potion_heal_l8','Potent Healing Potion','potion','High potency recovery.',160),
('potion_heal_l9','Grand Healing Potion','potion','Grand restorative.',196),
('potion_heal_l10','Mighty Healing Potion','potion','Mighty restorative.',236),
('potion_heal_l11','Royal Healing Elixir','potion','Royal grade healing.',280),
('potion_heal_l12','Sacred Healing Elixir','potion','Sacred infused healing.',328),
('potion_heal_l13','Mythic Healing Elixir','potion','Mythic scale healing.',380),
('potion_heal_l14','Empyreal Healing Elixir','potion','Empyreal potent healing.',436),
('potion_heal_l15','Transcendent Healing Elixir','potion','Transcendent restoration.',496),
('potion_heal_l16','Paragon Healing Elixir','potion','Peak tier restoration.',560),
('potion_heal_l17','Ascendant Healing Elixir','potion','Ascendant vitality.',628),
('potion_heal_l18','Eternal Healing Elixir','potion','Enduring supreme healing.',700),
('potion_heal_l19','Legendary Healing Elixir','potion','Legend-tier restoration.',776),
('potion_heal_l20','Ultimate Healing Elixir','potion','Maximum possible restoration.',856);

DELETE FROM item WHERE slug LIKE 'potion_mana_l%';
INSERT INTO item (slug, name, type, description, value_copper) VALUES
('potion_mana_l1','Minor Mana Potion','potion','Restores a small amount of mana.',18),
('potion_mana_l2','Lesser Mana Potion','potion','Restores modest mana.',28),
('potion_mana_l3','Standard Mana Potion','potion','Restores a fair amount of mana.',40),
('potion_mana_l4','Improved Mana Potion','potion','Restores significant mana.',56),
('potion_mana_l5','Greater Mana Potion','potion','Restores large mana.',76),
('potion_mana_l6','Superior Mana Potion','potion','Restores very large mana.',100),
('potion_mana_l7','Major Mana Potion','potion','Major mana restoration.',128),
('potion_mana_l8','Potent Mana Potion','potion','High potency mana.',160),
('potion_mana_l9','Grand Mana Potion','potion','Grand mana restorative.',196),
('potion_mana_l10','Mighty Mana Potion','potion','Mighty mana restorative.',236),
('potion_mana_l11','Royal Mana Elixir','potion','Royal grade mana.',280),
('potion_mana_l12','Sacred Mana Elixir','potion','Sacred infused mana.',328),
('potion_mana_l13','Mythic Mana Elixir','potion','Mythic scale mana.',380),
('potion_mana_l14','Empyreal Mana Elixir','potion','Empyreal potent mana.',436),
('potion_mana_l15','Transcendent Mana Elixir','potion','Transcendent mana.',496),
('potion_mana_l16','Paragon Mana Elixir','potion','Peak tier mana.',560),
('potion_mana_l17','Ascendant Mana Elixir','potion','Ascendant mana.',628),
('potion_mana_l18','Eternal Mana Elixir','potion','Enduring supreme mana.',700),
('potion_mana_l19','Legendary Mana Elixir','potion','Legend-tier mana.',776),
('potion_mana_l20','Ultimate Mana Elixir','potion','Maximum possible mana.',856);

-- Buff Potions (Attack, Defense, Speed) cycles; value set slightly above raw heal equivalent due to strategic utility.
DELETE FROM item WHERE slug LIKE 'potion_buff_attack_l%';
INSERT INTO item (slug, name, type, description, value_copper) VALUES
('potion_buff_attack_l1','Minor Attack Draught','potion','Slightly increases attack briefly.',22),
('potion_buff_attack_l2','Lesser Attack Draught','potion','Modest attack increase.',34),
('potion_buff_attack_l3','Standard Attack Draught','potion','Fair attack increase.',48),
('potion_buff_attack_l4','Improved Attack Draught','potion','Notable attack increase.',64),
('potion_buff_attack_l5','Greater Attack Draught','potion','Large attack increase.',84),
('potion_buff_attack_l6','Superior Attack Draught','potion','Very large attack increase.',108),
('potion_buff_attack_l7','Major Attack Draught','potion','Major attack surge.',136),
('potion_buff_attack_l8','Potent Attack Draught','potion','High potency attack boost.',168),
('potion_buff_attack_l9','Grand Attack Elixir','potion','Grand attack empowerment.',204),
('potion_buff_attack_l10','Mighty Attack Elixir','potion','Mighty attack empowerment.',244),
('potion_buff_attack_l11','Royal Attack Elixir','potion','Royal-grade attack boost.',288),
('potion_buff_attack_l12','Sacred Attack Elixir','potion','Sacred attack infusion.',336),
('potion_buff_attack_l13','Mythic Attack Elixir','potion','Mythic attack power.',388),
('potion_buff_attack_l14','Empyreal Attack Elixir','potion','Empyreal attack resonance.',444),
('potion_buff_attack_l15','Transcendent Attack Elixir','potion','Transcendent attack force.',504),
('potion_buff_attack_l16','Paragon Attack Elixir','potion','Peak attack empowerment.',568),
('potion_buff_attack_l17','Ascendant Attack Elixir','potion','Ascendant attack zeal.',636),
('potion_buff_attack_l18','Eternal Attack Elixir','potion','Enduring attack power.',708),
('potion_buff_attack_l19','Legendary Attack Elixir','potion','Legend-tier attack force.',784),
('potion_buff_attack_l20','Ultimate Attack Elixir','potion','Maximum attack surge.',864);

DELETE FROM item WHERE slug LIKE 'potion_buff_defense_l%';
INSERT INTO item (slug, name, type, description, value_copper) VALUES
('potion_buff_defense_l1','Minor Defense Draught','potion','Slightly increases defense briefly.',22),
('potion_buff_defense_l2','Lesser Defense Draught','potion','Modest defense increase.',34),
('potion_buff_defense_l3','Standard Defense Draught','potion','Fair defense increase.',48),
('potion_buff_defense_l4','Improved Defense Draught','potion','Notable defense increase.',64),
('potion_buff_defense_l5','Greater Defense Draught','potion','Large defense increase.',84),
('potion_buff_defense_l6','Superior Defense Draught','potion','Very large defense increase.',108),
('potion_buff_defense_l7','Major Defense Draught','potion','Major defense surge.',136),
('potion_buff_defense_l8','Potent Defense Draught','potion','High potency defense boost.',168),
('potion_buff_defense_l9','Grand Defense Elixir','potion','Grand defense empowerment.',204),
('potion_buff_defense_l10','Mighty Defense Elixir','potion','Mighty defense empowerment.',244),
('potion_buff_defense_l11','Royal Defense Elixir','potion','Royal-grade defense boost.',288),
('potion_buff_defense_l12','Sacred Defense Elixir','potion','Sacred defense infusion.',336),
('potion_buff_defense_l13','Mythic Defense Elixir','potion','Mythic defense power.',388),
('potion_buff_defense_l14','Empyreal Defense Elixir','potion','Empyreal defense resonance.',444),
('potion_buff_defense_l15','Transcendent Defense Elixir','potion','Transcendent defense force.',504),
('potion_buff_defense_l16','Paragon Defense Elixir','potion','Peak defense empowerment.',568),
('potion_buff_defense_l17','Ascendant Defense Elixir','potion','Ascendant defensive zeal.',636),
('potion_buff_defense_l18','Eternal Defense Elixir','potion','Enduring defense power.',708),
('potion_buff_defense_l19','Legendary Defense Elixir','potion','Legend-tier defense force.',784),
('potion_buff_defense_l20','Ultimate Defense Elixir','potion','Maximum defense surge.',864);

DELETE FROM item WHERE slug LIKE 'potion_buff_speed_l%';
INSERT INTO item (slug, name, type, description, value_copper) VALUES
('potion_buff_speed_l1','Minor Swiftness Draught','potion','Slightly increases speed briefly.',22),
('potion_buff_speed_l2','Lesser Swiftness Draught','potion','Modest speed increase.',34),
('potion_buff_speed_l3','Standard Swiftness Draught','potion','Fair speed increase.',48),
('potion_buff_speed_l4','Improved Swiftness Draught','potion','Notable speed increase.',64),
('potion_buff_speed_l5','Greater Swiftness Draught','potion','Large speed increase.',84),
('potion_buff_speed_l6','Superior Swiftness Draught','potion','Very large speed increase.',108),
('potion_buff_speed_l7','Major Swiftness Draught','potion','Major speed surge.',136),
('potion_buff_speed_l8','Potent Swiftness Draught','potion','High potency speed boost.',168),
('potion_buff_speed_l9','Grand Swiftness Elixir','potion','Grand speed empowerment.',204),
('potion_buff_speed_l10','Mighty Swiftness Elixir','potion','Mighty speed empowerment.',244),
('potion_buff_speed_l11','Royal Swiftness Elixir','potion','Royal-grade speed boost.',288),
('potion_buff_speed_l12','Sacred Swiftness Elixir','potion','Sacred speed infusion.',336),
('potion_buff_speed_l13','Mythic Swiftness Elixir','potion','Mythic speed power.',388),
('potion_buff_speed_l14','Empyreal Swiftness Elixir','potion','Empyreal speed resonance.',444),
('potion_buff_speed_l15','Transcendent Swiftness Elixir','potion','Transcendent speed force.',504),
('potion_buff_speed_l16','Paragon Swiftness Elixir','potion','Peak speed empowerment.',568),
('potion_buff_speed_l17','Ascendant Swiftness Elixir','potion','Ascendant velocity zeal.',636),
('potion_buff_speed_l18','Eternal Swiftness Elixir','potion','Enduring speed power.',708),
('potion_buff_speed_l19','Legendary Swiftness Elixir','potion','Legend-tier speed force.',784),
('potion_buff_speed_l20','Ultimate Swiftness Elixir','potion','Maximum speed surge.',864);

-- Utility / Resistance
DELETE FROM item WHERE slug LIKE 'potion_antidote_l%';
INSERT INTO item (slug, name, type, description, value_copper) VALUES
('potion_antidote_l1','Minor Antidote','potion','Cures minor poisons.',26),
('potion_antidote_l5','Greater Antidote','potion','Cures potent poisons.',86),
('potion_antidote_l10','Superior Antidote','potion','Cures virulent poisons.',236),
('potion_antidote_l15','Transcendent Antidote','potion','Purges nearly all toxins.',504),
('potion_antidote_l20','Ultimate Antidote','potion','Universal toxin purge.',856);

DELETE FROM item WHERE slug LIKE 'potion_resist_fire_l%';
INSERT INTO item (slug, name, type, description, value_copper) VALUES
('potion_resist_fire_l1','Minor Fire Resist Potion','potion','Slightly reduces fire damage.',30),
('potion_resist_fire_l5','Greater Fire Resist Potion','potion','Large fire resistance.',96),
('potion_resist_fire_l10','Superior Fire Resist Potion','potion','High fire resistance.',270),
('potion_resist_fire_l15','Transcendent Fire Resist Potion','potion','Near-immune to fire.',580),
('potion_resist_fire_l20','Ultimate Fire Resist Potion','potion','Brief fire immunity.',990);

COMMIT;
