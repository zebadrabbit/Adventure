-- Trading System Database Migration
-- Adds gold to Character table and creates Merchant tables

-- Step 1: Add gold column to Character table
ALTER TABLE character ADD COLUMN IF NOT EXISTS gold INTEGER NOT NULL DEFAULT 0;

-- Step 2: Create Merchant table
CREATE TABLE IF NOT EXISTS merchant (
    id SERIAL PRIMARY KEY,
    slug VARCHAR(100) UNIQUE NOT NULL,
    name VARCHAR(200) NOT NULL,
    merchant_type VARCHAR(50) DEFAULT 'general',
    icon TEXT,
    inventory_json TEXT NOT NULL DEFAULT '[]',
    buy_price_modifier REAL NOT NULL DEFAULT 1.0,
    sell_price_modifier REAL NOT NULL DEFAULT 0.5,
    last_restock TIMESTAMP,
    restock_interval_hours INTEGER DEFAULT 24,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Step 3: Create MerchantStock table for limited inventory tracking
CREATE TABLE IF NOT EXISTS merchant_stock (
    id SERIAL PRIMARY KEY,
    merchant_id INTEGER NOT NULL REFERENCES merchant(id) ON DELETE CASCADE,
    item_slug VARCHAR(100) NOT NULL,
    current_stock INTEGER NOT NULL DEFAULT 0,
    max_stock INTEGER NOT NULL DEFAULT 10,
    UNIQUE(merchant_id, item_slug)
);

-- Step 4: Create TradeTransaction table for history
CREATE TABLE IF NOT EXISTS trade_transaction (
    id SERIAL PRIMARY KEY,
    character_id INTEGER NOT NULL REFERENCES character(id) ON DELETE CASCADE,
    merchant_id INTEGER NOT NULL REFERENCES merchant(id) ON DELETE CASCADE,
    transaction_type VARCHAR(10) NOT NULL CHECK (transaction_type IN ('buy', 'sell')),
    item_slug VARCHAR(100) NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 1,
    price_per_item INTEGER NOT NULL,
    total_gold INTEGER NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Step 5: Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_merchant_stock_merchant ON merchant_stock(merchant_id);
CREATE INDEX IF NOT EXISTS idx_trade_transaction_character ON trade_transaction(character_id);
CREATE INDEX IF NOT EXISTS idx_trade_transaction_merchant ON trade_transaction(merchant_id);

-- Step 6: Seed starter merchants (optional - can be done separately)
INSERT INTO merchant (slug, name, description, location, merchant_type, inventory_json, buy_price_modifier, sell_price_modifier, restocks_every_hours, is_active, created_at)
VALUES
('general-merchant', 'General Store', 'A well-stocked general store with everyday supplies', 'town-square', 'general',
 '[{"slug":"potion-healing","name":"Healing Potion","type":"potion","price":50},{"slug":"potion-mana","name":"Mana Potion","type":"potion","price":50},{"slug":"rations","name":"Rations","type":"misc","price":10},{"slug":"rope","name":"Rope (50ft)","type":"tool","price":15},{"slug":"torch","name":"Torch","type":"tool","price":5}]',
 1.0, 0.5, 24, true, CURRENT_TIMESTAMP),
('weapon-shop', 'Weapon Smith', 'Fine weapons crafted by a master smith', 'town-square', 'weapons',
 '[{"slug":"dagger","name":"Dagger","type":"weapon","price":20},{"slug":"shortsword","name":"Shortsword","type":"weapon","price":100},{"slug":"longsword","name":"Longsword","type":"weapon","price":150},{"slug":"battleaxe","name":"Battleaxe","type":"weapon","price":200}]',
 1.1, 0.4, 48, true, CURRENT_TIMESTAMP),
('armor-shop', 'Armor Smith', 'Quality armor and shields for protection', 'town-square', 'armor',
 '[{"slug":"leather-armor","name":"Leather Armor","type":"armor","price":50},{"slug":"chainmail","name":"Chainmail","type":"armor","price":750},{"slug":"plate-armor","name":"Plate Armor","type":"armor","price":1500}]',
 1.1, 0.4, 48, true, CURRENT_TIMESTAMP)
ON CONFLICT (slug) DO NOTHING;
