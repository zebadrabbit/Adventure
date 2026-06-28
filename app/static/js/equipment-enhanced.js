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
        <div class="modal-content eq-modal-content">
            <div class="modal-header eq-modal-header">
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
                        <h6 class="text-center mb-3 eq-panel-heading">
                            <i class="bi bi-shield-check me-2"></i>Equipped
                        </h6>
                        <div id="equipment-slots-list"></div>
                    </div>

                    <!-- Center: Character Portrait -->
                    <div class="eq-portrait-panel">
                        <div class="eq-class-header" id="eq-class-header">
                            <span id="char-name-display"></span>
                            <span class="eq-class-label" id="char-class-display"></span>
                        </div>
                        <div class="eq-portrait-body">
                            <div id="eq-hp-bar-wrap" class="mb-2">
                                <div class="d-flex justify-content-between small eq-bar-label">
                                    <span><i class="bi bi-heart-fill text-danger me-1"></i>HP</span>
                                    <span id="eq-hp-text"></span>
                                </div>
                                <div class="progress eq-progress-bar">
                                    <div class="progress-bar bg-danger" id="eq-hp-bar" role="progressbar"></div>
                                </div>
                            </div>
                            <div id="eq-mp-bar-wrap" class="mb-2">
                                <div class="d-flex justify-content-between small eq-bar-label">
                                    <span><i class="bi bi-lightning-charge-fill text-primary me-1"></i>MP</span>
                                    <span id="eq-mp-text"></span>
                                </div>
                                <div class="progress eq-progress-bar">
                                    <div class="progress-bar bg-primary" id="eq-mp-bar" role="progressbar"></div>
                                </div>
                            </div>
                            <div id="eq-xp-bar-wrap" class="mb-3">
                                <div class="d-flex justify-content-between small eq-bar-label">
                                    <span><i class="bi bi-star-fill text-warning me-1"></i>XP</span>
                                    <span id="eq-xp-text"></span>
                                </div>
                                <div class="progress eq-progress-bar">
                                    <div class="progress-bar eq-xp-fill" id="eq-xp-bar" role="progressbar"></div>
                                </div>
                            </div>
                            <div id="gear-bonus-summary" class="small text-info mb-2"></div>
                            <div id="encumbrance-bar" class="mb-3"></div>
                            <div class="eq-stat-grid">
                                <div class="eq-stat-cell" id="eq-stat-atk">
                                    <div class="eq-stat-label"><i class="bi bi-sword text-warning"></i> ATK</div>
                                    <div class="eq-stat-value" id="eq-val-atk">—</div>
                                </div>
                                <div class="eq-stat-cell" id="eq-stat-def">
                                    <div class="eq-stat-label"><i class="bi bi-shield-fill text-info"></i> DEF</div>
                                    <div class="eq-stat-value" id="eq-val-def">—</div>
                                </div>
                                <div class="eq-stat-cell" id="eq-stat-hp">
                                    <div class="eq-stat-label"><i class="bi bi-heart-fill text-danger"></i> HP</div>
                                    <div class="eq-stat-value" id="eq-val-hp">—</div>
                                </div>
                                <div class="eq-stat-cell" id="eq-stat-mp">
                                    <div class="eq-stat-label"><i class="bi bi-lightning-charge-fill text-primary"></i> MP</div>
                                    <div class="eq-stat-value" id="eq-val-mp">—</div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- Right: Item Grid -->
                    <div class="inventory-bag">
                        <h6 class="text-center mb-2 eq-panel-heading">
                            <i class="bi bi-backpack me-2"></i>Inventory
                            <span class="badge bg-secondary ms-1" id="bag-count">0/20</span>
                        </h6>
                        <div id="inventory-items-list"></div>
                    </div>
                </div>
            </div>
            <div class="modal-footer eq-modal-footer">
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

        // Update header title
        document.getElementById('eq-char-name').textContent = this.character.name;

        // Render equipment slots
        this.renderEquipmentSlots();

        // Render portrait panel (replaces paper doll + total stats)
        this.renderPortrait();

        // Render inventory grid
        this.renderInventory();
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
        <div class="slot-item-name eq-slot-empty">Empty</div>
    </div>
</div>`;
        }
    }

    renderPortrait() {
        const ch = this.character;
        const stats = this.calculateTotalStats();
        const cls = (ch.char_class || ch.class_name || 'adventurer').toLowerCase();

        // Class header
        const header = document.getElementById('eq-class-header');
        header.className = `eq-class-header eq-class-bg-${cls}`;
        document.getElementById('char-name-display').textContent = ch.name;
        document.getElementById('char-class-display').textContent =
            `Lv ${ch.level || stats.level || 1} ${ch.char_class || ch.class_name || 'Adventurer'}`;

        // HP bar
        const hp = stats.hp, maxHp = stats.max_hp || 1;
        const hpPct = Math.min(100, Math.round((hp / maxHp) * 100));
        document.getElementById('eq-hp-text').textContent = `${hp} / ${maxHp}`;
        document.getElementById('eq-hp-bar').style.width = `${hpPct}%`;

        // MP bar
        const mp = stats.mana, maxMp = stats.max_mana || 1;
        const mpPct = Math.min(100, Math.round((mp / maxMp) * 100));
        document.getElementById('eq-mp-text').textContent = `${mp} / ${maxMp}`;
        document.getElementById('eq-mp-bar').style.width = `${mpPct}%`;

        // XP bar
        const xp = stats.xp, xpNext = stats.xp_to_next || 100;
        const xpPct = Math.min(100, Math.round((xp / xpNext) * 100));
        document.getElementById('eq-xp-text').textContent = `${xp} / ${xpNext}`;
        document.getElementById('eq-xp-bar').style.width = `${xpPct}%`;

        // Stat grid
        document.getElementById('eq-val-atk').textContent = stats.attack;
        document.getElementById('eq-val-def').textContent = stats.defense;
        document.getElementById('eq-val-hp').textContent = stats.max_hp;
        document.getElementById('eq-val-mp').textContent = stats.max_mana;

        // Gear bonus + encumbrance (moved here from left col)
        this.renderGearBonus();
        this.renderEncumbrance();
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
            <div class="d-flex justify-content-between small eq-bar-label">
                <span>Carry Weight</span>
                <span>${enc.weight.toFixed(1)} / ${enc.capacity.toFixed(1)}</span>
            </div>
            <div class="progress eq-progress-bar">
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

    renderInventory() {
        const bag = this.character.bag || [];
        const totalSlots = Math.max(20, bag.length + 4);
        document.getElementById('bag-count').textContent = `${bag.length} / ${totalSlots}`;

        // Build grid cells
        const cells = [];
        bag.forEach((item, index) => {
            const rarityClass = `rarity-${item.rarity || 'common'}`;
            const typeLabel = item.type || item.slot || 'gear';
            const icon = this.getItemIcon(typeLabel);
            const qtyBadge = (item.qty && item.qty > 1)
                ? `<span class="cell-qty">${item.qty}</span>`
                : '';

            cells.push(`
<div class="bag-grid-cell ${rarityClass}" draggable="true"
     data-item-index="${index}"
     data-item-slug="${this.escapeHTML(item.slug || '')}"
     data-item-uid="${this.escapeHTML(item.uid || '')}"
     title="${this.escapeHTML(item.name)}">
    ${icon}
    ${qtyBadge}
</div>`);
        });

        // Empty cells
        for (let i = bag.length; i < totalSlots; i++) {
            cells.push(`<div class="bag-grid-cell empty"></div>`);
        }

        document.getElementById('inventory-items-list').innerHTML =
            `<div class="bag-grid">${cells.join('')}</div>`;

        // Attach drag + tooltip handlers
        this.attachItemDragHandlers();
    }

    // Drag-and-drop handlers
    attachSlotHandlers() {
        document.querySelectorAll('.equipment-slot').forEach(slot => {
            slot.addEventListener('dragover', (e) => this.onSlotDragOver(e));
            slot.addEventListener('dragleave', (e) => this.onSlotDragLeave(e));
            slot.addEventListener('drop', (e) => this.onSlotDrop(e));
        });
    }

    attachItemDragHandlers() {
        document.querySelectorAll('.bag-grid-cell[draggable="true"]').forEach(cell => {
            cell.addEventListener('dragstart', (e) => this.onItemDragStart(e));
            cell.addEventListener('dragend', (e) => this.onItemDragEnd(e));
            cell.addEventListener('mouseenter', (e) => this.showComparisonTooltip(e));
            cell.addEventListener('mouseleave', () => this.hideComparisonTooltip());
            // Click to equip — auto-detects slot from item type
            cell.addEventListener('click', () => {
                const idx = parseInt(cell.dataset.itemIndex);
                const item = this.character.bag[idx];
                if (!item) return;
                const slot = this.getSlotForItemType(item.type || item.slot || '');
                this.equipItem(item, slot);
            });
        });
    }

    onItemDragStart(e) {
        const cell = e.currentTarget;
        const itemIndex = parseInt(cell.dataset.itemIndex);
        this.draggedItem = this.character.bag[itemIndex];
        e.dataTransfer.effectAllowed = 'move';
        cell.style.opacity = '0.4';
    }

    onItemDragEnd(e) {
        e.currentTarget.style.opacity = '1';
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
        } else {
            const d = await response.json().catch(() => ({}));
            this.toast(d.error || 'Could not equip item', false);
        }
    }

    toast(msg, ok = true) {
        const el = document.createElement('div');
        el.className = `alert alert-${ok ? 'success' : 'warning'} alert-dismissible fade show position-fixed top-0 end-0 m-3`;
        el.style.zIndex = '10000';
        el.innerHTML = `${this.escapeHTML(msg)}<button type="button" class="btn-close" data-bs-dismiss="alert"></button>`;
        document.body.appendChild(el);
        setTimeout(() => el.remove(), 3000);
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
        if (!item) return;
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
                <div class="tooltip-item-type">${this.escapeHTML(item.type || item.slot || '')}</div>
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
            hands: 'Hands',
            ring1: 'Ring 1',
            ring2: 'Ring 2',
            ring: 'Ring',
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
            hands: '<i class="bi bi-hand-index"></i>',
            ring1: '<i class="bi bi-circle"></i>',
            ring2: '<i class="bi bi-circle"></i>',
            ring: '<i class="bi bi-circle"></i>',
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
            hands: 'hands',
            ring: 'ring',
            ring1: 'ring1',
            amulet: 'amulet',
            legs: 'legs'
        };
        return mapping[type] || 'weapon';
    }

    getItemStats(item) {
        if (item.level) {
            return `Level ${item.level}`;
        }
        return '';
    }

    parseItemStats(item) {
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
        // Read directly from the character stats returned by the API
        const s = (this.character && this.character.stats) || {};
        return {
            hp:        s.hp        || 0,
            max_hp:    s.max_hp    || 0,
            mana:      s.mana      || 0,
            max_mana:  s.max_mana  || 0,
            attack:    s.attack    || 0,
            defense:   s.defense   || 0,
            level:     s.level     || this.character.level || 1,
            xp:        s.xp        || 0,
            xp_to_next: s.xp_to_next || 100
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
