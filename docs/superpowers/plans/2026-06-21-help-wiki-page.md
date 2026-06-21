# Help / Wiki Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the dead footer "Support" link with a real in-app help
page covering Getting Started, Combat, Hoard & Extraction, and Skills &
Progression, illustrated with real screenshots of the running app.

**Architecture:** A new static-content route/template
(`main.help` / `help.html`) following the existing
`privacy.html`/`terms.html`/`conduct.html` pattern, with `<img>` tags
pointing at files under `app/static/img/help/`. A second task generates
those image files by driving the actual dev server with Playwright (now
installed in `.venv`) plus direct DB setup (talent points, an unlocked
skill, a deterministic combat session) so the screenshots show real,
representative game state rather than a default empty one.

**Tech Stack:** Flask/Jinja (route + template), Playwright (Python sync
API, `.venv/lib` — confirmed working: `pip install playwright` succeeded
and a headless Chromium launch succeeded against the cached browser at
`~/.cache/ms-playwright/chromium-1228`), pytest.

## Global Constraints

- New route: `GET /help`, endpoint `main.help`, in `app/routes/main.py`.
- Template: `app/templates/help.html`, extends `base.html`.
- Four sections in this exact order: Getting Started, Dungeon Exploration
  & Combat, Hoard & Extraction, Skills & Progression. Anchor IDs:
  `#getting-started`, `#combat`, `#hoard-extraction`,
  `#skills-progression`.
- Screenshot files live under `app/static/img/help/` (new directory).
- Only the two dead "Support" links get wired
  (`app/templates/index.html:129`,
  `app/templates/partials/footer.html:28`) — no other footer link.
- Backend test suite must stay green:
  `tests/ -q --deselect tests/test_combat_persistence.py` (404 passed
  baseline as of this plan, after the prior combat-skill-buttons merge).
- `DATABASE_URL`/`TEST_DATABASE_URL` must both be exported to the test DB
  before running pytest.
- The screenshot-capture script in Task 2 must run against the **dev**
  database (not the test DB) since it needs a running dev server with
  persistent state — use plain `DATABASE_URL` pointed at the dev DB
  (`postgresql://adventure:changeme@localhost:5433/adventure` — confirmed
  via `app/__init__.py`'s `DATABASE_URL` env read), not
  `TEST_DATABASE_URL`.

---

### Task 1: Help route, template, and footer wiring

**Files:**
- Modify: `app/routes/main.py` (add route in the `--- Legal and Info
  Pages ---` block, after the existing `conduct` route, which ends around
  line 357)
- Create: `app/templates/help.html`
- Modify: `app/templates/index.html:129`
- Modify: `app/templates/partials/footer.html:28`
- Test: `tests/test_main_pages.py`

**Interfaces:**
- Produces: route `main.help` → `GET /help` → 200, rendering
  `help.html`. Template references five images by exact filename (Task 2
  must produce files with these exact names under
  `app/static/img/help/`):
  - `dashboard-overview.png`
  - `combat-action-panel.png`
  - `skill-tree-modal.png`
  - `extraction-modal.png`
  - `hoard-modal.png`

- [ ] **Step 1: Write the failing test**

Open `tests/test_main_pages.py`. It currently contains:

```python
def test_info_pages(client):
    for path in ["/", "/licenses", "/privacy", "/terms", "/conduct"]:
        r = client.get(path, follow_redirects=True)
        assert r.status_code == 200
```

Add `/help` to that list, and add a second test asserting the four
section headings are present:

```python
def test_info_pages(client):
    for path in ["/", "/licenses", "/privacy", "/terms", "/conduct", "/help"]:
        r = client.get(path, follow_redirects=True)
        assert r.status_code == 200


def test_help_page_has_all_sections(client):
    r = client.get("/help")
    body = r.get_data(as_text=True)
    assert r.status_code == 200
    assert 'id="getting-started"' in body
    assert 'id="combat"' in body
    assert 'id="hoard-extraction"' in body
    assert 'id="skills-progression"' in body
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
export DATABASE_URL=postgresql://adventure:changeme@localhost:5433/adventure_test
export TEST_DATABASE_URL=$DATABASE_URL
.venv/bin/python -m pytest tests/test_main_pages.py -v
```
Expected: `test_info_pages` FAILs with a 404 on `/help` (route doesn't
exist yet); `test_help_page_has_all_sections` FAILs the same way (404,
not 200, and the body won't contain the section markers).

- [ ] **Step 3: Add the route**

In `app/routes/main.py`, immediately after the existing `conduct` route
(which reads):

```python
@bp.route("/conduct", endpoint="conduct")
def conduct():
    return render_template("conduct.html")
```

add:

```python
@bp.route("/help", endpoint="help")
def help_page():
    return render_template("help.html")
```

(Named `help_page`, not `help` — `help` is a Python builtin and naming
the view function that shadows it module-wide is worth avoiding even
though Flask only cares about the `endpoint="help"` for `url_for()`
calls like `url_for('main.help')`.)

- [ ] **Step 4: Write the template**

Create `app/templates/help.html`:

```html
{% extends 'base.html' %}
{% block title %}Help - Adventure{% endblock %}
{% block content %}
<div class="container py-5">
  <h1>Help &amp; Guide</h1>
  <p class="lead">Adventure has no live game masters or support staff —
    this page is the closest thing to one. It covers the mechanics new
    players ask about most.</p>

  <nav class="help-toc mb-4" aria-label="Help page sections">
    <ul class="nav nav-pills">
      <li class="nav-item"><a class="nav-link" href="#getting-started">Getting Started</a></li>
      <li class="nav-item"><a class="nav-link" href="#combat">Dungeon Exploration &amp; Combat</a></li>
      <li class="nav-item"><a class="nav-link" href="#hoard-extraction">Hoard &amp; Extraction</a></li>
      <li class="nav-item"><a class="nav-link" href="#skills-progression">Skills &amp; Progression</a></li>
    </ul>
  </nav>

  <hr>

  <section id="getting-started" class="mb-5">
    <h2>Getting Started</h2>
    <p>Register an account, then create up to four characters from the
      dashboard. Each character gets a class, derived from their rolled
      stats, and starts with basic gear. Use the checkboxes on the
      character roster to pick a party of up to four, then press
      "Deploy" to enter the dungeon with them.</p>
    <p>The dashboard's "Hub Actions" panel (the tabbed row below the
      roster) holds the Merchants, Hoard, Party Management, and
      Achievements screens — everything that isn't about an individual
      character lives there.</p>
    <img src="{{ url_for('static', filename='img/help/dashboard-overview.png') }}"
         alt="The dashboard showing the character roster and Hub Actions tabs"
         class="img-fluid border rounded mt-3">
  </section>

  <section id="combat" class="mb-5">
    <h2>Dungeon Exploration &amp; Combat</h2>
    <p>Moving through a dungeon floor can trigger an ambient monster
      encounter, dropping your party into turn-based combat. Each
      character's turn shows an action panel: Attack and Defend are
      always available; Firebolt/Ice Shard/Lightning are universal
      spells any sufficiently magical character can cast for mana; a
      Potion button heals from that character's own potion stock (not a
      shared party pool). If a character has unlocked active skills from
      their talent tree (see Skills &amp; Progression below), those
      appear as extra buttons here too, each on its own cooldown.</p>
    <img src="{{ url_for('static', filename='img/help/combat-action-panel.png') }}"
         alt="The combat screen showing the party, monster, and action panel with both spells and an unlocked skill button"
         class="img-fluid border rounded mt-3">
  </section>

  <section id="hoard-extraction" class="mb-5">
    <h2>Hoard &amp; Extraction</h2>
    <p>This is the single most important thing to understand before you
      lose something you cared about: a character's carried gold and
      gear are <strong>at risk</strong> for the duration of a dungeon run.
      If your whole party is wiped out, that run's gold and any unsecured
      loot are lost. The only way to make loot permanent is to
      <strong>extract</strong> — return to the surface — which moves
      everything your party is carrying into your account's persistent
      <strong>Hoard</strong>, safe from any future run.</p>
    <p>Press the hearth/extraction button in the dungeon to see what
      would be secured before you commit. If a party member goes down but
      survivors remain, those survivors can loot the downed character's
      body before extracting, recovering what would otherwise be lost.</p>
    <img src="{{ url_for('static', filename='img/help/extraction-modal.png') }}"
         alt="The extraction confirmation panel showing what will be secured to the Hoard"
         class="img-fluid border rounded mt-3">
    <img src="{{ url_for('static', filename='img/help/hoard-modal.png') }}"
         alt="The Hoard screen showing persistent copper and items"
         class="img-fluid border rounded mt-3">
  </section>

  <section id="skills-progression" class="mb-5">
    <h2>Skills &amp; Progression</h2>
    <p>Characters earn XP from combat and successful extractions, leveling
      up over time. Each level grants stat points (spend them from the
      character card) and, at certain levels, talent points. Open a
      character's Skill Tree from their card to spend talent points
      unlocking passive bonuses (applied automatically) or active skills.
      Active skills show up as buttons in combat once unlocked — see
      Dungeon Exploration &amp; Combat above.</p>
    <img src="{{ url_for('static', filename='img/help/skill-tree-modal.png') }}"
         alt="The skill tree modal showing unlockable passive and active skills"
         class="img-fluid border rounded mt-3">
  </section>
</div>
{% endblock %}
```

- [ ] **Step 5: Wire the footer links**

In `app/templates/index.html`, line 129, change:

```html
                    <a href="#" class="footer-link">Support</a>
```

to:

```html
                    <a href="{{ url_for('main.help') }}" class="footer-link">Support</a>
```

In `app/templates/partials/footer.html`, line 28, change:

```html
          <li><a href="#">Support</a></li>
```

to:

```html
          <li><a href="{{ url_for('main.help') }}">Support</a></li>
```

- [ ] **Step 6: Run tests to verify they pass**

Run:
```bash
.venv/bin/python -m pytest tests/test_main_pages.py -v
```
Expected: both tests PASS. Note the images won't exist on disk yet
(Task 2 creates them) — this is fine, `url_for('static', ...)` only
builds a URL string at render time and doesn't check file existence, so
the page still renders 200 with broken image icons until Task 2 runs.

- [ ] **Step 7: Run the full suite to check for regressions**

Run:
```bash
.venv/bin/python -m pytest tests/ -q --deselect tests/test_combat_persistence.py
```
Expected: 406 passed (404 baseline + 2 new), 2 skipped, 3 deselected, 1
xpassed — no regressions.

- [ ] **Step 8: Commit**

```bash
git add app/routes/main.py app/templates/help.html app/templates/index.html app/templates/partials/footer.html tests/test_main_pages.py
git commit -m "feat(help): add help/wiki page, wire footer Support link"
```

---

### Task 2: Capture real screenshots for the help page

**Files:**
- Create: `scripts/screenshot_help.py`
- Modify: `requirements-dev.txt` (add `playwright==1.60.0`)
- Create (generated by running the script, not hand-written):
  `app/static/img/help/dashboard-overview.png`,
  `app/static/img/help/combat-action-panel.png`,
  `app/static/img/help/skill-tree-modal.png`,
  `app/static/img/help/extraction-modal.png`,
  `app/static/img/help/hoard-modal.png`

**Interfaces:**
- Consumes: Task 1's `help.html` filenames (must match exactly — listed
  above) so the images appear once committed.
- Consumes existing app internals directly (not just HTTP): the script
  imports `create_app`/`db` from the `app` package and calls
  `combat_service.start_session(user_id, monster)` and
  `spawn_service.choose_monster(level)` to deterministically create a
  combat encounter (ambient encounters are random during normal
  movement, too unreliable for a screenshot script), and inserts a
  `CharacterTalentPoints`/`CharacterSkill` row directly to guarantee at
  least one unlocked active skill is visible in the combat screenshot.
- Produces: five PNG files under `app/static/img/help/`. Nothing else in
  the codebase consumes this script's output programmatically — it's a
  one-off content-generation tool, run manually, not part of CI.

This task has no automated test — it produces static image assets, not
behavior. Verification is: the script runs to completion, prints five
file paths, and a human (or the implementer, reading the saved PNGs'
file sizes) confirms each is a non-trivial-sized real screenshot (a blank
white/error page is typically a few KB; a real UI screenshot with this
app's dark theme is reliably >50KB).

- [ ] **Step 1: Add the Playwright dependency**

In `requirements-dev.txt`, add a line:

```
playwright==1.60.0
```

Install it (already done once during planning, but make this
reproducible for anyone else):

```bash
.venv/bin/pip install -r requirements-dev.txt
```

Verify it can launch the cached browser:

```bash
.venv/bin/python -c "
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    print('launched ok')
    b.close()
"
```
Expected output: `launched ok`. If this fails with a "browser not found"
error, run `.venv/bin/python -m playwright install chromium` first (this
downloads a matching browser build — only needed if the cached one at
`~/.cache/ms-playwright/` doesn't satisfy this Playwright version).

- [ ] **Step 2: Start the dev server against the dev database**

```bash
export DATABASE_URL=postgresql://adventure:changeme@localhost:5433/adventure
./manage.sh restart
```

Confirm it's up:
```bash
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:5000/
```
Expected: `200`.

- [ ] **Step 3: Write the screenshot script**

Create `scripts/screenshot_help.py`. This follows the same
login/autofill-characters/start-adventure pattern already used by
`scripts/screenshot_storyboard.py` (read that file for the established
idioms this borrows: `upsert_user`, `ensure_characters_and_party`, the
`shot()` helper), extended with direct DB setup for a deterministic
combat encounter with an unlocked skill.

```python
#!/usr/bin/env python3
"""One-off content-generation script for the help page's screenshots.

Not part of CI or the test suite — run manually after `./manage.sh
restart` against the dev DB whenever help.html's illustrated screens
change enough to need fresh captures.
"""
import os
import sys
import time
from urllib.parse import urlencode

from playwright.sync_api import sync_playwright

BASE_URL = os.environ.get("ADVENTURE_BASE_URL", "http://localhost:5000")
USERNAME = os.environ.get("ADVENTURE_DEMO_USER", f"helpdemo_{int(time.time())}")
PASSWORD = os.environ.get("ADVENTURE_DEMO_PASS", "demo12345")

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app", "static", "img", "help")
os.makedirs(OUT_DIR, exist_ok=True)


def wait_for_server(page, timeout_sec: int = 25):
    start = time.time()
    while time.time() - start < timeout_sec:
        try:
            page.goto(f"{BASE_URL}/", timeout=3000)
            if page.url.startswith(BASE_URL):
                return True
        except Exception:
            time.sleep(0.5)
    return False


def upsert_user(page):
    page.goto(f"{BASE_URL}/register")
    try:
        page.fill('input[name="username"]', USERNAME)
        page.fill('input[name="password"]', PASSWORD)
        page.click('button[type="submit"]')
        page.wait_for_load_state("networkidle")
        if page.url.endswith("/register"):
            raise RuntimeError("register failed (likely exists)")
    except Exception:
        page.goto(f"{BASE_URL}/login")
        page.fill('input[name="username"]', USERNAME)
        page.fill('input[name="password"]', PASSWORD)
        page.click('button[type="submit"]')
        page.wait_for_load_state("networkidle")


def ensure_characters_and_party(page):
    page.goto(f"{BASE_URL}/dashboard")
    page.wait_for_load_state("networkidle")
    cards = page.locator(".character-card")
    if cards.count() == 0:
        page.request.post(f"{BASE_URL}/autofill_characters")
        page.goto(f"{BASE_URL}/dashboard")
        page.wait_for_load_state("networkidle")
    ids = page.evaluate(
        """() => Array.from(document.querySelectorAll('input.party-select')).slice(0,4).map(el => el.getAttribute('data-id')).filter(Boolean)"""
    )
    if ids:
        payload = [("form", "start_adventure")] + [("party_ids", i) for i in ids]
        data = urlencode(payload)
        page.request.post(
            f"{BASE_URL}/dashboard",
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    return ids


def shot(page, name, selector=None, full_page=True):
    path = os.path.join(OUT_DIR, f"{name}.png")
    if selector:
        page.locator(selector).screenshot(path=path)
    else:
        page.screenshot(path=path, full_page=full_page)
    print(path)


def setup_combat_with_skill(username, char_id):
    """Direct DB setup: grant a talent point, unlock one active skill for
    char_id, then start a deterministic combat session. Runs against
    whatever DATABASE_URL is currently exported -- must match the
    running dev server's DB so the browser sees this state immediately.
    """
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from app import create_app, db
    from app.models.skill import CharacterSkill, CharacterTalentPoints, Skill
    from app.services import combat_service, spawn_service

    app = create_app()
    with app.app_context():
        skill = Skill.query.filter_by(skill_type="active").first()
        if skill is None:
            print("[warn] no active skill seeded -- run `python run.py seed-skills` first")
            return None
        tp = CharacterTalentPoints.query.filter_by(character_id=char_id).first()
        if tp is None:
            tp = CharacterTalentPoints(character_id=char_id, total_earned=1, total_spent=0, available=1)
            db.session.add(tp)
        existing = CharacterSkill.query.filter_by(character_id=char_id, skill_id=skill.id).first()
        if existing is None:
            db.session.add(CharacterSkill(character_id=char_id, skill_id=skill.id))
        db.session.commit()

        from app.models.models import User

        user = User.query.filter_by(username=username).first()
        monster = spawn_service.choose_monster(level=1)
        session = combat_service.start_session(user.id, monster)
        db.session.commit()
        return session.id


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        page = context.new_page()

        if not wait_for_server(page):
            print(f"Server not reachable at {BASE_URL} -- run `./manage.sh restart` against the dev DB first.")
            browser.close()
            return

        upsert_user(page)
        ids = ensure_characters_and_party(page)

        # 1: Dashboard overview
        page.goto(f"{BASE_URL}/dashboard")
        page.wait_for_load_state("networkidle")
        shot(page, "dashboard-overview")

        # 2: Skill tree modal
        if ids:
            try:
                page.locator(f'.btn-skill-panel[data-char-id="{ids[0]}"]').click()
                page.wait_for_timeout(400)
                shot(page, "skill-tree-modal", selector="#skillTreeCanvas")
            except Exception as e:
                print(f"[warn] skill tree screenshot failed: {e}")

        # 3: Hoard modal
        try:
            page.goto(f"{BASE_URL}/dashboard")
            page.wait_for_load_state("networkidle")
            page.locator(".btn-hoard-open").click()
            page.wait_for_timeout(400)
            shot(page, "hoard-modal", full_page=False)
        except Exception as e:
            print(f"[warn] hoard screenshot failed: {e}")

        # 4: Extraction modal (requires an active dungeon instance, which
        # ensure_characters_and_party's start_adventure call established)
        try:
            page.goto(f"{BASE_URL}/adventure")
            page.wait_for_load_state("networkidle")
            page.locator("#btn-hearth").click()
            page.wait_for_timeout(600)
            shot(page, "extraction-modal", selector="#extractionModal .modal-content")
        except Exception as e:
            print(f"[warn] extraction screenshot failed: {e}")

        # 5: Combat action panel, with an unlocked skill button visible
        if ids:
            combat_id = setup_combat_with_skill(USERNAME, int(ids[0]))
            if combat_id:
                try:
                    page.goto(f"{BASE_URL}/combat/{combat_id}")
                    page.wait_for_load_state("networkidle")
                    page.wait_for_timeout(600)
                    shot(page, "combat-action-panel")
                except Exception as e:
                    print(f"[warn] combat screenshot failed: {e}")

        context.close()
        browser.close()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the script**

```bash
export DATABASE_URL=postgresql://adventure:changeme@localhost:5433/adventure
.venv/bin/python scripts/screenshot_help.py
```

Expected: prints up to 5 file paths under `app/static/img/help/`, one per
successful capture. Any `[warn] ... screenshot failed` lines mean that
particular screen's screenshot didn't get captured — note in your report
exactly which ones, and that section of `help.html` ships with prose only
for now (do not remove the `<img>` tag from the template; a missing file
just shows a broken-image icon, which is acceptable per the spec's
"ship with prose only and a one-line note" guidance, and a future
re-run of this script fills it in).

- [ ] **Step 5: Verify the captured files**

```bash
ls -la app/static/img/help/
```
Expected: up to 5 `.png` files, each comfortably over 50KB (a blank/error
page screenshot is typically only a few KB; this app's dark Cold Steel
theme with real UI chrome should be well above that). If any file is
suspiciously small, open it (e.g. with the Read tool, which can render
images) and confirm it shows real UI, not a login redirect or error page.

- [ ] **Step 6: Commit**

```bash
git add scripts/screenshot_help.py requirements-dev.txt app/static/img/help/
git commit -m "feat(help): capture real screenshots for the help page"
```

---

## Post-implementation

Update `docs/superpowers/TODO.md`: mark the "No 'Support' destination
exists anywhere in the app" entry (currently unchecked) as done,
summarizing the new `/help` route and noting which of the five
screenshots (if any) failed to capture and still need a follow-up run of
`scripts/screenshot_help.py`.
