# Skill/Talent Tree System

Complete character progression system with unlockable skills and talent trees.

## Features

### 1. Skill Trees
- **Class-specific trees**: Warrior Combat, Mage Arcane, Cleric Divine
- **Tier-based progression**: Skills organized in 5 tiers
- **Visual tree layout**: Interactive node-based skill tree
- **Prerequisites**: Skills require parent skills to unlock
- **Level requirements**: Character must be appropriate level

### 2. Talent Points
- **Earn on level up**: 1 talent point per character level
- **Spend to unlock**: Skills cost 1-3 points based on tier
- **Track spending**: View total earned, spent, and available points
- **Respec available**: Reset all skills and refund points

### 3. Skill Types
- **Passive**: Always active, permanent bonuses
- **Active**: Triggered abilities with cooldowns
- **Toggle**: Can be turned on/off

## Database Schema

### Skill Tree Table
```sql
CREATE TABLE skill_tree (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    class_requirement VARCHAR(30),
    description TEXT,
    icon VARCHAR(50),
    max_tier INTEGER DEFAULT 5,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);
```

### Skill Table
```sql
CREATE TABLE skill (
    id SERIAL PRIMARY KEY,
    tree_id INTEGER NOT NULL REFERENCES skill_tree(id),
    name VARCHAR(100) NOT NULL,
    description TEXT NOT NULL,
    tier INTEGER NOT NULL DEFAULT 1,
    position_x INTEGER DEFAULT 0,
    position_y INTEGER DEFAULT 0,
    required_level INTEGER DEFAULT 1,
    required_skill_id INTEGER REFERENCES skill(id),
    cost INTEGER NOT NULL DEFAULT 1,
    effect_json TEXT NOT NULL,
    cooldown INTEGER,
    skill_type VARCHAR(20) NOT NULL DEFAULT 'passive',
    icon VARCHAR(50)
);
```

### Character Skill Table
```sql
CREATE TABLE character_skill (
    id SERIAL PRIMARY KEY,
    character_id INTEGER NOT NULL REFERENCES character(id),
    skill_id INTEGER NOT NULL REFERENCES skill(id),
    unlocked_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    skill_rank INTEGER NOT NULL DEFAULT 1,
    times_used INTEGER DEFAULT 0,
    last_used TIMESTAMP,
    UNIQUE (character_id, skill_id)
);
```

### Character Talent Points Table
```sql
CREATE TABLE character_talent_points (
    id SERIAL PRIMARY KEY,
    character_id INTEGER NOT NULL REFERENCES character(id) UNIQUE,
    total_earned INTEGER NOT NULL DEFAULT 0,
    total_spent INTEGER NOT NULL DEFAULT 0,
    available INTEGER NOT NULL DEFAULT 0
);
```

## API Endpoints

### Get All Skill Trees
```
GET /api/skill-trees
```

### Get Skills in Tree
```
GET /api/skill-trees/{tree_id}/skills
```

### Get Character's Talent Points
```
GET /api/characters/{character_id}/talent-points
```

### Get Character's Learned Skills
```
GET /api/characters/{character_id}/skills
```

### Unlock a Skill
```
POST /api/characters/{character_id}/skills
Body: { "skill_id": 1 }
```

### Use Active Skill
```
POST /api/characters/{character_id}/skills/{skill_id}/use
```

### Grant Talent Points
```
POST /api/characters/{character_id}/talent-points/grant
Body: { "points": 1 }
```

### Reset All Skills (Respec)
```
POST /api/characters/{character_id}/skills/reset
```

### Get Skill Details
```
GET /api/skills/{skill_id}
```

## Seeded Skills

### Warrior Combat Tree

**Tier 1:**
- **Power Strike** (Active): 150% weapon damage
- **Armor Mastery** (Passive): +10 defense

**Tier 2:**
- **Whirlwind** (Active): 80% AoE damage to 4 enemies
- **Iron Skin** (Passive): 15% damage reduction

**Tier 3:**
- **Battle Fury** (Active): +25% damage, +10% crit for 10s

### Mage Arcane Tree

**Tier 1:**
- **Fireball** (Active): 120% spell damage
- **Mana Efficiency** (Passive): 20% reduced spell costs

**Tier 2:**
- **Chain Lightning** (Active): 90% damage to 3 targets
- **Arcane Focus** (Passive): +15% spell damage

**Tier 3:**
- **Meteor Storm** (Active): 200% AoE spell damage

### Cleric Divine Tree

**Tier 1:**
- **Heal** (Active): Restore 100 HP
- **Holy Resistance** (Passive): +20% damage resistance

**Tier 2:**
- **Group Heal** (Active): 60 HP to all allies
- **Divine Shield** (Active): Absorb next attack

**Tier 3:**
- **Resurrection** (Active): Revive ally with 50% HP

## Frontend Usage

### JavaScript

```javascript
// Open skill tree for a character
skillTreeSystem.openSkillTree(characterId);

// Close skill tree
skillTreeSystem.closeModal();

// Switch to different tree
skillTreeSystem.switchTree(treeId);

// Unlock a skill (via UI click or programmatic)
skillTreeSystem.unlockSkill(skillId);

// Testing helper
testSkillTree(1);  // Opens skill tree for character ID 1
```

### HTML Integration

Add button to open skill tree:
```html
<button onclick="skillTreeSystem.openSkillTree({{ character.id }})">
    <i class="bi bi-star-fill"></i> Skill Tree
</button>
```

## Visual Features

### Skill Node States
- **Locked**: Gray, requirements not met
- **Available**: Blue pulse animation, can be unlocked
- **Unlocked**: Green, skill is learned

### Connection Lines
- **Gray**: Path not unlocked
- **Green**: Prerequisites unlocked

### Tooltips
- **Hover over nodes**: See skill details
- **Requirements**: Check level, prerequisite, cost
- **Effects**: View all bonuses/abilities
- **One-click unlock**: Click button in tooltip

## Migration

Run the migration to set up all skill tables:

```bash
cd /home/winter/work/Adventure
PGPASSWORD=changeme psql -U adventure -h localhost -p 5433 -d adventure -f sql/skill_system_migration.sql
```

Creates:
- 3 skill trees (Warrior, Mage, Cleric)
- 15 starter skills with tier progression
- Character talent points (1 per level for existing characters)
- All necessary indexes

## Testing

### 1. Open Skill Tree
```javascript
testSkillTree(1);
```

### 2. Check Talent Points
- View available points in header
- Should show 1 point per character level

### 3. Unlock Skills
- Hover over Tier 1 skill
- Click "Unlock Skill" button
- Verify talent points decrease
- Node turns green

### 4. Try Locked Skill
- Hover over Tier 2 skill without Tier 1 prerequisite
- Button should be disabled
- Tooltip shows unmet requirements

### 5. Check Database
```sql
SELECT * FROM character_skill WHERE character_id = 1;
SELECT * FROM character_talent_points WHERE character_id = 1;
```

## Integration Points

### Level Up Hook
When a character levels up, grant talent points:
```python
# In your level up logic
response = requests.post(
    f'/api/characters/{char_id}/talent-points/grant',
    json={'points': 1}
)
```

### Combat System
Apply passive skill bonuses:
```python
# Calculate bonus damage from skills
character_skills = CharacterSkill.query.filter_by(character_id=char_id).all()
for cs in character_skills:
    effects = json.loads(cs.skill.effect_json)
    if 'damage_bonus_percent' in effects:
        total_damage *= (1 + effects['damage_bonus_percent'] / 100)
```

### Active Skills
Track cooldowns and usage:
```python
# When using active skill in combat
response = requests.post(
    f'/api/characters/{char_id}/skills/{skill_id}/use'
)
if response.ok:
    skill_effects = response.json()['effects']
    # Apply effects to combat
```

## Future Enhancements

- **Skill ranks**: Upgrade skills 1-5 for increased power
- **Multiple trees per class**: Specialization paths
- **Cross-class skills**: Universal skill tree
- **Synergy bonuses**: Unlock combos between skills
- **Skill loadouts**: Save/switch between builds
- **Visual effects**: Animations for skill usage
- **Skill tooltips in combat**: Show active buffs
- **Achievement integration**: Unlock skills via achievements
- **Party skill bonuses**: Skills that buff allies
- **Ultimate abilities**: Tier 5 game-changing powers

## Troubleshooting

### Modal doesn't open
- Check console: `console.log(skillTreeSystem)`
- Verify JS file loaded in Network tab
- Check character ID is valid

### Skills not showing
- Verify migration ran successfully
- Check database: `SELECT * FROM skill;`
- Verify tree_id matches in API call

### Can't unlock skills
- Check talent points available
- Verify level requirement met
- Check prerequisite skill unlocked
- Review browser console for errors

### Tooltip positioning
- Tooltip auto-positions to right of node
- May need CSS adjustments for edge cases
- Check `.skill-tooltip` CSS positioning

## Files

### Backend
- `/app/models/skill.py` - Database models (149 lines)
- `/app/routes/skill_api.py` - API endpoints (361 lines)

### Frontend
- `/app/static/css/skill-tree.css` - Styles (600+ lines)
- `/app/static/js/skill-tree.js` - Logic (420+ lines)
- `/app/templates/dashboard.html` - Modal HTML (integrated)

### Database
- `/sql/skill_system_migration.sql` - Setup script

### Documentation
- `/docs/SKILL_TREE_SYSTEM.md` - This file
