/**
 * Character Progression: stat-point allocation.
 *
 * The XP bar and the "Allocate N Stat Points" badge are server-rendered
 * (app/templates/dashboard.html, from app/routes/dashboard_helpers.py) using
 * already-known data, so no fetch is needed just to display them. This module
 * only handles the interactive allocation flow: opening the modal, fetching the
 * character's live stats/stat_points, submitting allocations, and updating the
 * server-rendered bar/badge in place afterward.
 */
class CharacterProgression {
    constructor() {
        this.activeCharacter = null;
        this.pendingStatPoints = 0;
        this.statAllocations = {};
        this.currentStats = {};
        this.init();
    }

    init() {
        this.createAllocationModal();
        this.attachButtonListeners();
    }

    createAllocationModal() {
        if (document.getElementById('level-up-modal')) return;

        const modalHTML = `
<div class="modal fade" id="level-up-modal" tabindex="-1" data-bs-backdrop="static">
    <div class="modal-dialog modal-lg">
        <div class="modal-content level-up-modal">
            <div class="modal-header" style="border-bottom: 1px solid rgba(100,100,120,0.3);">
                <h5 class="modal-title">Allocate Stat Points</h5>
                <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
            </div>
            <div class="modal-body">
                <div class="level-up-celebration d-none" id="level-up-celebration">
                    <div class="level-up-particles" id="level-up-particles"></div>
                    <div class="level-up-title">LEVEL UP!</div>
                    <div class="level-number" id="level-up-number">1</div>
                </div>
                <div class="stat-allocation">
                    <div class="stat-points-available">
                        <i class="bi bi-star-fill me-2"></i>
                        <span id="stat-points-text">0</span> Stat Points Available
                    </div>
                    <div id="stat-allocation-rows"></div>
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

        document.getElementById('confirm-level-up').addEventListener('click', () => {
            this.confirmAllocation();
        });
    }

    attachButtonListeners() {
        document.querySelectorAll('.btn-allocate-stats').forEach(btn => {
            if (btn.__progressionWired) return;
            btn.__progressionWired = true;
            btn.addEventListener('click', () => {
                const charId = parseInt(btn.getAttribute('data-char-id'), 10);
                this.openAllocationModal(charId);
            });
        });
    }

    async openAllocationModal(charId) {
        try {
            const r = await fetch(`/api/characters/${charId}`);
            if (!r.ok) throw new Error('Failed to load character');
            const char = await r.json();

            this.activeCharacter = charId;
            this.pendingStatPoints = char.stat_points || 0;
            this.statAllocations = {};
            this.currentStats = (char.stats && char.stats.base) || {};

            document.getElementById('level-up-celebration')?.classList.add('d-none');
            this.maybeCelebrateLevelUp(charId, char.level);
            this.renderStatAllocation();

            const modal = bootstrap.Modal.getOrCreateInstance(document.getElementById('level-up-modal'));
            modal.show();
        } catch (err) {
            console.error('Failed to open allocation modal:', err);
        }
    }

    // The server-rendered card badge ("LV{n}") is this tab's only record of what
    // level the player has already seen for this character. If the live fetch
    // shows a higher level, this is the first time this tab has observed the
    // level-up that granted the stat points being allocated — play the existing
    // celebration animation once, then update the badge so it doesn't repeat.
    maybeCelebrateLevelUp(charId, liveLevel) {
        const card = document.querySelector(`.operative-card[data-id="${charId}"]`);
        const badge = card ? card.querySelector('.operative-meta .badge') : null;
        if (!badge) return;
        const seenLevel = parseInt((badge.textContent || '').replace(/\D/g, ''), 10) || 1;
        if (liveLevel <= seenLevel) return;

        badge.textContent = `LV${liveLevel}`;

        const celebration = document.getElementById('level-up-celebration');
        const numberEl = document.getElementById('level-up-number');
        const particlesEl = document.getElementById('level-up-particles');
        if (!celebration || !numberEl || !particlesEl) return;

        numberEl.textContent = liveLevel;
        particlesEl.innerHTML = '';
        for (let i = 0; i < 50; i++) {
            const particle = document.createElement('div');
            particle.className = 'level-particle';
            particle.style.left = `${Math.random() * 100}%`;
            particle.style.bottom = '0';
            particle.style.animationDelay = `${Math.random() * 2}s`;
            particlesEl.appendChild(particle);
        }
        celebration.classList.remove('d-none');
    }

    renderStatAllocation() {
        const stats = [
            { key: 'str', name: 'Strength', icon: '<i class="bi bi-heart-fill text-danger"></i>' },
            { key: 'dex', name: 'Dexterity', icon: '<i class="bi bi-lightning-charge-fill text-warning"></i>' },
            { key: 'int', name: 'Intelligence', icon: '<i class="bi bi-star-fill text-primary"></i>' },
            { key: 'con', name: 'Constitution', icon: '<i class="bi bi-shield-fill text-success"></i>' },
            { key: 'wis', name: 'Wisdom', icon: '<i class="bi bi-eye-fill text-info"></i>' },
            { key: 'cha', name: 'Charisma', icon: '<i class="bi bi-chat-heart-fill text-purple"></i>' }
        ];

        const html = stats.map(stat => this.createStatAllocationRow(stat)).join('');
        document.getElementById('stat-allocation-rows').innerHTML = html;

        this.updateStatPointsDisplay();
    }

    createStatAllocationRow(stat) {
        const currentValue = this.currentStats[stat.key] != null ? this.currentStats[stat.key] : 10;
        const pending = this.statAllocations[stat.key] || 0;

        return `
<div class="stat-allocation-row" data-stat-key="${stat.key}">
    <div class="stat-name-icon">
        <div class="stat-icon-box">${stat.icon}</div>
        <div class="stat-name-label">${stat.name}</div>
    </div>
    <div class="stat-allocation-controls">
        <button class="stat-increment-btn" data-action="dec" data-stat="${stat.key}" ${pending === 0 ? 'disabled' : ''}>
            <i class="bi bi-dash"></i>
        </button>
        <div class="stat-current-value">${currentValue}</div>
        <div class="stat-pending-change">${pending > 0 ? `+${pending}` : ''}</div>
        <button class="stat-increment-btn" data-action="inc" data-stat="${stat.key}" ${this.pendingStatPoints === 0 ? 'disabled' : ''}>
            <i class="bi bi-plus"></i>
        </button>
    </div>
</div>`;
    }

    updateStatPointsDisplay() {
        document.getElementById('stat-points-text').textContent = this.pendingStatPoints;
        document.querySelectorAll('#stat-allocation-rows [data-action]').forEach(btn => {
            btn.addEventListener('click', () => {
                const statKey = btn.getAttribute('data-stat');
                if (btn.getAttribute('data-action') === 'inc') this.incrementStat(statKey);
                else this.decrementStat(statKey);
            });
        });
    }

    incrementStat(statKey) {
        if (this.pendingStatPoints <= 0) return;
        this.statAllocations[statKey] = (this.statAllocations[statKey] || 0) + 1;
        this.pendingStatPoints--;
        this.renderStatAllocation();
    }

    decrementStat(statKey) {
        if (!this.statAllocations[statKey]) return;
        this.statAllocations[statKey]--;
        this.pendingStatPoints++;
        this.renderStatAllocation();
    }

    async confirmAllocation() {
        try {
            const response = await fetch(`/api/characters/${this.activeCharacter}/level-up`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ stat_allocations: this.statAllocations })
            });

            if (!response.ok) {
                const err = await response.json().catch(() => ({}));
                console.error('Level-up allocation failed:', err);
                return;
            }

            bootstrap.Modal.getInstance(document.getElementById('level-up-modal'))?.hide();
            await this.refreshCharacterUI(this.activeCharacter);
        } catch (err) {
            console.error('Failed to confirm allocation:', err);
        }
    }

    async refreshCharacterUI(charId) {
        try {
            const r = await fetch(`/api/characters/${charId}`);
            if (!r.ok) return;
            const char = await r.json();

            const anchor = document.querySelector(`.xp-bar-anchor[data-char-id="${charId}"]`);
            if (anchor) {
                const span = char.xp_for_next_level - char.xp_for_current_level;
                const pct = span > 0 ? Math.min(100, Math.max(0, ((char.xp - char.xp_for_current_level) / span) * 100)) : 100;
                const fill = anchor.querySelector('.xp-fill');
                if (fill) fill.style.width = `${pct}%`;
            }

            const btn = document.querySelector(`.btn-allocate-stats[data-char-id="${charId}"]`);
            if (btn) {
                if (char.stat_points > 0) {
                    btn.innerHTML = `<i class="bi bi-star-fill me-1"></i> Allocate ${char.stat_points} Stat Point${char.stat_points !== 1 ? 's' : ''}`;
                } else {
                    btn.remove();
                }
            }
        } catch (err) {
            console.error('Failed to refresh character UI:', err);
        }
    }
}

window.characterProgression = new CharacterProgression();
