# Adventure HUD Shell Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn `/adventure` into a full-bleed dungeon map with a floating HUD — no navbar, party frames on the left edge, log and action bar floating — that fits a 1366×768 laptop without scrolling.

**Architecture:** A `chrome="minimal"` render flag lets `base.html` skip the navbar, the `.container` wrapper and the footer for one screen, and a `realm="dungeon"` flag stamps `data-realm` on `<body>` so the existing cold palette in `tokens.css` takes over. The adventure page then becomes one positioned root (`.adv-hud`) with the canvas filling it and every other element absolutely placed above it. All new styling lives in one page stylesheet, `app/static/css/adventure-hud.css`, built on `tokens.css`.

**Tech Stack:** Flask + Jinja2 templates, vanilla JS (no build step, no bundler), plain CSS with custom properties, pytest + Flask test client, Playwright for the e2e smoke.

## Global Constraints

Copied from `docs/DESIGN_SYSTEM.md` and the source specs. Every task's requirements implicitly include these.

- **One token file.** `app/static/css/tokens.css`. Never open a second `:root` block.
- **Semantic tokens only.** No hard-coded hex, no bare `z-index: 9999` — use `--z-hud: 200` for HUD overlays, `--z-modal` and above for dialogs.
- **`--radius` is `0`.** Hard edges. No `border-radius` other than the tokens, no diffuse `box-shadow` — `--elev-flat: none` is the default; `--elev-overlay` is only for things genuinely above the page.
- **Page CSS styles the page, not the app.** No bare element selectors in `adventure-hud.css`; scope everything under `.adv-hud`.
- **No `!important` in static CSS.**
- **Terminology is styling.** Player-facing copy uses D&D register — party, roster, provisions, delve, hoard, spoils. CSS class names may lag; copy may not.
- **Target viewport floor: 1366×768.** Everything essential visible without scrolling. Scales up to 2560×1440 by giving the map more room, never the HUD.
- **Not a mobile design.** Below `1200px` the layout may fall back to stacked; it must not overlap.
- **Do not move `Extract` or `Hearth` into the account menu.** They are game actions with consequences and stay with the game controls.
- **The canvas resizes itself.** `DungeonCanvas.resizeCanvas()` reads `getBoundingClientRect()` and multiplies by `devicePixelRatio`; sizing the canvas from CSS is sufficient and keeps tiles crisp.

## How to run the tests

```bash
export TEST_DATABASE_URL=postgresql://adventure:changeme@localhost:5433/adventure_test
.venv/bin/python -m pytest tests/ -q
```

The e2e browser checks need a running server and are skipped without `E2E=1`:

```bash
E2E=1 ADVENTURE_BASE_URL=http://localhost:5000 .venv/bin/python -m pytest e2e -q
```

## What this plan deliberately does not build

Stated up front so a reviewer does not read them as omissions:

- **Log tabs (adventure / combat / chat).** The HUD spec asks for three tabs; only one log stream exists on this screen. `chat-widget.js` is lobby-scoped (`lobby-chat-input-<tabId>`) and is not loaded by `adventure.html`; the combat log lives on the separate `combat.html`. Task 4 builds the floating panel with the single adventure log. Add the tab strip when a second stream actually lands on this screen.
- **The paper doll.** Task 3 makes the whole party frame a click target that opens the *existing* equipment panel. Replacing the two paper dolls with one is the next chunk (`specs/2026-07-28-character-panel-redesign.md`), and the frame click is the hook it will reuse.
- **Encumbrance on the frame.** Belongs to the character-panel chunk; the frame markup in Task 3 does not reserve a slot for it, because a slot with nothing in it is the thing that rots.
- **`stopPropagation` on the floating panels.** The HUD spec lists this as constraint 1, but it is already satisfied by construction — see the note in Task 2, Step 1. Writing the calls anyway would be dead code.

## File Structure

| File | Change | Responsible for |
|---|---|---|
| `app/templates/base.html` | modify | The `chrome` / `realm` flags: whether the navbar, container wrapper and footer render, and what `<body data-realm>` says |
| `app/templates/partials/account_anchor.html` | **create** | The top-right account affordance — avatar button plus the existing dropdown items |
| `app/routes/dungeon_api.py:2155` | modify | Pass `chrome="minimal"`, `realm="dungeon"` from the `/adventure` route |
| `app/templates/adventure.html` | modify | The HUD markup: canvas root, party rail, floating log, action bar. Its inline `<style>` block goes away |
| `app/static/css/adventure-hud.css` | **create** | Every rule for the new layout, scoped under `.adv-hud` |
| `app/static/css/utilities.css:41-47` | delete rule | Removing the duplicate `.map-fluid-fixed-height` |
| `app/static/js/dungeon-canvas.js` | modify | Camera centring that respects the HUD's reserved margins; minimap y-offset |
| `tests/test_adventure_hud.py` | **create** | Server-side assertions: chrome flag, realm attribute, HUD hooks, dashboard regression |
| `e2e/test_smoke.py` | modify | The check that actually matters: no vertical scroll at 1366×768 |

---

### Task 1: The `chrome` and `realm` render flags

The adventure screen needs to opt out of the navbar, the `.container py-4` wrapper and the footer, and opt in to the cold palette. Both are template-level flags with safe defaults so every other page is untouched.

**Files:**
- Modify: `app/templates/base.html:26-27`, `:28`, `:111-127`, `:131`
- Create: `app/templates/partials/account_anchor.html`
- Modify: `app/routes/dungeon_api.py:2155`
- Test: `tests/test_adventure_hud.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - Jinja variables `chrome` (`"full"` default, `"minimal"` on `/adventure`) and `realm` (`"town"` default, `"dungeon"` on `/adventure`), available to any `render_template` call.
  - `<body data-realm="{{ realm }}">` — the switch `tokens.css:102` already keys off.
  - A partial at `partials/account_anchor.html` rendering `<div id="account-anchor">` with the user dropdown inside. Task 2 positions it.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_adventure_hud.py`:

```python
"""The adventure screen renders as a game HUD, not a dashboard page.

Spec: docs/superpowers/specs/2026-07-28-adventure-hud-layout-design.md

The navbar's four informational links (#getting-started, #classes, #items,
#rules) are anchors into the *landing page*; on /adventure no such elements
exist, so they already scroll nowhere. They are dropped here along with the
rest of the page chrome, and the user dropdown is relocated to a corner
affordance.

Note the footer partial also contains the strings "Getting Started" etc., so
these tests key off structural ids (#navbarMain, #account-anchor) rather than
copy.
"""

import json

import pytest

from app import db
from app.models.dungeon_instance import DungeonInstance
from app.models.models import Character, User


@pytest.fixture()
def party(client):
    from werkzeug.security import generate_password_hash

    user = User.query.filter_by(username="hud_user").first()
    if not user:
        user = User(username="hud_user", password=generate_password_hash("pw"))
        db.session.add(user)
        db.session.commit()
    Character.query.filter_by(user_id=user.id).delete()
    db.session.commit()

    members = []
    for name in ("Ava", "Bo", "Cai", "Dun"):
        char = Character(
            user_id=user.id,
            name=name,
            stats=json.dumps({"str": 10, "con": 12, "int": 12, "hp": 20, "mana": 8}),
            gear="{}",
            items="[]",
            level=2,
        )
        db.session.add(char)
        members.append(char)
    db.session.commit()

    instance = DungeonInstance(user_id=user.id, seed=4242, pos_x=0, pos_y=0, pos_z=0)
    db.session.add(instance)
    db.session.commit()

    with client.session_transaction() as sess:
        sess["_user_id"] = str(user.id)
        sess["user_id"] = user.id
        sess["dungeon_instance_id"] = instance.id
        sess["last_party_ids"] = [c.id for c in members]
    return user, members


def test_adventure_drops_the_navbar(client, party):
    html = client.get("/adventure").get_data(as_text=True)

    assert 'id="navbarMain"' not in html, "the informational nav is still rendering in the dungeon"
    assert 'href="#getting-started"' not in html, "landing-page anchors still present on /adventure"


def test_adventure_keeps_an_account_anchor(client, party):
    html = client.get("/adventure").get_data(as_text=True)

    assert 'id="account-anchor"' in html, "no account affordance survived the navbar removal"
    assert "/logout" in html, "the account anchor must still reach logout"


def test_adventure_is_the_cold_realm(client, party):
    html = client.get("/adventure").get_data(as_text=True)

    assert 'data-realm="dungeon"' in html, "the dungeon screen is still rendering the warm town palette"


def test_adventure_keeps_the_run_ending_actions_out_of_the_menu(client, party):
    """Extract and Hearth are game actions with consequences, not settings."""
    html = client.get("/adventure").get_data(as_text=True)

    assert 'id="btn-extract"' in html
    assert 'id="btn-hearth"' in html


def test_dashboard_still_has_full_chrome(client, party):
    """Regression: the flag must not leak to every other page."""
    html = client.get("/dashboard").get_data(as_text=True)

    assert 'id="navbarMain"' in html, "the navbar vanished from the dashboard"
    assert 'data-realm="dungeon"' not in html, "the town screens went cold"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:
```bash
export TEST_DATABASE_URL=postgresql://adventure:changeme@localhost:5433/adventure_test
.venv/bin/python -m pytest tests/test_adventure_hud.py -q
```
Expected: 4 failures (`test_adventure_drops_the_navbar`, `..._keeps_an_account_anchor`, `..._is_the_cold_realm`, and possibly nothing else). `test_dashboard_still_has_full_chrome` and `..._run_ending_actions` should already PASS — they are the regression guards.

- [ ] **Step 3: Create the account anchor partial**

Create `app/templates/partials/account_anchor.html`. The dropdown items are lifted verbatim from `base.html:74-98` so nothing about the account menu changes except where it sits:

```html
{# Corner account affordance for chrome="minimal" screens. Same dropdown the
   navbar carries; only the trigger shrinks to an avatar. Positioned by the
   page's own stylesheet, not here. #}
<div id="account-anchor" class="dropdown">
  <a class="account-anchor-trigger" href="#" id="accountAnchorMenu" role="button" data-bs-toggle="dropdown"
    aria-expanded="false" aria-label="Account menu">
    <span class="avatar-circle">{{ current_user.username[0]|upper }}</span>
  </a>
  <ul class="dropdown-menu dropdown-menu-end" aria-labelledby="accountAnchorMenu">
    <li><a class="dropdown-item" href="{{ url_for('dashboard.dashboard') }}"><i
          class="bi bi-speedometer2 me-2"></i>Dashboard</a></li>
    <li><a class="dropdown-item" href="{{ url_for('account.profile') }}"><i
          class="bi bi-person-circle me-2"></i>Profile</a></li>
    <li><a class="dropdown-item" href="{{ url_for('account.settings') }}"><i
          class="bi bi-person-gear me-2"></i>Settings</a></li>
    {% if (current_user.role|default('user', true)) == 'admin' %}
    <li>
      <hr class="dropdown-divider">
    </li>
    <li><a class="dropdown-item" href="{{ url_for('admin_new.dashboard') }}"><i
          class="bi bi-shield-lock me-2"></i>Admin Dashboard</a></li>
    <li><a class="dropdown-item" href="{{ url_for('admin_new.themes') }}"><i
          class="bi bi-palette me-2"></i>Themes</a></li>
    {% endif %}
    <li>
      <hr class="dropdown-divider">
    </li>
    <li><a class="dropdown-item" href="{{ url_for('auth.logout') }}"><i
          class="bi bi-box-arrow-right me-2"></i>Logout</a></li>
  </ul>
</div>
```

- [ ] **Step 4: Teach `base.html` the two flags**

In `app/templates/base.html`, replace the `<body>` opening tag at line 26:

```html
<body class="d-flex flex-column min-vh-100" data-realm="{{ realm|default('town') }}">
```

Replace the `<header>` block (lines 27-28's opening and the matching `{% endif %}</header>` at 108-109) so the condition also honours the flag. The opening becomes:

```html
  <header>
    {% if chrome|default('full') == 'minimal' %}
    {% include 'partials/account_anchor.html' %}
    {% elif request.endpoint not in ['main.index', 'auth.login'] %}
    <nav class="navbar navbar-expand-md navbar-dark bg-dark fixed-top">
```

and the close at line 108 becomes:

```html
    {% endif %}
  </header>
```

(That line is already `{% endif %}` — the `{% elif %}` above folds into the same block, so no change is needed at 108 beyond confirming it still closes correctly.)

Replace the `<main>` block, lines 111-127, so a minimal screen gets no container and no top padding:

```html
  {% if chrome|default('full') == 'minimal' %}
  <main class="chrome-minimal">
    {% block content_minimal %}{{ self.content() }}{% endblock %}
  </main>
  {% else %}
  <main class="flex-shrink-0 {% if request.endpoint not in ['main.index', 'auth.login'] %}pt-5{% endif %}">
    <div class="container py-4">
      {% with messages = get_flashed_messages(with_categories=true) %}
      {% if messages %}
      {% for category, message in messages %}
      <div
        class="alert alert-{{ category if category in ['success', 'warning', 'danger', 'info'] else 'info' }} alert-dismissible fade show"
        role="alert">
        {{ message }}
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
      </div>
      {% endfor %}
      {% endif %}
      {% endwith %}
      {% block content %}{% endblock %}
    </div>
  </main>
  {% endif %}
```

Note: `{{ self.content() }}` renders the same `content` block without the wrapper. Flashed messages are deliberately dropped on minimal screens — the adventure page has its own notification banner template (`#notification-banner-template`).

And guard the footer at line 131:

```html
  {% if chrome|default('full') != 'minimal' %}
  {% include 'partials/footer.html' %}
  {% endif %}
```

- [ ] **Step 5: Pass the flags from the `/adventure` route**

In `app/routes/dungeon_api.py`, change line 2155:

```python
    return render_template(
        "adventure.html",
        party=enriched_party,
        seed=seed,
        pos=pos,
        game_clock=clock,
        # Once you enter the dungeon the game is the screen: no navbar, no
        # container, no footer, and the cold realm palette.
        chrome="minimal",
        realm="dungeon",
    )
```

- [ ] **Step 6: Run the tests to verify they pass**

Run:
```bash
.venv/bin/python -m pytest tests/test_adventure_hud.py tests/test_live_party_panel.py tests/test_main_pages.py -q
```
Expected: all PASS. `test_live_party_panel.py` is included because it asserts on `/adventure`'s rendered HTML and must not regress.

- [ ] **Step 7: Run the full suite**

Run:
```bash
.venv/bin/python -m pytest tests/ -q
```
Expected: no new failures. `tests/test_camp_regen_buff.py` has a known pre-existing flake — if it fails, re-run it alone to confirm it is the same one.

- [ ] **Step 8: Commit**

```bash
git add app/templates/base.html app/templates/partials/account_anchor.html \
        app/routes/dungeon_api.py tests/test_adventure_hud.py
git commit -m "feat(hud): add chrome/realm render flags and a corner account anchor

The adventure screen opts out of the navbar, container wrapper and footer
via chrome=minimal, and into the cold palette via realm=dungeon. The four
informational nav links were anchors into the landing page and scrolled
nowhere on /adventure; the user dropdown moves to a top-right affordance.

Spec: docs/superpowers/specs/2026-07-28-adventure-hud-layout-design.md"
```

---

### Task 2: Full-bleed map with a HUD-aware camera

The canvas stops being a 512px box inside a panel and becomes the screen. Camera centring learns about the margins the HUD occupies, so the party never sits under the party rail.

**Files:**
- Modify: `app/templates/adventure.html:1-169` (the `<style>` block and the map panel markup)
- Create: `app/static/css/adventure-hud.css`
- Modify: `app/static/css/utilities.css:41-47` (delete)
- Modify: `app/static/js/dungeon-canvas.js:388-406` (`centerOnPlayer`), `:905-950` (`renderMinimap`)
- Modify: `e2e/test_smoke.py`
- Test: `tests/test_adventure_hud.py` (extend)

**Interfaces:**
- Consumes: `chrome="minimal"` and `#account-anchor` from Task 1.
- Produces:
  - `.adv-hud` — the positioned root element wrapping the whole screen. Tasks 3 and 4 place their panels inside it.
  - Two CSS custom properties declared on `.adv-hud` and read by JS:
    `--hud-inset-left` (space the party rail occupies, px) and `--hud-inset-bottom` (space the log and action bar occupy, px). Task 3 and Task 4 set their panel widths from the same values.
  - `DungeonCanvas.prototype.hudInsets()` returning `{left: Number, bottom: Number}`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_adventure_hud.py`:

```python
def test_adventure_has_a_positioned_hud_root(client, party):
    html = client.get("/adventure").get_data(as_text=True)

    assert 'class="adv-hud"' in html, "no HUD root to position the overlays against"
    assert 'id="dungeon-map"' in html, "the canvas went missing"


def test_adventure_loads_the_hud_stylesheet(client, party):
    html = client.get("/adventure").get_data(as_text=True)

    assert "adventure-hud.css" in html


def test_adventure_has_no_inline_style_block(client, party):
    """Page rules belong in the page stylesheet, per DESIGN_SYSTEM.md."""
    html = client.get("/adventure").get_data(as_text=True)
    body = html.split("</head>", 1)[-1]

    assert "<style>" not in body, "inline <style> block still in the adventure body"
```

Add to `e2e/test_smoke.py`, after `test_adventure_page_renders_map`:

```python
def test_adventure_fits_a_1366x768_laptop(page):
    """The whole reason for the HUD redesign: no scrolling mid-run.

    The old layout needed ~880-910px of vertical space against the ~630-660
    usable on this screen, so the map and the controls could not both be on
    screen. A vertical scrollbar here means the regression is back.
    """
    page.set_viewport_size({"width": 1366, "height": 768})
    page.goto(f"{BASE_URL}/adventure")
    page.wait_for_load_state("networkidle")

    metrics = page.evaluate(
        """() => ({
            scrollH: document.documentElement.scrollHeight,
            clientH: document.documentElement.clientHeight,
            scrollW: document.documentElement.scrollWidth,
            clientW: document.documentElement.clientWidth,
            canvas: document.getElementById('dungeon-map').getBoundingClientRect(),
        })"""
    )

    assert metrics["scrollH"] <= metrics["clientH"] + 1, (
        f"page scrolls vertically at 1366x768: {metrics['scrollH']} > {metrics['clientH']}"
    )
    assert metrics["scrollW"] <= metrics["clientW"] + 1, "page scrolls horizontally at 1366x768"
    assert metrics["canvas"]["height"] > 500, "the map did not take the space the chrome gave back"
    assert metrics["canvas"]["width"] > 1200, "the map is not full-bleed"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:
```bash
.venv/bin/python -m pytest tests/test_adventure_hud.py -q
```
Expected: the three new tests FAIL (`class="adv-hud"` not found, `adventure-hud.css` not found, `<style>` still present).

The e2e check needs a server; run it after the implementation in Step 8.

- [ ] **Step 3: Create the page stylesheet**

Create `app/static/css/adventure-hud.css`. This is the layout skeleton only — Tasks 3 and 4 append their panel rules to this same file.

```css
/* Adventure HUD — the dungeon screen's own layout.
 *
 * Spec: docs/superpowers/specs/2026-07-28-adventure-hud-layout-design.md
 *
 * The map is the screen. Everything else floats above it, absolutely placed
 * against .adv-hud. Scoped under .adv-hud throughout: this file styles one
 * page, not the app (DESIGN_SYSTEM.md, rule 6).
 *
 * The two --hud-inset-* values are the contract between this file and
 * dungeon-canvas.js: they name how much of the viewport the HUD is standing
 * on, so the camera can centre the party in the space that is actually
 * visible rather than in the geometric middle of the canvas.
 */

.adv-hud {
    --hud-inset-left: 300px;
    --hud-inset-bottom: 220px;

    position: fixed;
    inset: 0;
    overflow: hidden;
    background: var(--viewport-bg);
}

/* The canvas fills the frame. resizeCanvas() reads getBoundingClientRect()
   and multiplies by devicePixelRatio, so sizing it here is enough — the
   backing store follows and the tiles stay crisp. */
.adv-hud #dungeon-map {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    display: block;
    cursor: grab;
    background: var(--viewport-bg);
    border: 0;
    border-radius: var(--radius);
}

.adv-hud #dungeon-map:active {
    cursor: grabbing;
}

/* Account anchor: top-right corner. The canvas-drawn minimap also lives
   top-right (dungeon-canvas.js renderMinimap), inset 10px and 120px square;
   it is offset downward there to clear this. */
.adv-hud #account-anchor {
    position: absolute;
    top: var(--space-2);
    right: var(--space-2);
    z-index: var(--z-hud);
}

.adv-hud .account-anchor-trigger {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 36px;
    height: 36px;
    background: var(--surface-overlay);
    border: 1px solid var(--edge);
    color: var(--ink);
    text-decoration: none;
}

.adv-hud .account-anchor-trigger:hover {
    border-color: var(--edge-strong);
    background: var(--surface-hover);
}

/* Zoom controls sit below the minimap, which sits below the account anchor:
   36 (anchor) + 8 (gap) = 44 minimap top, + 120 (minimap) + 8 = 172. */
.adv-hud .map-controls {
    position: absolute;
    top: 172px;
    right: var(--space-2);
    z-index: var(--z-hud);
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
}

.adv-hud .map-controls button {
    width: 32px;
    height: 32px;
    padding: 0;
    font-size: var(--text-base);
    background: var(--surface-overlay);
    border: 1px solid var(--edge);
    color: var(--ink);
    border-radius: var(--radius);
}

.adv-hud .map-controls button:hover {
    border-color: var(--edge-strong);
    color: var(--accent);
}

/* Run readout — seed, tick, entity sync. The strip the panel header used to
   carry, reduced to a corner readout. */
.adv-hud .hud-readout {
    position: absolute;
    top: var(--space-2);
    left: 50%;
    transform: translateX(-50%);
    z-index: var(--z-hud);
    display: flex;
    align-items: center;
    gap: var(--space-3);
    padding: var(--space-1) var(--space-3);
    background: var(--surface-overlay);
    border: 1px solid var(--edge-subtle);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    color: var(--ink-muted);
}

.adv-hud #hotkeys-panel {
    position: absolute;
    top: var(--space-2);
    left: var(--space-2);
    z-index: var(--z-hud);
    display: none;
    max-width: 300px;
    padding: var(--space-3);
    background: var(--surface);
    border: 1px solid var(--edge);
    color: var(--ink);
    font-size: var(--text-sm);
}

/* Below the design floor the HUD would overlap itself. Fall back to a
   stacked layout rather than a broken one: the map keeps a fixed slice of
   the viewport and the panels flow underneath it. */
@media (max-width: 1199px) {
    .adv-hud {
        --hud-inset-left: 0px;
        --hud-inset-bottom: 0px;

        position: static;
        overflow: visible;
    }

    .adv-hud #dungeon-map {
        position: relative;
        height: 55vh;
    }

    .adv-hud #account-anchor,
    .adv-hud .map-controls,
    .adv-hud .hud-readout {
        position: absolute;
    }
}
```

- [ ] **Step 4: Rewrite the adventure template's map frame**

In `app/templates/adventure.html`, delete the entire `<style>` block (lines 6-97) and replace the `mission-briefing` wrapper plus the `col-lg-9` panel (lines 98-170) with the HUD root. Keep the `col-lg-3` party column exactly where it is for now — Task 3 moves it. The block becomes:

```html
{% block head %}
{{ super() }}
<link rel="stylesheet" href="{{ asset_url('css/adventure-hud.css') }}">
{% endblock %}

{% block dashboard_content %}
<div class="adv-hud">
  <canvas id="dungeon-map" width="800" height="600"></canvas>

  <div class="hud-readout">
    <span class="badge badge-mono seed-badge" id="dungeon-seed-badge">seed: ?</span>
    <span>Time: <span id="time-tick-value"
        data-initial="{{ game_clock.tick if game_clock else 0 }}">0</span></span>
    <span id="entity-sync-status" title="Entity stream status">Syncing</span>
    <button id="btn-toggle-controls" class="tactical-btn-secondary" title="Toggle Map Controls">
      <i class="bi bi-sliders"></i>
    </button>
    <button id="btn-show-hotkeys" class="tactical-btn-secondary" title="Show Hotkeys">
      <i class="bi bi-keyboard"></i>
    </button>
  </div>

  <div class="map-controls" id="map-controls-panel">
    <button id="btn-zoom-in" title="Zoom In">+</button>
    <button id="btn-zoom-out" title="Zoom Out">−</button>
    <button id="btn-zoom-reset" title="Reset View">⌂</button>
  </div>

  <div id="hotkeys-panel">
    <div class="d-flex justify-content-between align-items-center mb-2">
      <strong>Hotkeys</strong>
      <button id="btn-close-hotkeys" class="btn btn-sm btn-close btn-close-white"></button>
    </div>
    <div class="small">
      <div class="mb-1"><kbd>W/↑</kbd> Move North</div>
      <div class="mb-1"><kbd>S/↓</kbd> Move South</div>
      <div class="mb-1"><kbd>A/←</kbd> Move West</div>
      <div class="mb-1"><kbd>D/→</kbd> Move East</div>
      <div class="mb-1"><kbd>Space</kbd> Search</div>
      <div class="mb-1"><kbd>C</kbd> Camp</div>
      <div class="mb-1"><kbd>E</kbd> Extract</div>
      <div class="mb-1"><kbd>H</kbd> Hearth</div>
      <div class="mb-1"><kbd>I</kbd> Inventory</div>
      <div class="mb-1"><kbd>Esc</kbd> Close panels</div>
    </div>
  </div>

  {# Party rail (Task 3) and floating log + action bar (Task 4) mount here. #}
  <div id="dungeon-controls">
    <div id="adventure-action-panel" class="d-flex flex-column gap-2">
      <button id="btn-search" type="button" class="tactical-btn-primary"
        title="Search the current tile for hidden treasures (2 turns)">Search</button>
      <button id="btn-party-inventory" type="button" class="tactical-btn-info"
        title="View party shared inventory and gold">Party Stash</button>
      <button id="btn-camp" type="button" class="tactical-btn-secondary"
        title="Make camp: advance time, minor recovery, possible risk">Camp</button>
      <button id="btn-extract" type="button" class="tactical-btn-success"
        title="Extract: bank the run's haul to your Hoard and end the run">Extract</button>
      <button id="btn-hearth" type="button" class="tactical-btn-danger"
        title="Hearthstone: abandon the run and keep what you found (this dungeon is gone)">Hearth</button>
    </div>
    <div id="dungeon-output" class="dungeon-output u-mono">
      <em>Begin your adventure! Your party stands at the entrance of the dungeon...</em>
    </div>
  </div>

  <div id="party-characters-data" data-json='{{ party|tojson }}' hidden></div>
</div>
```

Then move the existing `col-lg-3` party column (lines 171-237, the `{% if party %}` … `{% endif %}` block) so it sits **inside** `.adv-hud`, immediately before the `#party-characters-data` div, wrapped in a rail container. Task 3 styles it; this step only relocates it so nothing renders outside the HUD root:

```html
  <div class="adv-party-rail">
    {% if party and party|length > 0 %}
    ... existing per-member operative-card markup, unchanged ...
    {% else %}
    <div class="alert alert-secondary small">
      <strong>No party loaded.</strong> A fallback attempt to load your characters returned zero rows.<br>
      If you recently created characters, try refreshing or re-selecting a party.
    </div>
    {% endif %}
  </div>
```

Finally, delete the now-unused `.row` / `.col-lg-9` / `.col-lg-3` / `.mission-briefing` / `.tactical-panel` / `.panel-header` / `.panel-body` wrappers.

- [ ] **Step 5: Delete the duplicate map-height rule**

Confirm `utilities.css` is not referenced anywhere first:

```bash
grep -rn "utilities.css" app/ --include=*.html --include=*.py --include=*.css
```
Expected: only the two "merged into app.css" comments in `base.html:19` and `dashboard_base.html:13`. The file is a known orphan (`DESIGN_SYSTEM.md`, "Orphans — 1,607 lines never loaded").

Delete lines 41-47 of `app/static/css/utilities.css` — the duplicate `.map-fluid-fixed-height` block. Leave the rest of the orphan file alone; removing it entirely is its own cleanup.

Then remove the now-dead sibling in `app/static/css/app.css:273` onward — the whole `.map-fluid-fixed-height` rule, since no element carries that class any more:

```bash
grep -rn "map-fluid-fixed-height" app/
```
Expected after both deletions: no hits.

- [ ] **Step 6: Teach the camera about the HUD**

In `app/static/js/dungeon-canvas.js`, add a method immediately above `centerOnPlayer` (line 388):

```js
        /* How much of the viewport the HUD is standing on, in CSS pixels.
           Declared on .adv-hud so the numbers live with the layout that
           produces them; falls back to zero anywhere the HUD is absent
           (the dashboard map preview, the stacked narrow layout). */
        hudInsets() {
            const root = this.canvas.closest('.adv-hud');
            if (!root) return { left: 0, bottom: 0 };
            const cs = getComputedStyle(root);
            return {
                left: parseFloat(cs.getPropertyValue('--hud-inset-left')) || 0,
                bottom: parseFloat(cs.getPropertyValue('--hud-inset-bottom')) || 0,
            };
        }
```

Then in `centerOnPlayer`, replace the two offset lines (396-397):

```js
            const inset = this.hudInsets();
            // Centre the party in the space the player can actually see, not
            // in the geometric middle of the canvas — otherwise the party
            // rail and the log sit on top of them.
            const newOffsetX = (rect.width + inset.left) / 2 - centerX;
            const newOffsetY = (rect.height - inset.bottom) / 2 - centerY;
```

- [ ] **Step 7: Offset the minimap below the account anchor**

In `renderMinimap` (line 905), replace line 911:

```js
            // Below the account anchor, which owns the top-right corner:
            // 36px trigger + 8px gap. Keep in step with .adv-hud .map-controls
            // in adventure-hud.css, which sits below this in turn.
            const minimapY = 44;
```

- [ ] **Step 8: Run the tests**

Run:
```bash
.venv/bin/python -m pytest tests/test_adventure_hud.py tests/test_live_party_panel.py -q
```
Expected: all PASS.

Then boot the server and run the e2e check:
```bash
.venv/bin/python run.py &
E2E=1 ADVENTURE_BASE_URL=http://localhost:5000 .venv/bin/python -m pytest e2e -q
```
Expected: `test_adventure_fits_a_1366x768_laptop` PASSes.

- [ ] **Step 9: Look at it**

Load `http://localhost:5000/adventure` in a browser at 1366×768 and confirm: the map fills the window, no scrollbar, the minimap is visible in the top-right below the gear avatar, zoom buttons below that, and dragging the map still pans.

- [ ] **Step 10: Commit**

```bash
git add app/templates/adventure.html app/static/css/adventure-hud.css \
        app/static/css/utilities.css app/static/css/app.css \
        app/static/js/dungeon-canvas.js tests/test_adventure_hud.py e2e/test_smoke.py
git commit -m "feat(hud): give the map the whole frame

The canvas fills the viewport instead of a fixed 512px box inside a panel,
and the camera centres the party in the space left over after the HUD
rather than in the middle of the canvas. Collapses the duplicated
.map-fluid-fixed-height rule (app.css and the orphaned utilities.css both
declared it at 512px with different borders); the class has no callers now.

The e2e smoke gains the check this was all for: no vertical scroll at
1366x768."
```

---

### Task 3: Party frames on the left edge

The four character cards become a permanent rail down the left of the map. Same data, same refresh path — they move and get restyled, and the whole frame becomes the click target that opens the character.

**Files:**
- Modify: `app/templates/adventure.html` (the `.adv-party-rail` block from Task 2)
- Modify: `app/static/css/adventure-hud.css` (append)
- Modify: `app/static/js/adventure-controls.js:199-200`
- Test: `tests/test_adventure_hud.py` (extend)

**Interfaces:**
- Consumes: `.adv-hud`, `--hud-inset-left` from Task 2.
- Produces: `.adv-party-rail` positioned at the left edge, width matching `--hud-inset-left`. Each child keeps its existing `data-member-id` hook so `window.refreshPartyCards()` (`adventure-controls.js:234`) continues to paint it with no change.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_adventure_hud.py`:

```python
def test_party_frames_live_in_the_rail(client, party):
    html = client.get("/adventure").get_data(as_text=True)

    assert 'class="adv-party-rail"' in html
    assert html.count("data-member-id") == 4, "all four party frames must render in the rail"


def test_party_frames_keep_the_refresh_hooks(client, party):
    """refreshPartyCards() paints .hp-bar/.mana-bar inside [data-member-id]."""
    html = client.get("/adventure").get_data(as_text=True)

    assert "hp-bar" in html
    assert "mana-bar" in html
    assert "party-stat-bar-fill" in html


def test_party_frame_is_a_click_target(client, party):
    html = client.get("/adventure").get_data(as_text=True)

    assert "adv-frame-open" in html, "no hook for opening a character from their frame"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:
```bash
.venv/bin/python -m pytest tests/test_adventure_hud.py -k "rail or refresh_hooks or click_target" -q
```
Expected: `test_party_frames_live_in_the_rail` may already pass from Task 2's relocation; `test_party_frame_is_a_click_target` FAILs.

- [ ] **Step 3: Make the frame the click target**

In `app/templates/adventure.html`, on each party member's card root inside `.adv-party-rail`, add the class and a character id:

```html
        <div data-member-id="{{ m.id }}" data-char-id="{{ m.id }}" role="button" tabindex="0"
          class="operative-card party-card-compact adv-frame-open border-{{ class_lower if class_lower in ['fighter','rogue','mage','cleric','druid','ranger'] else 'secondary' }}">
```

Leave the existing equip/bag button group in place — it is the same action, and Task 3 is not the chunk that redesigns the panel it opens.

- [ ] **Step 4: Wire the frame click**

In `app/static/js/adventure-controls.js`, replace the comment at line 199 (`// Equipment/Bags buttons now handled by equipment.js`) with:

```js
    // Clicking anywhere on a party frame opens that character, same as the
    // frame's equip button. The paper doll itself is the next chunk
    // (specs/2026-07-28-character-panel-redesign.md); this is the hook it
    // will reuse.
    document.addEventListener('click', (e) => {
        const frame = e.target.closest('.adv-frame-open');
        if (!frame) return;
        // Let the frame's own buttons handle their own clicks.
        if (e.target.closest('button')) return;
        const equipBtn = frame.querySelector('.btn-equip-panel');
        if (equipBtn) equipBtn.click();
    });

    document.addEventListener('keydown', (e) => {
        if (e.key !== 'Enter' && e.key !== ' ') return;
        const frame = e.target.closest?.('.adv-frame-open');
        if (!frame || e.target !== frame) return;
        e.preventDefault();
        const equipBtn = frame.querySelector('.btn-equip-panel');
        if (equipBtn) equipBtn.click();
    });
```

- [ ] **Step 5: Style the rail**

Append to `app/static/css/adventure-hud.css`:

```css
/* --- Party rail ---------------------------------------------------------
 * Four frames down the left edge, always visible, always live. Width is the
 * same number the camera reserves (--hud-inset-left), declared once on
 * .adv-hud so the two cannot drift.
 *
 * Four frames at ~90px plus gaps clears 768px comfortably; if a fifth party
 * slot ever exists, the rail scrolls rather than the page.
 */

.adv-hud .adv-party-rail {
    position: absolute;
    top: var(--space-2);
    left: var(--space-2);
    bottom: var(--hud-inset-bottom);
    z-index: var(--z-hud);
    width: calc(var(--hud-inset-left) - var(--space-4));
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    overflow-y: auto;
    scrollbar-width: thin;
}

.adv-hud .adv-party-rail .operative-card {
    background: var(--surface-overlay);
    border: 1px solid var(--edge);
    border-radius: var(--radius);
    box-shadow: var(--elev-flat);
    cursor: pointer;
    transition: border-color var(--dur) var(--ease);
}

.adv-hud .adv-party-rail .operative-card:hover,
.adv-hud .adv-party-rail .operative-card:focus-visible {
    border-color: var(--edge-strong);
    outline: none;
}

.adv-hud .adv-party-rail .operative-card:focus-visible {
    box-shadow: var(--focus-ring);
}

/* A downed character is unmissable — refreshPartyCards() sets this. */
.adv-hud .adv-party-rail .operative-card.is-downed {
    border-color: var(--danger-line);
    background: var(--danger-wash);
}

.adv-hud .adv-party-rail .party-card-header,
.adv-hud .adv-party-rail .party-card-body {
    padding: var(--space-2) var(--space-3);
}

.adv-hud .adv-party-rail .party-card-name {
    font-size: var(--text-sm);
    font-weight: var(--weight-semibold);
}

.adv-hud .adv-party-rail .party-card-badge {
    font-size: var(--text-2xs);
    letter-spacing: var(--tracking-label);
    padding: 2px 6px;
}

.adv-hud .adv-party-rail .party-stat-bar {
    height: 0.9rem;
    font-size: var(--text-2xs);
    border-radius: var(--radius);
    box-shadow: var(--inset-well);
}

.adv-hud .adv-party-rail .party-stat-bar-fill {
    line-height: 0.9rem;
    border-radius: var(--radius);
}

.adv-hud .adv-party-rail .hp-bar .party-stat-bar-fill {
    background: var(--hp);
}

.adv-hud .adv-party-rail .mana-bar .party-stat-bar-fill {
    background: var(--mp);
}

.adv-hud .adv-party-rail .class-icon-slot {
    width: 20px;
    height: 20px;
}

.adv-hud .adv-party-rail .class-icon-slot img {
    width: 18px;
    height: 18px;
}

.adv-hud .adv-party-rail .last-roll-line {
    min-height: 1rem;
    font-size: var(--text-2xs);
}

.adv-hud .adv-party-rail .party-card-action-btn {
    padding: 2px 8px;
    font-size: var(--text-2xs);
}

@media (max-width: 1199px) {
    .adv-hud .adv-party-rail {
        position: static;
        width: auto;
        bottom: auto;
        flex-direction: row;
        flex-wrap: wrap;
        overflow: visible;
    }

    .adv-hud .adv-party-rail .operative-card {
        flex: 1 1 240px;
    }
}
```

- [ ] **Step 6: Run the tests**

Run:
```bash
.venv/bin/python -m pytest tests/test_adventure_hud.py tests/test_live_party_panel.py -q
```
Expected: all PASS.

- [ ] **Step 7: Look at it**

At 1366×768: four frames down the left, HP and MP bars filled from live values, the map visible to the right of them and the party not hidden behind the rail. Click a frame — the equipment panel opens. Take damage in a fight and confirm the bars move.

- [ ] **Step 8: Commit**

```bash
git add app/templates/adventure.html app/static/css/adventure-hud.css \
        app/static/js/adventure-controls.js tests/test_adventure_hud.py
git commit -m "feat(hud): party frames on the left edge

The four cards move out of a Bootstrap column into a permanent rail over
the map, restyled on the design tokens. Same data and the same
refreshPartyCards() hooks, so live HP/MP is unchanged. The whole frame is
now a click target for that character's panel -- the hook the paper-doll
chunk will reuse."
```

---

### Task 4: Floating log and action bar

The log stops being a 280px-tall column squeezed beside five stacked buttons and becomes a floating, collapsible panel in the bottom-right. The five game actions become a bar in the bottom-left.

Collapse is `<details>` / `<summary>` — a native element that needs no JS and no state to keep (ladder rung 4). Resizing is `resize: vertical`, also native.

**Files:**
- Modify: `app/templates/adventure.html` (the `#dungeon-controls` block from Task 2)
- Modify: `app/static/css/adventure-hud.css` (append)
- Modify: `app/static/css/app.css:179-215` (`.dungeon-output` — remove the fixed `max-height`)
- Test: `tests/test_adventure_hud.py` (extend), `e2e/test_smoke.py` (extend)

**Interfaces:**
- Consumes: `.adv-hud`, `--hud-inset-bottom` from Task 2.
- Produces: `.adv-log` (a `<details open>` wrapping `#dungeon-output`) and `.adv-actions` (wrapping `#adventure-action-panel`). `#dungeon-output` keeps its id — `adventure.js:28` grabs it by id and `adventure.js:488` queries `.dungeon-output .inline-search-btn`, so both selectors must survive.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_adventure_hud.py`:

```python
def test_log_is_a_floating_collapsible_panel(client, party):
    html = client.get("/adventure").get_data(as_text=True)

    assert 'class="adv-log"' in html
    assert "<details" in html, "collapse should be the native element, not a JS toggle"
    assert 'id="dungeon-output"' in html, "adventure.js grabs the log by this id"


def test_log_keeps_the_inline_search_button_selector(client, party):
    """adventure.js:488 queries '.dungeon-output .inline-search-btn'."""
    html = client.get("/adventure").get_data(as_text=True)

    assert 'class="dungeon-output' in html


def test_action_bar_holds_the_five_game_actions(client, party):
    html = client.get("/adventure").get_data(as_text=True)

    assert 'class="adv-actions"' in html
    for btn in ("btn-search", "btn-party-inventory", "btn-camp", "btn-extract", "btn-hearth"):
        assert f'id="{btn}"' in html, f"{btn} fell out of the action bar"
```

Append to `e2e/test_smoke.py`:

```python
def test_log_does_not_cover_the_party(page):
    """Overlays must not sit on the camera's target (HUD spec, constraint 2)."""
    page.set_viewport_size({"width": 1366, "height": 768})
    page.goto(f"{BASE_URL}/adventure")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(500)  # let centerOnPlayer settle

    overlap = page.evaluate(
        """() => {
            const hud = document.querySelector('.adv-hud');
            const cs = getComputedStyle(hud);
            const left = parseFloat(cs.getPropertyValue('--hud-inset-left'));
            const bottom = parseFloat(cs.getPropertyValue('--hud-inset-bottom'));
            const r = hud.getBoundingClientRect();
            // Where centerOnPlayer puts the party, per dungeon-canvas.js.
            const px = (r.width + left) / 2;
            const py = (r.height - bottom) / 2;
            const log = document.querySelector('.adv-log').getBoundingClientRect();
            const rail = document.querySelector('.adv-party-rail').getBoundingClientRect();
            const hits = (b) => px >= b.left && px <= b.right && py >= b.top && py <= b.bottom;
            return { log: hits(log), rail: hits(rail) };
        }"""
    )

    assert not overlap["log"], "the floating log is sitting on the party"
    assert not overlap["rail"], "the party rail is sitting on the party"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:
```bash
.venv/bin/python -m pytest tests/test_adventure_hud.py -k "log or action_bar" -q
```
Expected: three FAILs — `.adv-log`, `<details`, `.adv-actions` all absent.

- [ ] **Step 3: Split the controls block into two floating panels**

In `app/templates/adventure.html`, replace the whole `#dungeon-controls` div from Task 2 with:

```html
  <div class="adv-actions">
    <div id="adventure-action-panel" class="d-flex flex-column gap-2">
      <button id="btn-search" type="button" class="tactical-btn-primary"
        title="Search the current tile for hidden treasures (2 turns)">Search</button>
      <button id="btn-party-inventory" type="button" class="tactical-btn-info"
        title="View party shared inventory and gold">Party Stash</button>
      <button id="btn-camp" type="button" class="tactical-btn-secondary"
        title="Make camp: advance time, minor recovery, possible risk">Camp</button>
      <button id="btn-extract" type="button" class="tactical-btn-success"
        title="Extract: bank the run's haul to your Hoard and end the run">Extract</button>
      <button id="btn-hearth" type="button" class="tactical-btn-danger"
        title="Hearthstone: abandon the run and keep what you found (this dungeon is gone)">Hearth</button>
    </div>
  </div>

  {# Collapse is <details>, not a JS toggle: the browser owns the open state,
     the summary is focusable and announced, and there is nothing to keep in
     sync. Tabs (adventure/combat/chat) are deliberately not built -- this
     screen has one log stream today. #}
  <details class="adv-log" open>
    <summary class="adv-log-head">
      <span>Log</span>
    </summary>
    <div id="dungeon-output" class="dungeon-output u-mono">
      <em>Begin your adventure! Your party stands at the entrance of the dungeon...</em>
    </div>
  </details>
```

- [ ] **Step 4: Style both panels**

Append to `app/static/css/adventure-hud.css`:

```css
/* --- Floating log and action bar ----------------------------------------
 * Both sit in the bottom band the camera reserves via --hud-inset-bottom.
 * Actions bottom-left, log bottom-right, and the centre is left clear so the
 * party is never underneath a panel.
 *
 * No pointer-event plumbing is needed: DungeonCanvas binds mousedown,
 * mousemove, wheel and the touch handlers on the canvas element itself
 * (dungeon-canvas.js:182-199), and a canvas cannot have DOM children, so
 * events on these panels never reach it. Scrolling the log will not zoom the
 * map and dragging a panel will not pan it.
 */

.adv-hud .adv-actions {
    position: absolute;
    left: var(--space-2);
    bottom: var(--space-2);
    z-index: var(--z-hud);
    width: calc(var(--hud-inset-left) - var(--space-4));
}

.adv-hud .adv-actions .tactical-btn-primary,
.adv-hud .adv-actions .tactical-btn-secondary,
.adv-hud .adv-actions .tactical-btn-info,
.adv-hud .adv-actions .tactical-btn-success,
.adv-hud .adv-actions .tactical-btn-danger {
    width: 100%;
    padding: var(--space-2) var(--space-3);
    font-size: var(--text-sm);
    letter-spacing: var(--tracking-wide);
    border-radius: var(--radius);
}

.adv-hud .adv-log {
    position: absolute;
    right: var(--space-2);
    bottom: var(--space-2);
    z-index: var(--z-hud);
    width: clamp(360px, 34vw, 560px);
    background: var(--surface-overlay);
    border: 1px solid var(--edge);
}

.adv-hud .adv-log-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: var(--space-1) var(--space-3);
    cursor: pointer;
    list-style: none;
    font-family: var(--font-display);
    font-size: var(--text-xs);
    letter-spacing: var(--tracking-label);
    text-transform: uppercase;
    color: var(--ink-muted);
    border-bottom: 1px solid var(--edge-subtle);
}

.adv-hud .adv-log-head::-webkit-details-marker {
    display: none;
}

.adv-hud .adv-log-head::after {
    content: "▾";
    color: var(--accent);
}

.adv-hud .adv-log:not([open]) .adv-log-head {
    border-bottom: 0;
}

.adv-hud .adv-log:not([open]) .adv-log-head::after {
    content: "▸";
}

/* The "log window is too restrictive for looting" complaint, answered: the
   panel is taller by default and the player can drag it taller still. */
.adv-hud .adv-log .dungeon-output {
    max-height: 32vh;
    min-height: 120px;
    resize: vertical;
    overflow: auto;
    margin: 0;
    border: 0;
    border-left: 3px solid var(--accent-line);
    border-radius: var(--radius);
    background: transparent;
    line-height: var(--leading-loose);
}

@media (max-width: 1199px) {

    .adv-hud .adv-actions,
    .adv-hud .adv-log {
        position: static;
        width: auto;
        margin-top: var(--space-3);
    }

    .adv-hud .adv-actions #adventure-action-panel {
        flex-direction: row;
        flex-wrap: wrap;
    }
}
```

- [ ] **Step 5: Drop the fixed height from the shared log rule**

In `app/static/css/app.css`, in the `.dungeon-output` rule at line 179, delete the `max-height: 280px;` line. The HUD sets its own; other pages using the class get natural height. Leave the rest of the rule — the scrollbar styling and colours are still wanted.

- [ ] **Step 6: Run the tests**

Run:
```bash
.venv/bin/python -m pytest tests/test_adventure_hud.py -q
```
Expected: all PASS.

Boot the server and run the e2e checks:
```bash
.venv/bin/python run.py &
E2E=1 ADVENTURE_BASE_URL=http://localhost:5000 .venv/bin/python -m pytest e2e -q
```
Expected: `test_adventure_fits_a_1366x768_laptop` and `test_log_does_not_cover_the_party` both PASS.

- [ ] **Step 7: Run the full suite**

Run:
```bash
.venv/bin/python -m pytest tests/ -q
```
Expected: no new failures.

- [ ] **Step 8: Look at it, and play it**

At 1366×768: no scrollbar. Move with WASD and confirm the party stays clear of both panels. Collapse the log with its header and confirm the map is unobstructed. Drag the log's bottom edge to resize it. Loot something and confirm the log's inline search buttons still work (`adventure.js:488`). Type nothing — there is no text input on this screen, so the existing `INPUT`/`TEXTAREA` keyboard guard (`adventure-controls.js:124`) is still sufficient; revisit it when the chat tab lands.

- [ ] **Step 9: Commit**

```bash
git add app/templates/adventure.html app/static/css/adventure-hud.css \
        app/static/css/app.css tests/test_adventure_hud.py e2e/test_smoke.py
git commit -m "feat(hud): float the log and the action bar

The log leaves its 280px column beside five stacked buttons and becomes a
collapsible panel bottom-right, taller by default and resizable -- the
'log window is too restrictive for looting' complaint. Collapse is
<details>, so there is no toggle state to keep. The five game actions go
bottom-left; Extract and Hearth stay with them rather than moving into the
account menu.

Deliberately no tabs: this screen has one log stream. Add the strip when
chat or the combat log lands here."
```

- [ ] **Step 10: Update the TODO**

In `docs/superpowers/TODO.md`, mark the Adventure HUD item done and note what carried over:

```markdown
- [x] ~~**Adventure HUD**~~ — full-bleed map, chrome="minimal" render flag,
      account anchor top-right, party frames left, floating collapsible log,
      action bar bottom-left. Plan:
      [plans/2026-07-28-adventure-hud-shell.md](plans/2026-07-28-adventure-hud-shell.md).
      Not built: log tabs (one stream exists on this screen), and the paper
      doll behind the frame click — next chunk,
      [specs/2026-07-28-character-panel-redesign.md](specs/2026-07-28-character-panel-redesign.md).
```

Commit:
```bash
git add docs/superpowers/TODO.md
git commit -m "docs(todo): adventure HUD shell landed"
```

---

## Self-Review

**Spec coverage** — `2026-07-28-adventure-hud-layout-design.md`:

| Spec requirement | Task |
|---|---|
| Full-bleed map sized from viewport | 2 |
| Party frames, left edge, static, always live | 3 |
| Floating collapsible log, bottom-right | 4 |
| Log tabs (adventure/combat/chat) | **not built** — stated up front, one stream exists |
| Account anchor, single corner affordance | 1 |
| Drop the four informational nav links | 1 |
| Extract and Hearth stay out of the account menu | 1 (test), 4 (placement) |
| No on-screen movement pad | already absent — nothing to remove |
| Constraint 1: canvas owns pointer input | 4, Step 4 — satisfied by construction, documented |
| Constraint 2: overlays must not cover the player | 2 (camera insets), 4 (e2e check) |
| Constraint 3: `.map-fluid-fixed-height` declared twice | 2, Step 5 |
| Constraint 4: keyboard shortcuts not swallowed | 4, Step 8 — existing guard sufficient, no text input on this screen |
| Constraint 5: map never extremely letterboxed | 2 — full-bleed on a landscape viewport; narrow fallback at `<1200px` |
| Open question 1: minimap placement | **answered by the player**: stays top-right, floating. Offset 44px down to clear the account anchor (Task 2, Step 7) |
| Open question 2: narrow viewport | answered: stacked fallback at `max-width: 1199px`, defined in every task's CSS |
| Target: 1366×768, no scroll | 2 — the e2e assertion |
| Scales to 2560×1440 | 2 — HUD insets are fixed px, map takes the remainder |

**Type consistency check:** `--hud-inset-left` / `--hud-inset-bottom` declared once on `.adv-hud` (Task 2, Step 3), read by `hudInsets()` (Task 2, Step 6), and consumed by `.adv-party-rail` width (Task 3) and `.adv-actions` width (Task 4) — same names throughout. `.adv-frame-open` is introduced in Task 3, Step 3 and queried in Task 3, Step 4. `#dungeon-output` and `.dungeon-output` both survive Task 4, matching `adventure.js:28` and `:488`.

**Carried forward, not lost:**
- Log tabs — when a second stream reaches this screen.
- Encumbrance on the party frame — character-panel chunk.
- The paper-doll dedupe — character-panel chunk; the frame click is its hook.
- `utilities.css` is a 220-line orphan; only its duplicate rule is removed here. Deleting the file is its own cleanup.
- The keyboard guard widens when a chat input lands on this screen.
