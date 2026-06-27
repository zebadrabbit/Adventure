# Trading & Economy System

Complete merchant shop system with buy/sell mechanics, gold currency, and transaction tracking.

## Features

### 💰 Currency Model

Two pools contribute to spending power at town merchants:

| Pool | Field | Risk |
|---|---|---|
| **Party gold** | `Character.gold` (summed across active party) | At-risk — lost on wipe, banked to Hoard on extraction |
| **Hoard copper** | `Hoard.copper` | Safe — never lost in a dungeon run |

**Buy and repair transactions debit party gold first, then Hoard copper** for any shortfall.
Sell proceeds always go to the Hoard.
`GET /api/hoard` returns both: `copper` (safe), `party_gold` (at-risk), and
`total_available` (combined) alongside `*_display` strings.

### 🏪 Merchant Shops
- **General Store**: Potions, tools, supplies
- **Weapon Smith**: Weapons and combat gear
- **Armor Smith**: Armor and shields

Each merchant has:
- Custom inventory (JSON-based)
- Price modifiers (buy/sell ratios)
- Stock tracking (optional limited quantities)
- Restock timers

### 📊 Buy/Sell Mechanics
- **Buy Price**: `base_price × buy_modifier` (default 1.0x)
- **Sell Price**: `base_price × sell_modifier` (default 0.5x)
- Quantity selector for bulk purchases
- Validation: insufficient gold, out of stock
- Real-time inventory updates

### 📝 Transaction History
- All trades logged to `trade_transaction` table
- Track character spending patterns
- Merchant sales analytics
- Audit trail for debugging

## Database Schema

### Character Table
```sql
ALTER TABLE character ADD COLUMN gold INTEGER NOT NULL DEFAULT 0;
```

### Merchant Table
```sql
CREATE TABLE merchant (
    id SERIAL PRIMARY KEY,
    slug VARCHAR(80) UNIQUE NOT NULL,
    name VARCHAR(120) NOT NULL,
    description TEXT,
    location VARCHAR(80) NOT NULL,
    merchant_type VARCHAR(40) NOT NULL,
    inventory_json TEXT NOT NULL,
    buy_price_modifier REAL NOT NULL DEFAULT 1.0,
    sell_price_modifier REAL NOT NULL DEFAULT 0.5,
    restocks_every_hours INTEGER NOT NULL DEFAULT 24,
    last_restock TIMESTAMP,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    sprite_icon VARCHAR(120),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

### MerchantStock Table
```sql
CREATE TABLE merchant_stock (
    id SERIAL PRIMARY KEY,
    merchant_id INTEGER REFERENCES merchant(id),
    item_slug VARCHAR(100) NOT NULL,
    current_stock INTEGER NOT NULL DEFAULT 0,
    max_stock INTEGER NOT NULL DEFAULT 10,
    UNIQUE(merchant_id, item_slug)
);
```

### TradeTransaction Table
```sql
CREATE TABLE trade_transaction (
    id SERIAL PRIMARY KEY,
    character_id INTEGER REFERENCES character(id),
    merchant_id INTEGER REFERENCES merchant(id),
    transaction_type VARCHAR(10) CHECK (type IN ('buy', 'sell')),
    item_slug VARCHAR(100) NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 1,
    price_per_item INTEGER NOT NULL,
    total_gold INTEGER NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## API Endpoints

### Get Merchant Details
```
GET /api/merchants/{slug}
```
Returns merchant info, inventory, and pricing.

**Response:**
```json
{
  "slug": "general-merchant",
  "name": "General Store",
  "type": "general",
  "icon": null,
  "buy_modifier": 1.0,
  "sell_modifier": 0.5,
  "inventory": [
    {
      "slug": "potion-healing",
      "name": "Healing Potion",
      "type": "potion",
      "base_price": 50,
      "stock": null
    }
  ]
}
```

### Get Character Gold
```
GET /api/characters/{id}/gold
```
Returns character's current gold balance.

### Buy Item
```
POST /api/trade/buy
```
Purchase item from merchant.

**Request:**
```json
{
  "character_id": 1,
  "merchant_slug": "general-merchant",
  "item_slug": "potion-healing",
  "quantity": 3
}
```

**Response:**
```json
{
  "success": true,
  "item": "potion-healing",
  "quantity": 3,
  "total_cost": 150,
  "total_cost_display": "1s 50c",
  "new_balance": 850,
  "new_balance_display": "8s 50c",
  "hoard_balance": 400,
  "hoard_balance_display": "4s"
}
```
`new_balance` = combined party gold + hoard copper after the transaction.
`hoard_balance` = safe hoard-only balance.

### Sell Item
```
POST /api/trade/sell
```
Sell item to merchant.

**Request:**
```json
{
  "character_id": 1,
  "merchant_slug": "general-merchant",
  "item_slug": "dagger",
  "quantity": 1
}
```

**Response:**
```json
{
  "success": true,
  "item": "dagger",
  "quantity": 1,
  "total_value": 10,
  "new_gold": 860
}
```

### Get Character Inventory (for trading)
```
GET /api/characters/{id}/inventory
```
Returns inventory items with pricing info for selling.

## Frontend Components

### TradingSystem Class (`trading-system.js`)

**Initialization:**
```javascript
const tradingSystem = new TradingSystem();
```

**Open Merchant Shop:**
```javascript
tradingSystem.openMerchant('general-merchant', characterId);
```

**Test in Console:**
```javascript
testShop('general-merchant', 1);
```

### UI Components

1. **Merchant Shop Modal**
   - Portrait/icon display
   - Gold balance header
   - Buy/Sell tabs
   - Item grid with pricing

2. **Trade Confirmation Dialog**
   - Item preview
   - Quantity selector
   - Total cost calculator
   - Confirm/Cancel buttons

3. **Toast Notifications**
   - Success: Green with checkmark
   - Error: Red with X icon
   - Auto-dismiss after 4 seconds

### CSS Classes

- `.merchant-shop-modal` - Main shop container
- `.shop-tabs` - Buy/Sell tab switcher
- `.shop-items-grid` - Item display grid
- `.shop-item-card` - Individual item card
- `.trade-confirm-dialog` - Confirmation overlay
- `.trade-toast` - Notification toast

## Usage Examples

### Opening a Shop from Dashboard
```html
<button onclick="tradingSystem.openMerchant('weapon-shop', {{ character.id }})">
  Visit Weapon Smith
</button>
```

### Custom Event Integration
```javascript
// Listen for trade completion
document.addEventListener('trade-complete', (e) => {
  console.log('Traded:', e.detail);
  // { type: 'buy', item: 'sword', quantity: 1, gold: 850 }
});
```

### Adding New Merchant
```sql
INSERT INTO merchant (
  slug, name, description, location, merchant_type,
  inventory_json, buy_price_modifier, sell_price_modifier,
  restocks_every_hours, is_active, created_at
) VALUES (
  'potion-vendor',
  'Alchemist''s Shop',
  'Rare potions and elixirs',
  'town-square',
  'potions',
  '[{"slug":"potion-greater-healing","name":"Greater Healing","type":"potion","price":100}]',
  1.2,
  0.4,
  12,
  true,
  CURRENT_TIMESTAMP
);
```

## Configuration

### Price Modifiers
- **Buy Modifier**: How much player pays (1.0 = base price, 1.5 = 50% markup)
- **Sell Modifier**: How much player receives (0.5 = 50% of value, 0.8 = 80%)

### Stock Management
- `null` stock = unlimited
- Limited stock tracked in `merchant_stock` table
- Automatic restocking based on `restocks_every_hours`

## Migration Script

Run the migration to set up all tables:
```bash
PGPASSWORD=changeme psql -h localhost -p 5433 -U adventure -d adventure -f sql/trading_system_migration.sql
```

Give existing characters starting gold:
```sql
UPDATE character SET gold = 100 WHERE gold = 0;
```

## Testing

### Browser Console Tests
```javascript
// Test general store
testShop('general-merchant', 1);

// Test buying
tradingSystem.openMerchant('weapon-shop', 1);
// Click Buy tab, select item, confirm purchase

// Check gold balance
fetch('/api/characters/1/gold').then(r => r.json()).then(console.log);
```

### Database Verification
```sql
-- Check merchants
SELECT slug, name, merchant_type FROM merchant;

-- Check character gold
SELECT name, gold FROM character;

-- View transaction history
SELECT * FROM trade_transaction ORDER BY timestamp DESC LIMIT 10;
```

## Future Enhancements

- [ ] Dynamic pricing based on supply/demand
- [ ] Merchant reputation system
- [ ] Bulk discount pricing
- [ ] Trade agreements/contracts
- [ ] Black market merchants
- [ ] Item crafting at merchants
- [ ] Merchant quest integration
- [ ] Regional price variations

## Files Modified/Created

**Backend:**
- `/app/models/merchant.py` - Merchant models
- `/app/routes/trading_api.py` - Trading API endpoints
- `/app/__init__.py` - Blueprint registration
- `/app/models/models.py` - Added gold to Character

**Frontend:**
- `/app/static/css/trading-system.css` - Shop UI styling
- `/app/static/js/trading-system.js` - Trading logic
- `/app/templates/dashboard_base.html` - CSS include
- `/app/templates/dashboard.html` - JS include + merchant buttons

**Database:**
- `/sql/trading_system_migration.sql` - Complete migration script

## License

MIT (same as Adventure project)
