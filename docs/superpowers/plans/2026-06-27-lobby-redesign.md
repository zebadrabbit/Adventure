# Lobby Redesign — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the stacked-row dashboard with a 7-tab Dark & Darker–style lobby: PARTY · BARRACKS · RECRUIT · ⚔ DUNGEON ⚔ · MERCHANTS · HOARD · ACHIEVEMENTS.

**Architecture:** The dashboard page becomes a full-width tabbed lobby. Flask serves a single `/dashboard` GET that passes `characters` and `party_chars` to the template; tab panes are pure HTML rendered server-side. Four new JSON endpoints manage party composition and recruit generation. All existing systems (trading, hoard, achievements, party modal) remain unchanged — they're just invoked from new tab panes.

**Tech Stack:** Flask/Jinja2, Bootstrap tabs (`data-bs-toggle="tab"`), vanilla JS (no new deps), existing `tactical-panel` CSS framework.

## Global Constraints

- No new Python or JS dependencies.
- Keep existing tactical dark theme — no color changes.
- Existing routes (`/dashboard` POST, `/autofill_characters`, `/delete_character/<id>`, `/api/dungeon/seed`) unchanged.
- All existing modals (party modal, skill modal, achievement modal, hoard modal) and their JS files are **not modified**.
- Party limit: 1–4 characters. Barracks limit: 15 characters. Recruit points: 2 per candidate.
- Dungeon tab still POSTs `form=start_adventure` with `party_ids[]` — no change to dungeon entry logic.
- Tab bar tab IDs: `lobby-party`, `lobby-barracks`, `lobby-recruit`, `lobby-dungeon`, `lobby-merchants`, `lobby-hoard`, `lobby-achievements`.
- New API routes use prefix `/api/party/` and `/api/recruit/`.
- Existing `dashboard.js` XP/HP/MP bar rendering (`data-bar-pct`, `data-xp-pct`) must continue working.

---

## File Map

| File | Change |
|------|--------|
| `app/routes/dashboard_helpers.py` | Add `generate_candidate()` pure function; add `party_chars` to `render_dashboard()` context |
| `app/routes/dashboard.py` | Add 4 new routes: `/api/recruit/candidates`, `/api/recruit/hire`, `/api/party/add`, `/api/party/remove/<id>` |
| `app/templates/dashboard.html` | Full restructure: 7-tab nav + tab panes (replaces stacked layout) |
| `app/static/css/dashboard.css` | Add lobby tab styles, party slot styles, barracks card styles, candidate card styles, dungeon overview styles |
| `app/static/js/dashboard-lobby.js` | New file: tab persistence, party slot interactions, barracks sort/select, recruit fetch/tweak/hire |
| `app/static/js/dashboard.js` | Remove old party checkbox logic (lines ~19–115); keep config fetch + bar rendering |
| `tests/test_recruit_party_api.py` | New test file for the 4 new API routes |

---

## Task 1: Backend — recruit generation + party session APIs

**Files:**
- Modify: `app/routes/dashboard_helpers.py`
- Modify: `app/routes/dashboard.py`
- Create: `tests/test_recruit_party_api.py`

**Interfaces:**
- Produces: `generate_candidate(current_user_id: int, cls: str | None = None) -> dict` in `dashboard_helpers`
- Produces: `GET /api/recruit/candidates` → `[{name, cls, stats, gear_slugs}, ...]`
- Produces: `POST /api/recruit/hire` body `{name, cls, stats, gear_slugs, stat_tweaks}` → `{id, name, cls}`
- Produces: `POST /api/party/add` body `{char_ids: [int]}` → `{party: [...]}`
- Produces: `POST /api/party/remove/<int:char_id>` → `{party: [...]}`
- Produces: `party_chars` template variable (list of Character objects, ordered by party slot)

- [ ] **Step 1: Write failing tests**

Create `tests/test_recruit_party_api.py`:

```python
import json
import pytest
from werkzeug.security import generate_password_hash
from app import db
from app.models.models import Character, User


@pytest.fixture()
def lobby_client(client, test_app):
    with test_app.app_context():
        u = User.query.filter_by(username="lobby_test").first()
        if not u:
            u = User(username="lobby_test", password=generate_password_hash("pw123456"))
            db.session.add(u)
            db.session.commit()
        Character.query.filter_by(user_id=u.id).delete()
        db.session.commit()
    client.post("/login", data={"username": "lobby_test", "password": "pw123456"})
    return client


def _make_char(test_app, user_id, name="TestChar", cls="fighter"):
    with test_app.app_context():
        import json
        from app.routes.main import BASE_STATS, STARTER_ITEMS
        stats = dict(BASE_STATS.get(cls, BASE_STATS["fighter"]))
        stats["hp"] = 55
        stats["mana"] = 20
        ch = Character(
            user_id=user_id,
            name=name,
            stats=json.dumps({**stats, "class": cls}),
            gear=json.dumps({}),
            items=json.dumps([]),
            xp=0, level=1,
        )
        db.session.add(ch)
        db.session.commit()
        return ch.id


def _get_user_id(test_app):
    with test_app.app_context():
        return User.query.filter_by(username="lobby_test").first().id


def test_candidates_returns_four(lobby_client):
    r = lobby_client.get("/api/recruit/candidates")
    assert r.status_code == 200
    data = r.get_json()
    assert isinstance(data, list)
    assert len(data) == 4
    for c in data:
        assert "name" in c and "cls" in c and "stats" in c and "gear_slugs" in c


def test_candidate_stats_include_hp_mana(lobby_client):
    r = lobby_client.get("/api/recruit/candidates")
    candidates = r.get_json()
    for c in candidates:
        assert "hp" in c["stats"]
        assert "mana" in c["stats"]


def test_hire_saves_character(lobby_client, test_app):
    uid = _get_user_id(test_app)
    r = lobby_client.get("/api/recruit/candidates")
    candidate = r.get_json()[0]
    resp = lobby_client.post(
        "/api/recruit/hire",
        json={
            "name": candidate["name"],
            "cls": candidate["cls"],
            "stats": candidate["stats"],
            "gear_slugs": candidate["gear_slugs"],
            "stat_tweaks": {},
        },
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert "id" in data
    with test_app.app_context():
        ch = db.session.get(Character, data["id"])
        assert ch is not None
        assert ch.user_id == uid


def test_hire_with_stat_tweaks(lobby_client, test_app):
    r = lobby_client.get("/api/recruit/candidates")
    candidate = r.get_json()[0]
    base_str = candidate["stats"].get("str", 10)
    resp = lobby_client.post(
        "/api/recruit/hire",
        json={
            "name": candidate["name"],
            "cls": candidate["cls"],
            "stats": candidate["stats"],
            "gear_slugs": candidate["gear_slugs"],
            "stat_tweaks": {"str": 2},
        },
    )
    assert resp.status_code == 200
    data = resp.get_json()
    with test_app.app_context():
        ch = db.session.get(Character, data["id"])
        saved_stats = json.loads(ch.stats)
        assert saved_stats["str"] == base_str + 2


def test_hire_rejects_overspend(lobby_client, test_app):
    r = lobby_client.get("/api/recruit/candidates")
    candidate = r.get_json()[0]
    resp = lobby_client.post(
        "/api/recruit/hire",
        json={
            "name": candidate["name"],
            "cls": candidate["cls"],
            "stats": candidate["stats"],
            "gear_slugs": candidate["gear_slugs"],
            "stat_tweaks": {"str": 3},
        },
    )
    assert resp.status_code == 400


def test_hire_rejects_full_barracks(lobby_client, test_app):
    uid = _get_user_id(test_app)
    for i in range(15):
        _make_char(test_app, uid, name=f"Char{i}")
    r = lobby_client.get("/api/recruit/candidates")
    candidate = r.get_json()[0]
    resp = lobby_client.post(
        "/api/recruit/hire",
        json={
            "name": candidate["name"],
            "cls": candidate["cls"],
            "stats": candidate["stats"],
            "gear_slugs": candidate["gear_slugs"],
            "stat_tweaks": {},
        },
    )
    assert resp.status_code == 400


def test_party_add_updates_session(lobby_client, test_app):
    uid = _get_user_id(test_app)
    cid = _make_char(test_app, uid, name="Slot1")
    resp = lobby_client.post("/api/party/add", json={"char_ids": [cid]})
    assert resp.status_code == 200
    data = resp.get_json()
    assert any(p["id"] == cid for p in data["party"])


def test_party_remove_updates_session(lobby_client, test_app):
    uid = _get_user_id(test_app)
    cid = _make_char(test_app, uid, name="ToRemove")
    lobby_client.post("/api/party/add", json={"char_ids": [cid]})
    resp = lobby_client.post(f"/api/party/remove/{cid}")
    assert resp.status_code == 200
    data = resp.get_json()
    assert not any(p["id"] == cid for p in data["party"])


def test_party_add_respects_four_slot_limit(lobby_client, test_app):
    uid = _get_user_id(test_app)
    ids = [_make_char(test_app, uid, name=f"P{i}") for i in range(5)]
    resp = lobby_client.post("/api/party/add", json={"char_ids": ids})
    assert resp.status_code == 200
    assert len(resp.get_json()["party"]) <= 4
```

- [ ] **Step 2: Run tests to verify they fail**

```
cd /home/winter/work/Adventure
pytest tests/test_recruit_party_api.py -v 2>&1 | head -40
```

Expected: ImportError or 404s (routes don't exist yet).

- [ ] **Step 3: Add `generate_candidate()` to `dashboard_helpers.py`**

Add after line 358 (end of `handle_autofill`):

```python
def generate_candidate(current_user_id: int, cls: str | None = None) -> dict:
    """Return an unsaved level-1 character candidate dict."""
    import random as _random
    from app.routes.main import BASE_STATS, NAME_POOLS, STARTER_ITEMS
    from app.services.auto_equip import auto_equip_for

    classes = list(BASE_STATS.keys())
    if cls is None:
        cls = _random.choice(classes)

    pool = NAME_POOLS.get(cls, [])
    base_name = _random.choice(pool) if pool else cls.capitalize()
    name = f"{base_name}{_random.randint(100, 999)}"

    stats = dict(BASE_STATS.get(cls, BASE_STATS["fighter"]))
    stats["hp"] = 50 + int(stats.get("con", 10)) * 2 + 5
    stats["mana"] = 20 + int(stats.get("int", 10)) * 2
    coins = {"gold": 5, "silver": 20, "copper": 50}

    raw_items = STARTER_ITEMS.get(cls, STARTER_ITEMS["fighter"])
    expanded: list[str] = []
    if isinstance(raw_items, list):
        for ent in raw_items:
            if isinstance(ent, str):
                expanded.append(ent)
            elif isinstance(ent, dict):
                slug = ent.get("slug") or ent.get("name") or ent.get("id")
                if slug:
                    qty = max(1, int(ent.get("qty", 1)))
                    expanded.extend([slug] * qty)

    gear_map = auto_equip_for(cls, expanded)
    return {
        "name": name,
        "cls": cls,
        "stats": {**stats, **coins},
        "gear_slugs": expanded,
        "gear_map": gear_map,
    }
```

- [ ] **Step 4: Add `party_chars` to `render_dashboard()`**

In `dashboard_helpers.py`, modify `render_dashboard()` (around line 225) to compute and pass `party_chars`:

```python
def render_dashboard():
    """Render the dashboard template with serialized characters and metadata."""
    uid = _stable_current_user_id()
    if uid is None:
        from flask_login import logout_user
        logout_user()
        return redirect(url_for("auth.login"))
    char_list = serialize_character_list(uid)
    try:
        user_obj = db.session.get(User, current_user.id)
        user_email = getattr(user_obj, "email", None)
    except Exception:  # pragma: no cover
        user_email = None
    dungeon_seed = session.get("dungeon_seed", "")
    try:
        clock = GameClock.get()
    except Exception:  # pragma: no cover
        clock = None
    # Build ordered party chars list for the Party and Dungeon tab slots
    party_ids_ordered = session.get("last_party_ids") or [
        p["id"] for p in session.get("party", [])
    ]
    chars_by_id = {c["id"]: c for c in char_list}
    party_chars = [chars_by_id[pid] for pid in party_ids_ordered if pid in chars_by_id]
    return render_template(
        "dashboard.html",
        characters=char_list,
        party_chars=party_chars,
        user_email=user_email,
        dungeon_seed=dungeon_seed,
        game_clock=clock,
    )
```

- [ ] **Step 5: Add 4 new routes to `dashboard.py`**

Add after the `autofill_characters` route (after line 329):

```python
@bp_dashboard.route("/api/recruit/candidates")
@login_required
def recruit_candidates():
    from app.routes.dashboard_helpers import generate_candidate
    uid = int(current_user.get_id())
    candidates = [generate_candidate(uid) for _ in range(4)]
    return jsonify(candidates)


@bp_dashboard.route("/api/recruit/hire", methods=["POST"])
@login_required
def recruit_hire():
    uid = int(current_user.get_id())
    count = Character.query.filter_by(user_id=uid).count()
    if count >= 15:
        return jsonify({"error": "Barracks full (15/15)"}), 400

    data = request.get_json(force=True) or {}
    tweaks = data.get("stat_tweaks") or {}
    try:
        tweak_total = sum(int(v) for v in tweaks.values())
        tweak_negative = any(int(v) < 0 for v in tweaks.values())
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid stat tweaks"}), 400
    if tweak_total > 2 or tweak_negative:
        return jsonify({"error": "Invalid stat tweaks"}), 400

    stats = dict(data.get("stats") or {})
    for stat, delta in tweaks.items():
        if stat in stats:
            stats[stat] = int(stats[stat]) + int(delta)

    cls = data.get("cls") or "fighter"
    gear_slugs = data.get("gear_slugs") or []

    from app.services.auto_equip import auto_equip_for
    gear_map = auto_equip_for(cls, gear_slugs)

    ch = Character(
        user_id=uid,
        name=str(data.get("name") or "Adventurer")[:50],
        stats=json.dumps({**stats, "class": cls}),
        gear=json.dumps(gear_map),
        items=json.dumps(gear_slugs),
        xp=0,
        level=1,
    )
    db.session.add(ch)
    db.session.commit()
    return jsonify({"id": ch.id, "name": ch.name, "cls": cls})


@bp_dashboard.route("/api/party/add", methods=["POST"])
@login_required
def party_add():
    uid = int(current_user.get_id())
    data = request.get_json(force=True) or {}
    try:
        incoming_ids = [int(i) for i in (data.get("char_ids") or [])]
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid char_ids"}), 400

    current_party = session.get("party") or []
    current_ids = {p["id"] for p in current_party}
    open_slots = 4 - len(current_party)

    to_add = [i for i in incoming_ids if i not in current_ids][:open_slots]
    if to_add:
        chars = Character.query.filter(
            Character.id.in_(to_add), Character.user_id == uid
        ).all()
        new_entries = build_party_payload(chars)
        new_party = current_party + new_entries
        session["party"] = new_party
        session["last_party_ids"] = [p["id"] for p in new_party]

    return jsonify({"party": session.get("party") or []})


@bp_dashboard.route("/api/party/remove/<int:char_id>", methods=["POST"])
@login_required
def party_remove(char_id):
    party = [p for p in (session.get("party") or []) if p["id"] != char_id]
    session["party"] = party
    session["last_party_ids"] = [p["id"] for p in party]
    return jsonify({"party": party})
```

- [ ] **Step 6: Run the tests**

```
pytest tests/test_recruit_party_api.py -v
```

Expected: all 9 tests pass.

- [ ] **Step 7: Run the full suite to check for regressions**

```
pytest -x -q 2>&1 | tail -20
```

Expected: same pass/fail counts as before (no new failures).

- [ ] **Step 8: Commit**

```bash
git add app/routes/dashboard_helpers.py app/routes/dashboard.py tests/test_recruit_party_api.py
git commit -m "feat(lobby): add recruit generation, hire, and party session API routes"
```

---

## Task 2: CSS + Dashboard template restructure

**Files:**
- Modify: `app/static/css/dashboard.css`
- Modify: `app/templates/dashboard.html`

**Interfaces:**
- Consumes: `party_chars` template var from Task 1
- Consumes: `characters`, `dungeon_seed`, `game_clock` (existing)
- Consumes: all existing modals/JS — they must remain in `{% block scripts %}`

- [ ] **Step 1: Add lobby CSS to `dashboard.css`**

Append to end of `app/static/css/dashboard.css`:

```css
/* ===== LOBBY TAB NAV ===================================================== */
.lobby-nav {
    border-bottom: 2px solid color-mix(in srgb, var(--adv-primary, #f0a500) 25%, transparent);
    gap: 0;
    flex-wrap: nowrap;
    overflow-x: auto;
}

.lobby-nav .nav-link {
    background: transparent;
    border: none;
    border-bottom: 2px solid transparent;
    color: rgba(255, 255, 255, 0.55);
    padding: 0.85rem 1.25rem;
    font-size: 0.78rem;
    letter-spacing: 0.1em;
    font-weight: 700;
    text-transform: uppercase;
    margin-bottom: -2px;
    white-space: nowrap;
    transition: color 0.15s, border-color 0.15s;
}

.lobby-nav .nav-link:hover {
    color: rgba(255, 255, 255, 0.85);
    background: color-mix(in srgb, var(--adv-primary, #f0a500) 8%, transparent);
}

.lobby-nav .nav-link.active {
    color: #fff;
    border-bottom-color: var(--adv-primary, #f0a500);
    background: color-mix(in srgb, var(--adv-primary, #f0a500) 10%, transparent);
}

.lobby-nav .lobby-dungeon-tab {
    color: color-mix(in srgb, var(--adv-primary, #f0a500) 90%, white);
    font-size: 0.85rem;
    letter-spacing: 0.12em;
}

.lobby-nav .lobby-dungeon-tab.active {
    color: var(--adv-primary, #f0a500);
    border-bottom-color: var(--adv-primary, #f0a500);
    text-shadow: 0 0 8px color-mix(in srgb, var(--adv-primary, #f0a500) 60%, transparent);
}

/* ===== PARTY SLOTS ======================================================= */
.party-slot-empty {
    min-height: 120px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    border: 2px dashed rgba(255, 255, 255, 0.15);
    border-radius: 12px;
    cursor: pointer;
    transition: border-color 0.2s, background 0.2s;
    gap: 0.5rem;
    padding: 1.5rem 1rem;
}

.party-slot-empty:hover {
    border-color: color-mix(in srgb, var(--adv-primary, #f0a500) 50%, transparent);
    background: color-mix(in srgb, var(--adv-primary, #f0a500) 5%, transparent);
}

.party-slot-empty .slot-plus {
    font-size: 2rem;
    line-height: 1;
    opacity: 0.35;
}

.party-slot-empty .slot-label {
    font-size: 0.7rem;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    opacity: 0.4;
}

/* ===== BARRACKS CARDS ==================================================== */
.barracks-card {
    cursor: pointer;
    user-select: none;
    transition: border-color 0.15s, background 0.15s;
    border-radius: 10px;
    padding: 0.75rem 1rem;
}

.barracks-card.selected {
    border-color: var(--adv-primary, #f0a500) !important;
    background: color-mix(in srgb, var(--adv-primary, #f0a500) 12%, transparent) !important;
}

.barracks-card.in-party {
    opacity: 0.55;
    cursor: default;
}

.barracks-card .barracks-card-name {
    font-weight: 700;
    font-size: 0.9rem;
}

.barracks-card .barracks-card-meta {
    font-size: 0.75rem;
    opacity: 0.7;
    margin-bottom: 0.4rem;
}

/* ===== CANDIDATE (RECRUIT) CARDS ========================================= */
.candidate-card {
    border-radius: 12px;
}

.candidate-stats-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 0.2rem 0.5rem;
    font-size: 0.78rem;
    margin: 0.5rem 0;
}

.candidate-stat-row {
    display: flex;
    align-items: center;
    gap: 0.25rem;
}

.candidate-stat-row .stat-label {
    font-weight: 700;
    font-size: 0.7rem;
    opacity: 0.7;
    min-width: 2ch;
}

.candidate-stat-row .stat-val {
    min-width: 2ch;
    text-align: right;
}

.stat-tweak-btn {
    width: 20px;
    height: 20px;
    padding: 0;
    font-size: 0.7rem;
    line-height: 1;
    border-radius: 3px;
}

.stat-points-counter {
    font-size: 0.75rem;
    font-weight: 700;
    color: var(--adv-primary, #f0a500);
    letter-spacing: 0.05em;
}

/* ===== DUNGEON TAB OVERVIEW ============================================== */
.dungeon-overview-slots {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 1rem;
}

.dungeon-slot-mini {
    border: 1px dashed rgba(255, 255, 255, 0.2);
    border-radius: 8px;
    padding: 0.75rem;
    min-height: 90px;
    display: flex;
    flex-direction: column;
    justify-content: center;
}

.dungeon-slot-mini.filled {
    border-color: rgba(255, 255, 255, 0.35);
    background: rgba(255, 255, 255, 0.04);
}

.dungeon-slot-mini .slot-name {
    font-weight: 700;
    font-size: 0.88rem;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.dungeon-slot-mini .slot-meta {
    font-size: 0.72rem;
    opacity: 0.65;
    margin-bottom: 0.35rem;
}

.quick-checks {
    display: flex;
    gap: 1.25rem;
    flex-wrap: wrap;
    margin-bottom: 1.5rem;
}

.check-item {
    font-size: 0.82rem;
    font-weight: 600;
    letter-spacing: 0.04em;
}

.check-item.ok   { color: #4ade80; }
.check-item.warn { color: #f59e0b; }
.check-item.fail { color: #f87171; }

/* ===== LOBBY TAB CONTENT PANE ============================================ */
.lobby-tab-pane {
    padding: 1.5rem 0;
    min-height: 400px;
}

/* ===== PARTY COMPOSITION SUMMARY ========================================= */
.party-composition {
    font-size: 0.78rem;
    letter-spacing: 0.08em;
    opacity: 0.65;
    text-transform: uppercase;
}

/* ===== SORT BUTTON GROUP ================================================= */
.sort-btn-group .sort-btn {
    font-size: 0.72rem;
    letter-spacing: 0.08em;
    padding: 0.3rem 0.75rem;
}

.sort-btn-group .sort-btn.active {
    background: color-mix(in srgb, var(--adv-primary, #f0a500) 25%, transparent);
    border-color: color-mix(in srgb, var(--adv-primary, #f0a500) 60%, transparent);
    color: var(--adv-primary, #f0a500);
}
```

- [ ] **Step 2: Run existing tests to confirm CSS change has no impact**

```
pytest tests/test_dashboard_routes.py tests/test_lobby_extended.py -q
```

Expected: same pass/fail as before.

- [ ] **Step 3: Write the new `dashboard.html`**

Replace the entire `app/templates/dashboard.html` with:

```html
{% extends 'dashboard_base.html' %}
{% from 'macros/svg_icon.html' import svg_icon %}
{% from 'macros/seed_widget.html' import seed_widget %}

{% block head %}{{ super() }}{% endblock %}

{% block dashboard_content %}

<!-- Tactical HUD - Top Right -->
<div class="tactical-hud">
    <div class="hud-status">
        <span class="label">[ GAME CLOCK ]</span>
        <span class="value" id="dashboard-time-tick">{{ game_clock.tick if game_clock else 0 }}</span>
    </div>
</div>

<div class="mission-briefing pb-0">
    <!-- Alert Banner -->
    {% if validation_error %}
    <div class="alert-tactical mb-3">
        <div class="d-flex align-items-start gap-3">
            <i class="bi bi-exclamation-triangle-fill icon-warn-lg"></i>
            <div class="flex-grow-1">
                <strong>[ PARTY FORMATION ERROR ]</strong>
                <div class="mt-2">{{ validation_error }}</div>
                <div class="small mt-1 opacity-85">Party size: 1–4 adventurers required.</div>
            </div>
        </div>
    </div>
    {% endif %}

    <!-- Lobby Tab Nav -->
    <ul class="nav lobby-nav" id="lobbyTabNav" role="tablist">
        <li class="nav-item" role="presentation">
            <button class="nav-link active" id="tab-party" data-bs-toggle="tab"
                data-bs-target="#lobby-party" type="button" role="tab"
                aria-controls="lobby-party" aria-selected="true">PARTY</button>
        </li>
        <li class="nav-item" role="presentation">
            <button class="nav-link" id="tab-barracks" data-bs-toggle="tab"
                data-bs-target="#lobby-barracks" type="button" role="tab"
                aria-controls="lobby-barracks" aria-selected="false">BARRACKS</button>
        </li>
        <li class="nav-item" role="presentation">
            <button class="nav-link" id="tab-recruit" data-bs-toggle="tab"
                data-bs-target="#lobby-recruit" type="button" role="tab"
                aria-controls="lobby-recruit" aria-selected="false">RECRUIT</button>
        </li>
        <li class="nav-item" role="presentation">
            <button class="nav-link lobby-dungeon-tab" id="tab-dungeon" data-bs-toggle="tab"
                data-bs-target="#lobby-dungeon" type="button" role="tab"
                aria-controls="lobby-dungeon" aria-selected="false">⚔ DUNGEON ⚔</button>
        </li>
        <li class="nav-item" role="presentation">
            <button class="nav-link" id="tab-merchants" data-bs-toggle="tab"
                data-bs-target="#lobby-merchants" type="button" role="tab"
                aria-controls="lobby-merchants" aria-selected="false">MERCHANTS</button>
        </li>
        <li class="nav-item" role="presentation">
            <button class="nav-link" id="tab-hoard" data-bs-toggle="tab"
                data-bs-target="#lobby-hoard" type="button" role="tab"
                aria-controls="lobby-hoard" aria-selected="false">HOARD</button>
        </li>
        <li class="nav-item" role="presentation">
            <button class="nav-link" id="tab-achievements" data-bs-toggle="tab"
                data-bs-target="#lobby-achievements" type="button" role="tab"
                aria-controls="lobby-achievements" aria-selected="false">ACHIEVEMENTS</button>
        </li>
    </ul>
</div>

<div class="mission-briefing tab-content pt-0" id="lobbyTabContent">

    <!-- ══════════════════════════════════════════════════════════════════
         PARTY TAB
    ══════════════════════════════════════════════════════════════════════ -->
    <div class="tab-pane fade show active lobby-tab-pane" id="lobby-party" role="tabpanel"
        aria-labelledby="tab-party">

        <!-- 4 party slots -->
        <div class="row g-4 align-items-start mb-4">
            {% for slot in range(4) %}
            <div class="col-12 col-sm-6 col-xl-3">
                {% if slot < party_chars|length %}
                {% set c = party_chars[slot] %}
                {% set hp_pct = (c.stats.hp / c.hp_max * 100)|int if c.hp_max > 0 else 0 %}
                {% set hp_pct = [0, [100, hp_pct]|min]|max %}
                {% set mp_pct = (c.stats.mana / c.mana_max * 100)|int if c.mana_max > 0 else 0 %}
                {% set mp_pct = [0, [100, mp_pct]|min]|max %}
                <div class="operative-card selected" data-id="{{ c.id }}">
                    <div class="operative-summary">
                        <div class="operative-header">
                            <div class="operative-name">
                                <span class="icon-28">
                                    {% set class_lower = c.class_name.lower() %}
                                    {% if class_lower == 'fighter' %}{{ svg_icon('swords-power', 24) }}
                                    {% elif class_lower == 'mage' %}{{ svg_icon('fire-silhouette', 24) }}
                                    {% elif class_lower == 'rogue' %}{{ svg_icon('rogue', 24) }}
                                    {% elif class_lower == 'druid' %}{{ svg_icon('heavy-thorny-triskelion', 24) }}
                                    {% elif class_lower == 'cleric' %}{{ svg_icon('aura', 24) }}
                                    {% elif class_lower == 'ranger' %}{{ svg_icon('bowman', 24) }}
                                    {% else %}<i class="bi bi-person-fill"></i>{% endif %}
                                </span>
                                <span>{{ c.name }}</span>
                            </div>
                            <div class="operative-meta">
                                <span class="class-badge {{ c.class_name|lower }}-badge">{{ c.class_name }}</span>
                                <span class="badge">LV{{ c.level }}</span>
                            </div>
                        </div>
                        <div class="hp-mp-bars">
                            <div class="resource-bar-track">
                                <span class="bar-label">HP {{ c.stats.hp }}/{{ c.hp_max }}</span>
                                <div class="bar-track"><div class="bar-fill hp-fill" data-bar-pct="{{ hp_pct }}"></div></div>
                            </div>
                            <div class="resource-bar-track">
                                <span class="bar-label">MP {{ c.stats.mana }}/{{ c.mana_max }}</span>
                                <div class="bar-track"><div class="bar-fill mp-fill" data-bar-pct="{{ mp_pct }}"></div></div>
                            </div>
                        </div>
                    </div>
                    <div class="operative-detail" hidden>
                        <div class="operative-body">
                            {% set xp_span = c.xp_next - c.xp_current %}
                            {% set xp_pct = ((c.xp - c.xp_current) / xp_span * 100)|int if xp_span > 0 else 100 %}
                            {% set xp_pct = [0, [100, xp_pct]|min]|max %}
                            <div class="xp-bar-anchor" data-char-id="{{ c.id }}">
                                <div class="d-flex justify-content-between">
                                    <span class="xp-label-dim">EXPERIENCE:</span>
                                    <span><span class="xp-label-accent">{{ c.xp }}</span> / <span class="xp-label-dim">{{ c.xp_next }}</span></span>
                                </div>
                                <div class="progress mt-1 xp-progress-track">
                                    <div class="progress-bar xp-fill" data-xp-pct="{{ xp_pct }}"></div>
                                </div>
                            </div>
                            <div class="stat-block">
                                <h6>{{ svg_icon('bar-chart', 16, 'me-1') }}ATTRIBUTES</h6>
                                <div class="stat-grid">
                                    <div><span class="fw-bold">STR</span>{{ c.stats.str }}</div>
                                    <div><span class="fw-bold">DEX</span>{{ c.stats.dex }}</div>
                                    <div><span class="fw-bold">INT</span>{{ c.stats.int }}</div>
                                    <div><span class="fw-bold">WIS</span>{{ c.stats.wis }}</div>
                                    <div><span class="fw-bold">CHA</span>{{ c.stats.cha }}</div>
                                    <div><span class="fw-bold">CON</span>{{ c.stats.con }}</div>
                                    <div><span class="fw-bold">HP</span>{{ c.stats.hp }}</div>
                                    <div><span class="fw-bold">MP</span>{{ c.stats.mana }}</div>
                                </div>
                            </div>
                            <div class="resource-bar">
                                <span class="coin-gold">{{ svg_icon('cash', 18, 'me-1') }}{{ c.coins.gold }}g</span>
                                <span class="coin-silver">{{ svg_icon('two-coins', 18, 'me-1') }}{{ c.coins.silver }}s</span>
                                <span class="coin-copper">{{ svg_icon('token', 18, 'me-1') }}{{ c.coins.copper }}c</span>
                            </div>
                            {% if c.inventory and c.inventory|length > 0 %}
                            <div class="stat-block flex-grow-1-block">
                                <h6>{{ svg_icon('knapsack', 16, 'me-1') }}EQUIPMENT</h6>
                                <div class="inventory-list">
                                    <ul>
                                        {% for it in c.inventory %}
                                        <li>
                                            {% if it.type == 'weapon' %}{{ svg_icon('bloody-sword', 16) }}
                                            {% elif it.type == 'armor' %}{{ svg_icon('shield', 16) }}
                                            {% elif it.type == 'potion' %}{{ svg_icon('potion-ball', 16) }}
                                            {% else %}{{ svg_icon('chest', 16) }}{% endif %}
                                            <span>{{ it.name }}</span>
                                            <span class="item-type-tag">[{{ it.type }}]</span>
                                        </li>
                                        {% endfor %}
                                    </ul>
                                </div>
                            </div>
                            {% endif %}
                        </div>
                        <div class="operative-footer">
                            <button class="tactical-btn-danger btn-party-remove" data-char-id="{{ c.id }}">
                                {{ svg_icon('trash-can', 16, 'me-1') }} REMOVE
                            </button>
                            <div class="btn-group">
                                <button class="tactical-btn-secondary btn-equip-panel btn-icon-compact"
                                    data-char-id="{{ c.id }}" title="Equipment Panel">
                                    {{ svg_icon('anvil', 18) }}
                                </button>
                                <button class="tactical-btn-secondary btn-bag-panel btn-icon-compact"
                                    data-char-id="{{ c.id }}" title="Inventory">
                                    {{ svg_icon('knapsack', 18) }}
                                </button>
                                <button class="tactical-btn-secondary btn-skill-panel btn-icon-compact"
                                    data-char-id="{{ c.id }}" title="Skill Tree">
                                    {{ svg_icon('star-fill', 18) }}
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
                {% else %}
                <div class="party-slot-empty" data-slot="{{ slot }}" id="party-slot-empty-{{ slot }}">
                    <div class="slot-plus">+</div>
                    <div class="slot-label">ADD ADVENTURER</div>
                </div>
                {% endif %}
            </div>
            {% endfor %}
        </div>

        <!-- Party action bar -->
        <div class="d-flex justify-content-between align-items-center flex-wrap gap-2 pt-2"
            style="border-top: 1px solid rgba(255,255,255,0.08);">
            <div class="party-composition">
                {% if party_chars %}
                {{ party_chars|map(attribute='class_name')|join(' · ') }}
                {% if party_chars|length < 4 %}
                {% for _ in range(4 - party_chars|length) %} · —{% endfor %}
                {% endif %}
                {% else %}
                NO PARTY ASSEMBLED
                {% endif %}
            </div>
            <div class="d-flex gap-2">
                <button type="button" id="lobby-autofill-btn" class="tactical-btn-secondary">
                    {{ svg_icon('shuffle', 16, 'me-1') }} AUTO-FILL
                </button>
                <button type="button" id="lobby-go-dungeon-btn" class="deploy-btn"
                    {% if not party_chars %}disabled{% endif %}>
                    ⚔ ENTER DUNGEON →
                </button>
            </div>
        </div>
    </div>

    <!-- ══════════════════════════════════════════════════════════════════
         BARRACKS TAB
    ══════════════════════════════════════════════════════════════════════ -->
    <div class="tab-pane fade lobby-tab-pane" id="lobby-barracks" role="tabpanel"
        aria-labelledby="tab-barracks">

        <div class="d-flex justify-content-between align-items-center flex-wrap gap-2 mb-3">
            <span class="small text-muted">{{ characters|length }} / 15 ADVENTURERS</span>
            <div class="d-flex gap-2 sort-btn-group flex-wrap">
                <button class="tactical-btn-secondary sort-btn active" data-sort="level">LEVEL</button>
                <button class="tactical-btn-secondary sort-btn" data-sort="class">CLASS</button>
                <button class="tactical-btn-secondary sort-btn" data-sort="name">NAME</button>
                {% if characters|length < 15 %}
                <button class="tactical-btn-secondary" id="barracks-recruit-btn">RECRUIT MORE →</button>
                {% endif %}
            </div>
        </div>

        <div class="row g-3" id="barracks-grid">
            {% set party_id_set = party_chars|map(attribute='id')|list %}
            {% for c in characters %}
            {% set in_party = c.id in party_id_set %}
            {% set hp_pct = (c.stats.hp / c.hp_max * 100)|int if c.hp_max > 0 else 0 %}
            {% set hp_pct = [0, [100, hp_pct]|min]|max %}
            <div class="col-12 col-sm-6 col-lg-4 col-xl-3">
                <div class="tactical-panel barracks-card {% if in_party %}in-party{% endif %}"
                    data-id="{{ c.id }}"
                    data-class="{{ c.class_name }}"
                    data-level="{{ c.level }}"
                    data-name="{{ c.name }}"
                    data-in-party="{{ 'true' if in_party else 'false' }}">
                    <div class="barracks-card-name">
                        <span class="class-badge {{ c.class_name|lower }}-badge me-1">{{ c.class_name }}</span>
                        {{ c.name }}
                    </div>
                    <div class="barracks-card-meta">
                        LV{{ c.level }}
                        {% if in_party %}
                        · <span class="badge" style="background:color-mix(in srgb, var(--adv-primary) 25%, transparent); font-size:0.65rem;">IN PARTY</span>
                        {% endif %}
                    </div>
                    <div class="resource-bar-track">
                        <span class="bar-label" style="font-size:0.7rem;">HP {{ c.stats.hp }}/{{ c.hp_max }}</span>
                        <div class="bar-track"><div class="bar-fill hp-fill" data-bar-pct="{{ hp_pct }}"></div></div>
                    </div>
                    <div class="d-flex justify-content-between align-items-center mt-2">
                        <form action="{{ url_for('dashboard.delete_character', char_id=c.id) }}" method="post"
                            onsubmit="return confirm('⚠️ DISMISS {{ c.name }}?\n\nThis action is permanent.');">
                            <button class="tactical-btn-danger" style="font-size:0.7rem; padding:3px 8px;">
                                {{ svg_icon('trash-can', 14, 'me-1') }} DISMISS
                            </button>
                        </form>
                    </div>
                </div>
            </div>
            {% else %}
            <div class="col-12">
                <div class="text-center py-5 text-muted">
                    <p>No adventurers yet. <button class="tactical-btn-secondary btn-sm" id="barracks-recruit-empty-btn">RECRUIT YOUR FIRST →</button></p>
                </div>
            </div>
            {% endfor %}
        </div>

        <div class="d-flex justify-content-between align-items-center mt-3 pt-2"
            style="border-top: 1px solid rgba(255,255,255,0.08);">
            <span class="small text-muted">Select adventurers to add to party</span>
            <button class="tactical-btn-secondary" id="barracks-add-party-btn" disabled>
                {{ svg_icon('people-fill', 16, 'me-1') }} ADD TO PARTY
            </button>
        </div>
    </div>

    <!-- ══════════════════════════════════════════════════════════════════
         RECRUIT TAB
    ══════════════════════════════════════════════════════════════════════ -->
    <div class="tab-pane fade lobby-tab-pane" id="lobby-recruit" role="tabpanel"
        aria-labelledby="tab-recruit">

        {% if characters|length >= 15 %}
        <div class="text-center py-5">
            <p class="text-muted">Barracks full ({{ characters|length }}/15).</p>
            <button class="tactical-btn-secondary" data-lobby-switch="lobby-barracks">← VIEW BARRACKS</button>
        </div>
        {% else %}
        <div class="d-flex justify-content-between align-items-center flex-wrap gap-2 mb-3">
            <span class="small text-muted">Choose one adventurer to recruit. Each candidate has 2 free stat points.</span>
            <button class="tactical-btn-secondary" id="recruit-reroll-btn">
                {{ svg_icon('shuffle', 16, 'me-1') }} REROLL ALL
            </button>
        </div>
        <div class="row g-4" id="recruit-candidates-grid">
            <div class="col-12 text-center py-5 text-muted small">
                <span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>
                Loading candidates…
            </div>
        </div>
        {% endif %}
    </div>

    <!-- ══════════════════════════════════════════════════════════════════
         DUNGEON TAB
    ══════════════════════════════════════════════════════════════════════ -->
    <div class="tab-pane fade lobby-tab-pane" id="lobby-dungeon" role="tabpanel"
        aria-labelledby="tab-dungeon">

        <div class="briefing-header mb-4">
            <h2>{{ svg_icon('dungeon-gate', 28, 'me-3 align-text-bottom') }}DUNGEON BRIEFING</h2>
            <div class="subtitle">Gather your party // Equip adventurers // Embark on quest</div>
        </div>

        <!-- Party overview: 4 mini slots -->
        <div class="dungeon-overview-slots mb-4">
            {% for slot in range(4) %}
            <div class="dungeon-slot-mini {% if slot < party_chars|length %}filled{% endif %}">
                {% if slot < party_chars|length %}
                {% set c = party_chars[slot] %}
                {% set hp_pct = (c.stats.hp / c.hp_max * 100)|int if c.hp_max > 0 else 0 %}
                {% set hp_pct = [0, [100, hp_pct]|min]|max %}
                <div class="slot-name">{{ c.name }}</div>
                <div class="slot-meta">{{ c.class_name }} · LV{{ c.level }}</div>
                <div class="bar-track"><div class="bar-fill hp-fill" data-bar-pct="{{ hp_pct }}"></div></div>
                <div style="font-size:0.7rem; opacity:0.65; margin-top:0.2rem;">{{ c.stats.hp }}/{{ c.hp_max }} HP</div>
                {% else %}
                <div class="text-center text-muted small">— EMPTY —</div>
                {% endif %}
            </div>
            {% endfor %}
        </div>

        <!-- Quick checks -->
        {% set dead_count = namespace(n=0) %}{% for pc in party_chars %}{% if pc.stats.hp <= 0 %}{% set dead_count.n = dead_count.n + 1 %}{% endif %}{% endfor %}
        {% set all_alive = dead_count.n == 0 and party_chars|length > 0 %}
        <div class="quick-checks">
            <span class="check-item {% if party_chars|length >= 1 %}ok{% else %}fail{% endif %}">
                {% if party_chars|length >= 1 %}✓{% else %}✗{% endif %}
                Party assembled ({{ party_chars|length }}/4){% if party_chars|length < 4 and party_chars|length >= 1 %} — more slots available{% endif %}
            </span>
            <span class="check-item {% if all_alive %}ok{% elif not party_chars %}fail{% else %}warn{% endif %}">
                {% if all_alive and party_chars %}✓ All members alive
                {% elif not party_chars %}✗ No party members
                {% else %}⚠ One or more members are down{% endif %}
            </span>
        </div>

        <!-- Seed widget -->
        <div class="mb-4">{{ seed_widget(dungeon_seed) }}</div>

        <!-- Entry actions -->
        <div class="d-flex gap-3 align-items-center flex-wrap">
            <form method="POST" id="dungeon-enter-form">
                <input type="hidden" name="form" value="start_adventure">
                {% for p in session.get('party', []) %}
                <input type="hidden" name="party_ids" value="{{ p.id }}">
                {% endfor %}
                <button type="submit" class="deploy-btn"
                    {% if not party_chars or not all_alive %}disabled{% endif %}>
                    {{ svg_icon('dungeon-gate', 24, 'me-2 align-text-bottom') }} ENTER DUNGEON
                </button>
            </form>
            {% if session.get('dungeon_instance_id') and session.get('last_party_ids') %}
            <form method="POST">
                <input type="hidden" name="form" value="continue_adventure">
                <button type="submit" class="tactical-btn-secondary">
                    {{ svg_icon('campfire', 20, 'me-2') }} CONTINUE QUEST
                </button>
            </form>
            {% endif %}
        </div>
    </div>

    <!-- ══════════════════════════════════════════════════════════════════
         MERCHANTS TAB
    ══════════════════════════════════════════════════════════════════════ -->
    <div class="tab-pane fade lobby-tab-pane" id="lobby-merchants" role="tabpanel"
        aria-labelledby="tab-merchants">
        <div class="row g-4">
            <div class="col-12 col-md-4">
                <div class="tactical-panel h-100">
                    <div class="panel-header"><h5><i class="bi bi-basket me-2"></i>General Store</h5></div>
                    <div class="panel-body">
                        <p class="small text-muted">Adventuring supplies, tools, and everyday goods.</p>
                        <button type="button" class="tactical-btn-secondary btn-full-width"
                            onclick="window.tradingSystem && tradingSystem.openMerchant('general-store', {{ characters[0].id if characters else 1 }})">
                            OPEN
                        </button>
                    </div>
                </div>
            </div>
            <div class="col-12 col-md-4">
                <div class="tactical-panel h-100">
                    <div class="panel-header"><h5><i class="bi bi-bag-heart me-2"></i>The Apothecary</h5></div>
                    <div class="panel-body">
                        <p class="small text-muted">Potions, remedies, and alchemical compounds.</p>
                        <button type="button" class="tactical-btn-secondary btn-full-width"
                            onclick="window.tradingSystem && tradingSystem.openMerchant('apothecary', {{ characters[0].id if characters else 1 }})">
                            OPEN
                        </button>
                    </div>
                </div>
            </div>
            <div class="col-12 col-md-4">
                <div class="tactical-panel h-100">
                    <div class="panel-header"><h5><i class="bi bi-shield-fill me-2"></i>Dungeon Outfitter</h5></div>
                    <div class="panel-body">
                        <p class="small text-muted">Weapons, armor, and dungeon equipment.</p>
                        <button type="button" class="tactical-btn-secondary btn-full-width"
                            onclick="window.tradingSystem && tradingSystem.openMerchant('outfitter', {{ characters[0].id if characters else 1 }})">
                            OPEN
                        </button>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- ══════════════════════════════════════════════════════════════════
         HOARD TAB
    ══════════════════════════════════════════════════════════════════════ -->
    <div class="tab-pane fade lobby-tab-pane" id="lobby-hoard" role="tabpanel"
        aria-labelledby="tab-hoard">
        <div class="d-flex flex-column gap-2" style="max-width: 300px;">
            <button type="button" class="tactical-btn-secondary btn-hoard-open">
                <i class="bi bi-bank2 me-2"></i> View Hoard
            </button>
        </div>
    </div>

    <!-- ══════════════════════════════════════════════════════════════════
         ACHIEVEMENTS TAB
    ══════════════════════════════════════════════════════════════════════ -->
    <div class="tab-pane fade lobby-tab-pane" id="lobby-achievements" role="tabpanel"
        aria-labelledby="tab-achievements">
        <div class="d-flex flex-column gap-2" style="max-width: 300px;">
            <button type="button" class="tactical-btn-secondary"
                onclick="window.achievementSystem && achievementSystem.openAchievements({{ characters[0].id if characters else 1 }})">
                <i class="bi bi-trophy-fill me-2"></i> Achievements
            </button>
        </div>
    </div>

</div>

{# Chat widget - fixed at bottom-left, unchanged #}
<div id="lobby-chat-widget" class="mud-chat-widget">
    <div class="mud-chat-tabs-row d-flex align-items-center justify-content-between chat-header">
        <ul class="nav nav-tabs flex-grow-1 mb-0" id="chatTabNav" role="tablist">
            <li class="nav-item" role="presentation">
                <button class="nav-link active" id="tab-general" data-bs-toggle="tab"
                    data-bs-target="#chat-general" type="button" role="tab">TAVERN CHAT</button>
            </li>
        </ul>
        <button id="lobby-chat-toggle-btn" class="btn btn-sm btn-outline-secondary ms-2 btn-square-32"
            title="Toggle Chat">
            <i class="bi bi-chevron-up" id="lobby-chat-chevron"></i>
        </button>
    </div>
    <div class="mud-chat-body d-flex flex-column chat-body-240">
        <div class="tab-content flex-grow-1 d-flex flex-column" id="chatTabContent">
            <div class="tab-pane fade show active d-flex flex-column h-100" id="chat-general" role="tabpanel">
                <div class="chat-messages flex-grow-1" id="lobby-chat-messages-general"></div>
                <form class="chat-form mt-2" id="lobby-chat-form-general" autocomplete="off">
                    <input type="text" id="lobby-chat-input-general" class="form-control"
                        placeholder="Type message…" maxlength="200" required />
                    <button type="submit" id="lobby-chat-send-general" class="btn btn-primary">
                        <i class="bi bi-send"></i>
                    </button>
                </form>
            </div>
        </div>
    </div>
</div>

{% block scripts %}
<script src="{{ asset_url('js/chat-widget.js') }}"></script>
<script src="{{ asset_url('js/dashboard.js') }}"></script>
<script src="{{ asset_url('js/tooltips.js') }}"></script>
<script src="{{ asset_url('js/equipment.js') }}"></script>
<script src="{{ asset_url('js/equipment-enhanced.js') }}"></script>
<script src="{{ asset_url('js/character-progression.js') }}"></script>
<script src="{{ asset_url('js/loot-distribution.js') }}"></script>
<script src="{{ asset_url('js/quest-system.js') }}"></script>
<script src="{{ asset_url('js/trading-system.js') }}"></script>
<script src="{{ asset_url('js/hoard.js') }}"></script>
<script src="{{ asset_url('js/seed-widget.js') }}"></script>
<script src="{{ asset_url('js/dashboard-lobby.js') }}"></script>
<script src="{{ asset_url('js/character.js') }}"></script>
<script src="{{ asset_url('js/dashboard-operative-cards.js') }}"></script>

<!-- Party Management Modal (unchanged) -->
<div id="partyModal" class="party-modal">
    <div class="party-modal-content">
        <div class="party-modal-header">
            <div>
                <h2 class="party-modal-title" id="partyName">Party</h2>
                <div class="party-stats-summary">
                    <div class="party-stat-item"><span class="party-stat-label">Level:</span><span id="partyLevel">1</span></div>
                    <div class="party-stat-item"><span class="party-stat-label">Members:</span><span id="partyMembers">0</span></div>
                    <div class="party-stat-item"><span class="party-stat-label">💰</span><span id="partySharedGold">0</span></div>
                </div>
            </div>
            <button class="party-close-btn" onclick="partySystem.closeModal()">&times;</button>
        </div>
        <div class="party-tabs">
            <button class="party-tab active" data-tab="formation" onclick="partySystem.switchTab('formation')">Formation</button>
            <button class="party-tab" data-tab="members" onclick="partySystem.switchTab('members')">Members</button>
            <button class="party-tab" data-tab="inventory" onclick="partySystem.switchTab('inventory')">Shared Inventory</button>
            <button class="party-tab" data-tab="buffs" onclick="partySystem.switchTab('buffs')">Buffs</button>
        </div>
        <div class="party-tab-content">
            <div id="formationTab" class="party-tab-pane active">
                <div class="formation-editor">
                    <div class="formation-zones">
                        <div class="formation-zone front" id="frontZone">
                            <div class="formation-zone-header"><span class="formation-zone-label">Front Line</span><span class="formation-zone-count">0 members</span></div>
                            <div class="formation-members"></div>
                        </div>
                        <div class="formation-zone middle" id="middleZone">
                            <div class="formation-zone-header"><span class="formation-zone-label">Middle Line</span><span class="formation-zone-count">0 members</span></div>
                            <div class="formation-members"></div>
                        </div>
                        <div class="formation-zone back" id="backZone">
                            <div class="formation-zone-header"><span class="formation-zone-label">Back Line</span><span class="formation-zone-count">0 members</span></div>
                            <div class="formation-members"></div>
                        </div>
                    </div>
                    <div class="formation-preview" id="formationPreview"></div>
                </div>
            </div>
            <div id="membersTab" class="party-tab-pane"><div class="party-members-grid" id="partyMembersList"></div></div>
            <div id="inventoryTab" class="party-tab-pane">
                <div class="shared-inventory-header">
                    <div class="shared-gold-display"><span>Party Treasury:</span><span class="shared-gold-amount" id="sharedGoldAmount">0</span></div>
                    <div class="shared-inventory-actions">
                        <button class="shared-inventory-btn">Contribute Items</button>
                        <button class="shared-inventory-btn">Contribute Gold</button>
                    </div>
                </div>
                <div class="shared-items-grid" id="sharedItemsList"></div>
            </div>
            <div id="buffsTab" class="party-tab-pane"><div class="party-buffs-grid" id="partyBuffsList"></div></div>
        </div>
    </div>
</div>

<!-- Skill Tree Modal (unchanged) -->
<div id="skillModal" class="skill-modal">
    <div class="skill-modal-content">
        <div class="skill-modal-header">
            <div class="skill-modal-title-group">
                <h2 class="skill-modal-title">Skill Trees</h2>
                <div class="skill-modal-subtitle">Unlock powerful abilities and enhance your character</div>
            </div>
            <div class="talent-points-display">
                <span class="talent-points-label">Talent Points:</span>
                <span class="talent-points-value" id="talentPointsValue">0</span>
            </div>
            <button class="skill-close-btn" onclick="skillTreeSystem.closeModal()">&times;</button>
        </div>
        <div class="tree-selector" id="treeSelector"></div>
        <div class="skill-tree-container"><div class="skill-tree-canvas" id="skillTreeCanvas"></div></div>
    </div>
</div>
<div id="skillTooltip" class="skill-tooltip"></div>

<!-- Achievement Modal (unchanged) -->
<div id="achievementModal" class="achievement-modal">
    <div class="achievement-modal-content">
        <div class="achievement-header">
            <div>
                <h2>{{ svg_icon('trophy-fill', 28, 'me-2') }}Achievements</h2>
                <div class="achievement-stats">
                    <div class="achievement-stat"><i class="bi bi-star-fill"></i><span>Points: <span id="achievementTotalPoints" class="achievement-stat-value">0</span></span></div>
                    <div class="achievement-stat"><i class="bi bi-trophy-fill"></i><span>Unlocked: <span id="achievementUnlockedCount" class="achievement-stat-value">0/0</span></span></div>
                </div>
            </div>
            <button class="achievement-close-btn" onclick="achievementSystem.closeAchievements()"><i class="bi bi-x-lg"></i> Close</button>
        </div>
        <div class="achievement-category-tabs" id="achievementCategoryTabs"></div>
        <div class="achievement-list-container"><div class="achievement-list" id="achievementList"></div></div>
    </div>
</div>
<div id="achievementNotification" class="achievement-notification">
    <div class="achievement-notification-icon" id="achievementNotificationIcon">🏆</div>
    <div class="achievement-notification-content">
        <div class="achievement-notification-title">Achievement Unlocked!</div>
        <div class="achievement-notification-name" id="achievementNotificationName">Achievement Name</div>
        <div class="achievement-notification-reward" id="achievementNotificationReward">+100 gold</div>
    </div>
</div>

<script src="{{ asset_url('js/party-management.js') }}"></script>
<script src="{{ asset_url('js/skill-tree.js') }}"></script>
<script src="{{ asset_url('js/achievement-system.js') }}"></script>
{% endblock %}
{% endblock %}
```

- [ ] **Step 4: Strip old party-checkbox logic from `dashboard.js`**

The old party checkbox/table/card-click block is no longer needed (party is now managed via API + server-side slots). Replace `dashboard.js` with:

```javascript
(function () {
    // Config API prefetch (used by equipment/character panels)
    let config = {};
    async function fetchConfig() {
        const [namePools, starterItems, baseStats, classMap] = await Promise.all([
            fetch('/api/config/name_pools').then(r => r.json()),
            fetch('/api/config/starter_items').then(r => r.json()),
            fetch('/api/config/base_stats').then(r => r.json()),
            fetch('/api/config/class_map').then(r => r.json()),
        ]);
        config.namePools = namePools;
        config.starterItems = starterItems;
        config.baseStats = baseStats;
        config.classMap = classMap;
    }
    fetchConfig();

    // Apply server-rendered XP bar fill percentages
    document.querySelectorAll('.xp-fill[data-xp-pct]').forEach((bar) => {
        bar.style.width = bar.dataset.xpPct + '%';
    });

    // Apply server-rendered HP/MP bar fill percentages
    document.querySelectorAll('.bar-fill[data-bar-pct]').forEach((bar) => {
        bar.style.width = bar.dataset.barPct + '%';
    });
})();
```

- [ ] **Step 5: Run the full test suite**

```
pytest -x -q 2>&1 | tail -30
```

Expected: no new failures. The old party checkbox tests in `test_dashboard_routes.py` may need inspection if they assert on party-checkbox HTML that no longer exists — note any failures.

- [ ] **Step 6: Commit**

```bash
git add app/static/css/dashboard.css app/templates/dashboard.html app/static/js/dashboard.js
git commit -m "feat(lobby): restructure dashboard into 7-tab lobby layout"
```

---

## Task 3: JS — Lobby interactions (tab state, party, barracks, recruit)

**Files:**
- Create: `app/static/js/dashboard-lobby.js`

**Interfaces:**
- Consumes: Bootstrap `Tab` API (`data-bs-toggle="tab"`)
- Consumes: `/api/party/add`, `/api/party/remove/<id>`, `/autofill_characters`, `/api/recruit/candidates`, `/api/recruit/hire`
- Consumes: `#lobbyTabNav` button elements, `#barracks-grid` cards, `#recruit-candidates-grid`
- Produces: full tab state + party/barracks/recruit interactivity

- [ ] **Step 1: Create `dashboard-lobby.js`**

Create `app/static/js/dashboard-lobby.js`:

```javascript
/* dashboard-lobby.js — Lobby tab state + party/barracks/recruit interactions */
(function () {
  'use strict';

  // ── Tab state persistence ────────────────────────────────────────────────
  const NAV_KEY = 'lobby_active_tab';

  function activateTab(targetId) {
    const btn = document.querySelector(`#lobbyTabNav [data-bs-target="#${targetId}"]`);
    if (!btn) return;
    const tab = bootstrap.Tab.getOrCreateInstance(btn);
    tab.show();
  }

  const savedTab = sessionStorage.getItem(NAV_KEY);
  if (savedTab) activateTab(savedTab);

  document.querySelectorAll('#lobbyTabNav .nav-link').forEach(btn => {
    btn.addEventListener('shown.bs.tab', e => {
      const target = e.target.getAttribute('data-bs-target');
      if (target) sessionStorage.setItem(NAV_KEY, target.replace('#', ''));
      // Fetch candidates when Recruit tab opens
      if (target === '#lobby-recruit') loadCandidates();
    });
  });

  // ── Switch tab helper (used by buttons with data-lobby-switch) ───────────
  document.addEventListener('click', e => {
    const btn = e.target.closest('[data-lobby-switch]');
    if (btn) activateTab(btn.dataset.lobbySwitch);
  });

  // ── Party tab — empty slot clicks go to Barracks ─────────────────────────
  document.querySelectorAll('.party-slot-empty').forEach(slot => {
    slot.addEventListener('click', () => activateTab('lobby-barracks'));
  });

  // ── Party tab — REMOVE button ─────────────────────────────────────────────
  document.addEventListener('click', async e => {
    const btn = e.target.closest('.btn-party-remove');
    if (!btn) return;
    const charId = btn.dataset.charId;
    if (!charId) return;
    btn.disabled = true;
    try {
      const resp = await fetch(`/api/party/remove/${charId}`, { method: 'POST' });
      if (resp.ok) location.reload();
      else btn.disabled = false;
    } catch (_) { btn.disabled = false; }
  });

  // ── Party tab — GO DUNGEON button ─────────────────────────────────────────
  const goDungeonBtn = document.getElementById('lobby-go-dungeon-btn');
  if (goDungeonBtn) {
    goDungeonBtn.addEventListener('click', () => activateTab('lobby-dungeon'));
  }

  // ── Party tab — AUTO-FILL ─────────────────────────────────────────────────
  const autofillBtn = document.getElementById('lobby-autofill-btn');
  if (autofillBtn) {
    autofillBtn.addEventListener('click', async () => {
      autofillBtn.disabled = true;
      autofillBtn.textContent = 'Filling…';
      try {
        const resp = await fetch('/autofill_characters', {
          method: 'POST',
          headers: { 'X-Requested-With': 'fetch', 'Accept': 'application/json' },
        });
        if (resp.ok) location.reload();
        else { autofillBtn.disabled = false; autofillBtn.textContent = 'AUTO-FILL'; }
      } catch (_) { autofillBtn.disabled = false; autofillBtn.textContent = 'AUTO-FILL'; }
    });
  }

  // ── Barracks tab — card selection ────────────────────────────────────────
  const barracksGrid = document.getElementById('barracks-grid');
  const addPartyBtn = document.getElementById('barracks-add-party-btn');

  function selectedBarracksIds() {
    return Array.from(document.querySelectorAll('.barracks-card.selected')).map(c => parseInt(c.dataset.id));
  }

  function updateAddPartyBtn() {
    if (!addPartyBtn) return;
    const count = selectedBarracksIds().length;
    addPartyBtn.disabled = count === 0;
    addPartyBtn.textContent = count > 0 ? `ADD TO PARTY (${count})` : 'ADD TO PARTY';
  }

  if (barracksGrid) {
    barracksGrid.addEventListener('click', e => {
      const card = e.target.closest('.barracks-card');
      if (!card || card.dataset.inParty === 'true') return;
      if (e.target.closest('form') || e.target.closest('button')) return;
      card.classList.toggle('selected');
      updateAddPartyBtn();
    });
  }

  if (addPartyBtn) {
    addPartyBtn.addEventListener('click', async () => {
      const ids = selectedBarracksIds();
      if (!ids.length) return;
      addPartyBtn.disabled = true;
      try {
        const resp = await fetch('/api/party/add', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ char_ids: ids }),
        });
        if (resp.ok) { sessionStorage.setItem(NAV_KEY, 'lobby-party'); location.reload(); }
        else addPartyBtn.disabled = false;
      } catch (_) { addPartyBtn.disabled = false; }
    });
  }

  // Barracks "RECRUIT MORE →" button
  const barracksRecruitBtn = document.getElementById('barracks-recruit-btn');
  const barracksRecruitEmptyBtn = document.getElementById('barracks-recruit-empty-btn');
  if (barracksRecruitBtn) barracksRecruitBtn.addEventListener('click', () => activateTab('lobby-recruit'));
  if (barracksRecruitEmptyBtn) barracksRecruitEmptyBtn.addEventListener('click', () => activateTab('lobby-recruit'));

  // ── Barracks tab — sort controls ─────────────────────────────────────────
  document.querySelectorAll('.sort-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.sort-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      sortBarracks(btn.dataset.sort);
    });
  });

  function sortBarracks(by) {
    if (!barracksGrid) return;
    const cols = Array.from(barracksGrid.querySelectorAll(':scope > .col-12, :scope > [class*="col-"]'));
    cols.sort((a, b) => {
      const ca = a.querySelector('.barracks-card');
      const cb = b.querySelector('.barracks-card');
      if (!ca || !cb) return 0;
      if (by === 'level') return parseInt(cb.dataset.level || 0) - parseInt(ca.dataset.level || 0);
      if (by === 'class') return (ca.dataset.class || '').localeCompare(cb.dataset.class || '');
      if (by === 'name')  return (ca.dataset.name || '').localeCompare(cb.dataset.name || '');
      return 0;
    });
    cols.forEach(col => barracksGrid.appendChild(col));
  }

  // ── Recruit tab ──────────────────────────────────────────────────────────
  let candidates = [];
  let loaded = false;

  async function loadCandidates() {
    const grid = document.getElementById('recruit-candidates-grid');
    if (!grid) return;
    if (loaded) return;
    loaded = false;
    grid.innerHTML = '<div class="col-12 text-center py-4 text-muted small"><span class="spinner-border spinner-border-sm me-2"></span>Loading candidates…</div>';
    try {
      const resp = await fetch('/api/recruit/candidates');
      if (!resp.ok) throw new Error('HTTP ' + resp.status);
      candidates = await resp.json();
      renderCandidates(grid);
      loaded = true;
    } catch (err) {
      grid.innerHTML = `<div class="col-12 text-center py-4 text-danger small">Failed to load candidates. <button class="tactical-btn-secondary btn-sm ms-2" id="recruit-retry-btn">Retry</button></div>`;
      document.getElementById('recruit-retry-btn')?.addEventListener('click', () => { loaded = false; loadCandidates(); });
    }
  }

  function renderCandidates(grid) {
    const STAT_KEYS = ['str', 'dex', 'con', 'int', 'wis', 'cha'];
    const tweaks = candidates.map(() => ({}));

    function totalTweaks(i) {
      return Object.values(tweaks[i]).reduce((s, v) => s + v, 0);
    }

    function buildCard(i, c) {
      const t = tweaks[i];
      const remaining = 2 - totalTweaks(i);
      return `
        <div class="col-12 col-md-6 col-xl-3">
          <div class="tactical-panel candidate-card" data-candidate="${i}">
            <div class="panel-header">
              <h5><span class="class-badge ${c.cls}-badge me-2">${c.cls.toUpperCase()}</span>${c.name}</h5>
            </div>
            <div class="panel-body">
              <div class="candidate-stats-grid">
                ${STAT_KEYS.map(k => `
                  <div class="candidate-stat-row" data-stat="${k}" data-idx="${i}">
                    <span class="stat-label">${k.toUpperCase()}</span>
                    <span class="stat-val">${(c.stats[k] || 0) + (t[k] || 0)}</span>
                    <button class="tactical-btn-secondary stat-tweak-btn" data-dir="-1"
                      ${(t[k] || 0) <= 0 ? 'disabled' : ''}>−</button>
                    <button class="tactical-btn-secondary stat-tweak-btn" data-dir="1"
                      ${remaining <= 0 ? 'disabled' : ''}>+</button>
                  </div>`).join('')}
              </div>
              <div class="stat-points-counter mb-2">STAT POINTS: ${remaining} remaining</div>
              <div class="small text-muted mb-2">
                HP ${c.stats.hp} · MP ${c.stats.mana}
              </div>
              <button class="deploy-btn btn-full-width btn-hire" data-idx="${i}">HIRE</button>
            </div>
          </div>
        </div>`;
    }

    function rerender() {
      grid.innerHTML = candidates.map((c, i) => buildCard(i, c)).join('');
      attachCandidateEvents();
    }

    function attachCandidateEvents() {
      // Stat tweak buttons
      grid.querySelectorAll('.stat-tweak-btn').forEach(btn => {
        btn.addEventListener('click', e => {
          const row = btn.closest('[data-stat]');
          if (!row) return;
          const stat = row.dataset.stat;
          const idx = parseInt(row.dataset.idx);
          const dir = parseInt(btn.dataset.dir);
          const t = tweaks[idx];
          const cur = t[stat] || 0;
          if (dir < 0 && cur <= 0) return;
          if (dir > 0 && totalTweaks(idx) >= 2) return;
          t[stat] = cur + dir;
          if (t[stat] === 0) delete t[stat];
          rerender();
        });
      });

      // Hire buttons
      grid.querySelectorAll('.btn-hire').forEach(btn => {
        btn.addEventListener('click', async () => {
          const idx = parseInt(btn.dataset.idx);
          const c = candidates[idx];
          btn.disabled = true;
          btn.textContent = 'Hiring…';
          try {
            const resp = await fetch('/api/recruit/hire', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                name: c.name,
                cls: c.cls,
                stats: c.stats,
                gear_slugs: c.gear_slugs,
                stat_tweaks: tweaks[idx],
              }),
            });
            if (resp.ok) {
              sessionStorage.setItem(NAV_KEY, 'lobby-barracks');
              location.reload();
            } else {
              const err = await resp.json().catch(() => ({}));
              btn.disabled = false;
              btn.textContent = 'HIRE';
              alert(err.error || 'Hire failed');
            }
          } catch (_) { btn.disabled = false; btn.textContent = 'HIRE'; }
        });
      });
    }

    rerender();
  }

  // Reroll button
  const rerollBtn = document.getElementById('recruit-reroll-btn');
  if (rerollBtn) {
    rerollBtn.addEventListener('click', () => { loaded = false; loadCandidates(); });
  }

  // Auto-load if Recruit tab is already active on page load
  const activeTab = document.querySelector('#lobbyTabNav .nav-link.active');
  if (activeTab && activeTab.getAttribute('data-bs-target') === '#lobby-recruit') {
    loadCandidates();
  }

})();
```

- [ ] **Step 2: Run the full test suite**

```
pytest -x -q 2>&1 | tail -20
```

Expected: no new failures (JS is not exercised by pytest).

- [ ] **Step 3: Start the dev server and manually verify all tabs**

```
./manage.sh start
```

Checklist:
- [ ] PARTY tab loads with 4 slots (filled or empty dashes)
- [ ] Empty slot click navigates to BARRACKS tab
- [ ] REMOVE on a party slot removes that character and reloads (party shrinks by 1)
- [ ] AUTO-FILL calls `/autofill_characters` and reloads with party filled
- [ ] "⚔ ENTER DUNGEON →" button navigates to DUNGEON tab
- [ ] BARRACKS tab shows all characters, sort buttons work (re-orders DOM)
- [ ] Clicking a non-party barracks card selects it (gold border); clicking again deselects
- [ ] IN PARTY cards are greyed and not selectable
- [ ] ADD TO PARTY posts to `/api/party/add`, reloads on PARTY tab
- [ ] RECRUIT tab fetches 4 candidates on first open
- [ ] `+`/`−` tweak buttons increment/decrement stats, max 2 total
- [ ] HIRE saves character, reloads on BARRACKS tab
- [ ] REROLL ALL fetches new candidates
- [ ] DUNGEON tab shows party overview, seed widget, Enter Dungeon form
- [ ] ENTER DUNGEON form submits and creates dungeon instance
- [ ] MERCHANTS tab shows 3 cards with OPEN buttons
- [ ] HOARD / ACHIEVEMENTS tabs trigger existing modals
- [ ] Tab state persists on page reload (sessionStorage)
- [ ] Seed dial countdown continues working
- [ ] Chat widget unchanged

- [ ] **Step 4: Commit**

```bash
git add app/static/js/dashboard-lobby.js
git commit -m "feat(lobby): add dashboard-lobby.js for tab state, party/barracks/recruit interactions"
```
