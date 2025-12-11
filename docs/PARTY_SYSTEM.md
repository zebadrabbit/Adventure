# Party Management System

Complete party management system with formations, shared inventory, member management, and party buffs.

## Features

### 1. Formation System
- **Drag-and-drop interface** for positioning party members
- **Three positions**: Front Line, Middle Line, Back Line
- **Visual formation preview** showing battle arrangement
- **Real-time updates** when members change positions
- **Role-based positioning** (tanks in front, mages in back, etc.)

### 2. Member Management
- **View all party members** with detailed stats
- **Change member roles**: Tank, DPS, Healer, Support
- **Remove members** from the party
- **View member equipment** and combat stats
- **Party leadership** management

### 3. Shared Inventory
- **Party treasury** for shared gold
- **Contribute/withdraw items** from personal inventory
- **Use consumables** from shared stock
- **Item quantity tracking**
- **Contributor attribution**

### 4. Party Buffs
- **Active buff display** with effect details
- **Multiple buff types**: Leadership, Synergy, Formation, Item
- **Duration tracking** with automatic expiration
- **Buff stacking** and effect calculations
- **Source attribution** (who/what granted the buff)

## Database Schema

### Party Table
```sql
CREATE TABLE party (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    leader_id INTEGER REFERENCES character(id),
    formation_json TEXT DEFAULT '{}',
    shared_gold INTEGER NOT NULL DEFAULT 0,
    party_level INTEGER DEFAULT 1,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_active TIMESTAMP
);
```

### Party Member Table
```sql
CREATE TABLE party_member (
    id SERIAL PRIMARY KEY,
    party_id INTEGER NOT NULL REFERENCES party(id) ON DELETE CASCADE,
    character_id INTEGER NOT NULL REFERENCES character(id) ON DELETE CASCADE,
    role VARCHAR(20) DEFAULT 'dps',
    position VARCHAR(20) DEFAULT 'middle',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    joined_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (party_id, character_id)
);
```

### Party Buff Table
```sql
CREATE TABLE party_buff (
    id SERIAL PRIMARY KEY,
    party_id INTEGER NOT NULL REFERENCES party(id) ON DELETE CASCADE,
    buff_type VARCHAR(30) NOT NULL,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    effect_json TEXT NOT NULL,
    duration INTEGER,
    expires_at TIMESTAMP,
    source VARCHAR(100),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

### Party Shared Inventory Table
```sql
CREATE TABLE party_shared_inventory (
    id SERIAL PRIMARY KEY,
    party_id INTEGER NOT NULL REFERENCES party(id) ON DELETE CASCADE,
    item_slug VARCHAR(100) NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 1,
    added_by INTEGER REFERENCES character(id),
    added_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (party_id, item_slug)
);
```

## API Endpoints

### Get Party Data
```
GET /api/party/{party_id}
```

**Response:**
```json
{
  "id": 1,
  "name": "Default Party",
  "leader_id": 1,
  "party_level": 3,
  "shared_gold": 150,
  "members": [
    {
      "character_id": 1,
      "character_name": "Thorin",
      "level": 5,
      "role": "tank",
      "position": "front",
      "stats": {"hp": 120, "damage": 15}
    }
  ],
  "formation": {},
  "is_active": true
}
```

### Update Member Position
```
PUT /api/party/{party_id}/member/{member_id}/position
```

**Body:**
```json
{
  "position": "front"  // or "middle", "back"
}
```

### Update Member Role
```
PUT /api/party/{party_id}/member/{member_id}/role
```

**Body:**
```json
{
  "role": "tank"  // or "dps", "healer", "support"
}
```

### Remove Party Member
```
DELETE /api/party/{party_id}/member/{member_id}
```

### Get Shared Inventory
```
GET /api/party/{party_id}/inventory
```

**Response:**
```json
{
  "party_id": 1,
  "shared_gold": 150,
  "items": [
    {
      "slug": "healing-potion",
      "name": "Healing Potion",
      "quantity": 5,
      "rarity": "common"
    }
  ]
}
```

### Contribute to Shared Inventory
```
POST /api/party/{party_id}/inventory/contribute
```

**Body:**
```json
{
  "character_id": 1,
  "item_slug": "healing-potion",
  "quantity": 3
}
```

### Take from Shared Inventory
```
POST /api/party/{party_id}/inventory/take
```

**Body:**
```json
{
  "character_id": 1,
  "item_slug": "healing-potion",
  "quantity": 1
}
```

### Use Shared Item
```
POST /api/party/{party_id}/inventory/use
```

**Body:**
```json
{
  "item_slug": "healing-potion"
}
```

### Get Party Buffs
```
GET /api/party/{party_id}/buffs
```

**Response:**
```json
[
  {
    "id": 1,
    "buff_type": "leadership",
    "name": "United Front",
    "description": "Party gains +5% damage",
    "effect_json": "{\"damage_bonus_percent\": 5}",
    "source": "default"
  }
]
```

### Add Party Buff
```
POST /api/party/{party_id}/buffs
```

**Body:**
```json
{
  "buff_type": "synergy",
  "name": "Tank & Spank",
  "description": "Warriors and mages gain +10% damage",
  "effects": {
    "damage_bonus_percent": 10,
    "applies_to": ["warrior", "mage"]
  },
  "source": "formation"
}
```

### Contribute Gold
```
POST /api/party/{party_id}/gold/contribute
```

**Body:**
```json
{
  "character_id": 1,
  "amount": 50
}
```

### Withdraw Gold
```
POST /api/party/{party_id}/gold/withdraw
```

**Body:**
```json
{
  "character_id": 1,
  "amount": 25
}
```

**Note:** Only party leader can withdraw gold by default.

## Frontend Usage

### JavaScript

```javascript
// Open party management modal
partySystem.openParty(1);

// Switch to specific tab
partySystem.switchTab('formation');  // or 'members', 'inventory', 'buffs'

// Change a member's role
partySystem.changeRole(characterId);

// Remove a member
partySystem.removeMember(characterId);

// Take an item from shared inventory
partySystem.takeItem('healing-potion');

// Use a shared item
partySystem.useItem('healing-potion');

// Testing helper
testParty(1);  // Opens party ID 1
```

### HTML Integration

Add button to open party modal:
```html
<button onclick="partySystem.openParty(1)">
    <i class="bi bi-people-fill"></i> Manage Party
</button>
```

## Formation System Details

### Positions
- **Front Line**: Tanks, melee fighters. First to engage enemies.
- **Middle Line**: Balanced fighters, supports. Secondary defense line.
- **Back Line**: Ranged attackers, casters. Protected position.

### Roles
- **Tank**: High HP, defense. Protects party members.
- **DPS**: High damage output. Primary damage dealers.
- **Healer**: Restores HP. Keeps party alive.
- **Support**: Buffs, debuffs, utility. Enhances party effectiveness.

### Drag-and-Drop
1. Click and drag a member card in the formation editor
2. Drop into a different position zone (front/middle/back)
3. Formation updates automatically
4. Visual preview updates in real-time

## Party Buffs System

### Buff Types

**Leadership Buffs**: Granted by party leader, based on their level/stats
- Example: "United Front" - +5% damage to all members

**Synergy Buffs**: Triggered by specific class combinations
- Example: "Warrior-Mage Synergy" - +10% damage when both present

**Formation Buffs**: Based on optimal positioning
- Example: "Shield Wall" - +15 defense when 3+ tanks in front line

**Item Buffs**: From consumables or equipment
- Example: "Battle Banner" - +10% XP for 1 hour

### Adding Custom Buffs

```python
from app.models.party import PartyBuff
import json

buff = PartyBuff(
    party_id=1,
    buff_type='custom',
    name='My Custom Buff',
    description='Does something awesome',
    effect_json=json.dumps({
        'damage_bonus_percent': 15,
        'hp_bonus': 20,
        'crit_chance_percent': 5
    }),
    duration=100,  # Game ticks
    source='quest-reward'
)
db.session.add(buff)
db.session.commit()
```

## Migration

Run the migration to set up all party tables:

```bash
cd /home/winter/work/Adventure
PGPASSWORD=changeme psql -U adventure -h localhost -p 5433 -d adventure -f sql/party_system_migration.sql
```

This creates:
- party table
- party_member table
- party_buff table
- party_shared_inventory table
- All necessary indexes
- Default party with all existing characters
- Starter leadership buff

## Testing

### 1. Open Party Modal
```javascript
testParty(1);
```

### 2. Test Formation Changes
1. Open party modal
2. Switch to "Formation" tab
3. Drag a member from one position to another
4. Verify the visual preview updates
5. Check database: `SELECT * FROM party_member;`

### 3. Test Shared Inventory
1. Switch to "Shared Inventory" tab
2. Contribute an item (need to implement contribute UI)
3. Verify item appears in shared list
4. Take an item back
5. Check database: `SELECT * FROM party_shared_inventory;`

### 4. Test Party Buffs
1. Switch to "Buffs" tab
2. Should see default "United Front" buff
3. Add more buffs via API
4. Verify they appear in the UI

### 5. Test Member Management
1. Switch to "Members" tab
2. Click "Change Role" on a member
3. Verify role cycles through: tank → dps → healer → support
4. Try removing a member
5. Check database: `SELECT * FROM party_member;`

## Future Enhancements

### Planned Features
- **Party invitations**: Players can invite others to their party
- **Voting system**: Democracy for major party decisions
- **Party quests**: Special multi-character missions
- **Formation templates**: Save/load favorite formations
- **Auto-formation**: AI suggests optimal positioning
- **Party chat**: In-game communication
- **Shared quest log**: Party-wide quest tracking
- **Loot distribution rules**: Automatic item assignment
- **Party achievements**: Unlocked as a group
- **Formation bonuses**: Stats based on positioning synergy

### Buff Enhancements
- **Stacking rules**: How multiple buffs interact
- **Buff conflicts**: Negative interactions
- **Conditional buffs**: Triggered by game events
- **Aura buffs**: Affect nearby party members
- **Timed buffs**: Duration in real-time vs game ticks

### Integration Points
- **Combat system**: Apply party buffs in battles
- **Quest system**: Party quest sharing
- **Trading system**: Party marketplace
- **Achievement system**: Group achievements
- **Dungeon system**: Party-wide exploration

## Troubleshooting

### Modal doesn't open
- Check console for errors
- Verify `partySystem` is defined: `console.log(partySystem)`
- Ensure JavaScript file is loaded: check Network tab
- Verify party ID exists in database

### Formation drag-and-drop not working
- Check browser console for JavaScript errors
- Verify drag event listeners are attached
- Test in different browser
- Check CSS for `pointer-events: none` conflicts

### API errors
- Check server logs: `tail -f instance/app.log.1`
- Verify party ID exists: `SELECT * FROM party;`
- Check character membership: `SELECT * FROM party_member WHERE party_id = 1;`
- Verify database connection

### Buffs not showing
- Check if buffs exist: `SELECT * FROM party_buff WHERE party_id = 1;`
- Verify buff expiration dates
- Check API response in Network tab
- Look for JSON parsing errors

## Configuration

No special configuration needed. System uses existing database connection and integrates with existing inventory/item systems.

## Dependencies

- Flask (backend framework)
- SQLAlchemy (ORM)
- PostgreSQL (database)
- Bootstrap Icons (UI icons)
- Existing inventory system (`app.inventory.utils`)

## Files

### Backend
- `/app/models/party.py` - Database models
- `/app/routes/party_api.py` - API endpoints

### Frontend
- `/app/static/css/party-management.css` - Styles
- `/app/static/js/party-management.js` - JavaScript logic
- `/app/templates/dashboard.html` - Modal HTML

### Database
- `/sql/party_system_migration.sql` - Setup script

### Documentation
- `/docs/PARTY_SYSTEM.md` - This file
