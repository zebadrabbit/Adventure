/**
 * Party Management System
 *
 * Handles party formations, shared inventory, member management, and party buffs.
 */

class PartyManagementSystem {
    constructor() {
        this.currentPartyId = null;
        this.currentTab = 'formation';
        this.draggedMember = null;

        this.init();
    }

    init() {
        console.log('Party Management System initialized');

        // Set up drag and drop for formation editor
        this.setupDragAndDrop();
    }

    /**
     * Open party management modal for a specific party
     */
    async openParty(partyId) {
        this.currentPartyId = partyId;

        try {
            const response = await fetch(`/api/party/${partyId}`);
            if (!response.ok) throw new Error('Failed to load party');

            const party = await response.json();
            this.renderPartyModal(party);

        } catch (error) {
            console.error('Error loading party:', error);
            this.showNotification('Failed to load party', 'error');
        }
    }

    /**
     * Render the party management modal
     */
    renderPartyModal(party) {
        const modal = document.getElementById('partyModal');
        if (!modal) {
            console.error('Party modal not found');
            return;
        }

        // Update header
        document.getElementById('partyName').textContent = party.name;
        document.getElementById('partyLevel').textContent = party.party_level;
        document.getElementById('partyMembers').textContent = party.members.length;
        document.getElementById('partySharedGold').textContent = party.shared_gold;

        // Store party data
        this.partyData = party;

        // Show modal
        modal.classList.add('active');

        // Render initial tab
        this.switchTab('formation');
    }

    /**
     * Close the party modal
     */
    closeModal() {
        const modal = document.getElementById('partyModal');
        if (modal) {
            modal.classList.remove('active');
        }
    }

    /**
     * Switch between tabs
     */
    switchTab(tabName) {
        this.currentTab = tabName;

        // Update tab buttons
        document.querySelectorAll('.party-tab').forEach(tab => {
            tab.classList.toggle('active', tab.dataset.tab === tabName);
        });

        // Update tab panes
        document.querySelectorAll('.party-tab-pane').forEach(pane => {
            pane.classList.toggle('active', pane.id === `${tabName}Tab`);
        });

        // Render tab content
        switch (tabName) {
            case 'formation':
                this.renderFormationTab();
                break;
            case 'members':
                this.renderMembersTab();
                break;
            case 'inventory':
                this.renderInventoryTab();
                break;
            case 'buffs':
                this.renderBuffsTab();
                break;
        }
    }

    /**
     * Render formation editor tab
     */
    renderFormationTab() {
        if (!this.partyData) return;

        const members = this.partyData.members;

        // Organize members by position
        const positions = {
            front: members.filter(m => m.position === 'front'),
            middle: members.filter(m => m.position === 'middle'),
            back: members.filter(m => m.position === 'back')
        };

        // Render each zone
        ['front', 'middle', 'back'].forEach(position => {
            const container = document.getElementById(`${position}Zone`);
            const countEl = container.querySelector('.formation-zone-count');
            const membersEl = container.querySelector('.formation-members');

            countEl.textContent = `${positions[position].length} members`;

            membersEl.innerHTML = positions[position].map(member => `
                <div class="formation-member-card"
                     draggable="true"
                     data-member-id="${member.character_id}"
                     data-position="${position}">
                    <div class="formation-member-info">
                        <div class="formation-member-icon"></div>
                        <div class="formation-member-details">
                            <div class="formation-member-name">${member.character_name}</div>
                            <div class="formation-member-role">${member.role}</div>
                        </div>
                    </div>
                </div>
            `).join('');
        });

        // Render formation preview
        this.renderFormationPreview();
    }

    /**
     * Render formation preview visualization
     */
    renderFormationPreview() {
        const preview = document.getElementById('formationPreview');
        if (!preview) return;

        const members = this.partyData.members;

        // Group by position
        const positions = {
            front: members.filter(m => m.position === 'front'),
            middle: members.filter(m => m.position === 'middle'),
            back: members.filter(m => m.position === 'back')
        };

        preview.innerHTML = `
            <div class="formation-preview-title">Battle Formation</div>
            <div class="formation-preview-grid">
                ${this.renderFormationRow('front', positions.front)}
                ${this.renderFormationRow('middle', positions.middle)}
                ${this.renderFormationRow('back', positions.back)}
            </div>
        `;
    }

    renderFormationRow(position, members) {
        const maxSlots = 4;
        const slots = [];

        for (let i = 0; i < maxSlots; i++) {
            const member = members[i];
            if (member) {
                slots.push(`
                    <div class="formation-preview-slot filled ${member.role}">
                        <div class="formation-preview-name">${member.character_name}</div>
                    </div>
                `);
            } else {
                slots.push(`
                    <div class="formation-preview-slot"></div>
                `);
            }
        }

        return `<div class="formation-preview-row">${slots.join('')}</div>`;
    }

    /**
     * Render members list tab
     */
    renderMembersTab() {
        if (!this.partyData) return;

        const container = document.getElementById('partyMembersList');

        container.innerHTML = this.partyData.members.map(member => `
            <div class="party-member-card">
                <div class="party-member-header">
                    <div class="party-member-portrait"></div>
                    <div class="party-member-identity">
                        <div class="party-member-name">${member.character_name}</div>
                        <div class="party-member-level">Level ${member.level || 1}</div>
                    </div>
                </div>
                <div class="party-member-stats">
                    <div class="party-member-stat">
                        <span class="party-member-stat-label">Role:</span>
                        <span class="party-member-stat-value">${member.role}</span>
                    </div>
                    <div class="party-member-stat">
                        <span class="party-member-stat-label">Position:</span>
                        <span class="party-member-stat-value">${member.position}</span>
                    </div>
                    <div class="party-member-stat">
                        <span class="party-member-stat-label">HP:</span>
                        <span class="party-member-stat-value">${member.stats?.hp || 100}</span>
                    </div>
                    <div class="party-member-stat">
                        <span class="party-member-stat-label">Damage:</span>
                        <span class="party-member-stat-value">${member.stats?.damage || 10}</span>
                    </div>
                </div>
                <div class="party-member-actions">
                    <button class="party-member-btn" onclick="partySystem.changeRole(${member.character_id})">
                        Change Role
                    </button>
                    <button class="party-member-btn danger" onclick="partySystem.removeMember(${member.character_id})">
                        Remove
                    </button>
                </div>
            </div>
        `).join('');
    }

    /**
     * Render shared inventory tab
     */
    async renderInventoryTab() {
        if (!this.partyData) return;

        try {
            const response = await fetch(`/api/party/${this.currentPartyId}/inventory`);
            if (!response.ok) throw new Error('Failed to load inventory');

            const inventory = await response.json();

            const container = document.getElementById('sharedItemsList');

            if (inventory.items.length === 0) {
                container.innerHTML = `
                    <div class="empty-state">
                        <div class="empty-state-icon">📦</div>
                        <div class="empty-state-message">No shared items</div>
                        <div class="empty-state-hint">Contribute items from your personal inventory</div>
                    </div>
                `;
                return;
            }

            container.innerHTML = inventory.items.map(item => `
                <div class="shared-item-card rarity-${item.rarity || 'common'}">
                    <div class="shared-item-header">
                        <div class="shared-item-name">${item.name}</div>
                        <div class="shared-item-quantity">×${item.quantity}</div>
                    </div>
                    <div class="shared-item-description">${item.description || ''}</div>
                    <div class="shared-item-actions">
                        <button class="shared-item-btn" onclick="partySystem.takeItem('${item.slug}')">
                            Take
                        </button>
                        <button class="shared-item-btn" onclick="partySystem.useItem('${item.slug}')">
                            Use
                        </button>
                    </div>
                </div>
            `).join('');

        } catch (error) {
            console.error('Error loading shared inventory:', error);
        }
    }

    /**
     * Render party buffs tab
     */
    async renderBuffsTab() {
        if (!this.partyData) return;

        try {
            const response = await fetch(`/api/party/${this.currentPartyId}/buffs`);
            if (!response.ok) throw new Error('Failed to load buffs');

            const buffs = await response.json();

            const container = document.getElementById('partyBuffsList');

            if (buffs.length === 0) {
                container.innerHTML = `
                    <div class="empty-state">
                        <div class="empty-state-icon">✨</div>
                        <div class="empty-state-message">No active buffs</div>
                        <div class="empty-state-hint">Earn buffs through formations, leadership, and special items</div>
                    </div>
                `;
                return;
            }

            container.innerHTML = buffs.map(buff => {
                const effects = JSON.parse(buff.effect_json || '{}');
                const effectStrings = Object.entries(effects).map(([key, value]) => {
                    if (key.includes('percent')) {
                        return `+${value}% ${key.replace('_percent', '')}`;
                    }
                    return `+${value} ${key}`;
                });

                return `
                    <div class="party-buff-card">
                        <div class="party-buff-header">
                            <div class="party-buff-name">${buff.name}</div>
                            <div class="party-buff-type">${buff.buff_type}</div>
                        </div>
                        <div class="party-buff-description">${buff.description}</div>
                        <div class="party-buff-effects">
                            ${effectStrings.map(e => `<div class="party-buff-effect">${e}</div>`).join('')}
                        </div>
                    </div>
                `;
            }).join('');

        } catch (error) {
            console.error('Error loading party buffs:', error);
        }
    }

    /**
     * Set up drag and drop for formation editor
     */
    setupDragAndDrop() {
        document.addEventListener('dragstart', (e) => {
            if (e.target.classList.contains('formation-member-card')) {
                this.draggedMember = {
                    memberId: e.target.dataset.memberId,
                    fromPosition: e.target.dataset.position
                };
                e.target.classList.add('dragging');
            }
        });

        document.addEventListener('dragend', (e) => {
            if (e.target.classList.contains('formation-member-card')) {
                e.target.classList.remove('dragging');
            }
        });

        document.addEventListener('dragover', (e) => {
            if (e.target.closest('.formation-zone')) {
                e.preventDefault();
            }
        });

        document.addEventListener('drop', async (e) => {
            const zone = e.target.closest('.formation-zone');
            if (zone && this.draggedMember) {
                e.preventDefault();

                const toPosition = zone.classList.contains('front') ? 'front' :
                    zone.classList.contains('middle') ? 'middle' : 'back';

                if (toPosition !== this.draggedMember.fromPosition) {
                    await this.updateMemberPosition(
                        this.draggedMember.memberId,
                        toPosition
                    );
                }

                this.draggedMember = null;
            }
        });
    }

    /**
     * Update a member's position in the formation
     */
    async updateMemberPosition(memberId, newPosition) {
        try {
            const response = await fetch(`/api/party/${this.currentPartyId}/member/${memberId}/position`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ position: newPosition })
            });

            if (!response.ok) throw new Error('Failed to update position');

            // Reload party data
            const partyResponse = await fetch(`/api/party/${this.currentPartyId}`);
            this.partyData = await partyResponse.json();

            // Re-render formation tab
            this.renderFormationTab();
            this.showNotification('Formation updated', 'success');

        } catch (error) {
            console.error('Error updating position:', error);
            this.showNotification('Failed to update formation', 'error');
        }
    }

    /**
     * Change a member's role
     */
    async changeRole(memberId) {
        const roles = ['tank', 'dps', 'healer', 'support'];
        const currentMember = this.partyData.members.find(m => m.character_id === memberId);
        const currentIndex = roles.indexOf(currentMember.role);
        const newRole = roles[(currentIndex + 1) % roles.length];

        try {
            const response = await fetch(`/api/party/${this.currentPartyId}/member/${memberId}/role`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ role: newRole })
            });

            if (!response.ok) throw new Error('Failed to update role');

            // Reload and re-render
            const partyResponse = await fetch(`/api/party/${this.currentPartyId}`);
            this.partyData = await partyResponse.json();
            this.renderMembersTab();
            this.showNotification(`Role changed to ${newRole}`, 'success');

        } catch (error) {
            console.error('Error updating role:', error);
            this.showNotification('Failed to update role', 'error');
        }
    }

    /**
     * Remove a member from the party
     */
    async removeMember(memberId) {
        if (!confirm('Remove this character from the party?')) return;

        try {
            const response = await fetch(`/api/party/${this.currentPartyId}/member/${memberId}`, {
                method: 'DELETE'
            });

            if (!response.ok) throw new Error('Failed to remove member');

            // Reload and re-render
            const partyResponse = await fetch(`/api/party/${this.currentPartyId}`);
            this.partyData = await partyResponse.json();
            this.renderMembersTab();
            this.showNotification('Member removed', 'success');

        } catch (error) {
            console.error('Error removing member:', error);
            this.showNotification('Failed to remove member', 'error');
        }
    }

    /**
     * Take an item from shared inventory
     */
    async takeItem(itemSlug) {
        try {
            const response = await fetch(`/api/party/${this.currentPartyId}/inventory/take`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ item_slug: itemSlug, quantity: 1 })
            });

            if (!response.ok) throw new Error('Failed to take item');

            this.renderInventoryTab();
            this.showNotification('Item taken', 'success');

        } catch (error) {
            console.error('Error taking item:', error);
            this.showNotification('Failed to take item', 'error');
        }
    }

    /**
     * Use an item from shared inventory
     */
    async useItem(itemSlug) {
        try {
            const response = await fetch(`/api/party/${this.currentPartyId}/inventory/use`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ item_slug: itemSlug })
            });

            if (!response.ok) throw new Error('Failed to use item');

            const result = await response.json();
            this.renderInventoryTab();
            this.showNotification(result.message || 'Item used', 'success');

        } catch (error) {
            console.error('Error using item:', error);
            this.showNotification('Failed to use item', 'error');
        }
    }

    /**
     * Show a toast notification
     */
    showNotification(message, type = 'info') {
        // Reuse existing notification system if available
        if (window.showToast) {
            window.showToast(message, type);
        } else {
            console.log(`[${type}] ${message}`);
        }
    }
}

// Initialize global party system
const partySystem = new PartyManagementSystem();

// Helper function for testing
function testParty(partyId = 1) {
    partySystem.openParty(partyId);
}
