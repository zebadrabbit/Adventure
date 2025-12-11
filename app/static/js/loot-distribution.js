/**
 * Loot Distribution System
 *
 * Features:
 * - Displays unclaimed loot after combat
 * - Allows equitable distribution among party members
 * - Drag-and-drop or click-to-assign items
 * - Real-time Socket.IO updates for multiplayer
 * - Auto-shows modal when loot is available
 *
 * API Endpoints:
 * - GET  /api/loot/pending - Get pending loot for current combat session
 * - POST /api/loot/assign - Assign item to character
 * - POST /api/loot/confirm - Confirm all distributions and close loot
 *
 * Events:
 * - 'loot-available' - Fired when new loot is awarded
 * - 'loot-assigned' - Fired when item is assigned to character
 * - 'loot-distributed' - Fired when all loot is distributed
 *
 * Usage:
 * - Automatically shown after combat completion
 * - Can be manually opened via: lootDistribution.showForCombat(combatId)
 */

class LootDistribution {
    constructor() {
        this.modal = null;
        this.pendingLoot = [];
        this.assignments = {}; // { lootItemId: characterId }
        this.partyMembers = [];
        this.combatId = null;
        this.selectedItemId = null;

        this.init();
    }

    init() {
        // Create modal HTML
        this.createModal();

        // Listen for combat completion events
        document.addEventListener('combat-complete', (e) => {
            if (e.detail && e.detail.combatId) {
                this.checkForLoot(e.detail.combatId);
            }
        });

        // Socket.IO integration
        if (window.socket) {
            window.socket.on('loot_available', (data) => {
                if (data.combat_id) {
                    this.checkForLoot(data.combat_id);
                }
            });
        }
    }

    createModal() {
        const modalHTML = `
<div class="modal fade" id="loot-distribution-modal" tabindex="-1" aria-labelledby="loot-distribution-title" aria-hidden="true">
    <div class="modal-dialog modal-lg loot-distribution-modal">
        <div class="modal-content bg-transparent border-0">
            <div class="loot-distribution-header">
                <h2 class="loot-distribution-title" id="loot-distribution-title">
                    <i class="bi bi-treasure-fill me-2"></i>Loot Distribution
                </h2>
                <p class="loot-subtitle">Assign items to your party members</p>
            </div>

            <div class="loot-items-container">
                <div class="loot-items-grid" id="loot-items-grid">
                    <!-- Loot items populated here -->
                </div>
            </div>

            <div class="party-member-selector" id="party-selector" style="display: none;">
                <div class="party-member-selector-title">Assign to:</div>
                <div class="party-members-grid" id="party-members-grid">
                    <!-- Party members populated here -->
                </div>
            </div>

            <div class="loot-distribution-footer">
                <div class="loot-summary">
                    <span id="loot-assigned-count">0</span> / <span id="loot-total-count">0</span> items assigned
                    <span class="loot-summary-highlight ms-2" id="loot-unassigned-warning" style="display: none;">
                        <i class="bi bi-exclamation-triangle-fill"></i> Unassigned items will be lost
                    </span>
                </div>
                <div class="loot-action-buttons">
                    <button type="button" class="loot-btn loot-btn-secondary" data-bs-dismiss="modal">
                        Cancel
                    </button>
                    <button type="button" class="loot-btn loot-btn-primary" id="confirm-loot-btn" disabled>
                        Confirm Distribution
                    </button>
                </div>
            </div>
        </div>
    </div>
</div>`;

        document.body.insertAdjacentHTML('beforeend', modalHTML);
        this.modal = new bootstrap.Modal(document.getElementById('loot-distribution-modal'));

        // Event listeners
        document.getElementById('confirm-loot-btn').addEventListener('click', () => this.confirmDistribution());
    }

    async checkForLoot(combatId) {
        try {
            const response = await fetch(`/api/loot/pending?combat_id=${combatId}`);
            if (!response.ok) return;

            const data = await response.json();
            if (data.loot && data.loot.length > 0) {
                this.showLoot(combatId, data.loot, data.party);
            }
        } catch (err) {
            console.error('[loot-distribution] Failed to check for loot:', err);
        }
    }

    showLoot(combatId, loot, party) {
        this.combatId = combatId;
        this.pendingLoot = loot;
        this.partyMembers = party || [];
        this.assignments = {};
        this.selectedItemId = null;

        this.renderLoot();
        this.updateSummary();
        this.modal.show();
    }

    renderLoot() {
        const grid = document.getElementById('loot-items-grid');
        if (!this.pendingLoot || this.pendingLoot.length === 0) {
            grid.innerHTML = '<div class="text-center text-muted py-4">No loot available</div>';
            return;
        }

        const html = this.pendingLoot.map(item => {
            const assignedChar = this.assignments[item.id];
            const assignedMember = assignedChar ? this.partyMembers.find(p => p.id === assignedChar) : null;

            return `
<div class="loot-item-card ${assignedChar ? 'assigned' : ''}"
     data-item-id="${item.id}"
     data-rarity="${item.rarity || 'common'}"
     onclick="lootDistribution.selectItem(${item.id})">
    <div class="loot-item-header">
        <div class="loot-item-icon">
            ${this.getItemIcon(item.type)}
        </div>
        <div class="loot-item-info">
            <div class="loot-item-name">${item.name}</div>
            <div class="loot-item-type">
                <span class="badge bg-${this.getRarityColor(item.rarity)}">${item.rarity || 'common'}</span>
                ${item.type}
            </div>
        </div>
    </div>

    ${item.effects && Object.keys(item.effects).length > 0 ? `
    <div class="loot-item-stats">
        ${Object.entries(item.effects).map(([stat, val]) =>
                `<span class="loot-stat-badge">+${val} ${stat.toUpperCase()}</span>`
            ).join('')}
    </div>
    ` : ''}

    ${assignedMember ? `
    <div class="loot-assigned-to">
        <i class="bi bi-check-circle-fill"></i>
        Assigned to ${assignedMember.name}
    </div>
    ` : `
    <div class="quick-assign-buttons">
        ${this.partyMembers.slice(0, 4).map(member =>
                `<button class="quick-assign-btn" onclick="event.stopPropagation(); lootDistribution.assignItem(${item.id}, ${member.id});">
                ${member.name}
            </button>`
            ).join('')}
    </div>
    `}
</div>`;
        }).join('');

        grid.innerHTML = html;
    }

    selectItem(itemId) {
        this.selectedItemId = itemId;

        // Highlight selected item
        document.querySelectorAll('.loot-item-card').forEach(card => {
            card.style.outline = card.dataset.itemId == itemId ? '2px solid #fbbf24' : '';
        });

        // Show party selector
        this.renderPartySelector();
        document.getElementById('party-selector').style.display = 'block';
    }

    renderPartySelector() {
        const grid = document.getElementById('party-members-grid');
        if (!this.partyMembers || this.partyMembers.length === 0) {
            grid.innerHTML = '<div class="text-muted">No party members available</div>';
            return;
        }

        const currentAssignment = this.selectedItemId ? this.assignments[this.selectedItemId] : null;

        const html = this.partyMembers.map(member => `
<div class="party-member-option ${currentAssignment === member.id ? 'selected' : ''}"
     onclick="lootDistribution.assignItem(${this.selectedItemId}, ${member.id})">
    <div class="party-member-icon">
        ${this.getClassIcon(member.class)}
    </div>
    <div class="party-member-details">
        <div class="party-member-name">${member.name}</div>
        <div class="party-member-class">${member.class}</div>
    </div>
</div>`).join('');

        grid.innerHTML = html;
    }

    assignItem(itemId, characterId) {
        this.assignments[itemId] = characterId;
        this.renderLoot();
        this.updateSummary();

        // Hide party selector
        document.getElementById('party-selector').style.display = 'none';
        this.selectedItemId = null;

        // Show toast
        const item = this.pendingLoot.find(i => i.id === itemId);
        const member = this.partyMembers.find(p => p.id === characterId);
        if (item && member) {
            this.showToast(`${item.name} assigned to ${member.name}`);
        }
    }

    updateSummary() {
        const totalCount = this.pendingLoot.length;
        const assignedCount = Object.keys(this.assignments).length;

        document.getElementById('loot-total-count').textContent = totalCount;
        document.getElementById('loot-assigned-count').textContent = assignedCount;

        const confirmBtn = document.getElementById('confirm-loot-btn');
        const warning = document.getElementById('loot-unassigned-warning');

        if (assignedCount === totalCount) {
            confirmBtn.disabled = false;
            warning.style.display = 'none';
        } else if (assignedCount > 0) {
            confirmBtn.disabled = false;
            warning.style.display = 'inline';
        } else {
            confirmBtn.disabled = true;
            warning.style.display = 'none';
        }
    }

    async confirmDistribution() {
        if (Object.keys(this.assignments).length === 0) {
            alert('Please assign at least one item before confirming.');
            return;
        }

        try {
            const response = await fetch('/api/loot/confirm', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    combat_id: this.combatId,
                    assignments: this.assignments
                })
            });

            if (response.ok) {
                this.modal.hide();
                this.showToast('Loot distributed successfully!');

                // Fire event
                document.dispatchEvent(new CustomEvent('loot-distributed', {
                    detail: { combatId: this.combatId, assignments: this.assignments }
                }));

                // Refresh character data if progression system exists
                if (window.characterProgression) {
                    Object.values(this.assignments).forEach(charId => {
                        window.characterProgression.updateXPBar(charId);
                    });
                }
            } else {
                const error = await response.json();
                alert(error.error || 'Failed to distribute loot');
            }
        } catch (err) {
            console.error('[loot-distribution] Failed to confirm:', err);
            alert('Failed to distribute loot');
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

    getClassIcon(className) {
        const icons = {
            fighter: '<i class="bi bi-shield-fill"></i>',
            mage: '<i class="bi bi-star-fill"></i>',
            rogue: '<i class="bi bi-lightning-fill"></i>',
            cleric: '<i class="bi bi-heart-fill"></i>',
            ranger: '<i class="bi bi-bullseye"></i>',
            druid: '<i class="bi bi-tree-fill"></i>'
        };
        return icons[className?.toLowerCase()] || '<i class="bi bi-person-fill"></i>';
    }

    getRarityColor(rarity) {
        const colors = {
            common: 'secondary',
            uncommon: 'success',
            rare: 'primary',
            epic: 'purple',
            legendary: 'warning',
            mythic: 'danger'
        };
        return colors[rarity] || 'secondary';
    }

    showToast(message) {
        const toast = document.createElement('div');
        toast.className = 'loot-toast';
        toast.innerHTML = `
            <i class="bi bi-check-circle-fill text-success me-2"></i>
            ${message}
            <span class="loot-toast-close" onclick="this.parentElement.remove()">×</span>
        `;
        document.body.appendChild(toast);

        setTimeout(() => {
            toast.style.opacity = '0';
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }
}

// Initialize on page load
let lootDistribution;
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        lootDistribution = new LootDistribution();
        window.lootDistribution = lootDistribution;
    });
} else {
    lootDistribution = new LootDistribution();
    window.lootDistribution = lootDistribution;
}
