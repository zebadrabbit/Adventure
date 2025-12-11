# Achievement System Documentation

## Overview

The Achievement System tracks player accomplishments and rewards milestones across all game activities. Players earn achievement points, unlock badges, receive gold rewards, and can view their progress in a comprehensive achievement modal.

## Features

- **18 Starter Achievements** across 6 categories (Combat, Exploration, Progression, Collection, Social, Special)
- **Achievement Points** accumulate as players unlock achievements
- **Gold Rewards** automatically awarded on achievement unlock
- **Hidden Achievements** revealed only when unlocked
- **Progress Tracking** shows current progress toward unlock requirements
- **Real-time Notifications** toast notifications appear when achievements unlock
- **Category Filtering** organize achievements by type
- **Visual Progress Bars** track completion percentage

## Database Schema

### `achievement` Table

Stores achievement templates/definitions.

```sql
CREATE TABLE achievement (
    id SERIAL PRIMARY KEY,
    slug VARCHAR(100) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    description TEXT NOT NULL,
    category VARCHAR(30) NOT NULL,
    icon VARCHAR(50),
    points INTEGER DEFAULT 10,
    hidden BOOLEAN DEFAULT FALSE,
    requirement_type VARCHAR(50) NOT NULL,
    requirement_value INTEGER DEFAULT 1,
    requirement_data TEXT,
    reward_gold INTEGER DEFAULT 0,
    reward_items TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

**Key Fields:**
- `slug`: Unique identifier (e.g., 'first-blood')
- `requirement_type`: Event type that triggers progress (e.g., 'enemy_kills')
- `requirement_value`: How many times event must occur
- `hidden`: Whether achievement is secret until unlocked
- `reward_gold`: Gold awarded on unlock

### `character_achievement` Table

Tracks each character's progress toward achievements.

```sql
CREATE TABLE character_achievement (
    id SERIAL PRIMARY KEY,
    character_id INTEGER NOT NULL REFERENCES character(id) ON DELETE CASCADE,
    achievement_id INTEGER NOT NULL REFERENCES achievement(id) ON DELETE CASCADE,
    progress INTEGER DEFAULT 0,
    unlocked BOOLEAN NOT NULL DEFAULT FALSE,
    unlocked_at TIMESTAMP,
    notified BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT unique_character_achievement UNIQUE (character_id, achievement_id)
);
```

### `achievement_category` Table

Organizes achievements into categories.

```sql
CREATE TABLE achievement_category (
    id SERIAL PRIMARY KEY,
    slug VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    icon VARCHAR(50),
    display_order INTEGER DEFAULT 0
);
```

## API Endpoints

### 1. Get All Achievements

```http
GET /api/achievements
```

**Response:**
```json
[
  {
    "id": 1,
    "slug": "first-blood",
    "name": "First Blood",
    "description": "Defeat your first enemy",
    "category": "combat",
    "icon": "sword-clash",
    "points": 10,
    "hidden": false,
    "requirement_type": "enemy_kills",
    "requirement_value": 1,
    "reward_gold": 50,
    "reward_items": []
  }
]
```

### 2. Get Achievement Categories

```http
GET /api/achievements/categories
```

**Response:**
```json
[
  {
    "slug": "combat",
    "name": "Combat",
    "description": "Achievements for defeating enemies and winning battles",
    "icon": "sword",
    "display_order": 1
  }
]
```

### 3. Get Character Achievements

```http
GET /api/characters/{character_id}/achievements
```

Returns all achievements with character's progress.

**Response:**
```json
[
  {
    "achievement_id": 1,
    "slug": "first-blood",
    "name": "First Blood",
    "progress": 1,
    "unlocked": true,
    "unlocked_at": "2025-12-07T10:30:00",
    "notified": true
  }
]
```

### 4. Get Achievement Stats

```http
GET /api/characters/{character_id}/achievements/stats
```

**Response:**
```json
{
  "total_achievements": 18,
  "unlocked": 3,
  "locked": 15,
  "total_points": 50,
  "completion_percent": 16.7
}
```

### 5. Check Achievement Progress

```http
POST /api/characters/{character_id}/achievements/check
Content-Type: application/json

{
  "event_type": "enemy_kills",
  "event_data": {
    "count": 1
  }
}
```

Updates progress for matching achievements and returns newly unlocked ones.

**Response:**
```json
{
  "checked": 3,
  "unlocked": [
    {
      "id": 1,
      "slug": "first-blood",
      "name": "First Blood",
      "description": "Defeat your first enemy",
      "icon": "sword-clash",
      "points": 10,
      "reward_gold": 50
    }
  ],
  "count": 1
}
```

### 6. Manually Update Progress

```http
POST /api/characters/{character_id}/achievements/progress
Content-Type: application/json

{
  "achievement_slug": "slayer",
  "progress": 1,
  "set": false
}
```

**Parameters:**
- `set`: If true, sets progress to value; if false, increments by value

### 7. Claim Achievement Reward

```http
POST /api/characters/{character_id}/achievements/{achievement_id}/claim
```

Manually claims reward (usually auto-claimed on unlock).

### 8. Get Achievement Details

```http
GET /api/achievements/{achievement_id}
```

Returns detailed achievement info including unlock count across all characters.

### 9. Get Recent Achievements

```http
GET /api/achievements/recent?limit=10
```

Returns recently unlocked achievements across all characters.

## Seeded Achievements

### Combat (4 achievements)

1. **First Blood** (10 points, 50 gold) - Defeat your first enemy
   - Type: `enemy_kills`, Value: 1

2. **Slayer** (25 points, 200 gold) - Defeat 25 enemies
   - Type: `enemy_kills`, Value: 25

3. **Executioner** (50 points, 500 gold) - Defeat 100 enemies
   - Type: `enemy_kills`, Value: 100

4. **Boss Hunter** (50 points, 1000 gold) - Defeat 5 boss enemies
   - Type: `boss_kills`, Value: 5

### Exploration (3 achievements)

5. **Explorer** (15 points, 100 gold) - Complete your first dungeon
   - Type: `dungeons_completed`, Value: 1

6. **Adventurer** (30 points, 300 gold) - Complete 10 dungeons
   - Type: `dungeons_completed`, Value: 10

7. **Dungeon Master** (100 points, 1500 gold) - Complete 50 dungeons
   - Type: `dungeons_completed`, Value: 50

### Progression (3 achievements)

8. **Level Up!** (15 points, 100 gold) - Reach level 5
   - Type: `level_reached`, Value: 5

9. **Veteran** (40 points, 500 gold) - Reach level 10
   - Type: `level_reached`, Value: 10

10. **Legendary** (100 points, 2000 gold) - Reach level 20
    - Type: `level_reached`, Value: 20

### Collection (3 achievements)

11. **Treasure Hunter** (20 points, 100 gold) - Collect 1000 gold
    - Type: `gold_earned`, Value: 1000

12. **Merchant Prince** (50 points, 1000 gold) - Collect 10000 gold
    - Type: `gold_earned`, Value: 10000

13. **Fully Equipped** (30 points, 250 gold) - Have all equipment slots filled
    - Type: `full_equipment`, Value: 1

### Social (2 achievements)

14. **Team Player** (10 points, 50 gold) - Join a party
    - Type: `party_joined`, Value: 1

15. **Generous Soul** (25 points, 200 gold) - Trade 10 items with merchants
    - Type: `trades_completed`, Value: 10

### Special (3 hidden achievements)

16. **Lucky Strike** (15 points, 100 gold, HIDDEN) - Get a critical hit
    - Type: `critical_hits`, Value: 1

17. **Survivor** (50 points, 500 gold, HIDDEN) - Win a battle with 1 HP remaining
    - Type: `survived_low_hp`, Value: 1

18. **Perfectionist** (75 points, 1000 gold, HIDDEN) - Complete a dungeon without taking damage
    - Type: `flawless_dungeon`, Value: 1

## Frontend Usage

### JavaScript API

```javascript
// Open achievement modal
achievementSystem.openAchievements(characterId);

// Check achievements after game event
achievementSystem.checkAchievements(characterId, 'enemy_kills', { count: 1 });

// Show achievement notification
achievementSystem.showNotification(achievement);

// Test in console
testAchievements(1);
```

### HTML Integration

Achievement button in sidebar:
```html
<button onclick="achievementSystem.openAchievements({{ character.id }})">
    <i class="bi bi-trophy-fill"></i> Achievements
</button>
```

## Visual Features

### Achievement Modal
- **Header**: Total points and unlock count
- **Category Tabs**: Filter by Combat, Exploration, etc.
- **Achievement Cards**: Show icon, name, description, progress
- **Progress Bars**: Visual progress toward unlock
- **Locked State**: Grayscale icons, reduced opacity
- **Unlocked State**: Green border, unlock badge, unlock date

### Achievement Card States
1. **Locked**: Gray icon, progress bar, requirements shown
2. **Unlocked**: Green highlight, "✓ Unlocked" badge, unlock date
3. **Hidden**: "???" name, locked icon, no details until unlocked

### Notification Toast
- Slides in from right when achievement unlocks
- Shows achievement icon, name, and rewards
- Auto-hides after 5 seconds
- Golden gradient background

## Integration Points

### Combat System
Hook achievement checks after combat:
```javascript
// After enemy defeated
await achievementSystem.checkAchievements(characterId, 'enemy_kills', { count: 1 });

// After boss defeated
if (enemy.is_boss) {
    await achievementSystem.checkAchievements(characterId, 'boss_kills', { count: 1 });
}

// On critical hit
await achievementSystem.checkAchievements(characterId, 'critical_hits', { count: 1 });
```

### Dungeon System
```javascript
// After dungeon complete
await achievementSystem.checkAchievements(characterId, 'dungeons_completed', { count: 1 });

// If no damage taken
if (damageTaken === 0) {
    await achievementSystem.checkAchievements(characterId, 'flawless_dungeon', { count: 1 });
}
```

### Trading System
```javascript
// After successful trade
await achievementSystem.checkAchievements(characterId, 'trades_completed', { count: 1 });
```

### Party System
```javascript
// When joining party
await achievementSystem.checkAchievements(characterId, 'party_joined', { count: 1 });
```

### Level Up
```javascript
// On level up
await achievementSystem.checkAchievements(characterId, 'level_reached', {
    count: 0,  // Don't increment, use set mode
    set: true,
    value: newLevel
});
```

### Gold Accumulation
Track total gold earned (not current gold):
```javascript
// Add stat tracking to character model
character.total_gold_earned += goldAmount;

// Check achievement
await achievementSystem.checkAchievements(characterId, 'gold_earned', {
    count: 0,
    set: true,
    value: character.total_gold_earned
});
```

## Migration Instructions

The migration is already executed. To re-run or verify:

```bash
cd /home/winter/work/Adventure
PGPASSWORD=changeme psql -h localhost -p 5433 -U adventure -d adventure -f sql/achievement_system_migration.sql
```

Verify with:
```sql
SELECT COUNT(*) FROM achievement;  -- Should return 18
SELECT COUNT(*) FROM achievement_category;  -- Should return 6
```

## Testing

### Test Achievement Modal
```javascript
// Open in browser console
testAchievements(1);
```

### Test Achievement Unlock
```bash
# In psql
INSERT INTO character_achievement (character_id, achievement_id, progress, unlocked, unlocked_at)
VALUES (1, 1, 1, true, NOW());
```

### Test Progress Update
```bash
curl -X POST http://localhost:5000/api/characters/1/achievements/check \
  -H "Content-Type: application/json" \
  -d '{"event_type": "enemy_kills", "event_data": {"count": 1}}'
```

### Test Notification
```javascript
achievementSystem.showNotification({
    name: "First Blood",
    icon: "sword-clash",
    points: 10,
    reward_gold: 50
});
```

## Future Enhancements

1. **Tiered Achievements**: Bronze/Silver/Gold ranks for same achievement
2. **Rare Achievements**: Ultra-rare accomplishments with special rewards
3. **Achievement Chains**: Unlock one to reveal next in series
4. **Seasonal Achievements**: Time-limited special achievements
5. **Leaderboards**: Compare achievement points with other players
6. **Title Rewards**: Unlock special titles to display
7. **Item Rewards**: Award unique items for rare achievements
8. **Achievement Sharing**: Share unlocks on party/guild chat
9. **Statistics Tracking**: Detailed stats page with all metrics
10. **Retroactive Checking**: Award achievements for past accomplishments

## Troubleshooting

### Achievements Not Loading
Check browser console for errors. Verify API endpoints:
```javascript
fetch('/api/achievements').then(r => r.json()).then(console.log);
```

### Progress Not Updating
Ensure `checkAchievements` is called after events:
```javascript
console.log('Checking achievements...');
await achievementSystem.checkAchievements(charId, 'enemy_kills', { count: 1 });
```

### Notification Not Showing
Check if notification element exists:
```javascript
console.log(document.getElementById('achievementNotification'));
```

### Rewards Not Granted
Check database:
```sql
SELECT * FROM character_achievement WHERE character_id = 1 AND unlocked = true;
SELECT gold FROM character WHERE id = 1;
```

## Files Reference

**Backend (403 lines total):**
- `/app/models/achievement.py` (107 lines) - 3 database models
- `/app/routes/achievement_api.py` (296 lines) - 9 API endpoints
- `/sql/achievement_system_migration.sql` (migration script)

**Frontend (1050+ lines total):**
- `/app/static/css/achievement-system.css` (550+ lines) - Complete modal styling
- `/app/static/js/achievement-system.js` (500+ lines) - Achievement system class

**Integration:**
- `/app/__init__.py` - Blueprint registration
- `/app/templates/dashboard_base.html` - CSS link
- `/app/templates/dashboard.html` - Button, modal, notification, script

## Summary

The Achievement System is production-ready with:
- ✅ 3 database tables with 18 seeded achievements
- ✅ 9 comprehensive API endpoints
- ✅ Complete visual UI with modal and notifications
- ✅ Progress tracking and automatic reward distribution
- ✅ Category filtering and hidden achievements
- ✅ Integration points for all game systems
- ✅ Real-time unlock notifications

Players can now track their accomplishments across combat, exploration, progression, collection, social activities, and unlock special hidden achievements!
