/**
 * Character Progression System
 *
 * Features:
 * - Automatic XP bars on all character cards
 * - Real-time XP gain animations with particles
 * - Level-up detection and celebration modal
 * - Interactive stat allocation interface
 * - XP particle effects based on progress
 * - Socket.IO integration for combat rewards
 *
 * XP Formula: XP required for level N = (N-1)² × 100
 * - Level 1: 0 XP
 * - Level 2: 100 XP
 * - Level 3: 400 XP
 * - Level 4: 900 XP
 * - Level 5: 1600 XP
 *
 * Stat Points: 5 points per level
 * Available Stats: STR, DEX, INT, CON, WIS, CHA
 *
 * API Endpoints:
 * - GET  /api/characters/{id} - Get character data
 * - POST /api/characters/{id}/level-up - Apply stat allocations
 *
 * Events:
 * - 'xp-gained' - Fired when XP is awarded
 * - 'character-leveled-up' - Fired when level increases
 *
 * Test Helpers (localhost only):
 * - testLevelUp(charId, level) - Trigger level-up modal
 * - testXPGain(charId, amount) - Simulate XP gain
 */

class CharacterProgression {
    constructor() {
        this.activeCharacter = null;
        this.pendingStatPoints = 0;
        this.statAllocations = {};
        this.init();
    }

    init() {
        this.createXPBars();
        this.createLevelUpModal();
        this.attachEventListeners();
        this.updateAllXPBars();
    }

    createXPBars() {
        // Add XP bars to character cards on dashboard
        document.querySelectorAll('.operative-card').forEach(card => {
            const charId = card.querySelector('[data-char-id]')?.dataset.charId;
            if (!charId) return;

            const statsBlock = card.querySelector('.stats-block');
            if (!statsBlock || statsBlock.querySelector('.xp-bar-container')) return;

            const xpBarHTML = `
<div class="xp-bar-container">
    <div class="xp-bar-label">
        <span>XP</span>
        <span id="xp-text-${charId}">0 / 100</span>
    </div>
    <div class="xp-bar">
        <div class="xp-fill" id="xp-fill-${charId}" style="width: 0%">
            <div class="xp-particles" id="xp-particles-${charId}"></div>
        </div>
        <div class="xp-text" id="xp-percent-${charId}">0%</div>
    </div>
</div>`;

            statsBlock.insertAdjacentHTML('beforeend', xpBarHTML);
        });
    }

    createLevelUpModal() {
        if (document.getElementById('level-up-modal')) return;

        const modalHTML = `
<div class="modal fade" id="level-up-modal" tabindex="-1" data-bs-backdrop="static">
    <div class="modal-dialog modal-lg">
        <div class="modal-content level-up-modal">
            <div class="modal-body">
                <div class="level-up-celebration">
                    <div class="level-up-particles" id="level-up-particles"></div>
                    <div class="level-up-title">LEVEL UP!</div>
                    <div class="level-number" id="level-up-number">1</div>
                </div>

                <div class="stat-allocation">
                    <div class="stat-points-available">
                        <i class="bi bi-star-fill me-2"></i>
                        <span id="stat-points-text">5</span> Stat Points Available
                    </div>
                    <div id="stat-allocation-rows"></div>
                </div>

                <div class="rewards-summary">
                    <div class="rewards-title">Rewards</div>
                    <div id="level-up-rewards"></div>
                </div>
            </div>
            <div class="modal-footer" style="border-top: 1px solid rgba(100,100,120,0.3);">
                <button type="button" class="btn btn-primary btn-lg" id="confirm-level-up">
                    <i class="bi bi-check-circle me-2"></i>Confirm
                </button>
            </div>
        </div>
    </div>
</div>`;

        document.body.insertAdjacentHTML('beforeend', modalHTML);

        // Attach confirm button handler
        document.getElementById('confirm-level-up').addEventListener('click', () => {
            this.confirmLevelUp();
        });
    }

    attachEventListeners() {
        // Listen for XP gain events from server
        document.addEventListener('xp-gained', (e) => {
            this.onXPGained(e.detail.charId, e.detail.amount, e.detail.newXP, e.detail.newLevel);
        });

        // Listen for level up events
        document.addEventListener('character-leveled-up', (e) => {
            this.onLevelUp(e.detail.charId, e.detail.newLevel, e.detail.statPoints);
        });
    }

    updateAllXPBars() {
        // Update all XP bars with current character data
        document.querySelectorAll('[data-char-id]').forEach(el => {
            const charId = el.dataset.charId;
            this.updateXPBar(charId);
        });
    }

    async updateXPBar(charId, checkLevelUp = false) {
        try {
            const response = await fetch(`/api/characters/${charId}`);
            if (!response.ok) return;

            const char = await response.json();

            // Check for level-up if requested
            if (checkLevelUp) {
                const oldLevel = this.getCharacterLevel(charId);
                if (char.level > oldLevel) {
                    // Character leveled up!
                    this.onLevelUp(charId, char.level, 5); // 5 stat points per level
                }
                this.setCharacterLevel(charId, char.level);
            }

            this.renderXPBar(charId, char.xp, char.level);
        } catch (err) {
            console.error('Failed to update XP bar:', err);
        }
    }

    getCharacterLevel(charId) {
        return parseInt(localStorage.getItem(`char_${charId}_level`) || '1');
    }

    setCharacterLevel(charId, level) {
        localStorage.setItem(`char_${charId}_level`, level.toString());
    } renderXPBar(charId, xp, level) {
        const xpForLevel = this.getXPForLevel(level);
        const xpForNextLevel = this.getXPForLevel(level + 1);
        const currentLevelXP = xp - xpForLevel;
        const requiredXP = xpForNextLevel - xpForLevel;
        const percent = Math.min(100, (currentLevelXP / requiredXP) * 100);

        const fillEl = document.getElementById(`xp-fill-${charId}`);
        const textEl = document.getElementById(`xp-text-${charId}`);
        const percentEl = document.getElementById(`xp-percent-${charId}`);

        if (fillEl) {
            fillEl.style.width = `${percent}%`;
        }

        if (textEl) {
            textEl.textContent = `${currentLevelXP} / ${requiredXP}`;
        }

        if (percentEl) {
            percentEl.textContent = `${Math.floor(percent)}%`;
        }

        // Add particles if bar is active
        this.addXPParticles(charId, percent);
    }

    addXPParticles(charId, percent) {
        const particlesEl = document.getElementById(`xp-particles-${charId}`);
        if (!particlesEl || percent < 10) return;

        // Remove old particles
        particlesEl.innerHTML = '';

        // Add new particles based on fill percentage
        const particleCount = Math.floor(percent / 10);
        for (let i = 0; i < particleCount; i++) {
            const particle = document.createElement('div');
            particle.className = 'xp-particle';
            particle.style.left = `${Math.random() * 100}%`;
            particle.style.animationDelay = `${Math.random() * 1.5}s`;
            particle.style.setProperty('--drift', `${(Math.random() - 0.5) * 20}px`);
            particlesEl.appendChild(particle);
        }
    }

    onXPGained(charId, amount, newXP, newLevel) {
        // Show XP gain notification
        this.showXPNotification(amount);

        // Animate XP bar
        setTimeout(() => {
            this.renderXPBar(charId, newXP, newLevel);
        }, 100);
    }

    showXPNotification(amount) {
        const notification = document.createElement('div');
        notification.className = 'xp-gain-notification';
        notification.innerHTML = `
            <i class="bi bi-star-fill me-2"></i>
            +<span class="xp-amount">${amount}</span> XP
        `;
        document.body.appendChild(notification);

        setTimeout(() => {
            notification.style.opacity = '0';
            setTimeout(() => notification.remove(), 300);
        }, 2000);
    }

    onLevelUp(charId, newLevel, statPoints) {
        this.activeCharacter = charId;
        this.pendingStatPoints = statPoints || 5;
        this.statAllocations = {};

        this.showLevelUpModal(newLevel);
    }

    showLevelUpModal(newLevel) {
        // Update level number
        document.getElementById('level-up-number').textContent = newLevel;

        // Add celebration particles
        this.addLevelUpParticles();

        // Render stat allocation UI
        this.renderStatAllocation();

        // Render rewards
        this.renderLevelUpRewards(newLevel);

        // Show modal
        const modal = new bootstrap.Modal(document.getElementById('level-up-modal'));
        modal.show();

        // Play celebration sound (if available)
        this.playCelebrationSound();
    }

    addLevelUpParticles() {
        const container = document.getElementById('level-up-particles');
        container.innerHTML = '';

        for (let i = 0; i < 50; i++) {
            const particle = document.createElement('div');
            particle.className = 'level-particle';
            particle.style.left = `${Math.random() * 100}%`;
            particle.style.bottom = '0';
            particle.style.animationDelay = `${Math.random() * 2}s`;
            container.appendChild(particle);
        }
    }

    renderStatAllocation() {
        const stats = [
            { key: 'str', name: 'Strength', icon: '<i class="bi bi-heart-fill text-danger"></i>', desc: 'Increases HP and physical damage' },
            { key: 'dex', name: 'Dexterity', icon: '<i class="bi bi-lightning-charge-fill text-warning"></i>', desc: 'Increases evasion and critical chance' },
            { key: 'int', name: 'Intelligence', icon: '<i class="bi bi-star-fill text-primary"></i>', desc: 'Increases mana and spell damage' },
            { key: 'con', name: 'Constitution', icon: '<i class="bi bi-shield-fill text-success"></i>', desc: 'Increases defense and HP regeneration' }
        ];

        const html = stats.map(stat => this.createStatAllocationRow(stat)).join('');
        document.getElementById('stat-allocation-rows').innerHTML = html;

        this.updateStatPointsDisplay();
    }

    createStatAllocationRow(stat) {
        const currentValue = 10; // Placeholder - would fetch from character
        const pending = this.statAllocations[stat.key] || 0;

        return `
<div class="stat-allocation-row">
    <div class="stat-name-icon">
        <div class="stat-icon-box">${stat.icon}</div>
        <div>
            <div class="stat-name-label">${stat.name}</div>
            <div class="stat-name-description">${stat.desc}</div>
        </div>
    </div>
    <div class="stat-allocation-controls">
        <button class="stat-increment-btn" onclick="characterProgression.decrementStat('${stat.key}')" ${pending === 0 ? 'disabled' : ''}>
            <i class="bi bi-dash"></i>
        </button>
        <div class="stat-current-value">${currentValue}</div>
        <div class="stat-pending-change">${pending > 0 ? `+${pending}` : ''}</div>
        <button class="stat-increment-btn" onclick="characterProgression.incrementStat('${stat.key}')" ${this.pendingStatPoints === 0 ? 'disabled' : ''}>
            <i class="bi bi-plus"></i>
        </button>
    </div>
</div>`;
    }

    incrementStat(statKey) {
        if (this.pendingStatPoints <= 0) return;

        this.statAllocations[statKey] = (this.statAllocations[statKey] || 0) + 1;
        this.pendingStatPoints--;

        this.renderStatAllocation();
        this.flashStatChange(statKey, '+');
    }

    decrementStat(statKey) {
        if (!this.statAllocations[statKey] || this.statAllocations[statKey] === 0) return;

        this.statAllocations[statKey]--;
        this.pendingStatPoints++;

        this.renderStatAllocation();
        this.flashStatChange(statKey, '-');
    }

    flashStatChange(statKey, direction) {
        // Visual feedback for stat changes
        const row = document.querySelector(`[onclick*="Stat('${statKey}')"]`)?.closest('.stat-allocation-row');
        if (!row) return;

        const flash = document.createElement('div');
        flash.textContent = direction === '+' ? '+1' : '-1';
        flash.style.cssText = `
            position: absolute;
            left: 50%;
            top: 50%;
            transform: translate(-50%, -50%);
            color: ${direction === '+' ? '#4ade80' : '#fb923c'};
            font-weight: bold;
            font-size: 1.5rem;
            pointer-events: none;
            animation: statPop 0.5s ease-out;
            z-index: 1000;
        `;
        row.style.position = 'relative';
        row.appendChild(flash);

        setTimeout(() => flash.remove(), 500);
    } updateStatPointsDisplay() {
        document.getElementById('stat-points-text').textContent = this.pendingStatPoints;
    }

    renderLevelUpRewards(newLevel) {
        const rewards = [
            { icon: '<i class="bi bi-star-fill text-warning"></i>', text: '<strong>5</strong> Stat Points' },
            { icon: '<i class="bi bi-heart-fill text-danger"></i>', text: '<strong>+10</strong> Maximum HP' },
            { icon: '<i class="bi bi-lightning-charge-fill text-primary"></i>', text: '<strong>+5</strong> Maximum Mana' }
        ];

        if (newLevel % 5 === 0) {
            rewards.push({ icon: '<i class="bi bi-gift-fill text-success"></i>', text: 'New Ability Unlocked' });
        }

        const html = rewards.map((reward, index) => `
<div class="reward-item" style="animation-delay: ${index * 0.1}s">
    <div class="reward-icon">${reward.icon}</div>
    <div class="reward-text">${reward.text}</div>
</div>`).join('');

        document.getElementById('level-up-rewards').innerHTML = html;
    }

    async confirmLevelUp() {
        if (this.pendingStatPoints > 0) {
            if (!confirm(`You have ${this.pendingStatPoints} unallocated stat points. Confirm anyway?`)) {
                return;
            }
        }

        try {
            const response = await fetch(`/api/characters/${this.activeCharacter}/level-up`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ stat_allocations: this.statAllocations })
            });

            if (response.ok) {
                // Close modal
                bootstrap.Modal.getInstance(document.getElementById('level-up-modal')).hide();

                // Refresh character data
                this.updateXPBar(this.activeCharacter);

                // Show success message
                this.showSuccessMessage('Character leveled up successfully!');
            }
        } catch (err) {
            console.error('Failed to confirm level up:', err);
        }
    }

    showSuccessMessage(message) {
        // Placeholder - would show toast notification
        console.log(message);
    }

    playCelebrationSound() {
        // Placeholder for sound effect
    }

    getXPForLevel(level) {
        // XP curve: level^2 * 100
        return Math.floor(Math.pow(level - 1, 2) * 100);
    }

    // Development helper: Simulate XP gain for testing
    testXPGain(charId, amount = 100) {
        if (typeof charId === 'string') {
            charId = parseInt(charId);
        }
        this.showXPNotification(amount);
        setTimeout(() => {
            this.updateXPBar(charId, true);
        }, 500);
        console.log(`Simulated ${amount} XP gain for character ${charId}`);
    }

    // Development helper: Trigger level-up modal for testing
    testLevelUp(charId, level = 2) {
        if (typeof charId === 'string') {
            charId = parseInt(charId);
        }
        this.onLevelUp(charId, level, 5);
        console.log(`Triggered level-up modal for character ${charId} to level ${level}`);
    }
}

// Initialize global instance
window.characterProgression = new CharacterProgression();

// Expose test helpers in development
if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
    window.testLevelUp = (charId, level) => window.characterProgression.testLevelUp(charId, level);
    window.testXPGain = (charId, amount) => window.characterProgression.testXPGain(charId, amount);
    console.log('%c💫 Character Progression System Loaded', 'color: #fbbf24; font-weight: bold');
    console.log('%cTest commands available:', 'color: #64b4ff');
    console.log('%c  testLevelUp(charId, level) - Trigger level-up modal', 'color: #888');
    console.log('%c  testXPGain(charId, amount) - Simulate XP gain', 'color: #888');
}
