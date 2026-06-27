/**
 * Achievement System
 * Handles achievement tracking, display, and notifications
 */

class AchievementSystem {
    constructor() {
        this.achievements = [];
        this.characterAchievements = [];
        this.categories = [];
        this.currentCategory = 'all';
        this.currentCharacterId = null;
        this.totalPoints = 0;
        this.unlockedCount = 0;
    }

    /**
     * Open achievement modal for a character
     */
    async openAchievements(characterId) {
        this.currentCharacterId = characterId;

        try {
            // Load all data in parallel
            const [achievementsResp, categoriesResp, progressResp] = await Promise.all([
                fetch('/api/achievements'),
                fetch('/api/achievements/categories'),
                fetch(`/api/characters/${characterId}/achievements`)
            ]);

            if (!achievementsResp.ok || !categoriesResp.ok || !progressResp.ok) {
                throw new Error('Failed to load achievements');
            }

            this.achievements = await achievementsResp.json();
            this.categories = await categoriesResp.json();
            this.characterAchievements = await progressResp.json();

            // Calculate stats
            this.calculateStats();

            this.renderModal();
        } catch (error) {
            console.error('Error loading achievements:', error);
            alert('Failed to load achievements. Please try again.');
        }
    }

    /**
     * Calculate achievement statistics
     */
    calculateStats() {
        this.unlockedCount = this.characterAchievements.filter(a => a.unlocked).length;
        this.totalPoints = this.characterAchievements
            .filter(a => a.unlocked)
            .reduce((sum, a) => sum + a.points, 0);
    }

    /**
     * Render the achievement modal
     */
    renderModal() {
        // Update stats
        document.getElementById('achievementTotalPoints').textContent = this.totalPoints;
        document.getElementById('achievementUnlockedCount').textContent =
            `${this.unlockedCount}/${this.achievements.length}`;

        // Render category tabs
        this.renderCategoryTabs();

        // Render achievement list
        this.renderAchievementList();
    }

    /**
     * Render category tabs
     */
    renderCategoryTabs() {
        const container = document.getElementById('achievementCategoryTabs');

        const tabs = [
            { slug: 'all', name: 'All', icon: 'grid-fill' },
            ...this.categories
        ];

        container.innerHTML = tabs.map(cat => {
            const count = cat.slug === 'all'
                ? this.achievements.length
                : this.achievements.filter(a => a.category === cat.slug).length;

            const unlockedCount = cat.slug === 'all'
                ? this.unlockedCount
                : this.characterAchievements.filter(ca =>
                    ca.unlocked && this.achievements.find(a => a.id === ca.achievement_id)?.category === cat.slug
                  ).length;

            return `
                <div class="achievement-category-tab ${this.currentCategory === cat.slug ? 'active' : ''}"
                     onclick="achievementSystem.selectCategory('${cat.slug}')">
                    <i class="bi bi-${cat.icon || 'star'}"></i>
                    <span>${cat.name}</span>
                    <span style="opacity: 0.7; font-size: 12px;">(${unlockedCount}/${count})</span>
                </div>
            `;
        }).join('');
    }

    /**
     * Select a category
     */
    selectCategory(categorySlug) {
        this.currentCategory = categorySlug;
        this.renderCategoryTabs();
        this.renderAchievementList();
    }

    /**
     * Render achievement list
     */
    renderAchievementList() {
        const container = document.getElementById('achievementList');

        // Filter achievements by category
        let filtered = this.currentCategory === 'all'
            ? this.achievements
            : this.achievements.filter(a => a.category === this.currentCategory);

        // Sort: unlocked first, then by points
        filtered.sort((a, b) => {
            const aProgress = this.getAchievementProgress(a.id);
            const bProgress = this.getAchievementProgress(b.id);

            if (aProgress.unlocked !== bProgress.unlocked) {
                return bProgress.unlocked ? 1 : -1;
            }
            return b.points - a.points;
        });

        if (filtered.length === 0) {
            container.innerHTML = `
                <div class="achievement-empty-state">
                    <i class="bi bi-trophy"></i>
                    <p>No achievements in this category yet.</p>
                </div>
            `;
            return;
        }

        container.innerHTML = filtered.map(achievement =>
            this.renderAchievementCard(achievement)
        ).join('');
    }

    /**
     * Get achievement progress for character
     */
    getAchievementProgress(achievementId) {
        return this.characterAchievements.find(ca => ca.achievement_id === achievementId) || {
            progress: 0,
            unlocked: false,
            unlocked_at: null
        };
    }

    /**
     * Render a single achievement card
     */
    renderAchievementCard(achievement) {
        const progress = this.getAchievementProgress(achievement.id);
        const isUnlocked = progress.unlocked;
        const isHidden = achievement.hidden && !isUnlocked;

        const progressPercent = Math.min(100, (progress.progress / achievement.requirement_value) * 100);

        const icon = this.getAchievementIcon(achievement.icon);

        const unlockedDate = progress.unlocked_at
            ? new Date(progress.unlocked_at).toLocaleDateString()
            : '';

        return `
            <div class="achievement-card ${isUnlocked ? 'unlocked' : 'locked'} ${isHidden ? 'hidden' : ''}">
                ${isUnlocked ? '<div class="achievement-unlocked-badge">✓ Unlocked</div>' : ''}

                <div class="achievement-icon">
                    ${icon}
                </div>

                <div class="achievement-info">
                    <h3 class="achievement-name">
                        ${isHidden ? '???' : achievement.name}
                    </h3>
                    <p class="achievement-description">
                        ${isHidden ? 'Hidden achievement - unlock to reveal' : achievement.description}
                    </p>

                    ${!isHidden ? `
                        <div class="achievement-meta">
                            <div class="achievement-points">
                                <i class="bi bi-star-fill"></i>
                                <span>${achievement.points} points</span>
                            </div>
                            ${achievement.reward_gold > 0 ? `
                                <div class="achievement-reward">
                                    <i class="bi bi-coin"></i>
                                    <span>${achievement.reward_gold} gold</span>
                                </div>
                            ` : ''}
                        </div>
                    ` : ''}

                    ${!isUnlocked && !isHidden ? `
                        <div class="achievement-progress-container">
                            <div class="achievement-progress-bar">
                                <div class="achievement-progress-fill" style="width: ${progressPercent}%"></div>
                            </div>
                            <div class="achievement-progress-text">
                                ${progress.progress} / ${achievement.requirement_value}
                            </div>
                        </div>
                    ` : ''}

                    ${isUnlocked && unlockedDate ? `
                        <div class="achievement-unlocked-date">
                            Unlocked: ${unlockedDate}
                        </div>
                    ` : ''}
                </div>
            </div>
        `;
    }

    /**
     * Get icon emoji for achievement
     */
    getAchievementIcon(iconName) {
        const iconMap = {
            'sword': '⚔️',
            'sword-clash': '⚔️',
            'crossed-swords': '⚔️',
            'skull': '💀',
            'dragon': '🐉',
            'map': '🗺️',
            'compass': '🧭',
            'castle': '🏰',
            'arrow-up': '⬆️',
            'shield-check': '🛡️',
            'crown': '👑',
            'coin': '💰',
            'gem': '💎',
            'armor-helmet': '🪖',
            'people-fill': '👥',
            'gift': '🎁',
            'lightning-bolt': '⚡',
            'heart-pulse': '💗',
            'shield-fill': '🛡️',
            'trophy': '🏆',
            'star': '⭐'
        };

        return iconMap[iconName] || '🏆';
    }

    /**
     * Show achievement unlock notification
     */
    showNotification(achievement) {
        const notification = document.getElementById('achievementNotification');

        // Set content
        document.getElementById('achievementNotificationIcon').textContent = this.getAchievementIcon(achievement.icon);
        document.getElementById('achievementNotificationName').textContent = achievement.name;

        let rewardText = '';
        if (achievement.reward_gold > 0) {
            rewardText = `+${achievement.reward_gold} gold`;
        }
        if (achievement.points > 0) {
            rewardText += (rewardText ? ', ' : '') + `+${achievement.points} points`;
        }
        document.getElementById('achievementNotificationReward').textContent = rewardText;

        // Show notification
        notification.classList.add('show');

        // Auto-hide after 5 seconds
        setTimeout(() => {
            notification.classList.remove('show');
        }, 5000);
    }

    /**
     * Check for achievement progress (called from game events)
     */
    async checkAchievements(characterId, eventType, eventData) {
        try {
            const response = await fetch(`/api/characters/${characterId}/achievements/check`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ event_type: eventType, event_data: eventData })
            });

            if (!response.ok) return;

            const result = await response.json();

            // Show notification for newly unlocked achievements
            if (result.unlocked && result.unlocked.length > 0) {
                for (const achievement of result.unlocked) {
                    this.showNotification(achievement);
                }
            }
        } catch (error) {
            console.error('Error checking achievements:', error);
        }
    }
}

// Global instance
const achievementSystem = new AchievementSystem();

// Test helper
function testAchievements(characterId = 1) {
    achievementSystem.openAchievements(characterId);
}
