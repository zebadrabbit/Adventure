/**
 * Trading & Economy System
 *
 * Features:
 * - Merchant shop UI with buy/sell tabs
 * - Gold currency management
 * - Item pricing with buy/sell modifiers
 * - Stock management for limited inventory
 * - Trade confirmations with quantity selector
 * - Transaction history
 * - Merchant types: general, weapons, armor, potions, rare
 *
 * API Endpoints:
 * - GET  /api/merchants/{slug} - Get merchant details and inventory
 * - POST /api/trade/buy - Purchase items from merchant
 * - POST /api/trade/sell - Sell items to merchant
 * - GET  /api/characters/{id}/gold - Get character gold balance
 *
 * Events:
 * - 'trade-complete' - Fired when transaction completes
 * - 'gold-changed' - Fired when gold amount changes
 */

class TradingSystem {
    constructor() {
        this.shopModal = null;
        this.confirmDialog = null;
        this.currentMerchant = null;
        this.currentCharacter = null;
        this.characterGold = 0;
        this.currentTab = 'buy';
        this.pendingTrade = null;

        this.init();
    }

    init() {
        this.createShopModal();
        this.createConfirmDialog();

        // Listen for merchant interactions
        document.addEventListener('merchant-interact', (e) => {
            if (e.detail && e.detail.merchantSlug) {
                this.openMerchant(e.detail.merchantSlug, e.detail.characterId);
            }
        });
    }

    createShopModal() {
        const modalHTML = `
<div class="modal fade" id="merchant-shop-modal" tabindex="-1" aria-hidden="true">
    <div class="modal-dialog modal-xl merchant-shop-modal">
        <div class="modal-content bg-transparent border-0">
            <div class="merchant-shop-header">
                <div class="merchant-portrait" id="merchant-portrait">
                    <i class="bi bi-shop"></i>
                </div>
                <div class="merchant-info">
                    <div class="merchant-name" id="merchant-name">Merchant</div>
                    <div class="merchant-type" id="merchant-type">General Goods</div>
                </div>
                <div class="character-gold">
                    <i class="bi bi-coin gold-icon"></i>
                    <div>
                        <div class="gold-amount" id="character-gold-amount">0</div>
                        <div class="gold-label">Gold</div>
                    </div>
                </div>
            </div>

            <div class="shop-tabs">
                <div class="shop-tab active" data-tab="buy" onclick="tradingSystem.switchTab('buy')">
                    <i class="bi bi-cart-plus me-2"></i>Buy
                </div>
                <div class="shop-tab" data-tab="sell" onclick="tradingSystem.switchTab('sell')">
                    <i class="bi bi-cash-coin me-2"></i>Sell
                </div>
            </div>

            <div class="shop-inventory">
                <div class="shop-items-grid" id="shop-items-grid">
                    <!-- Items populated here -->
                </div>
            </div>

            <div class="modal-footer">
                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">
                    Close Shop
                </button>
            </div>
        </div>
    </div>
</div>`;

        document.body.insertAdjacentHTML('beforeend', modalHTML);
        this.shopModal = new bootstrap.Modal(document.getElementById('merchant-shop-modal'));
    }

    createConfirmDialog() {
        const dialogHTML = `
<div id="trade-confirm-overlay" class="trade-confirm-overlay" style="display: none;">
    <div class="trade-confirm-dialog">
        <div class="trade-confirm-header">
            <div class="trade-confirm-title" id="trade-confirm-title">Confirm Purchase</div>
        </div>

        <div class="trade-confirm-item">
            <div class="trade-confirm-icon" id="trade-item-icon">
                <i class="bi bi-box"></i>
            </div>
            <div class="trade-confirm-details">
                <div class="trade-confirm-item-name" id="trade-item-name">Item</div>
                <div class="trade-confirm-price buy" id="trade-unit-price">
                    <i class="bi bi-coin"></i>
                    <span id="trade-price-amount">0</span>
                </div>
            </div>
        </div>

        <div class="trade-quantity-selector">
            <button class="quantity-btn" id="qty-decrease" onclick="tradingSystem.adjustQuantity(-1)">−</button>
            <div class="quantity-display" id="trade-quantity">1</div>
            <button class="quantity-btn" id="qty-increase" onclick="tradingSystem.adjustQuantity(1)">+</button>
        </div>

        <div class="trade-total">
            <div class="trade-total-label">Total Cost</div>
            <div class="trade-total-amount">
                <i class="bi bi-coin"></i>
                <span id="trade-total-amount">0</span>
            </div>
        </div>

        <div class="trade-confirm-actions">
            <button class="trade-btn trade-btn-cancel" onclick="tradingSystem.cancelTrade()">
                Cancel
            </button>
            <button class="trade-btn trade-btn-confirm" id="trade-confirm-btn" onclick="tradingSystem.confirmTrade()">
                Confirm
            </button>
        </div>
    </div>
</div>`;

        document.body.insertAdjacentHTML('beforeend', dialogHTML);
    }

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

    renderMerchantShop() {
        // Set merchant info
        document.getElementById('merchant-name').textContent = this.currentMerchant.name;
        document.getElementById('merchant-type').textContent = this.currentMerchant.type || 'General Merchant';
        document.getElementById('merchant-portrait').innerHTML = this.currentMerchant.icon || '<i class="bi bi-shop"></i>';
        document.getElementById('character-gold-amount').textContent = this.characterGold.toLocaleString();

        this.switchTab(this.currentTab);
    }

    switchTab(tab) {
        this.currentTab = tab;

        // Update tab active state
        document.querySelectorAll('.shop-tab').forEach(t => {
            t.classList.toggle('active', t.dataset.tab === tab);
        });

        if (tab === 'buy') {
            this.renderBuyTab();
        } else if (tab === 'sell') {
            this.renderSellTab();
        }
    }

    async renderBuyTab() {
        const grid = document.getElementById('shop-items-grid');

        if (!this.currentMerchant || !this.currentMerchant.inventory) {
            grid.innerHTML = '<div class="text-center text-muted py-5">No items available</div>';
            return;
        }

        const html = this.currentMerchant.inventory.map(item => {
            const buyPrice = Math.floor(item.base_price * this.currentMerchant.buy_modifier);
            const canAfford = this.characterGold >= buyPrice;
            const inStock = item.stock === null || item.stock > 0;

            return `
<div class="shop-item-card ${!inStock ? 'out-of-stock' : ''} ${!canAfford ? 'cannot-afford' : ''}"
     onclick="tradingSystem.startBuy('${item.slug}')">
    <div class="shop-item-icon-wrapper">
        ${this.getItemIcon(item.type)}
        ${item.stock !== null ? `<div class="item-stock-badge ${item.stock < 3 ? 'low-stock' : ''}">×${item.stock}</div>` : ''}
    </div>
    <div class="shop-item-name">${item.name}</div>
    <div class="shop-item-price">
        <i class="bi bi-coin price-icon"></i>
        <span class="price-amount">${buyPrice.toLocaleString()}</span>
    </div>
    ${!inStock ? '<div class="text-danger text-center mt-2 small">Out of Stock</div>' : ''}
    ${!canAfford && inStock ? '<div class="text-warning text-center mt-2 small">Not enough gold</div>' : ''}
</div>`;
        }).join('');

        grid.innerHTML = html;
    }

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

    startBuy(itemSlug) {
        const item = this.currentMerchant.inventory.find(i => i.slug === itemSlug);
        if (!item) return;

        const buyPrice = Math.floor(item.base_price * this.currentMerchant.buy_modifier);
        const maxQty = item.stock !== null ? item.stock : Math.floor(this.characterGold / buyPrice);

        if (item.stock !== null && item.stock === 0) {
            this.showToast('Out of Stock', 'This item is currently unavailable', 'error');
            return;
        }

        if (buyPrice > this.characterGold) {
            this.showToast('Insufficient Gold', 'You cannot afford this item', 'error');
            return;
        }

        this.pendingTrade = {
            type: 'buy',
            item: item,
            unitPrice: buyPrice,
            quantity: 1,
            maxQuantity: maxQty
        };

        this.showTradeConfirm();
    }

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

    showTradeConfirm() {
        if (!this.pendingTrade) return;

        const { type, item, unitPrice, quantity, maxQuantity } = this.pendingTrade;

        document.getElementById('trade-confirm-title').textContent = type === 'buy' ? 'Confirm Purchase' : 'Confirm Sale';
        document.getElementById('trade-item-icon').innerHTML = this.getItemIcon(item.type);
        document.getElementById('trade-item-name').textContent = item.name;
        document.getElementById('trade-price-amount').textContent = unitPrice.toLocaleString();
        document.getElementById('trade-quantity').textContent = quantity;
        document.getElementById('trade-total-amount').textContent = (unitPrice * quantity).toLocaleString();

        const confirmBtn = document.getElementById('trade-confirm-btn');
        const unitPriceEl = document.getElementById('trade-unit-price');

        if (type === 'buy') {
            confirmBtn.textContent = 'Buy';
            confirmBtn.classList.remove('trade-btn-sell');
            unitPriceEl.classList.remove('sell');
            unitPriceEl.classList.add('buy');
        } else {
            confirmBtn.textContent = 'Sell';
            confirmBtn.classList.add('trade-btn-sell');
            unitPriceEl.classList.remove('buy');
            unitPriceEl.classList.add('sell');
        }

        // Update quantity buttons
        document.getElementById('qty-decrease').disabled = quantity <= 1;
        document.getElementById('qty-increase').disabled = quantity >= maxQuantity || (type === 'buy' && (unitPrice * (quantity + 1)) > this.characterGold);

        document.getElementById('trade-confirm-overlay').style.display = 'flex';
    }

    adjustQuantity(delta) {
        if (!this.pendingTrade) return;

        const newQty = this.pendingTrade.quantity + delta;
        const maxQty = this.pendingTrade.maxQuantity || 99;

        if (newQty < 1 || newQty > maxQty) return;

        // Check if can afford
        if (this.pendingTrade.type === 'buy') {
            const totalCost = this.pendingTrade.unitPrice * newQty;
            if (totalCost > this.characterGold) return;
        }

        this.pendingTrade.quantity = newQty;
        this.showTradeConfirm();
    }

    cancelTrade() {
        this.pendingTrade = null;
        document.getElementById('trade-confirm-overlay').style.display = 'none';
    }

    async confirmTrade() {
        if (!this.pendingTrade) return;

        this.executeTrade();
    }

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

            if (!response.ok) {
                const error = await response.json();
                this.showToast('Trade Failed', error.error || 'Transaction failed', 'error');
                this.cancelTrade();
                return;
            }

            const result = await response.json();

            // Update gold
            this.characterGold = result.new_balance;
            document.getElementById('character-gold-amount').textContent = this.characterGold.toLocaleString();

            // Show success
            const itemName = item ? item.name : slug;
            if (type === 'buy') {
                this.showToast('Purchase Complete!', `Bought ${quantity}x ${itemName} for ${unitPrice * quantity} gold`, 'success');
            } else {
                this.showToast('Sale Complete!', `Sold ${quantity}x ${itemName} for ${unitPrice * quantity} gold`, 'success');
            }

            // Fire event
            document.dispatchEvent(new CustomEvent('trade-complete', {
                detail: { type, item: slug, quantity, gold: this.characterGold }
            }));

            // Refresh display
            this.cancelTrade();

            // Reload merchant inventory
            const merchantResponse = await fetch(`/api/merchants/${this.currentMerchant.slug}`);
            if (merchantResponse.ok) {
                this.currentMerchant = await merchantResponse.json();
            }

            this.switchTab(this.currentTab);

        } catch (err) {
            console.error('[trading] Trade failed:', err);
            this.showToast('Error', 'Transaction failed', 'error');
            this.cancelTrade();
        }
    }

    getItemIcon(type) {
        const icons = {
            weapon: '<i class="bi bi-lightning-charge-fill text-warning"></i>',
            armor: '<i class="bi bi-shield-fill text-primary"></i>',
            potion: '<i class="bi bi-heart-fill text-danger"></i>',
            ring: '<i class="bi bi-gem text-info"></i>',
            amulet: '<i class="bi bi-stars text-warning"></i>',
            tool: '<i class="bi bi-wrench-adjustable-circle-fill text-secondary"></i>'
        };
        return icons[type] || '<i class="bi bi-box-fill text-muted"></i>';
    }

    showToast(title, message, type = 'success') {
        const toast = document.createElement('div');
        toast.className = `trade-toast ${type}`;
        toast.innerHTML = `
            <div class="trade-toast-header">
                <div class="trade-toast-icon">
                    <i class="bi bi-${type === 'success' ? 'check-circle' : 'x-circle'}-fill"></i>
                </div>
                <div class="trade-toast-title">${title}</div>
                <span class="trade-toast-close" onclick="this.closest('.trade-toast').remove()">×</span>
            </div>
            <div class="trade-toast-body">${message}</div>
        `;
        document.body.appendChild(toast);

        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateX(400px)';
            setTimeout(() => toast.remove(), 300);
        }, 4000);
    }
}

// Initialize on page load
let tradingSystem;
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        tradingSystem = new TradingSystem();
        window.tradingSystem = tradingSystem;
    });
} else {
    tradingSystem = new TradingSystem();
    window.tradingSystem = tradingSystem;
}

// Test helper for localhost
if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
    window.testShop = (merchantSlug = 'general-merchant', characterId = 1) => {
        tradingSystem.openMerchant(merchantSlug, characterId);
    };
}
