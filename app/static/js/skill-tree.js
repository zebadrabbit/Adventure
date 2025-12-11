/**
 * Skill/Talent Tree System
 *
 * Manages skill trees, talent point allocation, and skill unlocking.
 */

class SkillTreeSystem {
    constructor() {
        this.currentCharacterId = null;
        this.currentTreeId = null;
        this.skillTrees = [];
        this.skills = [];
        this.characterSkills = [];
        this.talentPoints = { available: 0, total_earned: 0, total_spent: 0 };
        this.activeTooltip = null;

        this.init();
    }

    init() {
        console.log('Skill Tree System initialized');
    }

    /**
     * Open skill tree modal for a character
     */
    async openSkillTree(characterId) {
        this.currentCharacterId = characterId;

        try {
            // Load skill trees
            const treesResponse = await fetch('/api/skill-trees');
            if (!treesResponse.ok) throw new Error('Failed to load skill trees');
            this.skillTrees = await treesResponse.json();

            // Load character's talent points
            const pointsResponse = await fetch(`/api/characters/${characterId}/talent-points`);
            if (!pointsResponse.ok) throw new Error('Failed to load talent points');
            this.talentPoints = await pointsResponse.json();

            // Load character's learned skills
            const skillsResponse = await fetch(`/api/characters/${characterId}/skills`);
            if (!skillsResponse.ok) throw new Error('Failed to load character skills');
            this.characterSkills = await skillsResponse.json();

            this.renderModal();

            // Open first available tree
            if (this.skillTrees.length > 0) {
                this.switchTree(this.skillTrees[0].id);
            }

        } catch (error) {
            console.error('Error loading skill tree:', error);
            this.showNotification('Failed to load skill tree', 'error');
        }
    }

    /**
     * Render the skill tree modal
     */
    renderModal() {
        const modal = document.getElementById('skillModal');
        if (!modal) {
            console.error('Skill modal not found');
            return;
        }

        // Update talent points display
        document.getElementById('talentPointsValue').textContent = this.talentPoints.available;

        // Render tree selector buttons
        const treeSelector = document.getElementById('treeSelector');
        treeSelector.innerHTML = this.skillTrees.map(tree => `
            <button class="tree-selector-btn ${tree.id === this.currentTreeId ? 'active' : ''}"
                    onclick="skillTreeSystem.switchTree(${tree.id})">
                <div class="tree-selector-icon">🌳</div>
                <div class="tree-selector-name">${tree.name}</div>
                <div class="tree-selector-class">${tree.class_requirement || 'Universal'}</div>
            </button>
        `).join('');

        modal.classList.add('active');
    }

    /**
     * Close the skill tree modal
     */
    closeModal() {
        const modal = document.getElementById('skillModal');
        if (modal) {
            modal.classList.remove('active');
        }
        this.hideTooltip();
    }

    /**
     * Switch to a different skill tree
     */
    async switchTree(treeId) {
        this.currentTreeId = treeId;

        try {
            // Load skills for this tree
            const response = await fetch(`/api/skill-trees/${treeId}/skills`);
            if (!response.ok) throw new Error('Failed to load tree skills');
            this.skills = await response.json();

            // Update active tree selector button
            document.querySelectorAll('.tree-selector-btn').forEach(btn => {
                btn.classList.remove('active');
            });
            event.target.closest('.tree-selector-btn').classList.add('active');

            // Render the skill tree
            this.renderSkillTree();

        } catch (error) {
            console.error('Error loading tree skills:', error);
            this.showNotification('Failed to load skill tree', 'error');
        }
    }

    /**
     * Render the skill tree visualization
     */
    renderSkillTree() {
        const canvas = document.getElementById('skillTreeCanvas');
        if (!canvas) return;

        canvas.innerHTML = '';

        if (this.skills.length === 0) {
            canvas.innerHTML = `
                <div class="skill-tree-empty">
                    <div class="skill-tree-empty-icon">🌳</div>
                    <div class="skill-tree-empty-message">No skills in this tree</div>
                    <div class="skill-tree-empty-hint">Check back later for updates</div>
                </div>
            `;
            return;
        }

        // Draw connection lines first
        this.drawConnections();

        // Draw skill nodes
        this.skills.forEach(skill => {
            const node = this.createSkillNode(skill);
            canvas.appendChild(node);
        });
    }

    /**
     * Draw connection lines between skills
     */
    drawConnections() {
        const canvas = document.getElementById('skillTreeCanvas');

        this.skills.forEach(skill => {
            if (!skill.required_skill_id) return;

            const parentSkill = this.skills.find(s => s.id === skill.required_skill_id);
            if (!parentSkill) return;

            // Calculate positions
            const x1 = parentSkill.position_x * 200 + 100;
            const y1 = parentSkill.position_y * 200 + 100;
            const x2 = skill.position_x * 200 + 100;
            const y2 = skill.position_y * 200 + 100;

            // Calculate line properties
            const length = Math.sqrt(Math.pow(x2 - x1, 2) + Math.pow(y2 - y1, 2));
            const angle = Math.atan2(y2 - y1, x2 - x1) * 180 / Math.PI;

            // Check if connection should be highlighted
            const isUnlocked = this.isSkillUnlocked(skill.id) && this.isSkillUnlocked(parentSkill.id);

            const line = document.createElement('div');
            line.className = `skill-connection ${isUnlocked ? 'unlocked' : ''}`;
            line.style.left = `${x1}px`;
            line.style.top = `${y1}px`;
            line.style.width = `${length}px`;
            line.style.transform = `rotate(${angle}deg)`;

            canvas.appendChild(line);
        });
    }

    /**
     * Create a skill node element
     */
    createSkillNode(skill) {
        const node = document.createElement('div');
        node.className = 'skill-node';

        // Determine skill state
        const isUnlocked = this.isSkillUnlocked(skill.id);
        const isAvailable = this.isSkillAvailable(skill);
        const state = isUnlocked ? 'unlocked' : (isAvailable ? 'available' : 'locked');

        node.classList.add(state);
        node.classList.add(`skill-type-${skill.skill_type}`);

        // Position node
        node.style.left = `${skill.position_x * 200 + 60}px`;
        node.style.top = `${skill.position_y * 200 + 60}px`;

        // Render node content
        node.innerHTML = `
            <div class="skill-node-icon-wrapper">
                <div class="skill-node-icon">${this.getSkillIcon(skill.icon)}</div>
                <div class="skill-tier-badge">T${skill.tier}</div>
            </div>
            <div class="skill-node-name">${skill.name}</div>
            <div class="skill-node-cost">${skill.cost} PT</div>
        `;

        // Add event listeners
        node.addEventListener('mouseenter', (e) => this.showTooltip(skill, e));
        node.addEventListener('mouseleave', () => this.hideTooltip());
        node.addEventListener('click', () => this.handleSkillClick(skill));

        return node;
    }

    /**
     * Get icon for skill (placeholder - expand with real icons)
     */
    getSkillIcon(iconName) {
        const iconMap = {
            'sword-clash': '⚔️',
            'shield': '🛡️',
            'tornado': '🌪️',
            'armor': '🧥',
            'fire': '🔥',
            'flame': '🔥',
            'sparkles': '✨',
            'lightning-bolt': '⚡',
            'target': '🎯',
            'meteor': '☄️',
            'health-increase': '❤️',
            'shield-checkered': '��️',
            'hearts': '💕',
            'shield-alt': '🛡️',
            'angel': '👼'
        };
        return iconMap[iconName] || '⭐';
    }

    /**
     * Check if a skill is unlocked
     */
    isSkillUnlocked(skillId) {
        return this.characterSkills.some(cs => cs.skill_id === skillId);
    }

    /**
     * Check if a skill can be unlocked
     */
    isSkillAvailable(skill) {
        // Already unlocked
        if (this.isSkillUnlocked(skill.id)) return false;

        // Check level requirement
        // (Need to get character level - for now assume available)

        // Check prerequisite skill
        if (skill.required_skill_id && !this.isSkillUnlocked(skill.required_skill_id)) {
            return false;
        }

        // Check talent points
        if (this.talentPoints.available < skill.cost) {
            return false;
        }

        return true;
    }

    /**
     * Show skill tooltip
     */
    showTooltip(skill, event) {
        const tooltip = document.getElementById('skillTooltip');
        if (!tooltip) return;

        const isUnlocked = this.isSkillUnlocked(skill.id);
        const isAvailable = this.isSkillAvailable(skill);

        // Parse effects
        const effects = JSON.parse(skill.effect_json);
        const effectStrings = Object.entries(effects).map(([key, value]) => {
            let label = key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
            let displayValue = value;

            if (key.includes('percent')) {
                displayValue = `+${value}%`;
                label = label.replace(' Percent', '');
            } else if (key.includes('bonus') || key.includes('multiplier')) {
                displayValue = `+${value}`;
            }

            return { label, value: displayValue };
        });

        // Build tooltip content
        tooltip.innerHTML = `
            <div class="skill-tooltip-header">
                <div class="skill-tooltip-name">${skill.name}</div>
                <div class="skill-tooltip-type">${skill.skill_type}</div>
            </div>
            <div class="skill-tooltip-description">${skill.description}</div>
            <div class="skill-tooltip-effects">
                ${effectStrings.map(e => `
                    <div class="skill-tooltip-effect">
                        <span class="skill-tooltip-effect-label">${e.label}:</span>
                        <span class="skill-tooltip-effect-value">${e.value}</span>
                    </div>
                `).join('')}
            </div>
            <div class="skill-tooltip-requirements">
                <div class="skill-tooltip-requirement ${true ? 'met' : 'unmet'}">
                    ✓ Level ${skill.required_level}
                </div>
                ${skill.required_skill_id ? `
                    <div class="skill-tooltip-requirement ${this.isSkillUnlocked(skill.required_skill_id) ? 'met' : 'unmet'}">
                        ${this.isSkillUnlocked(skill.required_skill_id) ? '✓' : '✗'}
                        Requires: ${this.skills.find(s => s.id === skill.required_skill_id)?.name || 'Unknown Skill'}
                    </div>
                ` : ''}
                <div class="skill-tooltip-requirement ${this.talentPoints.available >= skill.cost ? 'met' : 'unmet'}">
                    ${this.talentPoints.available >= skill.cost ? '✓' : '✗'}
                    Cost: ${skill.cost} Talent Points
                </div>
            </div>
            <div class="skill-tooltip-footer">
                ${!isUnlocked ? `
                    <button class="skill-tooltip-unlock-btn"
                            ${!isAvailable ? 'disabled' : ''}
                            onclick="skillTreeSystem.unlockSkill(${skill.id})">
                        ${isAvailable ? 'Unlock Skill' : 'Cannot Unlock'}
                    </button>
                ` : '<div style="text-align: center; color: #48bb78; font-weight: 600;">✓ Unlocked</div>'}
            </div>
        `;

        // Position tooltip near cursor
        const rect = event.target.closest('.skill-node').getBoundingClientRect();
        tooltip.style.left = `${rect.right + 15}px`;
        tooltip.style.top = `${rect.top}px`;

        tooltip.classList.add('active');
        this.activeTooltip = skill.id;
    }

    /**
     * Hide skill tooltip
     */
    hideTooltip() {
        const tooltip = document.getElementById('skillTooltip');
        if (tooltip) {
            tooltip.classList.remove('active');
        }
        this.activeTooltip = null;
    }

    /**
     * Handle skill node click
     */
    handleSkillClick(skill) {
        if (this.isSkillUnlocked(skill.id)) {
            // Already unlocked - maybe show details
            return;
        }

        if (this.isSkillAvailable(skill)) {
            this.unlockSkill(skill.id);
        }
    }

    /**
     * Unlock a skill
     */
    async unlockSkill(skillId) {
        const skill = this.skills.find(s => s.id === skillId);
        if (!skill) return;

        if (!this.isSkillAvailable(skill)) {
            this.showNotification('Skill requirements not met', 'error');
            return;
        }

        try {
            const response = await fetch(`/api/characters/${this.currentCharacterId}/skills`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ skill_id: skillId })
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || 'Failed to unlock skill');
            }

            const result = await response.json();

            // Update local state
            this.characterSkills.push({
                skill_id: skillId,
                skill_rank: 1,
                unlocked_at: new Date().toISOString()
            });

            this.talentPoints.available = result.remaining_points;
            this.talentPoints.total_spent += skill.cost;

            // Update display
            document.getElementById('talentPointsValue').textContent = this.talentPoints.available;
            this.renderSkillTree();
            this.hideTooltip();

            this.showNotification(`Unlocked: ${skill.name}!`, 'success');

        } catch (error) {
            console.error('Error unlocking skill:', error);
            this.showNotification(error.message || 'Failed to unlock skill', 'error');
        }
    }

    /**
     * Show a toast notification
     */
    showNotification(message, type = 'info') {
        if (window.showToast) {
            window.showToast(message, type);
        } else {
            console.log(`[${type}] ${message}`);
        }
    }
}

// Initialize global skill tree system
const skillTreeSystem = new SkillTreeSystem();

// Helper function for testing
function testSkillTree(characterId = 1) {
    skillTreeSystem.openSkillTree(characterId);
}
