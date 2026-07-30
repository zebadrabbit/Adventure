/*
 * project: Adventure MUD
 * module: equipment-panel.js
 *
 * Container-scoped equipment & inventory panel. All element lookups are
 * scoped to `this.root` -- the DOM node passed to mount() -- instead of
 * `document`, so this renderer can be mounted in more than one place on a
 * page (or on different pages) without collisions: two mounts can't fight
 * over the same ids, and a mount that doesn't exist yet can't accidentally
 * match a global querySelectorAll.
 *
 * On the dashboard, nothing calls mount() explicitly -- the panel creates
 * its own Bootstrap modal the first time it's opened, exactly as the old
 * equipment-enhanced.js did, so the dashboard's behaviour is unchanged.
 * A future caller (the adventure HUD) can call mount(container) itself
 * with a plain container and get the same renderer without any modal
 * chrome forcing itself into existence.
 *
 * Folds in what used to be equipment-shared.js (encumbranceView,
 * gearBonusText) as module-private helpers -- that file existed only to
 * keep two rival equipment implementations from drifting apart, and there
 * is one implementation now.
 *
 * Public interface:
 *   window.EquipmentPanel = { mount, open, close, isOpen, refresh }
 *
 * This module wires its own delegated `.btn-equip-panel` click listener at
 * load time (see the bottom of this file), so every page that loads this
 * script gets a working equip button with no separate wiring script -- see
 * the dashboard's and the adventure HUD's templates, neither of which binds
 * it themselves.
 */
(function () {
    "use strict";

    // Fallback only -- used solely if /api/characters/state can't be
    // reached. The real vocabulary comes from that endpoint's `slots`
    // field (see _ensureSlots below); this is not a second copy of it.
    const FALLBACK_SLOTS = ["weapon", "offhand", "head", "chest", "hands", "feet", "ring", "amulet"];

    // ---- folded in from equipment-shared.js ----

    function encumbranceView(enc) {
        if (!enc || typeof enc.weight !== "number" || typeof enc.capacity !== "number") return null;
        const pct = enc.capacity > 0 ? Math.min(100, (enc.weight / enc.capacity) * 100) : 0;
        // Token-backed classes from equipment.css, not Bootstrap's bg-*/text-*.
        // The HP/MP/XP bars a few centimetres away are realm-aware (--hp/--mp/
        // --xp); an encumbrance bar painted from Bootstrap's fixed palette was
        // the one element inside this panel that ignored the realm.
        const barClass = enc.status === "blocked" ? "eq-enc-blocked" : (enc.status === "encumbered" ? "eq-enc-encumbered" : "eq-enc-normal");
        const textClass = enc.status === "blocked" ? "eq-enc-text-blocked" : (enc.status === "encumbered" ? "eq-enc-text-encumbered" : "");
        const statusLabel = enc.status === "blocked"
            ? "Overloaded — cannot carry more"
            : (enc.status === "encumbered" ? "Encumbered" : "");
        const penaltyNote = (enc.status !== "normal" && enc.dex_penalty) ? ` (-${enc.dex_penalty} DEX)` : "";
        return {
            pct,
            barClass,
            textClass,
            statusLabel,
            penaltyNote,
            weightLabel: `${enc.weight.toFixed(1)} / ${enc.capacity.toFixed(1)}`,
            status: enc.status,
        };
    }

    function gearBonusText(gear) {
        const totals = {};
        Object.values(gear || {}).forEach((inst) => {
            if (!inst) return;
            const affixes = Array.isArray(inst.affixes) ? inst.affixes
                : (inst.effects && typeof inst.effects === "object"
                    ? Object.entries(inst.effects).map(([stat, val]) => ({ stat, val }))
                    : []);
            affixes.forEach((a) => {
                if (!a || !a.stat || typeof a.val !== "number") return;
                totals[a.stat] = (totals[a.stat] || 0) + a.val;
            });
        });
        return Object.entries(totals)
            .filter(([, v]) => v !== 0)
            .map(([stat, v]) => {
                const num = Number.isInteger(v) ? v : Math.round(v * 10) / 10;
                return `${num >= 0 ? "+" : ""}${num} ${stat.toUpperCase()}`;
            })
            .join(", ");
    }

    // ---- skeleton mounted into the container by mount() ----
    // (Same markup equipment-enhanced.js used to build its modal from, minus
    // the outer .modal/.modal-dialog wrapper -- that part is dashboard-only
    // chrome, created by _ensureDashboardMount() below.)
    //
    // The three wrappers are .eq-panel-* and not Bootstrap's .modal-header/
    // -body/-footer. Bootstrap 5.3 declares --bs-modal-padding and friends on
    // .modal itself and its chrome rules read them through var(); on the HUD
    // mount (#adv-character-panel) there is no .modal ancestor, so those
    // var()s were unresolvable, the padding declarations were invalid at
    // computed-value time, and every one of them fell back to 0 -- the title
    // and the X sat flush against the panel border and the grid had no outer
    // gutter, while the identical markup on /dashboard had 1rem. Owning the
    // three classes in equipment.css removes the undeclared dependency
    // instead of patching around it, and makes both mounts render the same.
    // .modal-* survives only on the dashboard's own wrapper (see
    // _ensureDashboardMount), which really does live inside a .modal.

    const SKELETON_HTML = `
<div class="eq-panel-header">
    <h5 class="eq-panel-title">
        <i class="bi bi-person-gear me-2"></i>
        <span id="eq-char-name">Character</span> - Equipment & Inventory
    </h5>
    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal" data-action="close"></button>
</div>
<div class="eq-panel-body">
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
                        <div class="progress-bar eq-hp-fill" id="eq-hp-bar" role="progressbar"></div>
                    </div>
                </div>
                <div id="eq-mp-bar-wrap" class="mb-2">
                    <div class="d-flex justify-content-between small eq-bar-label">
                        <span><i class="bi bi-lightning-charge-fill text-primary me-1"></i>MP</span>
                        <span id="eq-mp-text"></span>
                    </div>
                    <div class="progress eq-progress-bar">
                        <div class="progress-bar eq-mp-fill" id="eq-mp-bar" role="progressbar"></div>
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
                        <div class="eq-stat-label"><i class="bi bi-sword text-warning"></i> STR</div>
                        <div class="eq-stat-value" id="eq-val-atk">—</div>
                    </div>
                    <div class="eq-stat-cell" id="eq-stat-def">
                        <div class="eq-stat-label"><i class="bi bi-shield-fill text-info"></i> CON</div>
                        <div class="eq-stat-value" id="eq-val-def">—</div>
                    </div>
                    <div class="eq-stat-cell" id="eq-stat-hp">
                        <div class="eq-stat-label"><i class="bi bi-heart-fill text-danger"></i> DEX</div>
                        <div class="eq-stat-value" id="eq-val-hp">—</div>
                    </div>
                    <div class="eq-stat-cell" id="eq-stat-mp">
                        <div class="eq-stat-label"><i class="bi bi-lightning-charge-fill text-primary"></i> INT</div>
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
<div class="eq-panel-footer">
    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal" data-action="close">Close</button>
</div>`;

    class EquipmentPanelController {
        constructor() {
            this.root = null;
            this.character = null;
            this.draggedItem = null;
            this.comparisonTooltip = null;
            this.slots = null;
            this._slotsPromise = null;
            this._isModal = false;
            this._bsModal = null;
            this._open = false;
            this._openCharId = null;
            this._openGen = 0;
        }

        // ---- mount contract ----

        mount(container) {
            if (!container) return;
            this.root = container;
            if (container.dataset.eqPanelMounted === "1") return; // idempotent
            container.innerHTML = SKELETON_HTML;
            container.dataset.eqPanelMounted = "1";
            if (!this._isModal) {
                // The header X and footer Close button carry
                // data-bs-dismiss="modal" for the dashboard's real modal.
                // Bootstrap's own globally-registered click delegate also
                // matches that attribute and tries to resolve a .modal
                // ancestor for it; on a plain (non-modal) mount there is
                // none, and instead of no-oping it throws internally
                // ("Cannot read properties of undefined (reading
                // 'backdrop')"). Stripped here so only this controller's own
                // data-action="close" handling (_attachRootListeners) ever
                // reacts to these buttons outside the dashboard's modal.
                container.querySelectorAll('[data-bs-dismiss="modal"]').forEach((el) => {
                    el.removeAttribute('data-bs-dismiss');
                });
            }
            this._attachRootListeners();
        }

        async open(charId) {
            if (!this.root) this._ensureDashboardMount();
            // Request-generation guard: open() is async (a character fetch),
            // so clicking two frames quickly starts two overlapping calls.
            // Without this, whichever fetch resolves last wins regardless of
            // which was clicked last -- a slow response for character A could
            // land after a fast one for character B and paint A over B. Each
            // call captures the generation counter as it starts and bails
            // before rendering if a newer call has since begun.
            //
            // The fetch is captured into a local and assigned only after the
            // gate. Assigning unconditionally as the response lands would
            // still let a stale one win: the DOM would show the fast
            // character but this.character -- what every later click reads
            // (bag lookups, the id in the equip/unequip/consume POST) --
            // would silently belong to the stale one. The gate has to guard
            // the model, not just the repaint. Every other async
            // fetch-then-render path in this class does the same thing via
            // _reloadAndRender(); open() spells it out because it has extra
            // work to gate (the slot vocabulary, _openCharId, _reveal).
            const gen = ++this._openGen;
            let painted = false;
            try {
                const [characterData] = await Promise.all([this.fetchCharacter(charId), this._ensureSlots()]);
                if (gen !== this._openGen) return;
                this.character = characterData;
                this.render();
                this._openCharId = charId;
                this._reveal();
                painted = true;
            } finally {
                this._releaseGeneration(gen, painted);
            }
        }

        /**
         * Hand the generation counter back if this call never painted.
         *
         * fetchCharacter() rejects on any non-ok response (and on a dropped
         * connection), and the bump happens before the request. Without this,
         * a failed open/refresh/equip/unequip/consume would leave the counter
         * raised forever, so an *older* call still in flight -- one that is
         * about to resolve with perfectly good data -- fails its own gate and
         * silently cancels itself, leaving the panel showing nothing or stale
         * contents with no error and no repaint. Only rolled back when
         * nothing newer has claimed the counter since; if it has, that newer
         * call owns the paint and must not be cancelled by our cleanup.
         */
        _releaseGeneration(gen, painted) {
            if (!painted && gen === this._openGen) this._openGen = gen - 1;
        }

        /**
         * Re-fetch `charId` and repaint, under the same generation guard
         * open() uses.
         *
         * This is the one rule for every async fetch-then-render path in the
         * panel -- open() and refresh() go through it or repeat it exactly,
         * and the three mutation paths reach it via refresh(). The mutation
         * paths used to call loadCharacter(), which assigned this.character
         * with no gate at all: drop an item on character A's slot, click
         * frame B while the POST is in flight, and A's reload lands after
         * open(B) has already painted B and set _openCharId = B -- repainting
         * A over B while _openCharId still says B. Guarding the model matters
         * as much as guarding the repaint, because this.character is what
         * every later click reads (bag lookups, the id in the next POST), so
         * a stale response winning there is a wrong-character mutation and
         * not merely a wrong-character picture.
         *
         * The guard only orders calls against each other; it cannot tell that
         * a *newer* call is fetching the *wrong* character. That is why the
         * mutation paths must not pass their own captured id here -- see
         * refresh().
         */
        async _reloadAndRender(charId) {
            const gen = ++this._openGen;
            let painted = false;
            try {
                const characterData = await this.fetchCharacter(charId);
                if (gen !== this._openGen) return;
                this.character = characterData;
                this.render();
                painted = true;
            } finally {
                this._releaseGeneration(gen, painted);
            }
        }

        close() {
            // The comparison tooltip lives on document.body, not this.root,
            // so hiding/removing the panel never took it with it -- it would
            // otherwise be stranded over the map by a close-on-move.
            this.hideComparisonTooltip();
            if (this._isModal && this._bsModal) {
                this._bsModal.hide();
            } else if (this.root) {
                // The generic (non-modal) mount case, e.g. the HUD's <aside
                // hidden>: visibility there is the native hidden attribute
                // (adventure-hud.css keys off [hidden]), not a Bootstrap
                // class, so that's what has to be set here for the panel to
                // actually disappear.
                this.root.hidden = true;
            }
            this._open = false;
        }

        isOpen() {
            return !!this._open;
        }

        async refresh() {
            if (this._openCharId == null) return;
            // Takes part in the same generation counter open() uses, and for
            // the same reason: this is an async fetch-then-render sequence
            // that can race a real one. refresh() reads _openCharId, which
            // only updates after open()'s own gate passes -- so a loot claim
            // landing mid-swap (open(B) in flight, _openCharId still A) can
            // fetch the outgoing character, and if that resolves after the
            // incoming open() already painted B, it would repaint the panel
            // back to A with no open() call involved. Guarding this fetch
            // the same way open() guards its own closes that path.
            //
            // This is also why equipItem/unequipItem/consumeItem reload
            // through here rather than through _reloadAndRender(charId) with
            // the id they captured for the POST. Equip on A, click frame B
            // while the POST is in flight, open(B) completes and paints B,
            // then the POST resolves: a reload of A started at that moment is
            // the *newest* generation, so the guard passes it and A is
            // painted over B -- the exact failure the guard exists to
            // prevent, arrived at from the other side. _openCharId is read
            // after the await and names whoever is actually on screen.
            await this._reloadAndRender(this._openCharId);
        }

        // ---- dashboard self-bootstrap ----
        // Only runs the first time open() is called on a page that never
        // mounted the panel into a container of its own.
        // A caller that mounts explicitly (the adventure HUD) never reaches
        // this, so open() there just re-renders into the already-mounted
        // container instead of spawning an unrelated hidden modal.

        _ensureDashboardMount() {
            // A page that ships its own mount point always wins, even if
            // this runs before that page's own explicit mount() call gets a
            // chance to. The delegated .btn-equip-panel listener is
            // registered at module load, so an unusually early click (before
            // adventure-controls.js's DOMContentLoaded handler mounts the
            // HUD panel) can beat it here. Without this check that race would
            // latch _isModal = true and spawn an orphan Bootstrap modal
            // instead of ever using #adv-character-panel -- permanently, for
            // the rest of the page's life, since _isModal is never reset.
            const ownMount = document.getElementById("adv-character-panel");
            if (ownMount) {
                this.mount(ownMount);
                return;
            }
            let modalEl = document.getElementById("equipment-panel-modal");
            if (!modalEl) {
                const wrapperHTML = `
<div class="modal fade" id="equipment-panel-modal" tabindex="-1">
    <div class="modal-dialog modal-xl modal-dialog-scrollable equipment-modal">
        <div class="modal-content eq-modal-content"></div>
    </div>
</div>`;
                document.body.insertAdjacentHTML("beforeend", wrapperHTML);
                modalEl = document.getElementById("equipment-panel-modal");
                modalEl.addEventListener("hidden.bs.modal", () => { this._open = false; });
            }
            this._isModal = true;
            this.mount(modalEl.querySelector(".modal-content"));
        }

        _reveal() {
            // Unconditionally clear whatever close() may have set on
            // this.root, regardless of which branch runs below. Previously
            // this only ran in the non-modal branch, so a close() that fired
            // while _isModal was true but _bsModal had not been created yet
            // (a failed first open() on the dashboard) left the modal-content
            // hidden forever after -- the modal chrome would show, but its
            // content stayed display:none, i.e. a permanently empty panel.
            if (this.root) {
                this.root.classList.remove("d-none");
                this.root.hidden = false;
            }
            if (this._isModal) {
                if (!this._bsModal) {
                    this._bsModal = new bootstrap.Modal(document.getElementById("equipment-panel-modal"));
                }
                this._bsModal.show();
            }
            this._open = true;
        }

        // ---- slot vocabulary: the eight canonical slots, fetched once from
        // the server and cached. Falls back to a hard-coded copy only if the
        // request fails, so there is exactly one real source of truth. ----

        async _ensureSlots() {
            if (this.slots) return this.slots;
            if (!this._slotsPromise) {
                this._slotsPromise = fetch("/api/characters/state")
                    .then((r) => {
                        if (!r.ok) throw new Error("bad status");
                        return r.json();
                    })
                    .then((data) => {
                        this.slots = (Array.isArray(data.slots) && data.slots.length) ? data.slots : FALLBACK_SLOTS.slice();
                    })
                    .catch(() => {
                        this.slots = FALLBACK_SLOTS.slice();
                    });
            }
            return this._slotsPromise;
        }

        async fetchCharacter(charId) {
            const response = await fetch(`/api/characters/${charId}`);
            if (!response.ok) throw new Error("Failed to load character");
            return response.json();
        }

        // ---- rendering ----

        render() {
            if (!this.character || !this.root) return;

            this.root.querySelector("#eq-char-name").textContent = this.character.name;

            this.renderEquipmentSlots();
            this.renderPortrait();
            this.renderInventory();
        }

        renderEquipmentSlots() {
            const slots = this.slots || FALLBACK_SLOTS;
            const gear = this.character.gear || {};

            const html = slots.map((slot) => this.createSlotHTML(slot, gear[slot])).join("");
            this.root.querySelector("#equipment-slots-list").innerHTML = html;

            this.attachSlotHandlers();
        }

        createSlotHTML(slot, item) {
            const slotLabel = this.getSlotLabel(slot);
            const slotIcon = this.getSlotIcon(slot);
            const hasItem = !!item;

            if (hasItem) {
                const rarityClass = `rarity-${item.rarity || "common"}`;
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
    <button class="btn btn-sm btn-outline-danger slot-action" data-action="unequip">
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
            const s = this.calculateTotalStats();
            const cls = s.cls.toLowerCase();

            // Class header
            const header = this.root.querySelector("#eq-class-header");
            header.className = `eq-class-header eq-class-bg-${cls}`;
            this.root.querySelector("#char-name-display").textContent = ch.name;
            this.root.querySelector("#char-class-display").textContent =
                `Lv ${s.level} ${s.cls.charAt(0).toUpperCase() + s.cls.slice(1)}`;

            // HP bar
            const hpPct = Math.min(100, Math.round((s.hp / (s.max_hp || 1)) * 100));
            this.root.querySelector("#eq-hp-text").textContent = `${s.hp} / ${s.max_hp}`;
            this.root.querySelector("#eq-hp-bar").style.width = `${hpPct}%`;

            // MP bar
            const mpPct = Math.min(100, Math.round((s.mana / (s.max_mana || 1)) * 100));
            this.root.querySelector("#eq-mp-text").textContent = `${s.mana} / ${s.max_mana}`;
            this.root.querySelector("#eq-mp-bar").style.width = `${mpPct}%`;

            // XP bar
            const xpPct = Math.min(100, Math.round((s.xp / (s.xp_to_next || 1)) * 100));
            this.root.querySelector("#eq-xp-text").textContent = `${s.xp} / ${s.xp_to_next}`;
            this.root.querySelector("#eq-xp-bar").style.width = `${xpPct}%`;

            // Stat grid -- core D&D-style attributes. The labels (STR/CON/
            // DEX/INT) live in the skeleton markup itself; only the values
            // are set here (the original wrote ATK/DEF/HP/MP in the markup
            // and then rewrote them to STR/CON/DEX/INT here -- fixed by
            // putting the right labels in the markup and dropping the
            // rewrite entirely).
            this.root.querySelector("#eq-val-atk").textContent = s.str;
            this.root.querySelector("#eq-val-def").textContent = s.con;
            this.root.querySelector("#eq-val-hp").textContent = s.dex;
            this.root.querySelector("#eq-val-mp").textContent = s.int;

            this.renderGearBonus();
            this.renderEncumbrance();
        }

        renderEncumbrance() {
            const container = this.root.querySelector("#encumbrance-bar");
            if (!container) return;
            const view = encumbranceView(this.character && this.character.encumbrance);
            if (!view) {
                container.innerHTML = "";
                return;
            }
            container.innerHTML = `
                <div class="d-flex justify-content-between small eq-bar-label">
                    <span>Carry Weight</span>
                    <span>${view.weightLabel}</span>
                </div>
                <div class="progress eq-progress-bar">
                    <div class="progress-bar ${view.barClass}" style="width:${view.pct}%"></div>
                </div>
                ${view.statusLabel ? `<div class="small ${view.textClass} mt-1">${view.statusLabel}${view.penaltyNote}</div>` : ""}
            `;
        }

        renderGearBonus() {
            const container = this.root.querySelector("#gear-bonus-summary");
            if (!container) return;
            const gear = (this.character && this.character.gear) || {};
            const text = gearBonusText(gear);
            container.innerHTML = text ? `Gear bonus: ${this.escapeHTML(text)}` : "";
        }

        renderInventory() {
            const bag = this.character.bag || [];
            const totalSlots = Math.max(20, bag.length + 4);
            this.root.querySelector("#bag-count").textContent = `${bag.length} / ${totalSlots}`;

            // Build grid cells.
            //
            // Every filled cell is role="button" + tabindex="0" with a
            // keydown handler, not a bare <div> with a click listener. The
            // grid is where equipping happens -- the thing this panel exists
            // for -- and until now it could only be reached with a mouse, on
            // a screen whose hotkey suppression was written specifically to
            // protect the keyboard affordances inside this panel.
            const cells = [];
            bag.forEach((item, index) => {
                const rarityClass = `rarity-${item.rarity || "common"}`;
                const typeLabel = item.type || item.slot || "gear";
                const icon = this.getItemIcon(typeLabel);
                const qtyBadge = (item.qty && item.qty > 1)
                    ? `<span class="cell-qty">${item.qty}</span>`
                    : "";
                const drinkable = this.isConsumable(item);
                // Everything filled is draggable. A potion still cannot land in
                // an equipment slot -- onSlotDrop refuses it there -- but it is
                // the single most likely thing a player hands to an ally, and
                // making the cell undraggable took that away to prevent a 400
                // the drop handler can decline for free.
                const draggable = "true";
                const verb = drinkable ? "drink" : "equip";

                cells.push(`
<div class="bag-grid-cell ${rarityClass}" draggable="${draggable}"
     role="button" tabindex="0"
     data-item-index="${index}"
     data-consumable="${drinkable ? "true" : "false"}"
     data-item-slug="${this.escapeHTML(item.slug || "")}"
     data-item-uid="${this.escapeHTML(item.uid || "")}"
     aria-label="${this.escapeHTML(`${verb === "drink" ? "Drink" : "Equip"} ${item.name}`)}"
     title="${this.escapeHTML(`${item.name} — click to ${verb}`)}">
    ${icon}
    ${qtyBadge}
</div>`);
            });

            // Empty cells -- decoration for the grid's shape, nothing to
            // land on and nothing to announce.
            for (let i = bag.length; i < totalSlots; i++) {
                cells.push(`<div class="bag-grid-cell empty" aria-hidden="true"></div>`);
            }

            this.root.querySelector("#inventory-items-list").innerHTML =
                `<div class="bag-grid">${cells.join("")}</div>`;

            // Attach drag + keyboard + tooltip handlers
            this.attachBagCellHandlers();
        }

        /**
         * Whether this bag entry is drunk rather than worn.
         *
         * Potions are the only thing /consume accepts (inventory_api.py's
         * consume_item rejects any other type), and a procedural gear
         * instance -- which carries a uid -- is never one.
         */
        isConsumable(item) {
            if (!item || item.uid) return false;
            return String(item.type || "").toLowerCase() === "potion";
        }

        // ---- delegated + per-element listeners ----

        _attachRootListeners() {
            // Delegated on the (stable) root rather than bound per-button:
            // renderEquipmentSlots() replaces #equipment-slots-list wholesale
            // on every render, so per-button listeners would need
            // re-attaching each time and inline onclick="" would need a
            // hard-coded global name in the markup. One delegated listener,
            // attached once at mount time, covers every slot across every
            // re-render without re-binding or leaking.
            this.root.addEventListener("click", (e) => {
                // The skeleton's header X and footer Close button both carry
                // data-action="close" (see SKELETON_HTML above).
                // On the dashboard's real modal, data-bs-dismiss="modal" is
                // what actually closes it (Bootstrap's own global delegate);
                // on a generic (non-modal) mount there is no .modal ancestor
                // for that delegate to find, so it used to no-op (or, once
                // mount() stops stripping the attribute for this case,
                // throw) and a mouse-only player had no way to close the
                // panel at all -- only Escape or a movement key did
                // anything. Wired to close() ourselves here, but only for
                // the non-modal case: on the dashboard this would be
                // redundant with (not a replacement for) Bootstrap's own
                // handling, so it's left untouched there.
                if (!this._isModal && e.target.closest('[data-action="close"]')) {
                    this.close();
                    return;
                }
                const btn = e.target.closest('[data-action="unequip"]');
                if (!btn) return;
                const slotEl = btn.closest("[data-slot]");
                if (!slotEl) return;
                this.unequipItem(slotEl.dataset.slot);
            });
        }

        attachSlotHandlers() {
            this.root.querySelectorAll(".equipment-slot").forEach((slot) => {
                slot.addEventListener("dragover", (e) => this.onSlotDragOver(e));
                slot.addEventListener("dragleave", (e) => this.onSlotDragLeave(e));
                slot.addEventListener("drop", (e) => this.onSlotDrop(e));
            });
        }

        attachBagCellHandlers() {
            // Every filled cell, not just the draggable ones: potions are
            // deliberately not draggable (there is no slot to drop one in)
            // and still need the click, the keyboard and the tooltip.
            this.root.querySelectorAll(".bag-grid-cell[data-item-index]").forEach((cell) => {
                cell.addEventListener("dragstart", (e) => this.onItemDragStart(e));
                cell.addEventListener("dragend", (e) => this.onItemDragEnd(e));
                cell.addEventListener("mouseenter", (e) => this.showComparisonTooltip(e));
                cell.addEventListener("mouseleave", () => this.hideComparisonTooltip());
                // Focus gets the same tooltip hover does -- it is where the
                // "click to equip"/"click to drink" line lives, so without
                // this a keyboard user has the affordance but not the notice
                // that it is there.
                cell.addEventListener("focus", (e) => this.showComparisonTooltip(e));
                cell.addEventListener("blur", () => this.hideComparisonTooltip());
                cell.addEventListener("click", () => this.activateBagCell(cell, false));
                cell.addEventListener("keydown", (e) => {
                    if (e.key !== "Enter" && e.key !== " " && e.key !== "Spacebar") return;
                    // Space would otherwise scroll the panel, and both keys
                    // would carry on to adventure-controls.js's document-level
                    // hotkey handler.
                    e.preventDefault();
                    e.stopPropagation();
                    // Held keys auto-repeat at ~30/s after ~500ms, and
                    // activateBagCell is not awaited by this handler -- so one
                    // deliberate long press on a potion drank the whole stack,
                    // irreversibly, for exactly the keyboard and motor-impaired
                    // users this affordance was added for. A native <button>
                    // does not behave that way (Space activates on keyup), so
                    // neither does the control imitating one.
                    if (e.repeat) return;
                    this.activateBagCell(cell, true);
                });
            });
        }

        /**
         * Do the one thing this cell's item is for: drink it, or wear it.
         *
         * Potions route to /consume; everything else to /equip. Splitting on
         * the item rather than adding a second control per cell keeps the
         * 48px cell a single target -- and the tooltip, the title attribute
         * and the aria-label all name the verb before the player commits, so
         * which of the two will happen is never a guess.
         */
        async activateBagCell(cell, fromKeyboard) {
            const idx = parseInt(cell.dataset.itemIndex, 10);
            const item = this.character.bag[idx];
            if (!item) return;

            if (this.isConsumable(item)) {
                await this.consumeItem(item);
            } else {
                await this.equipItem(item, this.getSlotForItemType(item.type || item.slot || ""));
            }

            if (!fromKeyboard) return;
            // The repaint above rebuilds the whole grid, so the cell the
            // player was standing on no longer exists and focus has dropped
            // to <body>. Put it back on the same position -- or the last
            // cell, if the bag just got shorter -- so using one item doesn't
            // end the keyboard run through the bag.
            const cells = this.root.querySelectorAll(".bag-grid-cell[data-item-index]");
            if (!cells.length) return;
            cells[Math.min(idx, cells.length - 1)].focus();
        }

        onItemDragStart(e) {
            const cell = e.currentTarget;
            const itemIndex = parseInt(cell.dataset.itemIndex, 10);
            this.draggedItem = this.character.bag[itemIndex];
            e.dataTransfer.effectAllowed = "move";
            cell.style.opacity = "0.4";
        }

        onItemDragEnd(e) {
            e.currentTarget.style.opacity = "1";
            this.draggedItem = null;
        }

        onSlotDragOver(e) {
            e.preventDefault();
            e.dataTransfer.dropEffect = "move";
            e.currentTarget.setAttribute("data-drag-over", "true");
        }

        onSlotDragLeave(e) {
            e.currentTarget.removeAttribute("data-drag-over");
        }

        async onSlotDrop(e) {
            e.preventDefault();
            e.currentTarget.removeAttribute("data-drag-over");

            if (!this.draggedItem) return;
            // Bag cells are all draggable so they can be handed to an ally;
            // a potion still has no business in an equipment slot.
            if (this.isConsumable(this.draggedItem)) {
                this.toast("That is something to drink, not to wear.", false);
                return;
            }

            const targetSlot = e.currentTarget.dataset.slot;
            await this.equipItem(this.draggedItem, targetSlot);
        }

        // --- Giving an item to another party member -------------------------
        // The drop target is a party-rail frame, which lives outside this
        // panel's root, so these are registered as one delegated listener at
        // module load rather than attached per frame. On the dashboard the
        // selector simply never matches (the modal's backdrop covers the
        // roster anyway), so the give is a dungeon-HUD affordance.

        onFrameDragOver(e, frame) {
            if (!this.draggedItem) return;
            if (!this.canGiveTo(frame)) return;
            e.preventDefault();
            e.dataTransfer.dropEffect = "move";
            frame.setAttribute("data-drag-over", "true");
        }

        canGiveTo(frame) {
            const to = frame.dataset.charId;
            if (!to || !this.character) return false;
            // Your own frame is not a target, and neither is a corpse -- the
            // server refuses both, but there is no reason to offer the gesture.
            if (String(to) === String(this.character.id)) return false;
            if (frame.classList.contains("is-downed")) return false;
            return true;
        }

        async onFrameDrop(e, frame) {
            e.preventDefault();
            frame.removeAttribute("data-drag-over");

            const item = this.draggedItem;
            if (!item || !this.canGiveTo(frame)) return;

            // Captured before the POST: this.character can be swapped out from
            // under us by an open() landing mid-flight. The reload afterwards
            // still goes through refresh(), which reads _openCharId.
            const from = this.character.id;
            const body = { to_character_id: Number(frame.dataset.charId) };
            if (item.uid) body.uid = item.uid;
            else body.slug = item.slug;

            try {
                const response = await fetch(`/api/characters/${from}/give`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(body),
                });
                const d = await response.json().catch(() => ({}));
                if (!response.ok) {
                    this.toast(this.refusalText(d, "They cannot take that."), false);
                    return;
                }
                this.toast(`${item.name} passed to ${d.to_name || "your ally"}.`);
                await this.refresh();
                // The receiver is never the open panel, so its frame is the
                // only place the change shows -- same pair consumeItem uses.
                if (window.refreshPartyCards) window.refreshPartyCards();
            } catch (err) {
                this.toast("They cannot take that.", false);
            }
        }

        async equipItem(item, slot) {
            // Read once, before the POST. this.character can be swapped out
            // from under us by an open() landing while the request is in
            // flight, and the POST must address the character the player
            // actually acted on, not whichever one the panel drifted to.
            //
            // The *reload* is the opposite question and must not reuse this
            // id: see refresh() below. Mutating A and then reloading A would
            // paint the outgoing character over an open(B) that has already
            // finished -- and because that reload starts last, it is the
            // newest generation, so the guard passes it. refresh() reloads
            // _openCharId, which is whoever is actually on screen.
            const charId = this.character.id;
            // Procedural gear instances carry a `uid` and self-describe their
            // slot; equip them by uid. Legacy catalog items equip by slug +
            // target slot.
            const isInstance = item && typeof item === "object" && item.uid;
            const body = isInstance
                ? { uid: item.uid }
                : { slug: (typeof item === "object" ? item.slug : item), slot: slot };
            const response = await fetch(`/api/characters/${charId}/equip`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(body),
            });

            if (response.ok) {
                await this.refresh();
            } else {
                const d = await response.json().catch(() => ({}));
                this.toast(this.refusalText(d, "Could not equip that."), false);
            }
        }

        async unequipItem(slot) {
            // POST addresses the mutated character; the reload follows the
            // panel. See equipItem.
            const charId = this.character.id;
            const response = await fetch(`/api/characters/${charId}/unequip`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ slot: slot }),
            });

            if (response.ok) {
                await this.refresh();
            } else {
                // Previously absent entirely, which made a refused unequip --
                // an armour slot locked mid-fight, most commonly -- a button
                // that did nothing at all with no explanation.
                const d = await response.json().catch(() => ({}));
                this.toast(this.refusalText(d, "Could not remove that."), false);
            }
        }

        /**
         * Drink a potion out of combat.
         *
         * The panel this one replaced rendered a `Use` button on every potion
         * in the bag and posted it here; the replacement never had one, so
         * out-of-combat healing (and regen potions, which are out-of-combat
         * only by design) had no route into the game at all -- clicking a
         * potion tried to *equip* it and earned a 400. Combat potions were
         * never affected; they go through combat.js.
         */
        async consumeItem(item) {
            // POST addresses the mutated character; the reload follows the
            // panel. See equipItem.
            const charId = this.character.id;
            const response = await fetch(`/api/characters/${charId}/consume`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ slug: item.slug }),
            });

            if (response.ok) {
                this.toast(`${item.name} — drained to the last drop.`, true);
                // No mud-characters-state-invalidated dispatch: this panel is
                // that event's only listener, so firing it here would just
                // queue a second, identical fetch behind the reload below.
                await this.refresh();
                // Drinking changes current HP, and the party rail is showing
                // that exact number a few inches away. Without this the panel
                // reads 10/30 and the frame behind it still reads 5/30 --
                // the rail listens for nothing, so it would stay wrong until
                // the next move. Camp calls the same function for the same
                // reason. (Equipping does not move current HP, which is why
                // it is only wired up here.)
                if (window.refreshPartyCards) window.refreshPartyCards();
            } else {
                const d = await response.json().catch(() => ({}));
                this.toast(this.refusalText(d, "Nothing happens."), false);
            }
        }

        /**
         * The human sentence a refusal carries, never the machine code.
         *
         * These endpoints answer with `{error: "in_combat", message: "Armour
         * cannot be changed during a fight..."}`; the panel used to show the
         * player `in_combat`, or `item not equippable`, which reads as a bug
         * report rather than a rule of the game. `error` is kept as a second
         * choice only because a few older branches of the API send it alone.
         */
        refusalText(payload, fallback) {
            const d = payload || {};
            return d.message || d.error || fallback;
        }

        toast(msg, ok = true) {
            const el = document.createElement("div");
            el.className = `eq-toast alert alert-${ok ? "success" : "warning"} alert-dismissible fade show position-fixed top-0 end-0 m-3`;
            el.innerHTML = `${this.escapeHTML(msg)}<button type="button" class="btn-close" data-bs-dismiss="alert"></button>`;
            document.body.appendChild(el);
            setTimeout(() => el.remove(), 3000);
        }

        // ---- item comparison tooltip ----

        showComparisonTooltip(e) {
            const itemIndex = parseInt(e.currentTarget.dataset.itemIndex, 10);
            const item = this.character.bag[itemIndex];
            if (!item) return;
            // A consumable has nothing to compare against. getSlotForItemType
            // falls back to "weapon" for anything outside the canonical eight,
            // so without this a potion was shown "vs. Equipped" against
            // whatever the character was holding.
            const equipped = this.isConsumable(item)
                ? null
                : this.character.gear?.[this.getSlotForItemType(item.type || item.slot || "")];

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
            const tooltip = document.createElement("div");
            tooltip.className = "item-comparison-tooltip";

            const rarityClass = `rarity-${item.rarity || "common"}`;
            const itemStats = this.parseItemStats(item);

            let html = `
                <div class="tooltip-item-header">
                    <div class="tooltip-item-name ${rarityClass}">${this.escapeHTML(item.name)}</div>
                    <div class="tooltip-item-type">${this.escapeHTML(item.type || item.slot || "")}</div>
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
                const aff = item.affixes.map((a) => `+${a.val} ${String(a.stat).toUpperCase()}`).join(", ");
                html += `<div class="tooltip-affixes ${rarityClass}">${this.escapeHTML(aff)}</div>`;
            }

            if (item.description) {
                html += `<div class="tooltip-description">${this.escapeHTML(item.description)}</div>`;
            }

            // What activating the cell will actually do. The grid is icons in
            // 48px squares with no room for a label, so this line is the only
            // place a player is told that clicking does anything at all --
            // and, for a potion, that it drinks rather than equips.
            html += `<div class="tooltip-action-hint">${
                this.isConsumable(item)
                    ? "Click or press Enter to drink"
                    : "Click or press Enter to equip"
            }</div>`;

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

        // ---- helper functions ----

        getSlotLabel(slot) {
            // The canonical eight (app/loot/data/archetypes.py SLOTS). Old
            // ring1/ring2/legs/boots/gloves vocabulary is gone -- carrying
            // dead keys here shipped a slot (feet) with no label at all.
            const labels = {
                weapon: "Main Hand",
                offhand: "Off Hand",
                head: "Head",
                chest: "Chest",
                hands: "Hands",
                feet: "Feet",
                ring: "Ring",
                amulet: "Amulet",
            };
            return labels[slot] || slot;
        }

        getSlotIcon(slot) {
            const icons = {
                weapon: '<i class="bi bi-sword"></i>',
                offhand: '<i class="bi bi-shield"></i>',
                head: '<i class="bi bi-person-circle"></i>',
                chest: '<i class="bi bi-shield-fill-check"></i>',
                hands: '<i class="bi bi-hand-index"></i>',
                feet: '<i class="bi bi-person-walking"></i>',
                ring: '<i class="bi bi-circle"></i>',
                amulet: '<i class="bi bi-gem"></i>',
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
                tool: '<i class="bi bi-wrench"></i>',
            };
            return icons[type] || '<i class="bi bi-box"></i>';
        }

        getSlotForItemType(type) {
            // Procedural gear instances self-describe their slot and it is
            // already one of the canonical eight (see app/loot/generator.py)
            // -- pass it straight through. The original mapping had no
            // entries for offhand/head/chest/feet, so those fell through to
            // the `|| 'weapon'` fallback and compared looted gear against
            // the equipped weapon regardless of what was actually looted;
            // checking the canonical vocabulary first fixes that.
            const canonical = this.slots || FALLBACK_SLOTS;
            if (canonical.includes(type)) return type;
            // Legacy catalog items describe themselves by `type`, not
            // `slot`, and only ever use a couple of names that don't match
            // a canonical slot directly.
            const legacyMap = {
                armor: "chest",
                shield: "offhand",
            };
            return legacyMap[type] || "weapon";
        }

        getItemStats(item) {
            if (item.level) {
                return `Level ${item.level}`;
            }
            return "";
        }

        parseItemStats(item) {
            return {
                attack: item.attack || 0,
                defense: item.defense || 0,
            };
        }

        renderStatsHTML(stats) {
            let html = "";
            if (stats.attack) html += `<div class="tooltip-stat-row"><span>Attack</span><span class="stat-positive">+${stats.attack}</span></div>`;
            if (stats.defense) html += `<div class="tooltip-stat-row"><span>Defense</span><span class="stat-positive">+${stats.defense}</span></div>`;
            return html || '<div class="stat-neutral">No special stats</div>';
        }

        renderComparisonHTML(newStats, oldStats) {
            let html = "";
            if (newStats.attack !== oldStats.attack) {
                const diff = newStats.attack - oldStats.attack;
                const diffClass = diff > 0 ? "better" : "worse";
                html += `<div class="tooltip-stat-row"><span>Attack</span><span class="comparison-diff ${diffClass}">${diff > 0 ? "+" : ""}${diff}</span></div>`;
            }
            if (newStats.defense !== oldStats.defense) {
                const diff = newStats.defense - oldStats.defense;
                const diffClass = diff > 0 ? "better" : "worse";
                html += `<div class="tooltip-stat-row"><span>Defense</span><span class="comparison-diff ${diffClass}">${diff > 0 ? "+" : ""}${diff}</span></div>`;
            }
            return html || '<div class="stat-neutral">No difference</div>';
        }

        calculateTotalStats() {
            const ch = this.character || {};
            const apiStats = ch.stats || {};
            // API returns stats: { base: {...}, computed: {...} }
            const base = apiStats.base || apiStats;
            const computed = apiStats.computed || base;
            const level = ch.level || base.level || 1;
            return {
                cls:       base.class || "adventurer",
                hp:        base.hp    || 0,
                max_hp:    20 + level * 10,
                mana:      base.mana  || 0,
                max_mana:  10 + level * 5,
                str:       computed.str || base.str || 0,
                dex:       computed.dex || base.dex || 0,
                con:       computed.con || base.con || 0,
                int:       computed.int || base.int || 0,
                level,
                xp:        ch.xp || 0,
                xp_to_next: ch.xp_for_next_level || 100,
            };
        }

        escapeHTML(str) {
            if (!str) return "";
            return String(str).replace(/[&<>"']/g, (m) => ({
                "&": "&amp;",
                "<": "&lt;",
                ">": "&gt;",
                '"': "&quot;",
                "'": "&#39;",
            }[m]));
        }
    }

    const panel = new EquipmentPanelController();

    window.EquipmentPanel = {
        mount: (container) => panel.mount(container),
        open: (charId) => panel.open(charId),
        close: () => panel.close(),
        isOpen: () => panel.isOpen(),
        refresh: () => panel.refresh(),
    };

    // The panel owns its trigger. Both screens use .btn-equip-panel on an
    // element carrying data-char-id; the adventure screen additionally opens
    // from anywhere on a party frame (see adventure-controls.js). Registered
    // once at module load, unconditionally -- not inside mount(). On the
    // dashboard nothing ever calls mount() explicitly (it only happens
    // lazily, as a side effect of open()'s own _ensureDashboardMount()), so
    // a listener registered inside mount() would never exist to be clicked:
    // open() is what triggers the first mount(), and this listener is what
    // is supposed to trigger open(). Module-load registration breaks that
    // circularity; open() still lazily mounts on first call either way.
    document.addEventListener('click', (e) => {
        const btn = e.target.closest('.btn-equip-panel');
        if (!btn) return;
        const host = btn.closest('[data-char-id]');
        if (host && host.dataset.charId) window.EquipmentPanel.open(host.dataset.charId);
    });

    // Giving: drag a bag cell onto another party member's frame. Registered
    // the same way and for the same reason as the click delegate above -- the
    // frames are server-rendered outside this panel's root, and drag events
    // bubble, so one document listener covers all four without a per-frame
    // attach or a re-attach hook. closest() no-ops on the dashboard, which has
    // no rail.
    ['dragover', 'dragleave', 'drop'].forEach((type) => {
        document.addEventListener(type, (e) => {
            const frame = e.target.closest && e.target.closest('.adv-frame-open');
            if (!frame) return;
            if (type === 'dragover') panel.onFrameDragOver(e, frame);
            else if (type === 'dragleave') frame.removeAttribute('data-drag-over');
            else panel.onFrameDrop(e, frame);
        });
    });

    // Loot claimed elsewhere (adventure.js:774, adventure-extraction.js:89)
    // dispatches this to invalidate cached character state. equipment.js was
    // its only listener; that died with it, so without this, gear picked up
    // while the panel is open (a search-tile claim, a shrine reward) doesn't
    // show up in the bag until the panel is closed and reopened. Only
    // refresh while actually open -- refresh() only matters for what's on
    // screen right now.
    document.addEventListener('mud-characters-state-invalidated', () => {
        if (window.EquipmentPanel.isOpen()) window.EquipmentPanel.refresh();
    });

    if (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1") {
        window.openEquipment = (charId) => window.EquipmentPanel.open(charId);
        console.log("%c⚔️ Equipment Panel Loaded", "color: #64b4ff; font-weight: bold");
        console.log("%cTest command available:", "color: #64b4ff");
        console.log("%c  openEquipment(charId) - Open equipment panel", "color: #888");
    }
})();
