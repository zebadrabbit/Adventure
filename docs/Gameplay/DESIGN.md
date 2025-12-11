
# Adventure Roguelite Design Document (Copilot Reference)

## GAME LOOP SYSTEM (EXPANDED DESIGN)

### GameLoop Structure
The game uses a procedural, instanced, scalable dungeon with extraction risk.
Each run is based on a **Dungeon Seed** that determines layout and content.

---

## Dungeon Initialization

### Inputs
- DungeonSeed (number or string)
- PartyAverageLevel
- DungeonTier
- OptionalAffixes (volcanic, poisonous, armored, frenzied, etc.)

### Generation Steps
- Generate terrain layout: rooms, corridors, choke points
- Generate fog-of-war mask (unrevealed by default)
- Generate monster density map
- Assign elite spawn positions
- Assign boss lairs (1–3 based on tier)
- Place loot nodes weighted by region difficulty

### Scaling
- Scale monster stats by PartyAverageLevel, DungeonTier, and Affixes

---

## Exploration

### Fog of War
- Reveal radius determined by LOS + Perception stat

### Discoverables
- Loot chests (quality randomized by tier and luck modifiers)
- Traps (trigger, detect, or disarm)
- Secret rooms (Perception + Investigation)
- Shrines (temporary buffs similar to Diablo)

---

## Combat

### Monster Scaling Factors
- PartyLevel
- DungeonTier
- Affixes
- Local difficulty region

### Progress System
- Killing monsters increments dungeon progress bar
- Killing elites contributes to elite quota and drops higher-tier loot
- Killing bosses drops boss caches (extraction rewards)

---

## Extraction System

### Conditions
- All bosses defeated → **Hearthstone Portal** unlocks
- Early extraction allowed with penalties:
  - XP penalty
  - Loot penalty
  - Reputation penalty (optional)

### Characters Left Behind
- Become **LockedInDungeon**
- Cannot be used until run resumes
- If the rest of the party extracts → permadeath

---

## Death Rules
- Characters may be resurrected inside using:
  - Items
  - Spells
  - Rare shrines
- If party extracts leaving a corpse behind → **permadeath**
- Full wipe = all characters lost, dungeon failed

---

## XP & Currency

### XP Sources
- Lockpicking
- Detecting traps
- Disarming traps
- Killing enemies
- Effective ability usage (heals, taunts, CC)

### Currency Types
- Gold
- Silver
- Copper

Weight-based inventory encourages extraction over greed.

---

## Loot System
Loot is influenced by:
- Class compatibility
- Monster level
- Dungeon tier
- Hidden modifiers (luck, crit-find, treasure-sense)

---

# LOBBY SYSTEM

## Party Creation (Hunt: Showdown Style)

### Rules
- Max party size: 4
- Creation methods:
  - Manual creation (stat array or point buy)
  - Random generation (optional auto-backstories)

### Persistence
- Party saved as a long-term roster

---

## Dungeon Selection

### Options
- Generate new dungeon (seed-based procedural world)
- Resume abandoned dungeon

### Persistence Conditions
- Dungeon remains until:
  - Completed
  - Wiped
  - Abandoned

---

## Loadout Phase
Players may spend gold on:
- Weapons
- Armor
- Potions
- Scrolls
- Tools (lockpicks, torches, bombs)

Optionally:
- Crafting system for extraction-looter flavor

---

# CHARACTER SYSTEM

## Levels
- Max level: **50**
- Level curve:
  - Early: fast (Diablo)
  - Midgame: gear checks (Hunt)
  - Lategame: flattening (D&D)

---

## Stats (D&D 5E Style)
- STR
- DEX
- CON
- INT
- WIS
- CHA

Saving throws tied to class.
Skill checks use DC threshold system.

---

## Abilities & Spells

### Obtained Through
- Level-ups
- Tomes/manuals found in dungeons
- Training shrines (temporary or permanent)

### Synergy Examples
- Rogue Sneak Attack + Ranger Hunter’s Mark + Bard Advantage Buff

---

## Starting Gear
Auto-assigned from class metadata:
- Simple weapons
- Basic armor
- 1–2 potions
- Class tools (holy symbol, arcane focus, thieves' tools, etc.)

---

# CLASS FRAMEWORK
- Total classes: **12**
- Each includes:
  - Hit die
  - Primary stat
  - Weapons/armors
  - Spellcasting type
  - Skills
  - Abilities
  - Resource formulas
  - Derived stats (AC, mana, stamina)

---

# SYSTEM ADDITIONS

## Dungeon Affixes (Diablo-Style)
Examples:
- Frenzied (faster attacks)
- Bolstered (elite HP ×2)
- Volcanic (ground eruptions)
- Necrotic (DoT on hit)
- Arcane Beams
- Cursed Shrines

---

## Extraction Modifiers (Hunt: Showdown Style)
- Early extraction → loot penalty
- Full clear → loot bonus
- No deaths → XP multiplier
- Time remaining affects cache quality

---

## Home Base Upgrades
- Training Hall → XP bonus
- Workshop → Craft rare items
- Magic Library → Research spells
- Treasure Vault → Increase carry weight

---

# DATA SPECIFICATION (CSV IMPLEMENTATION)

## ITEM SYSTEM

### Overview
The game features **87 predefined base items** across 4 categories:
- **32 Weapons** (12 categories)
- **25 Armor pieces** (5 slots, 4 types)
- **20 Consumables** (potions, bombs, scrolls, food, keys)
- **10 Jewelry** (rings, amulets)

All items support **procedural stat generation** via the affix system (see below).

### Weapons (`items_weapons.csv`)

**Categories (12 total):**
- **One-Handed Melee:** sword_1h, axe_1h, dagger, fist
- **Two-Handed Melee:** sword_2h, axe_2h, polearm
- **Ranged:** bow, xbow_light, xbow_heavy
- **Magic:** staff, wand

**Key Properties:**
- **Level Range:** 1-50 (MinLevel/MaxLevel determine drop eligibility)
- **Base Rarity:** Common, Uncommon, Rare, Epic, Legendary
- **Damage Bonuses:** Flat damage added to category base dice
- **Stat Requirements:** STR, DEX, INT, WIS (enforced for equipping)
- **Sockets:** 0-7 (Mythic items can roll up to 7 sockets for gems/runes)
- **Flavor Tags:** Enchanted, Cursed, Blessed, Ancient, Dragonforged, etc.

**Examples:**
- `Rusty Shortsword` (Common, Lv1-5, sword_1h, 0 sockets)
- `Sunbreaker` (Legendary, Lv25-50, sword_1h, +7 damage, STR req, +4 CHA, 4 sockets)
- `Ember Longbow` (Epic, Lv15-35, bow, fire damage, 2 sockets)

### Armor (`items_armor.csv`)

**Slots (5):** Chest, Head, Hands, Feet, Shield

**Types (4):**
- **Cloth:** Low AC (4-12), casters (Wizard, Sorcerer, Warlock)
- **Leather:** Medium AC (8-16), rogues/rangers (Rogue, Ranger, Monk)
- **Mail:** Medium-Heavy AC (12-18), soldiers (Fighter, Paladin, Cleric)
- **Plate:** Heavy AC (14-24), tanks (Fighter, Paladin)

**Key Properties:**
- **Armor Class (AC):** Base defense value (4-24 range)
- **Stat Requirements:** STR for plate/mail, DEX for leather
- **Stat Bonuses:** HP, resistances, movement speed
- **Sockets:** 0-4 for rare/legendary armor

**Examples:**
- `Threadbare Robes` (Common, Cloth Chest, AC 4, Lv1-5)
- `Dragonscale Aegis` (Mythic, Shield, AC 24, +50 HP, +15% all resist, 4 sockets)
- `Shadowstalker Boots` (Epic, Leather Feet, AC 14, +10% movespeed, 2 sockets)

### Consumables (`items_consumables.csv`)

**Categories:**
- **Potions:** Healing, Mana, Stamina, Antidote, Resistance
- **Bombs:** Fire, Frost, Poison, Smoke (AOE damage/utility)
- **Scrolls:** Teleport, Identify, Town Portal, Resurrection
- **Food:** Bread, Cheese, Meat (out-of-combat regen)
- **Keys:** Dungeon keys for locked doors/chests

**Key Properties:**
- **Effect:** Healing formula (e.g., `25 + Level*2 HP`)
- **Potency:** Scaling value (Lesser/Greater variants)
- **Duration:** Buff/debuff length in seconds
- **Cooldown:** Global potion cooldown (prevents spam)
- **Max Stack:** 1-99 (potions stack to 10, keys to 99)

**Examples:**
- `Lesser Healing Potion` (restores 25 + Level×2 HP, 30s cooldown, stack 10)
- `Alchemical Firebomb` (40 + Level×3 fire AOE, 3m radius, stack 5)
- `Scroll of Town Portal` (instant extraction, consumes scroll, stack 3)
- `Dungeon Key (Silver)` (opens silver chests, stack 99)

### Jewelry (`items_jewelry.csv`)

**Slots:** Ring (2 slots), Amulet (1 slot)

**Key Properties:**
- **Stat Bonuses:** +1 to +5 to any stat (STR/DEX/INT/WIS/CHA/CON)
- **Special Effects:** XP bonus, magic find, gold find, resistances
- **Sockets:** 0-2 (rare on jewelry)

**Examples:**
- `Simple Copper Band` (Common, Ring, +1 random stat)
- `Ring of the Bear` (Rare, Ring, +3 STR, +25 HP)
- `Stars of the Wanderer` (Mythic, Amulet, +3 all mental stats, +10% XP, 2 sockets)

---

## RARITY SYSTEM & PROCEDURAL GENERATION

### Rarity Tiers (`loot_rarities.csv`)

| Rarity | Color | Drop Weight | Min Affixes | Max Affixes | Value Mult | Min Sockets | Socket Chance |
|--------|-------|-------------|-------------|-------------|------------|-------------|---------------|
| Common | Gray (#bfbfbf) | 600 | 0 | 1 | 1.0x | 0 | 0% |
| Uncommon | Green (#40bf40) | 250 | 1 | 2 | 2.5x | 0 | 5% |
| Rare | Blue (#4080ff) | 100 | 2 | 3 | 5.0x | 1 | 10% |
| Epic | Purple (#a335ee) | 35 | 3 | 4 | 8.0x | 2 | 12% |
| Legendary | Orange (#ff8000) | 13 | 3 | 5 | 10.0x | 3 | 15% |
| Mythic | Gold (#e6cc80) | 2 | 4 | 6 | 12.0x | 8 | 15% |

**Drop Mechanics:**
- Total weight = 1000 (600+250+100+35+13+2)
- Common drops ~60% of the time, Mythic ~0.2%
- **Magic Find** stat increases rare drop chances
- **Luck** modifiers from dungeon affixes shift distribution

**Upgrade System:**
- Upgrade chance column (not shown) allows rare crafting recipes to promote rarity
- Example: 3 Rare items → 1 Epic (15% success rate)

### Procedural Affixes (`procedural_affixes.csv`)

**20 Total Affixes** (Prefixes & Suffixes)

**Categories:**

**Offensive:**
- `Brutal` (prefix): +2-10 STR
- `Precise` (prefix): +2-10 DEX
- `of Precision` (suffix): +2-8% Crit Chance
- `of Carnage` (suffix): +5-20% Crit Damage
- `of the Leech` (suffix): +2-8% Lifesteal

**Defensive:**
- `Fortified` (prefix): +10-50 HP
- `Warded` (prefix): +1-5 AC
- `of Vitality` (suffix): +10-50 HP
- `of the Aegis` (suffix): +3-10% all resistances
- `of the Juggernaut` (suffix): +5-15 armor

**Elemental:**
- `Fiery` (prefix): +5-25 fire damage
- `Frozen` (prefix): +5-25 cold damage
- `Shocking` (prefix): +5-25 lightning damage

**Utility:**
- `Swift` (prefix): +5-15% movement speed
- `Arcane` (prefix): +2-10 INT
- `of Insight` (suffix): +2-10 WIS
- `of Regeneration` (suffix): +5-20 mana/stamina regen
- `of Haste` (suffix): -5-15% cooldown reduction
- `of Fortune` (suffix): +5-20% XP gain
- `of Wealth` (suffix): +10-50% gold find

**Generation Algorithm:**
1. Roll rarity (weighted by drop table + magic find)
2. Select base item (filtered by dungeon level)
3. Roll affix count (min-max from rarity tier)
4. Randomly select affixes (no duplicates)
5. Roll affix values within min-max ranges
6. Roll sockets (probability from rarity tier)
7. Calculate final item value (base × rarity mult × affix mult)

**Example Generated Item:**
- Base: `Iron Longsword` (Rare, 1d8 damage)
- Affixes: `Brutal` (+7 STR), `of Precision` (+5% crit), `of Vitality` (+35 HP)
- Final Name: `Brutal Iron Longsword of Precision and Vitality`
- Sockets: 2
- Value: 450g (base 30g × 5.0 rare mult × 3.0 affix mult)

---

## ENEMY SYSTEM

### Enemy Templates (`enemy_templates.csv`)

**8 Archetypes** ranked by difficulty:

| Template | Rank | Base HP | HP/Lvl | Base Dmg | Dmg/Lvl | AC | Crit% | Base XP | XP/Lvl | Loot Mult |
|----------|------|---------|--------|----------|---------|----|----|---------|---------|-----------|
| Trash | Normal | 25 | 10 | 4 | 2 | 10 | 0.3% | 15 | 5 | 1.0x |
| Skirmisher | Normal | 40 | 12 | 6 | 2.5 | 12 | 5% | 25 | 8 | 1.2x |
| Brute | Normal | 80 | 20 | 8 | 3 | 14 | 2% | 35 | 10 | 1.5x |
| Caster | Normal | 50 | 15 | 10 | 4 | 11 | 8% | 40 | 12 | 1.8x |
| Elite | Elite | 150 | 35 | 12 | 5 | 16 | 10% | 100 | 25 | 2.5x |
| Champion | Elite | 250 | 50 | 18 | 6.5 | 18 | 12% | 200 | 40 | 3.0x |
| MiniBoss | Boss | 350 | 65 | 22 | 7.5 | 20 | 15% | 300 | 60 | 3.5x |
| Boss | Boss | 400 | 70 | 26 | 8.5 | 16 | 0.8% | 400 | 70 | 4.0x |

**Scaling Formula:**
- Final HP = Base HP + (HP per Level × Dungeon Level)
- Final Damage = Base Dmg + (Dmg per Level × Dungeon Level)
- Final XP = Base XP + (XP per Level × Dungeon Level)
- Final Loot Value = Base Loot × Loot Multiplier × (1 + 0.1 × Dungeon Level)

**Example (Level 20 Dungeon):**
- **Trash Mob:** 25 + (10×20) = 225 HP, 44 damage, 115 XP
- **Elite:** 150 + (35×20) = 850 HP, 112 damage, 600 XP, 2.5× loot
- **Boss:** 400 + (70×20) = 1800 HP, 196 damage, 1800 XP, 4.0× loot

**Dungeon Composition:**
- 60-70% Trash mobs (rapid kills, low rewards)
- 20-25% Skirmishers/Brutes (moderate challenge)
- 5-10% Casters (priority targets, ranged threat)
- 3-5% Elites (mini-events, guaranteed rare+ loot)
- 1-3 Bosses per dungeon (extraction objectives)

**Affix Modifiers:**
- **Frenzied:** +30% attack speed, +20% damage
- **Bolstered:** +100% HP
- **Necrotic:** DoT aura (5% max HP/sec)
- **Volcanic:** Periodic ground eruptions (+50% fire damage)

---

## WEAPON MECHANICS

### Weapon Categories (`weapon_categories.csv`)

**12 Categories** with distinct combat profiles:

| Category | Damage Dice | Primary Stat | Attack Speed | Crit Mult | Allowed Classes | Tags |
|----------|-------------|--------------|--------------|-----------|-----------------|------|
| sword_1h | 1d8 | STR/DEX | 1.0 | 2.0x | Fighter, Paladin, Ranger, Rogue | Versatile, Balanced |
| sword_2h | 2d6 | STR | 0.8 | 2.5x | Fighter, Paladin, Barbarian | Heavy, Cleave |
| axe_1h | 1d6 | STR | 0.9 | 2.2x | Fighter, Barbarian | Critical |
| axe_2h | 1d12 | STR | 0.7 | 3.0x | Fighter, Barbarian | Heavy, Crit |
| polearm | 1d10 | STR | 0.75 | 2.0x | Fighter, Paladin | Reach, Two-Handed |
| dagger | 1d4 | DEX | 1.3 | 3.0x | Rogue, Ranger, Bard | Fast, Finesse, Sneak |
| fist | 1d6 | STR/DEX | 1.2 | 1.8x | Monk, Barbarian | Unarmed, Dual |
| bow | 1d10 | DEX | 0.9 | 2.5x | Ranger, Rogue, Fighter | Ranged, Ammo |
| xbow_light | 1d8 | DEX | 1.0 | 2.0x | Rogue, Ranger | Ranged, Reload |
| xbow_heavy | 1d12 | STR | 0.6 | 3.5x | Fighter | Ranged, Heavy, Slow |
| staff | 1d6 | INT/WIS | 1.0 | 1.5x | Wizard, Cleric, Druid | Magic, Two-Handed |
| wand | 1d4 | INT | 1.1 | 1.5x | Wizard, Sorcerer, Warlock | Magic, Fast |

**Combat Mechanics:**
- **Attack Speed:** Multiplier for DPS calculations (1.0 = baseline)
- **Crit Multiplier:** Damage × multiplier on critical hit
- **Primary Stat:** Adds damage modifier (e.g., STR mod for greataxe)
- **Tags:**
  - `Versatile`: Can use 1H or 2H (extra damage if 2H)
  - `Finesse`: Can use DEX instead of STR for attacks
  - `Reach`: Attack from 10ft instead of 5ft
  - `Heavy`: Disadvantage for Small races
  - `Reload`: Requires action to reload after attack

**Class Restrictions:**
- Wizards: Staff, Wand only
- Rogues: Dagger, Sword_1h, Bow, Xbow_light
- Fighters: All weapons
- Clerics: No greataxe, no heavy xbow

**DPS Formula:**
```
Base DPS = (Average Dice Roll + Stat Modifier + Weapon Damage Bonus) × Attack Speed
Crit DPS = Base DPS × (1 + Crit Chance × (Crit Mult - 1))
Final DPS = Crit DPS × (1 + Affix Bonuses)
```

---

## PROGRESSION SYSTEM

### XP Table (`xp_table_level_1_to_50.csv`)

**Key Milestones:**

| Level Range | XP Curve | Phase | Talent Points | Loot Tier Bonus |
|-------------|----------|-------|---------------|-----------------|
| 1-10 | Fast (100-5011 per level) | Early game | Every 2 levels | 1.0 → 1.09 |
| 11-30 | Moderate (5893-32441) | Mid game | Every 2 levels | 1.1 → 1.29 |
| 31-50 | Slow (34301-77312) | Late game | Every 2 levels | 1.3 → 1.49 |

**Total XP Required:**
- Level 10: 21,133 XP
- Level 25: 232,348 XP
- Level 50: 1,470,558 XP

**Talent Points:**
- Awarded every **even level** (2, 4, 6, etc.)
- Total at level 50: **25 talent points**
- Used for:
  - Passive stat bonuses
  - Ability upgrades
  - Class specializations
  - Skill tree unlocks

**Loot Tier Bonus:**
- Increases item quality/value by % per level
- Level 1: 1.0× (baseline)
- Level 25: 1.24× (24% better loot)
- Level 50: 1.49× (49% better loot)
- Stacks multiplicatively with rarity multipliers

**XP Sources:**
- Monster kills: 15-400 base XP (×dungeon level)
- Quest completion: 500-5000 XP
- Exploration: 10-50 XP per discovered room
- Skill usage: 5-25 XP (lockpicking, trap disarm, persuasion)
- Dungeon completion: 1000 base × dungeon tier

**Death Penalty:**
- **10% XP loss** on death (cannot delevel)
- Resurrection spells reduce penalty to 5%
- Hardcore mode: Permadeath (no XP recovery)

---

## LOOT GENERATION PIPELINE

### Full Loot Drop Algorithm

**Step 1: Determine Drop Eligibility**
- Enemy defeated → roll loot table
- Chest opened → guaranteed loot (quantity based on chest tier)
- Boss killed → guaranteed boss cache (4.0× loot mult)

**Step 2: Roll Rarity**
```
Total Weight = 1000 (before modifiers)
Magic Find Bonus = Player MF% + Party MF%
Adjusted Weights = Base Weight × (1 + MF Bonus / 100)
Random Roll = RNG(0, Total Adjusted Weight)
Select Rarity Tier matching roll
```

**Step 3: Select Base Item**
```
Filter items by:
- Dungeon Level (MinLevel ≤ DungeonLevel ≤ MaxLevel)
- Class compatibility (if smart loot enabled)
- Item category weights (weapons 40%, armor 30%, consumables 20%, jewelry 10%)
Random select from eligible pool
```

**Step 4: Generate Affixes**
```
Affix Count = Random(Min Affixes, Max Affixes) from rarity tier
For each affix slot:
  - Select random affix type (no duplicates)
  - Roll value within affix min-max range
  - Apply level scaling (higher level = better rolls)
```

**Step 5: Roll Sockets**
```
Socket Chance = Base chance from rarity tier + Item socket bonus
If Random(0,1) < Socket Chance:
  Socket Count = Random(Min Sockets, Min Sockets + Item Max Sockets)
```

**Step 6: Calculate Final Stats**
```
Item Value = Base Value × Rarity Mult × Affix Mult × Loot Tier Bonus
Item Level = Dungeon Level ± Random(0, 3)
Final Stats = Base Stats + Affix Stats + Socket Bonuses
```

**Step 7: Smart Loot (Optional)**
```
If enabled:
  - Prioritize player's class items (70% chance)
  - Weight stats toward player's build (STR for fighters, INT for wizards)
  - Avoid duplicate uniques already owned
```

### Example Full Drop Sequence

**Context:** Level 20 Elite killed in Tier 3 dungeon, player has 50% Magic Find

**Execution:**
1. **Drop Roll:** Elite = 2.5× loot mult → guaranteed drop
2. **Rarity Roll:**
   - Total weight: 1000 × 1.5 (MF bonus) = 1500
   - Roll: 823 → **Rare** tier selected
3. **Base Item:**
   - Filter: Level 17-23 items
   - Category: Weapon (40% weight)
   - Result: `Iron Battleaxe` (axe_1h, 1d6 base, Level 20)
4. **Affixes:**
   - Rare tier: 2-3 affixes
   - Roll: 3 affixes
   - Selected: `Brutal` (+8 STR), `of Precision` (+6% crit), `of the Leech` (+5% lifesteal)
5. **Sockets:**
   - Rare socket chance: 10%
   - Roll: 0.07 → **1 socket** added
6. **Final Item:**
   - Name: `Brutal Iron Battleaxe of Precision and the Leech`
   - Damage: 1d6 + 8 (from STR bonus)
   - Stats: +8 STR, +6% crit chance, +5% lifesteal
   - Sockets: 1 (can add ruby for +fire damage)
   - Value: 125g (base 25g × 5.0 rare mult)
   - Item Level: 20

---

## EXTRACTION ECONOMICS

### Risk vs Reward

**Time Investment:**
- Longer runs = more loot but higher risk
- Early extraction penalty: -30% XP, -20% loot quality

**Death Risk:**
- Character locked in dungeon until extraction
- Party wipe = all loot lost + character permadeath

**Optimal Strategies:**
- **Speed Runs:** 15-20 min, kill trash + 1 boss, extract (safe, low reward)
- **Full Clears:** 45-60 min, kill all elites + all bosses (risky, high reward)
- **Boss Rush:** 25-35 min, skip trash, kill bosses only (medium risk/reward)

**Loot Carry Weight:**
- Each character: 50 base + (10 × STR modifier) lbs
- Heavy items (plate armor, greataxes): 15-25 lbs each
- Potions/scrolls: 0.5-1 lb each
- Gold: 0.01 lb per coin
- Overweight penalty: -20% movement speed per 10 lbs over limit

**Extraction Bonuses:**
- **Flawless Run** (no deaths): +25% XP, +1 rarity tier to best item
- **Speed Clear** (<30 min): +50% gold
- **Full Clear** (100% map): +Bonus chest with guaranteed Epic+

---

This data specification provides the concrete implementation details for all CSV-defined game systems, enabling developers to understand exact formulas, probabilities, and progression curves.
