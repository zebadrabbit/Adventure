# Trading UI: Repoint to Hoard + Repair Tab Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Repoint the merchant shop modal's Buy/Sell tabs from character gold/inventory to the
per-user Hoard, and add a new Repair tab — all using existing backend endpoints, no backend
changes.

**Architecture:** All changes are in one file, `app/static/js/trading-system.js` (a single
`TradingSystem` class instantiated once per page), plus a one-line export addition in
`app/static/js/tooltips.js` (to share its rarity-class helper) and a small CSS addition in
`app/static/css/trading-system.css`. No Python/template changes.

**Tech Stack:** Vanilla JS (ES6 class), Bootstrap 5 modal, Flask JSON APIs already in place
(`GET /api/hoard`, `GET /api/characters/state`, `POST /api/trade/buy|sell|repair`).

## Global Constraints

- No backend or template changes — this plan is frontend-only (per spec).
- All money must render through the backend's `*_display` strings (`copper_display`,
  `new_balance_display`, `cost_display`), never hand-rolled from raw copper ints.
- Reuse existing CSS conventions: rarity color classes (`.rarity-common` … `.rarity-mythic`
  from `equipment.css`, already loaded on the dashboard page) and the durability bar classes
  (`.durability-bar` / `.durability-fill.high|medium|low`, also from `equipment.css`). Do not
  invent new selectors for these.
- Verification is manual via a live browser (this repo's frontend has no JS test runner) —
  use the `run`/`verify` skills, not automated test commands. Each task also gets a
  `node --check` syntax-validation step, which **is** automatable.
- Spec reference: `docs/superpowers/specs/2026-06-17-trading-hoard-repair-ui-design.md`.

---

## File Structure

- **Modify `app/static/js/tooltips.js`** — export the existing internal `rarityClass`
  helper on `window.MUDTooltips` so `trading-system.js` can reuse it instead of
  re-implementing the rarity→CSS-class mapping.
- **Modify `app/static/js/trading-system.js`** — the entire scope of this plan:
  - Header/balance now sourced from the hoard (Task 1).
  - Sell tab sourced from the hoard, supporting both stackable items and gear instances
    (Task 2).
  - New Repair tab (Task 3).
- **Modify `app/static/css/trading-system.css`** — small additions for the Repair tab's
  card layout (Task 3, folded in since it's a tiny, inseparable part of that deliverable).

---

### Task 1: Repoint header balance + Buy tab to the hoard

**Files:**
- Modify: `app/static/js/trading-system.js:24-35` (constructor), `:49-93` (header markup in
  `createShopModal`), `:148-185` (`openMerchant`, `renderMerchantShop`), `:202-233`
  (`renderBuyTab`), `:279-305` (`startBuy`), `:319-351` (`showTradeConfirm`), `:353-369`
  (`adjustQuantity`), `:382-443` (`executeTrade`)

**Interfaces:**
- Produces: `TradingSystem.hoardCopper` (number, current hoard copper — replaces the old
  `characterGold`), `TradingSystem.hoardCopperDisplay` (string, e.g. `"3g 12s 4c"`),
  `TradingSystem.hoardItems` (array, raw `GET /api/hoard` `items` list — populated here,
  consumed by Task 2 and Task 3), `TradingSystem.refreshHoard()` (async, no args, populates
  the three fields above from `GET /api/hoard`).

- [ ] **Step 1: Replace the constructor's gold field with hoard fields**

In `app/static/js/trading-system.js`, replace:

```javascript
        this.shopModal = null;
        this.confirmDialog = null;
        this.currentMerchant = null;
        this.currentCharacter = null;
        this.characterGold = 0;
        this.currentTab = 'buy';
        this.pendingTrade = null;
```

with:

```javascript
        this.shopModal = null;
        this.confirmDialog = null;
        this.currentMerchant = null;
        this.currentCharacter = null;
        this.hoardCopper = 0;
        this.hoardCopperDisplay = '0c';
        this.hoardItems = [];
        this.currentTab = 'buy';
        this.pendingTrade = null;
```

- [ ] **Step 2: Update the header markup's id/label**

In `createShopModal()`, replace:

```javascript
                <div class="character-gold">
                    <i class="bi bi-coin gold-icon"></i>
                    <div>
                        <div class="gold-amount" id="character-gold-amount">0</div>
                        <div class="gold-label">Gold</div>
                    </div>
                </div>
```

with:

```javascript
                <div class="character-gold">
                    <i class="bi bi-coin gold-icon"></i>
                    <div>
                        <div class="gold-amount" id="hoard-copper-amount">0c</div>
                        <div class="gold-label">Hoard</div>
                    </div>
                </div>
```

- [ ] **Step 3: Replace the per-character gold fetch in `openMerchant` with a hoard fetch**

Replace:

```javascript
    async openMerchant(merchantSlug, characterId) {
        this.currentCharacter = characterId;

        try {
            // Load merchant data
            const merchantResponse = await fetch(`/api/merchants/${merchantSlug}`);
            if (!merchantResponse.ok) {
                this.showToast('Error', 'Merchant not found', 'error');
                return;
            }

            this.currentMerchant = await merchantResponse.json();

            // Load character gold
            const goldResponse = await fetch(`/api/characters/${characterId}/gold`);
            if (goldResponse.ok) {
                const goldData = await goldResponse.json();
                this.characterGold = goldData.gold || 0;
            }

            this.renderMerchantShop();
            this.shopModal.show();

        } catch (err) {
            console.error('[trading] Failed to open merchant:', err);
            this.showToast('Error', 'Failed to load shop', 'error');
        }
    }
```

with:

```javascript
    async openMerchant(merchantSlug, characterId) {
        this.currentCharacter = characterId;

        try {
            // Load merchant data
            const merchantResponse = await fetch(`/api/merchants/${merchantSlug}`);
            if (!merchantResponse.ok) {
                this.showToast('Error', 'Merchant not found', 'error');
                return;
            }

            this.currentMerchant = await merchantResponse.json();

            await this.refreshHoard();

            this.renderMerchantShop();
            this.shopModal.show();

        } catch (err) {
            console.error('[trading] Failed to open merchant:', err);
            this.showToast('Error', 'Failed to load shop', 'error');
        }
    }

    async refreshHoard() {
        const hoardResponse = await fetch('/api/hoard');
        if (hoardResponse.ok) {
            const hoardData = await hoardResponse.json();
            this.hoardCopper = hoardData.copper || 0;
            this.hoardCopperDisplay = hoardData.copper_display || `${this.hoardCopper}c`;
            this.hoardItems = hoardData.items || [];
        }
    }
```

- [ ] **Step 4: Render the hoard display string in the header**

In `renderMerchantShop()`, replace:

```javascript
        document.getElementById('character-gold-amount').textContent = this.characterGold.toLocaleString();
```

with:

```javascript
        document.getElementById('hoard-copper-amount').textContent = this.hoardCopperDisplay;
```

- [ ] **Step 5: Repoint the Buy tab's afford-check to hoard copper**

In `renderBuyTab()`, replace:

```javascript
            const canAfford = this.characterGold >= buyPrice;
```

with:

```javascript
            const canAfford = this.hoardCopper >= buyPrice;
```

- [ ] **Step 6: Repoint `startBuy`'s max-quantity and afford-check to hoard copper**

In `startBuy(itemSlug)`, replace:

```javascript
        const maxQty = item.stock !== null ? item.stock : Math.floor(this.characterGold / buyPrice);

        if (item.stock !== null && item.stock === 0) {
            this.showToast('Out of Stock', 'This item is currently unavailable', 'error');
            return;
        }

        if (buyPrice > this.characterGold) {
```

with:

```javascript
        const maxQty = item.stock !== null ? item.stock : Math.floor(this.hoardCopper / buyPrice);

        if (item.stock !== null && item.stock === 0) {
            this.showToast('Out of Stock', 'This item is currently unavailable', 'error');
            return;
        }

        if (buyPrice > this.hoardCopper) {
```

- [ ] **Step 7: Repoint the quantity-stepper's afford-check in `showTradeConfirm`**

Replace:

```javascript
        document.getElementById('qty-increase').disabled = quantity >= maxQuantity || (type === 'buy' && (unitPrice * (quantity + 1)) > this.characterGold);
```

with:

```javascript
        document.getElementById('qty-increase').disabled = quantity >= maxQuantity || (type === 'buy' && (unitPrice * (quantity + 1)) > this.hoardCopper);
```

- [ ] **Step 8: Repoint `adjustQuantity`'s afford-check**

Replace:

```javascript
        // Check if can afford
        if (this.pendingTrade.type === 'buy') {
            const totalCost = this.pendingTrade.unitPrice * newQty;
            if (totalCost > this.characterGold) return;
        }
```

with:

```javascript
        // Check if can afford
        if (this.pendingTrade.type === 'buy') {
            const totalCost = this.pendingTrade.unitPrice * newQty;
            if (totalCost > this.hoardCopper) return;
        }
```

- [ ] **Step 9: Repoint the post-trade balance update in `executeTrade`**

Replace:

```javascript
            // Update gold
            this.characterGold = result.new_balance;
            document.getElementById('character-gold-amount').textContent = this.characterGold.toLocaleString();
```

with:

```javascript
            // Update hoard copper
            this.hoardCopper = result.new_balance;
            this.hoardCopperDisplay = result.new_balance_display || `${this.hoardCopper}c`;
            document.getElementById('hoard-copper-amount').textContent = this.hoardCopperDisplay;
```

- [ ] **Step 10: Update the event-dispatch field name for consistency**

Still in `executeTrade`, replace:

```javascript
            // Fire event
            document.dispatchEvent(new CustomEvent('trade-complete', {
                detail: { type, item: slug, quantity, gold: this.characterGold }
            }));
```

with:

```javascript
            // Fire event
            document.dispatchEvent(new CustomEvent('trade-complete', {
                detail: { type, item: slug, quantity, copper: this.hoardCopper }
            }));
```

- [ ] **Step 11: Syntax-check the file**

Run: `node --check app/static/js/trading-system.js`
Expected: no output (exit code 0).

- [ ] **Step 12: Manual verification (Buy tab + header)**

Use the `run` skill to start the app, log in as a user with hoard copper and at least one
character. Open a merchant (`window.tradingSystem.openMerchant('general-merchant', <id>)` in
devtools console, or click the in-game vendor trigger). Confirm:
- The header shows a 3-tier copper string (e.g. `"2g 14s 6c"`), not a bare integer.
- Buying an affordable item succeeds and the header balance decreases by the correct amount.
- Buying an item costing more than the hoard balance is blocked (greyed card / toast).

- [ ] **Step 13: Commit**

```bash
git add app/static/js/trading-system.js
git commit -m "feat(trading-ui): repoint shop header and buy flow to the hoard"
```

---

### Task 2: Repoint the Sell tab to the hoard (stackables + gear instances)

**Files:**
- Modify: `app/static/js/tooltips.js:209` (export `rarityClass`)
- Modify: `app/static/js/trading-system.js:235-277` (`renderSellTab`), `:307-317`
  (`startSell`), `:382-443` (`executeTrade` request-body assembly and item-name resolution)

**Interfaces:**
- Consumes: `TradingSystem.hoardItems` and `TradingSystem.refreshHoard()` (Task 1).
- Produces: `TradingSystem.renderSellStackableCard(item, catalogEntry)`,
  `TradingSystem.renderSellInstanceCard(item)`, `TradingSystem.durabilityBarHtml(item)`,
  `TradingSystem.startSell(opts)` where `opts` is either
  `{slug, name, type, basePrice, qty}` (stackable) or `{uid, name, value}` (instance) —
  consumed by Task 3's repair cards reusing `durabilityBarHtml`.

- [ ] **Step 1: Export `rarityClass` from tooltips.js**

In `app/static/js/tooltips.js`, replace:

```javascript
  window.MUDTooltips = { attrForItem, apply, itemHtml, getMode, setMode, cycleMode };
```

with:

```javascript
  window.MUDTooltips = { attrForItem, apply, itemHtml, getMode, setMode, cycleMode, rarityClass };
```

- [ ] **Step 2: Replace `renderSellTab` and the old `startSell` with hoard-driven versions**

Replace the entire `renderSellTab` method:

```javascript
    async renderSellTab() {
        const grid = document.getElementById('shop-items-grid');

        try {
            // Get character inventory
            const response = await fetch(`/api/characters/${this.currentCharacter}/inventory`);
            if (!response.ok) {
                grid.innerHTML = '<div class="text-center text-muted py-5">Failed to load inventory</div>';
                return;
            }

            const data = await response.json();
            const inventory = data.items || [];

            if (inventory.length === 0) {
                grid.innerHTML = '<div class="text-center text-muted py-5">No items to sell</div>';
                return;
            }

            const html = inventory.map(item => {
                const sellPrice = Math.floor(item.base_price * this.currentMerchant.sell_modifier);

                return `
<div class="shop-item-card sell-item-card" onclick="tradingSystem.startSell('${item.slug}')">
    <div class="shop-item-icon-wrapper">
        ${this.getItemIcon(item.type)}
        ${item.quantity > 1 ? `<div class="item-quantity-badge">×${item.quantity}</div>` : ''}
    </div>
    <div class="shop-item-name">${item.name}</div>
    <div class="shop-item-price sell-price-display">
        <i class="bi bi-coin price-icon"></i>
        <span class="price-amount">${sellPrice.toLocaleString()}</span>
    </div>
</div>`;
            }).join('');

            grid.innerHTML = html;

        } catch (err) {
            console.error('[trading] Failed to load inventory:', err);
            grid.innerHTML = '<div class="text-center text-muted py-5">Failed to load inventory</div>';
        }
    }
```

with:

```javascript
    async renderSellTab() {
        const grid = document.getElementById('shop-items-grid');

        await this.refreshHoard();

        // Stackables are priced via the merchant's own catalog (Item.value_copper isn't
        // exposed to the frontend), so only stackables this merchant actually deals in are
        // sellable here. Gear instances are always sellable (priced by their own `value`).
        const catalogBySlug = {};
        (this.currentMerchant.inventory || []).forEach(i => { catalogBySlug[i.slug] = i; });

        const sellable = this.hoardItems.filter(item => item.uid || catalogBySlug[item.slug]);

        if (sellable.length === 0) {
            grid.innerHTML = '<div class="text-center text-muted py-5">No items to sell</div>';
            return;
        }

        const html = sellable.map(item => {
            if (item.uid) {
                return this.renderSellInstanceCard(item);
            }
            return this.renderSellStackableCard(item, catalogBySlug[item.slug]);
        }).join('');

        grid.innerHTML = html;
    }

    renderSellStackableCard(item, catalogEntry) {
        const sellPrice = Math.floor((catalogEntry.base_price || 0) * this.currentMerchant.sell_modifier);
        const safeName = (catalogEntry.name || item.slug).replace(/'/g, "\\'");
        return `
<div class="shop-item-card sell-item-card" onclick="tradingSystem.startSell({slug: '${item.slug}', name: '${safeName}', type: '${catalogEntry.type}', basePrice: ${catalogEntry.base_price || 0}, qty: ${item.qty || 1}})">
    <div class="shop-item-icon-wrapper">
        ${this.getItemIcon(catalogEntry.type)}
        ${item.qty > 1 ? `<div class="item-quantity-badge">×${item.qty}</div>` : ''}
    </div>
    <div class="shop-item-name">${catalogEntry.name}</div>
    <div class="shop-item-price sell-price-display">
        <i class="bi bi-coin price-icon"></i>
        <span class="price-amount">${sellPrice.toLocaleString()}</span>
    </div>
</div>`;
    }

    renderSellInstanceCard(item) {
        const sellPrice = Math.floor((item.value || 0) * this.currentMerchant.sell_modifier);
        const rarity = window.MUDTooltips ? window.MUDTooltips.rarityClass(item.rarity) : 'rarity-common';
        const safeName = (item.name || item.slug || 'Item').replace(/'/g, "\\'");
        return `
<div class="shop-item-card sell-item-card" onclick="tradingSystem.startSell({uid: '${item.uid}', name: '${safeName}', value: ${item.value || 0}})">
    <div class="shop-item-icon-wrapper">
        ${this.getItemIcon(item.type)}
    </div>
    <div class="shop-item-name ${rarity}">${item.name || item.slug}</div>
    ${this.durabilityBarHtml(item)}
    <div class="shop-item-price sell-price-display">
        <i class="bi bi-coin price-icon"></i>
        <span class="price-amount">${sellPrice.toLocaleString()}</span>
    </div>
</div>`;
    }

    durabilityBarHtml(item) {
        if (item.durability == null || !item.max_durability) return '';
        const pct = Math.max(0, Math.min(100, (item.durability / item.max_durability) * 100));
        const tier = pct > 60 ? 'high' : pct > 25 ? 'medium' : 'low';
        return `<div class="durability-bar"><div class="durability-fill ${tier}" style="width: ${pct}%"></div></div>`;
    }
```

Then replace the old `startSell`:

```javascript
    startSell(itemSlug) {
        // Would need to get item details from inventory
        this.pendingTrade = {
            type: 'sell',
            itemSlug: itemSlug,
            quantity: 1
        };

        // For now, confirm directly
        this.executeTrade();
    }
```

with:

```javascript
    startSell(opts) {
        if (opts.uid) {
            const sellPrice = Math.floor((opts.value || 0) * this.currentMerchant.sell_modifier);
            this.pendingTrade = {
                type: 'sell',
                kind: 'instance',
                uid: opts.uid,
                item: { name: opts.name, type: 'gear' },
                unitPrice: sellPrice,
                quantity: 1,
                maxQuantity: 1
            };
        } else {
            const sellPrice = Math.floor((opts.basePrice || 0) * this.currentMerchant.sell_modifier);
            this.pendingTrade = {
                type: 'sell',
                kind: 'stackable',
                slug: opts.slug,
                item: { name: opts.name, type: opts.type },
                unitPrice: sellPrice,
                quantity: 1,
                maxQuantity: opts.qty || 1
            };
        }

        this.showTradeConfirm();
    }
```

- [ ] **Step 3: Run, then verify it still fails for the next step (sanity check on diff scope)**

Run: `node --check app/static/js/trading-system.js`
Expected: no output (exit code 0) — this confirms the replacement is syntactically valid
before wiring `executeTrade`, which still references the old `slug`-only sell body and will
send the wrong payload for instance sells until Step 4.

- [ ] **Step 4: Fix `executeTrade`'s request body and item-name resolution for sell**

Replace:

```javascript
    async executeTrade() {
        if (!this.pendingTrade) return;

        const { type, item, itemSlug, quantity, unitPrice } = this.pendingTrade;
        const slug = item ? item.slug : itemSlug;

        try {
            const endpoint = type === 'buy' ? '/api/trade/buy' : '/api/trade/sell';
            const response = await fetch(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    character_id: this.currentCharacter,
                    merchant_slug: this.currentMerchant.slug,
                    item_slug: slug,
                    quantity: quantity
                })
            });
```

with:

```javascript
    async executeTrade() {
        if (!this.pendingTrade) return;

        const { type, item, slug, uid, kind, quantity, unitPrice } = this.pendingTrade;

        try {
            const endpoint = type === 'buy' ? '/api/trade/buy' : '/api/trade/sell';
            const body = {
                character_id: this.currentCharacter,
                merchant_slug: this.currentMerchant.slug,
                quantity: quantity
            };
            if (type === 'buy') {
                body.item_slug = item.slug;
            } else if (kind === 'instance') {
                body.uid = uid;
            } else {
                body.item_slug = slug;
            }

            const response = await fetch(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            });
```

Then, further down in the same method, replace:

```javascript
            // Show success
            const itemName = item ? item.name : slug;
```

with:

```javascript
            // Show success
            const itemName = item ? item.name : (slug || uid);
```

And replace the merchant-inventory-refresh-then-tab-switch tail:

```javascript
            // Reload merchant inventory
            const merchantResponse = await fetch(`/api/merchants/${this.currentMerchant.slug}`);
            if (merchantResponse.ok) {
                this.currentMerchant = await merchantResponse.json();
            }

            this.switchTab(this.currentTab);
```

with (unchanged — confirm it reads exactly this; `renderSellTab` now refetches the hoard
itself via `refreshHoard()`, so no extra hoard fetch is needed here):

```javascript
            // Reload merchant inventory
            const merchantResponse = await fetch(`/api/merchants/${this.currentMerchant.slug}`);
            if (merchantResponse.ok) {
                this.currentMerchant = await merchantResponse.json();
            }

            this.switchTab(this.currentTab);
```

(No change needed for that tail block — it already re-renders the current tab, which for
`sell` re-fetches the hoard and shows the updated item list.)

- [ ] **Step 5: Syntax-check the file**

Run: `node --check app/static/js/trading-system.js`
Expected: no output (exit code 0).

- [ ] **Step 6: Manual verification (Sell tab)**

With the app running (from Task 1's `run` session), open a merchant for a character whose
hoard has both a stackable item the merchant deals in and at least one gear instance
(generate one via a dungeon run, or seed one). Switch to Sell. Confirm:
- Stackable items show name, quantity badge (if >1), and a sell price.
- Gear instances show their rarity-colored name and a durability bar (high/medium/low color
  matching their current durability).
- Selling either kind succeeds, removes the item from the list, and the header balance
  increases by the correct amount.
- A hoard stackable the current merchant doesn't deal in is correctly omitted from the list
  (sanity-check the filter).

- [ ] **Step 7: Commit**

```bash
git add app/static/js/tooltips.js app/static/js/trading-system.js
git commit -m "feat(trading-ui): repoint sell tab to the hoard, support gear instances"
```

---

### Task 3: Add the Repair tab

**Files:**
- Modify: `app/static/js/trading-system.js:71-78` (tab markup in `createShopModal`),
  `:187-200` (`switchTab`)
- Modify: `app/static/css/trading-system.css` (new rules after the existing
  `.item-quantity-badge` block, before `/* Trade Confirmation Modal */`)

**Interfaces:**
- Consumes: `TradingSystem.refreshHoard()`, `TradingSystem.hoardItems`,
  `TradingSystem.durabilityBarHtml(item)`, `TradingSystem.getItemIcon(type)`,
  `TradingSystem.showToast(title, message, type)` — all from Tasks 1–2.
- Produces: `TradingSystem.renderRepairTab()`, `TradingSystem.renderRepairCard(instance,
  source)`, `TradingSystem.repairItem(uid)`.

- [ ] **Step 1: Add the Repair tab button**

In `createShopModal()`, replace:

```javascript
            <div class="shop-tabs">
                <div class="shop-tab active" data-tab="buy" onclick="tradingSystem.switchTab('buy')">
                    <i class="bi bi-cart-plus me-2"></i>Buy
                </div>
                <div class="shop-tab" data-tab="sell" onclick="tradingSystem.switchTab('sell')">
                    <i class="bi bi-cash-coin me-2"></i>Sell
                </div>
            </div>
```

with:

```javascript
            <div class="shop-tabs">
                <div class="shop-tab active" data-tab="buy" onclick="tradingSystem.switchTab('buy')">
                    <i class="bi bi-cart-plus me-2"></i>Buy
                </div>
                <div class="shop-tab" data-tab="sell" onclick="tradingSystem.switchTab('sell')">
                    <i class="bi bi-cash-coin me-2"></i>Sell
                </div>
                <div class="shop-tab" data-tab="repair" onclick="tradingSystem.switchTab('repair')">
                    <i class="bi bi-hammer me-2"></i>Repair
                </div>
            </div>
```

- [ ] **Step 2: Wire the tab into `switchTab`**

Replace:

```javascript
        if (tab === 'buy') {
            this.renderBuyTab();
        } else if (tab === 'sell') {
            this.renderSellTab();
        }
    }
```

with:

```javascript
        if (tab === 'buy') {
            this.renderBuyTab();
        } else if (tab === 'sell') {
            this.renderSellTab();
        } else if (tab === 'repair') {
            this.renderRepairTab();
        }
    }
```

- [ ] **Step 3: Add `renderRepairTab`, `renderRepairCard`, and `repairItem`**

Insert these three methods immediately after `renderSellInstanceCard` (defined in Task 2):

```javascript
    async renderRepairTab() {
        const grid = document.getElementById('shop-items-grid');
        grid.innerHTML = '<div class="text-center text-muted py-5">Loading...</div>';

        await this.refreshHoard();

        let charStates = [];
        try {
            const stateResponse = await fetch('/api/characters/state');
            if (stateResponse.ok) {
                const stateData = await stateResponse.json();
                charStates = stateData.characters || [];
            }
        } catch (err) {
            console.error('[trading] Failed to load character state:', err);
        }

        const repairable = [];
        this.hoardItems.forEach(item => {
            if (item.uid && item.durability != null && item.max_durability
                && item.durability < item.max_durability) {
                repairable.push({ instance: item, source: 'In Hoard' });
            }
        });
        charStates.forEach(ch => {
            Object.entries(ch.gear || {}).forEach(([slot, inst]) => {
                if (inst && typeof inst === 'object' && inst.uid && inst.durability != null
                    && inst.max_durability && inst.durability < inst.max_durability) {
                    repairable.push({ instance: inst, source: `Equipped — ${ch.name} (${slot})` });
                }
            });
        });

        if (repairable.length === 0) {
            grid.innerHTML = '<div class="text-center text-muted py-5">Nothing needs repair.</div>';
            return;
        }

        grid.innerHTML = repairable.map(({ instance, source }) => this.renderRepairCard(instance, source)).join('');
    }

    renderRepairCard(instance, source) {
        const rarity = window.MUDTooltips ? window.MUDTooltips.rarityClass(instance.rarity) : 'rarity-common';
        return `
<div class="shop-item-card repair-item-card" id="repair-card-${instance.uid}">
    <div class="shop-item-icon-wrapper">
        ${this.getItemIcon(instance.type)}
    </div>
    <div class="shop-item-name ${rarity}">${instance.name || instance.slug}</div>
    <div class="repair-item-source small text-muted">${source}</div>
    ${this.durabilityBarHtml(instance)}
    <button type="button" class="trade-btn trade-btn-confirm repair-btn" onclick="tradingSystem.repairItem('${instance.uid}')">
        Repair
    </button>
</div>`;
    }

    async repairItem(uid) {
        try {
            const response = await fetch('/api/trade/repair', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ uid })
            });

            const result = await response.json();

            if (!response.ok) {
                this.showToast('Repair Failed', result.error || 'Could not repair item', 'error');
                return;
            }

            this.hoardCopper = result.new_balance;
            this.hoardCopperDisplay = result.new_balance_display || `${this.hoardCopper}c`;
            document.getElementById('hoard-copper-amount').textContent = this.hoardCopperDisplay;

            this.showToast('Repaired!', `Restored to full durability for ${result.cost_display || result.cost + 'c'}`, 'success');

            document.dispatchEvent(new CustomEvent('repair-complete', {
                detail: { uid, new_balance: this.hoardCopper }
            }));

            this.renderRepairTab();

        } catch (err) {
            console.error('[trading] Repair failed:', err);
            this.showToast('Error', 'Repair failed', 'error');
        }
    }
```

- [ ] **Step 4: Add Repair tab CSS**

In `app/static/css/trading-system.css`, insert immediately after the `.item-quantity-badge`
block and before the `/* Trade Confirmation Modal */` comment:

```css
/* Repair Tab */
.repair-item-card {
    cursor: default;
}

.repair-item-source {
    text-align: center;
    margin-bottom: 0.5rem;
}

.repair-btn {
    width: 100%;
    margin-top: 0.75rem;
}
```

- [ ] **Step 5: Syntax-check the JS file**

Run: `node --check app/static/js/trading-system.js`
Expected: no output (exit code 0).

- [ ] **Step 6: Manual verification (Repair tab)**

With the app running, ensure at least one gear instance (in the hoard or equipped on a
character) has `durability < max_durability` — either fight a few combat rounds with
durability loss enabled, or manually edit the instance JSON in the dev DB for a quick check.
Then:
- Open the shop, switch to the Repair tab.
- Confirm damaged items appear with correct source labels (`"In Hoard"` vs
  `"Equipped — <Character> (<slot>)"`), rarity color, and durability bar.
- Click Repair on one; confirm the durability bar disappears from the list (card removed
  since it's back to full) and the header hoard balance decreases by the charged cost (shown
  in the success toast).
- With insufficient hoard copper, confirm the "Insufficient funds" error toasts correctly
  (temporarily zero out the hoard's copper in the dev DB to force this, or repair an
  expensive item with a near-empty hoard).
- With nothing damaged, confirm the "Nothing needs repair." empty state.

- [ ] **Step 7: Commit**

```bash
git add app/static/js/trading-system.js app/static/css/trading-system.css
git commit -m "feat(trading-ui): add hoard-aware repair tab to the shop modal"
```

---

## Plan Self-Review Notes

- **Spec coverage:** Header hoard balance (Task 1) ✅, Buy tab unaffected functionally but
  repointed to hoard checks (Task 1) ✅, Sell tab stackables + gear instances with rarity/
  durability (Task 2) ✅, Repair tab listing hoard + equipped damaged gear with repair action
  (Task 3) ✅. Out-of-scope items (hoard/stash screen, extraction surface, encumbrance bar)
  correctly excluded — they're separate sub-specs per the brainstorming decision.
- **Open question from spec:** resolved by not pre-computing repair cost client-side; the
  Repair tab shows the durability bar and a plain button, and the actual cost is surfaced in
  the success toast from `cost_display`. Reflected in Task 3 Step 3.
- **Type/name consistency check:** `hoardCopper`/`hoardCopperDisplay`/`hoardItems` introduced
  in Task 1 are the only fields used by Tasks 2–3 (no stray `characterGold` references
  remain — verified against every occurrence found in the original file). `pendingTrade`
  shape (`kind`, `slug`, `uid`, `item`, `unitPrice`, `quantity`, `maxQuantity`) is established
  in Task 2 and consumed unchanged by `executeTrade` (also Task 2) and `showTradeConfirm`
  (Task 1, unmodified — already generic over `item`/`unitPrice`/`quantity`/`maxQuantity`).
