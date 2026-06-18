/**
 * Enhanced Equipment & Inventory System
 * Features: Drag-and-drop, visual slots, item comparison, set bonuses
 */

class EquipmentManager {
    constructor() {
        this.character = null;
        this.draggedItem = null;
        this.comparisonTooltip = null;
        this.init();
    }

    init() {
        this.createModal();
        this.attachEventListeners();
    }

    createModal() {
        if (document.getElementById('equipment-enhanced-modal')) return;

        const modalHTML = `
<div class="modal fade" id="equipment-enhanced-modal" tabindex="-1">
    <div class="modal-dialog modal-xl modal-dialog-scrollable equipment-modal">
        <div class="modal-content" style="background: linear-gradient(135deg, rgba(20,20,30,0.98), rgba(30,30,40,0.98)); border: 2px solid rgba(100,100,120,0.3);">
            <div class="modal-header" style="border-bottom: 1px solid rgba(100,100,120,0.3);">
                <h5 class="modal-title">
                    <i class="bi bi-person-gear me-2"></i>
                    <span id="eq-char-name">Character</span> - Equipment & Inventory
                </h5>
                <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
            </div>
            <div class="modal-body">
                <div class="equipment-grid">
                    <!-- Left: Equipment Slots -->
                    <div class="equipment-slots">
                        <h6 class="text-center mb-3" style="color: rgba(255,255,255,0.8); text-transform: uppercase; letter-spacing: 1px;">
                            <i class="bi bi-shield-check me-2"></i>Equipped
                        </h6>
                        <div id="equipment-slots-list"></div>
                        <div id="gear-bonus-summary" class="small text-info mt-2"></div>
                        <div id="encumbrance-bar" class="mt-2"></div>
                        <div class="stats-summary mt-3">
                            <h6>Total Stats</h6>
                            <div id="total-stats"></div>
                        </div>
                    </div>

                    <!-- Center: Paper Doll -->
                    <div class="paper-doll">
                        <h6 class="text-center mb-3" style="color: rgba(255,255,255,0.8); text-transform: uppercase; letter-spacing: 1px;">
                            <span id="char-level-display">Lv 1</span>  <span id="char-class-display">Adventurer</span>
                        </h6>
                        <div class="doll-figure" id="paper-doll-figure">
                            <!-- Visual slots positioned absolutely -->
                        </div>
                    </div>

                    <!-- Right: Inventory Bag -->
                    <div class="inventory-bag">
                        <h6 class="text-center mb-3" style="color: rgba(255,255,255,0.8); text-transform: uppercase; letter-spacing: 1px;">
                            <i class="bi bi-backpack me-2"></i>Inventory
                            <span class="badge bg-secondary" id="bag-count">0/50</span>
                        </h6>
                        <div id="inventory-items-list"></div>
                    </div>
                </div>
            </div>
            <div class="modal-footer" style="border-top: 1px solid rgba(100,100,120,0.3);">
                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
            </div>
        </div>
    </div>
</div>`;

        document.body.insertAdjacentHTML('beforeend', modalHTML);
    }

    attachEventListeners() {
        // Listen for equipment panel button clicks
        document.addEventListener('click', (e) => {
            if (e.target.closest('.btn-equip-panel')) {
                const charId = e.target.closest('[data-char-id]').dataset.charId;
                this.openForCharacter(charId);
            }
        });
    }

    async openForCharacter(charId) {
        // Load character data
        await this.loadCharacter(charId);

        // Render UI
        this.render();

        // Show modal
        const modal = new bootstrap.Modal(document.getElementById('equipment-enhanced-modal'));
        modal.show();
    }

    async loadCharacter(charId) {
        const response = await fetch(`/api/characters/${charId}`);
        if (!response.ok) throw new Error('Failed to load character');
        this.character = await response.json();
    }

    render() {
        if (!this.character) return;

        // Update header
        document.getElementById('eq-char-name').textContent = this.character.name;
        document.getElementById('char-level-display').textContent = `Lv ${this.character.level}`;
        document.getElementById('char-class-display').textContent = this.character.char_class || 'Adventurer';

        // Render equipment slots
        this.renderEquipmentSlots();

        // Render paper doll
        this.renderPaperDoll();

        // Render inventory
        this.renderInventory();

        // Render total stats
        this.renderTotalStats();
    }

    renderEquipmentSlots() {
        const slots = ['weapon', 'offhand', 'head', 'chest', 'hands', 'feet', 'ring', 'amulet'];
        const gear = this.character.gear || {};

        const html = slots.map(slot => this.createSlotHTML(slot, gear[slot])).join('');
        document.getElementById('equipment-slots-list').innerHTML = html;

        // Attach drag-drop handlers
        this.attachSlotHandlers();
    }

    createSlotHTML(slot, item) {
        const slotLabel = this.getSlotLabel(slot);
        const slotIcon = this.getSlotIcon(slot);
        const hasItem = !!item;

        if (hasItem) {
            const rarityClass = `rarity-${item.rarity || 'common'}`;
            const stats = this.getItemStats(item);

            return `
<div class="equipment-slot" data-slot="${slot}" data-has-item="true" droppable="true">
    <div class="slot-icon">
        ${slotIcon}
    </div>
    <div class="slot-info">
        <div class="slot-label">${slotLabel}</div>
        <div class="slot-item-name ${rarityClass}">${this.escapeHTML(item.name)}</div>
        <div class="slot-item-stats">${stats}</div>
    </div>
    <button class="btn btn-sm btn-outline-danger slot-action" onclick="equipmentManager.unequipItem('${slot}')">
        <i class="bi bi-x-lg"></i>
    </button>
</div>`;
        } else {
            return `
<div class="equipment-slot" data-slot="${slot}" data-has-item="false" droppable="true">
    <div class="slot-icon empty">
        ${slotIcon}
    </div>
    <div class="slot-info">
        <div class="slot-label">${slotLabel}</div>
        <div class="slot-item-name" style="color: rgba(255,255,255,0.4); font-style: italic;">Empty</div>
    </div>
</div>`;
        }
    }

    renderPaperDoll() {
        const slots = ['head', 'amulet', 'chest', 'weapon', 'offhand', 'gloves', 'ring1', 'ring2', 'legs', 'boots'];
        const gear = this.character.gear || {};

        const html = slots.map(slot => {
            const hasItem = !!gear[slot];
            const slotIcon = this.getSlotIcon(slot);
            const equippedClass = hasItem ? 'equipped' : '';

            return `<div class="doll-slot ${equippedClass}" data-slot="${slot}" droppable="true" title="${this.getSlotLabel(slot)}">${slotIcon}</div>`;
        }).join('');

        document.getElementById('paper-doll-figure').innerHTML = html;

        // Attach drag-drop handlers
        this.attachSlotHandlers();
    }

    renderInventory() {
        const bag = this.character.bag || [];
        document.getElementById('bag-count').textContent = `${bag.length}/50`;

        if (bag.length === 0) {
            document.getElementById('inventory-items-list').innerHTML = `
                <div style="text-align: center; padding: 3rem; color: rgba(255,255,255,0.4);">
                    <i class="bi bi-inbox" style="font-size: 3rem; margin-bottom: 1rem;"></i>
                    <div>No items in inventory</div>
                </div>`;
            return;
        }

        const html = bag.map((item, index) => this.createBagItemHTML(item, index)).join('');
        document.getElementById('inventory-items-list').innerHTML = html;

        // Attach drag handlers
        this.attachItemDragHandlers();
    }

    createBagItemHTML(item, index) {
        const rarityClass = `rarity-${item.rarity || 'common'}`;
        // Procedural gear instances expose `slot`/`affixes` instead of a catalog
        // `type`/`slug`; fall back gracefully so they render in the bag too.
        const typeLabel = item.type || item.slot || 'gear';
        const icon = this.getItemIcon(typeLabel);
        const stats = Array.isArray(item.affixes) && item.affixes.length
            ? item.affixes.map(a => `+${a.val} ${String(a.stat).toUpperCase()}`).join(', ')
            : this.getItemStats(item);

        return `
<div class="bag-item ${rarityClass}" draggable="true" data-item-index="${index}" data-item-slug="${this.escapeHTML(item.slug || '')}" data-item-uid="${this.escapeHTML(item.uid || '')}">
    <div class="item-icon" style="color: currentColor;">
        ${icon}
    </div>
    <div class="item-details">
        <div>
            <span class="item-name">${this.escapeHTML(item.name)}</span>
            <span class="item-type-badge">${this.escapeHTML(typeLabel)}</span>
        </div>
        <div class="item-stats-preview">${stats}</div>
    </div>
</div>`;
    }

    renderTotalStats() {
        const stats = this.calculateTotalStats();
        const html = `
            <div class="stat-item">
                <span class="stat-label"><i class="bi bi-heart-fill text-danger me-2"></i>HP</span>
                <span class="stat-value">${stats.hp}</span>
            </div>
            <div class="stat-item">
                <span class="stat-label"><i class="bi bi-lightning-charge-fill text-primary me-2"></i>MP</span>
                <span class="stat-value">${stats.mana}</span>
            </div>
            <div class="stat-item">
                <span class="stat-label"><i class="bi bi-sword text-warning me-2"></i>Attack</span>
                <span class="stat-value">${stats.attack} ${stats.bonus_attack ? `<span class="stat-bonus">+${stats.bonus_attack}</span>` : ''}</span>
            </div>
            <div class="stat-item">
                <span class="stat-label"><i class="bi bi-shield-fill text-info me-2"></i>Defense</span>
                <span class="stat-value">${stats.defense} ${stats.bonus_defense ? `<span class="stat-bonus">+${stats.bonus_defense}</span>` : ''}</span>
            </div>
        `;
        document.getElementById('total-stats').innerHTML = html;
        this.renderEncumbrance();
        this.renderGearBonus();
    }

    renderEncumbrance() {
        const enc = this.character && this.character.encumbrance;
        const container = document.getElementById('encumbrance-bar');
        if (!container) return;
        if (!enc || typeof enc.weight !== 'number' || typeof enc.capacity !== 'number') {
            container.innerHTML = '';
            return;
        }
        const pct = enc.capacity > 0 ? Math.min(100, (enc.weight / enc.capacity) * 100) : 0;
        const barClass = enc.status === 'blocked' ? 'bg-danger' : (enc.status === 'encumbered' ? 'bg-warning' : 'bg-success');
        const textClass = enc.status === 'blocked' ? 'text-danger' : (enc.status === 'encumbered' ? 'text-warning' : '');
        const statusLabel = enc.status === 'blocked' ? 'Overloaded — cannot carry more' : (enc.status === 'encumbered' ? 'Encumbered' : '');
        const penaltyNote = (enc.status !== 'normal' && enc.dex_penalty) ? ` (-${enc.dex_penalty} DEX)` : '';
        container.innerHTML = `
            <div class="d-flex justify-content-between small" style="color: rgba(255,255,255,0.8);">
                <span>Carry Weight</span>
                <span>${enc.weight.toFixed(1)} / ${enc.capacity.toFixed(1)}</span>
            </div>
            <div class="progress" style="height:6px;">
                <div class="progress-bar ${barClass}" style="width:${pct}%"></div>
            </div>
            ${statusLabel ? `<div class="small ${textClass} mt-1">${statusLabel}${penaltyNote}</div>` : ''}
        `;
    }

    renderGearBonus() {
        const container = document.getElementById('gear-bonus-summary');
        if (!container) return;
        const gear = (this.character && this.character.gear) || {};
        const totals = {};
        Object.values(gear).forEach(inst => {
            if (!inst) return;
            const affixes = Array.isArray(inst.affixes) ? inst.affixes
                : (inst.effects && typeof inst.effects === 'object'
                    ? Object.entries(inst.effects).map(([stat, val]) => ({ stat, val }))
                    : []);
            affixes.forEach(a => {
                if (!a || !a.stat || typeof a.val !== 'number') return;
                totals[a.stat] = (totals[a.stat] || 0) + a.val;
            });
        });
        const parts = Object.entries(totals)
            .filter(([, v]) => v !== 0)
            .map(([stat, v]) => {
                const num = Number.isInteger(v) ? v : Math.round(v * 10) / 10;
                return `${num >= 0 ? '+' : ''}${num} ${stat.toUpperCase()}`;
            });
        container.innerHTML = parts.length ? `Gear bonus: ${this.escapeHTML(parts.join(', '))}` : '';
    }

    // Drag-and-drop handlers
    attachSlotHandlers() {
        document.querySelectorAll('.equipment-slot, .doll-slot').forEach(slot => {
            slot.addEventListener('dragover', (e) => this.onSlotDragOver(e));
            slot.addEventListener('dragleave', (e) => this.onSlotDragLeave(e));
            slot.addEventListener('drop', (e) => this.onSlotDrop(e));
        });
    }

    attachItemDragHandlers() {
        document.querySelectorAll('.bag-item[draggable="true"]').forEach(item => {
            item.addEventListener('dragstart', (e) => this.onItemDragStart(e));
            item.addEventListener('dragend', (e) => this.onItemDragEnd(e));

            // Attach hover for comparison tooltip
            item.addEventListener('mouseenter', (e) => this.showComparisonTooltip(e));
            item.addEventListener('mouseleave', (e) => this.hideComparisonTooltip());
        });
    }

    onItemDragStart(e) {
        const itemIndex = parseInt(e.target.dataset.itemIndex);
        this.draggedItem = this.character.bag[itemIndex];
        e.dataTransfer.effectAllowed = 'move';
        e.target.style.opacity = '0.4';
    }

    onItemDragEnd(e) {
        e.target.style.opacity = '1';
        this.draggedItem = null;
    }

    onSlotDragOver(e) {
        e.preventDefault();
        e.dataTransfer.dropEffect = 'move';
        e.currentTarget.setAttribute('data-drag-over', 'true');
    }

    onSlotDragLeave(e) {
        e.currentTarget.removeAttribute('data-drag-over');
    }

    async onSlotDrop(e) {
        e.preventDefault();
        e.currentTarget.removeAttribute('data-drag-over');

        if (!this.draggedItem) return;

        const targetSlot = e.currentTarget.dataset.slot;
        await this.equipItem(this.draggedItem, targetSlot);
    }

    async equipItem(item, slot) {
        // Procedural gear instances carry a `uid` and self-describe their slot;
        // equip them by uid. Legacy catalog items equip by slug + target slot.
        // `item` may also be a bare slug string for backward compatibility.
        const isInstance = item && typeof item === 'object' && item.uid;
        const body = isInstance
            ? { uid: item.uid }
            : { item_slug: (typeof item === 'object' ? item.slug : item), slot: slot };
        const response = await fetch(`/api/characters/${this.character.id}/equip`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        });

        if (response.ok) {
            await this.loadCharacter(this.character.id);
            this.render();
        }
    }

    async unequipItem(slot) {
        const response = await fetch(`/api/characters/${this.character.id}/unequip`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ slot: slot })
        });

        if (response.ok) {
            await this.loadCharacter(this.character.id);
            this.render();
        }
    }

    // Item comparison tooltip
    showComparisonTooltip(e) {
        const itemIndex = parseInt(e.currentTarget.dataset.itemIndex);
        const item = this.character.bag[itemIndex];
        const slot = this.getSlotForItemType(item.type);
        const equipped = this.character.gear?.[slot];

        this.hideComparisonTooltip();

        this.comparisonTooltip = this.createComparisonTooltip(item, equipped);
        document.body.appendChild(this.comparisonTooltip);

        this.positionTooltip(e.currentTarget);
    }

    hideComparisonTooltip() {
        if (this.comparisonTooltip) {
            this.comparisonTooltip.remove();
            this.comparisonTooltip = null;
        }
    }

    createComparisonTooltip(item, equippedItem) {
        const tooltip = document.createElement('div');
        tooltip.className = 'item-comparison-tooltip';

        const rarityClass = `rarity-${item.rarity || 'common'}`;
        const itemStats = this.parseItemStats(item);

        let html = `
            <div class="tooltip-item-header">
                <div class="tooltip-item-name ${rarityClass}">${this.escapeHTML(item.name)}</div>
                <div class="tooltip-item-type">${this.escapeHTML(item.type)}</div>
            </div>
            <div class="tooltip-stats">
                ${this.renderStatsHTML(itemStats)}
            </div>
        `;

        if (equippedItem) {
            const equippedStats = this.parseItemStats(equippedItem);
            html += `<div class="tooltip-comparison">
                <div class="tooltip-comparison-label">vs. Equipped</div>
                ${this.renderComparisonHTML(itemStats, equippedStats)}
            </div>`;
        }

        if (Array.isArray(item.affixes) && item.affixes.length) {
            const aff = item.affixes.map(a => `+${a.val} ${String(a.stat).toUpperCase()}`).join(', ');
            html += `<div class="tooltip-affixes ${rarityClass}">${this.escapeHTML(aff)}</div>`;
        }

        if (item.description) {
            html += `<div class="tooltip-description">${this.escapeHTML(item.description)}</div>`;
        }

        tooltip.innerHTML = html;
        return tooltip;
    }

    positionTooltip(targetElement) {
        if (!this.comparisonTooltip) return;

        const rect = targetElement.getBoundingClientRect();
        const tooltipRect = this.comparisonTooltip.getBoundingClientRect();

        let left = rect.right + 10;
        let top = rect.top;

        // Keep within viewport
        if (left + tooltipRect.width > window.innerWidth) {
            left = rect.left - tooltipRect.width - 10;
        }

        if (top + tooltipRect.height > window.innerHeight) {
            top = window.innerHeight - tooltipRect.height - 10;
        }

        this.comparisonTooltip.style.left = `${left}px`;
        this.comparisonTooltip.style.top = `${top}px`;
    }

    // Helper functions
    getSlotLabel(slot) {
        const labels = {
            weapon: 'Main Hand',
            offhand: 'Off Hand',
            head: 'Head',
            chest: 'Chest',
            legs: 'Legs',
            boots: 'Boots',
            gloves: 'Gloves',
            ring1: 'Ring 1',
            ring2: 'Ring 2',
            amulet: 'Amulet'
        };
        return labels[slot] || slot;
    }

    getSlotIcon(slot) {
        const icons = {
            weapon: '<i class="bi bi-sword"></i>',
            offhand: '<i class="bi bi-shield"></i>',
            head: '<i class="bi bi-person-circle"></i>',
            chest: '<i class="bi bi-shield-fill-check"></i>',
            legs: '<i class="bi bi-dash-lg"></i>',
            boots: '<i class="bi bi-box"></i>',
            gloves: '<i class="bi bi-hand-index"></i>',
            ring1: '<i class="bi bi-circle"></i>',
            ring2: '<i class="bi bi-circle"></i>',
            amulet: '<i class="bi bi-gem"></i>'
        };
        return icons[slot] || '<i class="bi bi-box"></i>';
    }

    getItemIcon(type) {
        const icons = {
            weapon: '<i class="bi bi-sword"></i>',
            armor: '<i class="bi bi-shield"></i>',
            potion: '<i class="bi bi-cup-straw"></i>',
            ring: '<i class="bi bi-circle"></i>',
            amulet: '<i class="bi bi-gem"></i>',
            tool: '<i class="bi bi-wrench"></i>'
        };
        return icons[type] || '<i class="bi bi-box"></i>';
    }

    getSlotForItemType(type) {
        const mapping = {
            weapon: 'weapon',
            armor: 'chest',
            helmet: 'head',
            shield: 'offhand',
            boots: 'boots',
            gloves: 'gloves',
            ring: 'ring1',
            amulet: 'amulet',
            legs: 'legs'
        };
        return mapping[type] || 'weapon';
    }

    getItemStats(item) {
        // Placeholder - would parse actual item stats
        if (item.level) {
            return `Level ${item.level}`;
        }
        return '';
    }

    parseItemStats(item) {
        // Placeholder - would parse from item stats JSON
        return {
            attack: item.attack || 0,
            defense: item.defense || 0
        };
    }

    renderStatsHTML(stats) {
        let html = '';
        if (stats.attack) html += `<div class="tooltip-stat-row"><span>Attack</span><span class="stat-positive">+${stats.attack}</span></div>`;
        if (stats.defense) html += `<div class="tooltip-stat-row"><span>Defense</span><span class="stat-positive">+${stats.defense}</span></div>`;
        return html || '<div class="stat-neutral">No special stats</div>';
    }

    renderComparisonHTML(newStats, oldStats) {
        let html = '';
        if (newStats.attack !== oldStats.attack) {
            const diff = newStats.attack - oldStats.attack;
            const diffClass = diff > 0 ? 'better' : 'worse';
            html += `<div class="tooltip-stat-row"><span>Attack</span><span class="comparison-diff ${diffClass}">${diff > 0 ? '+' : ''}${diff}</span></div>`;
        }
        if (newStats.defense !== oldStats.defense) {
            const diff = newStats.defense - oldStats.defense;
            const diffClass = diff > 0 ? 'better' : 'worse';
            html += `<div class="tooltip-stat-row"><span>Defense</span><span class="comparison-diff ${diffClass}">${diff > 0 ? '+' : ''}${diff}</span></div>`;
        }
        return html || '<div class="stat-neutral">No difference</div>';
    }

    calculateTotalStats() {
        // Placeholder - would calculate from character + gear
        return {
            hp: 100,
            mana: 50,
            attack: 12,
            defense: 8,
            bonus_attack: 5,
            bonus_defense: 3
        };
    }

    escapeHTML(str) {
        if (!str) return '';
        return String(str).replace(/[&<>"']/g, (m) => ({
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#39;'
        }[m]));
    }
}

// Initialize global instance
window.equipmentManager = new EquipmentManager();

// Development helpers
if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
    window.openEquipment = (charId) => window.equipmentManager.openForCharacter(charId);
    console.log('%c⚔️ Enhanced Equipment System Loaded', 'color: #64b4ff; font-weight: bold');
    console.log('%cTest command available:', 'color: #64b4ff');
    console.log('%c  openEquipment(charId) - Open equipment modal', 'color: #888');
}
