/**
 * Quest System
 *
 * Features:
 * - Quest journal UI with active/completed tabs
 * - NPC dialogue system for quest givers
 * - Quest objective tracking and progress
 * - Quest rewards (XP, gold, items)
 * - Quest markers on dungeon map
 * - Quest completion notifications
 *
 * Quest Types:
 * - main_story: Main storyline quests
 * - side_quest: Optional side quests
 * - daily: Reset daily
 * - repeatable: Can be done multiple times
 *
 * Objective Types:
 * - kill: Kill X monsters of type Y
 * - collect: Collect X items
 * - explore: Visit location
 * - talk: Talk to NPC
 *
 * API Endpoints:
 * - GET  /api/quests/available - Get available quests for character
 * - GET  /api/quests/active - Get active quests
 * - POST /api/quests/accept - Accept a quest
 * - POST /api/quests/complete - Complete a quest
 * - GET  /api/npcs/{slug} - Get NPC details and dialogue
 */

class QuestSystem {
    constructor() {
        this.activeQuests = [];
        this.completedQuests = [];
        this.currentCharacterId = null;
        this.journalModal = null;
        this.npcModal = null;
        this.currentNPC = null;

        this.init();
    }

    init() {
        // Create quest journal modal
        this.createJournalModal();
        this.createNPCModal();

        // Listen for quest-related events
        document.addEventListener('monster-killed', (e) => this.handleMonsterKilled(e.detail));
        document.addEventListener('item-collected', (e) => this.handleItemCollected(e.detail));
        document.addEventListener('location-visited', (e) => this.handleLocationVisited(e.detail));

        // Add quest journal button to UI
        this.addJournalButton();
    }

    createJournalModal() {
        const modalHTML = `
<div class="modal fade" id="quest-journal-modal" tabindex="-1" aria-labelledby="quest-journal-title" aria-hidden="true">
    <div class="modal-dialog modal-lg">
        <div class="modal-content quest-journal">
            <div class="quest-journal-header">
                <h2 class="quest-journal-title" id="quest-journal-title">
                    <i class="bi bi-journal-text me-2"></i>Quest Journal
                </h2>
            </div>

            <div class="quest-tabs">
                <div class="quest-tab active" data-tab="active" onclick="questSystem.switchTab('active')">
                    Active Quests <span id="active-quest-count" class="badge bg-primary ms-2">0</span>
                </div>
                <div class="quest-tab" data-tab="completed" onclick="questSystem.switchTab('completed')">
                    Completed <span id="completed-quest-count" class="badge bg-success ms-2">0</span>
                </div>
                <div class="quest-tab" data-tab="available" onclick="questSystem.switchTab('available')">
                    Available <span id="available-quest-count" class="badge bg-warning ms-2">0</span>
                </div>
            </div>

            <div class="quest-list" id="quest-list-container">
                <!-- Quests populated here -->
            </div>

            <div class="modal-footer">
                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
            </div>
        </div>
    </div>
</div>`;

        document.body.insertAdjacentHTML('beforeend', modalHTML);
        this.journalModal = new bootstrap.Modal(document.getElementById('quest-journal-modal'));
    }

    createNPCModal() {
        const modalHTML = `
<div class="modal fade" id="npc-dialogue-modal" tabindex="-1" aria-hidden="true">
    <div class="modal-dialog npc-dialogue-modal">
        <div class="modal-content bg-transparent border-0">
            <div class="npc-dialogue-header">
                <div class="npc-portrait" id="npc-portrait">
                    <i class="bi bi-person-fill"></i>
                </div>
                <div class="npc-info">
                    <div class="npc-name" id="npc-name">NPC Name</div>
                    <div class="npc-title" id="npc-title">Quest Giver</div>
                </div>
            </div>

            <div class="npc-dialogue-body">
                <div class="npc-dialogue-text" id="npc-dialogue-text">
                    <!-- Dialogue populated here -->
                </div>

                <div id="npc-quest-offer" style="display: none;">
                    <!-- Quest offer details -->
                </div>

                <div class="npc-dialogue-actions" id="npc-dialogue-actions">
                    <!-- Dialogue options populated here -->
                </div>
            </div>
        </div>
    </div>
</div>`;

        document.body.insertAdjacentHTML('beforeend', modalHTML);
        this.npcModal = new bootstrap.Modal(document.getElementById('npc-dialogue-modal'));
    }

    addJournalButton() {
        // Add to dashboard if it exists
        const dashboardHeader = document.querySelector('.tactical-panel .panel-header');
        if (dashboardHeader) {
            const button = document.createElement('button');
            button.className = 'btn btn-sm btn-outline-warning';
            button.innerHTML = '<i class="bi bi-journal-text me-1"></i>Quests';
            button.onclick = () => this.openJournal();
            dashboardHeader.appendChild(button);
        }
    }

    async openJournal(characterId = null) {
        if (characterId) {
            this.currentCharacterId = characterId;
        }

        await this.loadQuests();
        this.switchTab('active');
        this.journalModal.show();
    }

    switchTab(tab) {
        // Update tab active state
        document.querySelectorAll('.quest-tab').forEach(t => {
            t.classList.toggle('active', t.dataset.tab === tab);
        });

        // Render appropriate quest list
        const container = document.getElementById('quest-list-container');

        if (tab === 'active') {
            this.renderQuestList(this.activeQuests, 'active');
        } else if (tab === 'completed') {
            this.renderQuestList(this.completedQuests, 'completed');
        } else if (tab === 'available') {
            this.loadAvailableQuests();
        }
    }

    async loadQuests() {
        if (!this.currentCharacterId) return;

        try {
            const response = await fetch(`/api/quests/active?character_id=${this.currentCharacterId}`);
            if (!response.ok) return;

            const data = await response.json();
            this.activeQuests = data.active || [];
            this.completedQuests = data.completed || [];

            // Update counts
            document.getElementById('active-quest-count').textContent = this.activeQuests.length;
            document.getElementById('completed-quest-count').textContent = this.completedQuests.length;
        } catch (err) {
            console.error('[quest-system] Failed to load quests:', err);
        }
    }

    async loadAvailableQuests() {
        if (!this.currentCharacterId) return;

        try {
            const response = await fetch(`/api/quests/available?character_id=${this.currentCharacterId}`);
            if (!response.ok) return;

            const data = await response.json();
            this.renderQuestList(data.quests || [], 'available');

            document.getElementById('available-quest-count').textContent = (data.quests || []).length;
        } catch (err) {
            console.error('[quest-system] Failed to load available quests:', err);
        }
    }

    renderQuestList(quests, status) {
        const container = document.getElementById('quest-list-container');

        if (!quests || quests.length === 0) {
            container.innerHTML = `
                <div class="text-center text-muted py-5">
                    <i class="bi bi-journal-x" style="font-size: 3rem;"></i>
                    <p class="mt-3">No ${status} quests</p>
                </div>`;
            return;
        }

        const html = quests.map(quest => this.renderQuestItem(quest, status)).join('');
        container.innerHTML = html;
    }

    renderQuestItem(quest, status) {
        const progress = quest.progress || {};
        const objectives = quest.objectives || [];
        const totalObjectives = objectives.length;
        const completedObjectives = objectives.filter(obj =>
            progress[obj.id] >= obj.count
        ).length;
        const progressPercent = totalObjectives > 0 ? (completedObjectives / totalObjectives) * 100 : 0;

        return `
<div class="quest-item ${status}" data-quest-id="${quest.id}">
    <div class="quest-header">
        <h4 class="quest-title">${quest.title}</h4>
        <span class="quest-type-badge quest-type-${quest.type}">${quest.type.replace('_', ' ')}</span>
    </div>

    <div class="quest-description">${quest.description}</div>

    ${objectives.length > 0 ? `
    <div class="quest-objectives">
        ${objectives.map(obj => {
            const current = progress[obj.id] || 0;
            const isComplete = current >= obj.count;
            return `
        <div class="quest-objective ${isComplete ? 'completed' : ''}">
            <div class="quest-objective-icon">
                <i class="bi bi-${this.getObjectiveIcon(obj.type)}"></i>
            </div>
            <div class="quest-objective-text">
                ${this.getObjectiveText(obj)}
            </div>
            <div class="quest-objective-progress">
                ${current}/${obj.count}
            </div>
        </div>`;
        }).join('')}
    </div>

    <div class="quest-progress-bar">
        <div class="quest-progress-fill" style="width: ${progressPercent}%"></div>
    </div>
    ` : ''}

    <div class="quest-rewards">
        ${quest.rewards.xp ? `<div class="quest-reward"><i class="bi bi-star-fill"></i> ${quest.rewards.xp} XP</div>` : ''}
        ${quest.rewards.gold ? `<div class="quest-reward"><i class="bi bi-coin"></i> ${quest.rewards.gold} Gold</div>` : ''}
        ${quest.rewards.items ? quest.rewards.items.map(item =>
            `<div class="quest-reward"><i class="bi bi-box-fill"></i> ${item}</div>`
        ).join('') : ''}
    </div>

    ${status === 'active' && progressPercent === 100 ? `
    <button class="btn btn-success w-100 mt-3" onclick="questSystem.completeQuest(${quest.id})">
        <i class="bi bi-check-circle-fill me-2"></i>Turn In Quest
    </button>
    ` : ''}

    ${status === 'available' ? `
    <button class="btn btn-primary w-100 mt-3" onclick="questSystem.acceptQuestDirect(${quest.id})">
        <i class="bi bi-plus-circle-fill me-2"></i>Accept Quest
    </button>
    ` : ''}
</div>`;
    }

    getObjectiveIcon(type) {
        const icons = {
            kill: 'crosshair',
            collect: 'box-seam',
            explore: 'compass',
            talk: 'chat-dots'
        };
        return icons[type] || 'circle';
    }

    getObjectiveText(objective) {
        const templates = {
            kill: `Defeat ${objective.count} ${objective.target}`,
            collect: `Collect ${objective.count} ${objective.target}`,
            explore: `Explore ${objective.target}`,
            talk: `Speak with ${objective.target}`
        };
        return templates[objective.type] || objective.description || 'Unknown objective';
    }

    async talkToNPC(npcSlug) {
        try {
            const response = await fetch(`/api/npcs/${npcSlug}`);
            if (!response.ok) return;

            const npc = await response.json();
            this.currentNPC = npc;
            this.showNPCDialogue(npc);
        } catch (err) {
            console.error('[quest-system] Failed to load NPC:', err);
        }
    }

    showNPCDialogue(npc) {
        document.getElementById('npc-name').textContent = npc.name;
        document.getElementById('npc-title').textContent = npc.title || 'Quest Giver';
        document.getElementById('npc-portrait').innerHTML = npc.icon || '<i class="bi bi-person-fill"></i>';
        document.getElementById('npc-dialogue-text').textContent = npc.dialogue || 'Greetings, adventurer!';

        // Show quest offer if available
        if (npc.quest) {
            this.showQuestOffer(npc.quest);
        }

        // Render dialogue options
        this.renderDialogueOptions(npc);

        this.npcModal.show();
    }

    showQuestOffer(quest) {
        const container = document.getElementById('npc-quest-offer');
        container.style.display = 'block';
        container.innerHTML = this.renderQuestItem(quest, 'offer');
    }

    renderDialogueOptions(npc) {
        const container = document.getElementById('npc-dialogue-actions');
        const options = [];

        if (npc.quest) {
            options.push(`
<button class="dialogue-option accept" onclick="questSystem.acceptQuest(${npc.quest.id})">
    <i class="bi bi-check-circle me-2"></i>Accept Quest
</button>`);

            options.push(`
<button class="dialogue-option decline" data-bs-dismiss="modal">
    <i class="bi bi-x-circle me-2"></i>Maybe later
</button>`);
        } else {
            options.push(`
<button class="dialogue-option" data-bs-dismiss="modal">
    <i class="bi bi-arrow-left me-2"></i>Farewell
</button>`);
        }

        container.innerHTML = options.join('');
    }

    async acceptQuest(questId) {
        try {
            const response = await fetch('/api/quests/accept', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    character_id: this.currentCharacterId,
                    quest_id: questId
                })
            });

            if (response.ok) {
                this.npcModal.hide();
                this.showToast('Quest Accepted!', 'New quest added to your journal');
                await this.loadQuests();
            }
        } catch (err) {
            console.error('[quest-system] Failed to accept quest:', err);
        }
    }

    async acceptQuestDirect(questId) {
        await this.acceptQuest(questId);
        this.switchTab('active');
    }

    async completeQuest(questId) {
        try {
            const response = await fetch('/api/quests/complete', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    character_id: this.currentCharacterId,
                    quest_id: questId
                })
            });

            if (response.ok) {
                const data = await response.json();
                this.showToast('Quest Complete!', `Rewards: ${JSON.stringify(data.rewards)}`);
                await this.loadQuests();
                this.switchTab('active');

                // Fire event
                document.dispatchEvent(new CustomEvent('quest-completed', {
                    detail: { questId, rewards: data.rewards }
                }));
            }
        } catch (err) {
            console.error('[quest-system] Failed to complete quest:', err);
        }
    }

    handleMonsterKilled(data) {
        // Update quest progress for kill objectives
        this.updateQuestProgress('kill', data.monsterType, 1);
    }

    handleItemCollected(data) {
        // Update quest progress for collect objectives
        this.updateQuestProgress('collect', data.itemSlug, 1);
    }

    handleLocationVisited(data) {
        // Update quest progress for explore objectives
        this.updateQuestProgress('explore', data.locationId, 1);
    }

    async updateQuestProgress(type, target, amount) {
        // This would call the backend to update progress
        // For now, just reload quests
        await this.loadQuests();
    }

    showToast(title, message) {
        const toast = document.createElement('div');
        toast.className = 'quest-toast';
        toast.innerHTML = `
            <div class="quest-toast-header">
                <div class="quest-toast-icon">
                    <i class="bi bi-journal-check"></i>
                </div>
                <div class="quest-toast-title">${title}</div>
                <span class="quest-toast-close" onclick="this.closest('.quest-toast').remove()">×</span>
            </div>
            <div class="quest-toast-body">${message}</div>
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
let questSystem;
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        questSystem = new QuestSystem();
        window.questSystem = questSystem;
    });
} else {
    questSystem = new QuestSystem();
    window.questSystem = questSystem;
}
