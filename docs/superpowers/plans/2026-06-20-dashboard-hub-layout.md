# Dashboard Hub Layout & Flow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pull the Merchants/Hoard/Party-Management/Achievements action buttons out of the
Party Roster card and into their own tabbed "Hub Actions" panel, so the dashboard's
core navigation flows clearly instead of being buried inside an unrelated card.

**Architecture:** Template-only restructuring of `app/templates/dashboard.html` plus
new scoped CSS in `app/static/css/dashboard.css`. No backend, no JS changes — every
button keeps its exact `onclick`/class wiring, only its container markup moves.

**Tech Stack:** Jinja2 templates, Bootstrap 5 nav-tabs (`data-bs-toggle="tab"`), existing
Cold Steel CSS variables (`var(--ui-*)`, `var(--adv-*)`, `color-mix()`).

## Global Constraints

- No backend route/Python changes — this is template + CSS only (per spec's Architecture
  section: "No backend changes: this is template + CSS only").
- No JS changes — `tradingSystem.openMerchant(...)`, `partySystem.openParty(...)`,
  `achievementSystem.openAchievements(...)`, and the hoard-open button's click handler
  must be invoked with the exact same `onclick`/class attributes as today (per spec's
  "No JS changes" section).
- Drop the in-pane `subtitle` line for each moved button group (e.g. "MERCHANTS") since
  the tab label already names the section (per spec's explicit default decision).
- New CSS must reuse existing `var(--adv-*)`/`color-mix()` patterns already used by
  `.chat-header .nav-tabs` in `dashboard.css` — no new color literals.
- Character/operative cards below the "Available Adventurers" divider are out of scope —
  untouched.
- No automated pytest tests for this plan — this is a template/CSS-only change with no
  Python logic touched (per spec's Testing section). Verification is manual via the
  `run` skill.

---

### Task 1: Slim the Party Roster card and add the Hub Actions panel

**Files:**
- Modify: `app/templates/dashboard.html:89-198` (Party Roster card + the row it's in)

**Interfaces:**
- Consumes: existing `svg_icon()` Jinja macro (already imported at the top of the file),
  existing `characters` template variable, existing `window.tradingSystem` /
  `window.partySystem` / `window.achievementSystem` JS globals and the `.btn-hoard-open`
  class (all already wired by other JS files — not touched by this task).
- Produces: a new full-width row with class `hub-actions-row` containing one
  `tactical-panel hub-actions-panel` card, placed between the existing Recruit/Roster
  row's closing `</div>` and the `<!-- Section Divider -->` comment. Task 2 styles this
  exact `hub-actions-panel` class.

- [ ] **Step 1: Remove the four button-group blocks from the Party Roster form**

In `app/templates/dashboard.html`, inside `<form method="POST" id="begin-adventure-form">`,
delete everything from the `<!-- Merchant Shops -->` comment through the end of the
`<!-- Achievements -->` block (currently lines 132–192), i.e. delete this whole chunk:

```html
                            <!-- Merchant Shops -->
                            <div class="mt-4">
                                <div class="subtitle mb-3">{{ svg_icon('cash', 16, 'me-2') }}MERCHANTS</div>
                                <div class="d-flex flex-column gap-2">
                                    <button type="button"
                                        class="tactical-btn-secondary d-flex align-items-center justify-content-between"
                                        onclick="window.tradingSystem && tradingSystem.openMerchant('general-merchant', {{ characters[0].id if characters else 1 }})">
                                        <span><i class="bi bi-basket me-2"></i> General Store</span>
                                        <span class="badge"
                                            style="background: rgba(212, 165, 116, 0.2); font-size: 0.65rem;">OPEN</span>
                                    </button>
                                    <button type="button"
                                        class="tactical-btn-secondary d-flex align-items-center justify-content-between"
                                        onclick="window.tradingSystem && tradingSystem.openMerchant('weapon-shop', {{ characters[0].id if characters else 1 }})">
                                        <span>{{ svg_icon('bloody-sword', 16, 'me-2') }} Weapon Smith</span>
                                        <span class="badge"
                                            style="background: rgba(212, 165, 116, 0.2); font-size: 0.65rem;">OPEN</span>
                                    </button>
                                    <button type="button"
                                        class="tactical-btn-secondary d-flex align-items-center justify-content-between"
                                        onclick="window.tradingSystem && tradingSystem.openMerchant('armor-shop', {{ characters[0].id if characters else 1 }})">
                                        <span><i class="bi bi-shield-fill me-2"></i> Armor Smith</span>
                                        <span class="badge"
                                            style="background: rgba(212, 165, 116, 0.2); font-size: 0.65rem;">OPEN</span>
                                    </button>
                                </div>
                            </div>

                            <!-- Hoard -->
                            <div class="mt-4">
                                <div class="subtitle mb-3">{{ svg_icon('locked-chest', 16, 'me-2') }}HOARD</div>
                                <div class="d-flex flex-column gap-2">
                                    <button type="button" class="tactical-btn-secondary btn-hoard-open">
                                        <i class="bi bi-bank2 me-2"></i> View Hoard
                                    </button>
                                </div>
                            </div>

                            <!-- Party Management -->
                            <div class="mt-4">
                                <div class="subtitle mb-3">{{ svg_icon('people-fill', 16, 'me-2') }}PARTY</div>
                                <div class="d-flex flex-column gap-2">
                                    <button type="button" class="tactical-btn-secondary"
                                        onclick="window.partySystem && partySystem.openParty(1)">
                                        <i class="bi bi-people-fill me-2"></i> Manage Party
                                    </button>
                                </div>
                            </div>

                            <!-- Skill Trees: opened per-character from each operative card's button -->

                            <!-- Achievements -->
                            <div class="mt-4">
                                <div class="subtitle mb-3">{{ svg_icon('trophy-fill', 16, 'me-2') }}ACHIEVEMENTS</div>
                                <div class="d-flex flex-column gap-2">
                                    <button type="button" class="tactical-btn-secondary"
                                        onclick="window.achievementSystem && achievementSystem.openAchievements({{ characters[0].id if characters else 1 }})">
                                        <i class="bi bi-trophy-fill me-2"></i> Achievements
                                    </button>
                                </div>
                            </div>
```

After deletion, the form's closing structure should read (the `mt-4` seed-widget block
stays immediately before `</form>`):

```html
                            <div class="mt-4">
                                {{ seed_widget(dungeon_seed) }}
                            </div>
                        </form>
```

- [ ] **Step 2: Insert the new Hub Actions panel row**

Immediately after the Recruit/Roster row's closing `</div>` (the line directly above
`<!-- Section Divider -->`), insert this new row:

```html
    <!-- Hub Actions: shops, hoard, party management, achievements -->
    <div class="row mb-4 g-4 hub-actions-row">
        <div class="col-12">
            <div class="tactical-panel hub-actions-panel">
                <div class="panel-header">
                    <h5>{{ svg_icon('cash', 20, 'me-2') }}HUB</h5>
                </div>
                <div class="panel-body">
                    <ul class="nav nav-tabs" id="hubActionsTabs" role="tablist">
                        <li class="nav-item" role="presentation">
                            <button class="nav-link active" id="hub-tab-merchants" data-bs-toggle="tab"
                                data-bs-target="#hub-pane-merchants" type="button" role="tab"
                                aria-controls="hub-pane-merchants" aria-selected="true">Merchants</button>
                        </li>
                        <li class="nav-item" role="presentation">
                            <button class="nav-link" id="hub-tab-hoard" data-bs-toggle="tab"
                                data-bs-target="#hub-pane-hoard" type="button" role="tab"
                                aria-controls="hub-pane-hoard" aria-selected="false">Hoard</button>
                        </li>
                        <li class="nav-item" role="presentation">
                            <button class="nav-link" id="hub-tab-party" data-bs-toggle="tab"
                                data-bs-target="#hub-pane-party" type="button" role="tab"
                                aria-controls="hub-pane-party" aria-selected="false">Party</button>
                        </li>
                        <li class="nav-item" role="presentation">
                            <button class="nav-link" id="hub-tab-achievements" data-bs-toggle="tab"
                                data-bs-target="#hub-pane-achievements" type="button" role="tab"
                                aria-controls="hub-pane-achievements" aria-selected="false">Achievements</button>
                        </li>
                    </ul>
                    <div class="tab-content pt-3" id="hubActionsTabContent">
                        <div class="tab-pane fade show active" id="hub-pane-merchants" role="tabpanel"
                            aria-labelledby="hub-tab-merchants">
                            <div class="d-flex flex-column gap-2">
                                <button type="button"
                                    class="tactical-btn-secondary d-flex align-items-center justify-content-between"
                                    onclick="window.tradingSystem && tradingSystem.openMerchant('general-merchant', {{ characters[0].id if characters else 1 }})">
                                    <span><i class="bi bi-basket me-2"></i> General Store</span>
                                    <span class="badge"
                                        style="background: rgba(212, 165, 116, 0.2); font-size: 0.65rem;">OPEN</span>
                                </button>
                                <button type="button"
                                    class="tactical-btn-secondary d-flex align-items-center justify-content-between"
                                    onclick="window.tradingSystem && tradingSystem.openMerchant('weapon-shop', {{ characters[0].id if characters else 1 }})">
                                    <span>{{ svg_icon('bloody-sword', 16, 'me-2') }} Weapon Smith</span>
                                    <span class="badge"
                                        style="background: rgba(212, 165, 116, 0.2); font-size: 0.65rem;">OPEN</span>
                                </button>
                                <button type="button"
                                    class="tactical-btn-secondary d-flex align-items-center justify-content-between"
                                    onclick="window.tradingSystem && tradingSystem.openMerchant('armor-shop', {{ characters[0].id if characters else 1 }})">
                                    <span><i class="bi bi-shield-fill me-2"></i> Armor Smith</span>
                                    <span class="badge"
                                        style="background: rgba(212, 165, 116, 0.2); font-size: 0.65rem;">OPEN</span>
                                </button>
                            </div>
                        </div>
                        <div class="tab-pane fade" id="hub-pane-hoard" role="tabpanel"
                            aria-labelledby="hub-tab-hoard">
                            <div class="d-flex flex-column gap-2">
                                <button type="button" class="tactical-btn-secondary btn-hoard-open">
                                    <i class="bi bi-bank2 me-2"></i> View Hoard
                                </button>
                            </div>
                        </div>
                        <div class="tab-pane fade" id="hub-pane-party" role="tabpanel"
                            aria-labelledby="hub-tab-party">
                            <div class="d-flex flex-column gap-2">
                                <button type="button" class="tactical-btn-secondary"
                                    onclick="window.partySystem && partySystem.openParty(1)">
                                    <i class="bi bi-people-fill me-2"></i> Manage Party
                                </button>
                            </div>
                        </div>
                        <div class="tab-pane fade" id="hub-pane-achievements" role="tabpanel"
                            aria-labelledby="hub-tab-achievements">
                            <div class="d-flex flex-column gap-2">
                                <button type="button" class="tactical-btn-secondary"
                                    onclick="window.achievementSystem && achievementSystem.openAchievements({{ characters[0].id if characters else 1 }})">
                                    <i class="bi bi-trophy-fill me-2"></i> Achievements
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

```

(The "Skill Trees: opened per-character from each operative card's button" comment is
intentionally dropped — it documented why there was no Skill Trees button here, which
remains true and needs no restating now that the surrounding clutter is gone.)

- [ ] **Step 3: Verify the template still renders**

Run: `source .venv/bin/activate && python -c "from app import create_app; app = create_app(); app.test_client().get('/dashboard')"`

This won't authenticate (expect a redirect, not a 200), but it proves the Jinja template
has no syntax errors. Expected: no `TemplateSyntaxError` / `TemplateNotFound` traceback.

- [ ] **Step 4: Commit**

```bash
git add app/templates/dashboard.html
git commit -m "refactor(dashboard): move hub actions into their own tabbed panel"
```

---

### Task 2: Style the Hub Actions panel and tighten Recruit/Roster spacing

**Files:**
- Modify: `app/static/css/dashboard.css` (append new rules near the existing
  `.chat-header .nav-tabs` block, lines ~147-168)

**Interfaces:**
- Consumes: the `hub-actions-panel` class and Bootstrap's `.nav-tabs`/`.nav-link`/
  `.nav-link.active` classes produced by Task 1's markup.
- Produces: nothing consumed by later tasks (this is the final task in this plan).

- [ ] **Step 1: Add Hub Actions panel tab styling**

Append to `app/static/css/dashboard.css` (after the existing `.chat-header .nav-link.active`
rule, i.e. after line 168):

```css

/* Hub Actions panel (Merchants/Hoard/Party/Achievements tabs) */
.hub-actions-panel .nav-tabs {
    border-bottom: 1px solid color-mix(in srgb, var(--adv-primary) 25%, transparent);
}

.hub-actions-panel .nav-link {
    background: transparent;
    border: none;
    color: rgba(255, 255, 255, 0.7);
    padding: 0.5rem 1.25rem;
    transition: all 0.2s ease;
}

.hub-actions-panel .nav-link:hover {
    color: rgba(255, 255, 255, 0.9);
    background: color-mix(in srgb, var(--adv-primary) 10%, transparent);
}

.hub-actions-panel .nav-link.active {
    color: #fff;
    background: color-mix(in srgb, var(--adv-primary) 15%, transparent);
    border-bottom: 2px solid color-mix(in srgb, var(--adv-primary) 80%, transparent);
}
```

- [ ] **Step 2: Tighten Recruit/Roster spacing now that the Roster card is shorter**

In `app/templates/dashboard.html`, in the Party Roster card (Task 1 already removed the
four button groups), change the seed widget's wrapping margin from `mt-4` to `mt-3` so
the now-shorter card doesn't have an oversized gap before its last element:

Find (inside `#begin-adventure-form`, the block right before `</form>`):

```html
                            <div class="mt-4">
                                {{ seed_widget(dungeon_seed) }}
                            </div>
                        </form>
```

Replace with:

```html
                            <div class="mt-3">
                                {{ seed_widget(dungeon_seed) }}
                            </div>
                        </form>
```

- [ ] **Step 3: Visually verify with the `run` skill**

Start the dev server (or confirm it's already running), then load `/dashboard` in a
browser as a logged-in user and confirm:
- The Party Roster card shows only the party slot grid, deploy/continue buttons, and the
  seed widget — no Merchants/Hoard/Party/Achievements buttons.
- A new "HUB" panel appears below the Recruit/Roster row, above "AVAILABLE ADVENTURERS",
  with four tabs: Merchants, Hoard, Party, Achievements.
- Clicking each tab switches panes without a page reload; the active tab is visually
  highlighted per the new CSS.
- Clicking "General Store" opens the trading modal; "View Hoard" opens the hoard modal;
  "Manage Party" opens the party modal; "Achievements" opens the achievements modal —
  i.e. all four still work exactly as before, just relocated.
- No browser console errors on page load or tab switching.

- [ ] **Step 4: Commit**

```bash
git add app/templates/dashboard.html app/static/css/dashboard.css
git commit -m "style(dashboard): theme the new hub actions panel, tighten roster spacing"
```
