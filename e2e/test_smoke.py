"""End-to-end smoke test: real browser, real server, real database.

Covers the core loop — register, dashboard, party deploy, dungeon page,
one API move — plus a positive and negative check of the CSRF header
guard (the fetch wrapper in static/js/api-guard.js must stamp the header;
a bare request without it must be rejected).

Lives outside tests/ deliberately: tests/conftest.py's autouse fixtures
import the app and rebind the DB session, which a black-box browser test
must not do. Skipped unless E2E=1 is set and a server is reachable at
ADVENTURE_BASE_URL (default http://localhost:5000). The CI job
`e2e-smoke` boots the server; locally:

    E2E=1 ADVENTURE_BASE_URL=http://localhost:5000 pytest e2e -q
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(os.getenv("E2E") != "1", reason="E2E=1 not set")

playwright_sync = pytest.importorskip("playwright.sync_api")

BASE_URL = os.environ.get("ADVENTURE_BASE_URL", "http://localhost:5000")
USERNAME = f"e2e_smoke_{int(time.time())}"
PASSWORD = "e2e-smoke-pass-1"

REPO_ROOT = Path(__file__).resolve().parent.parent

_SEED_SCRIPT = """
import json, random, sys
from app import create_app, db
from app.loot.generator import generate_item
from app.models.models import Character

app = create_app()
with app.app_context():
    ch = db.session.get(Character, int(sys.argv[1]))
    if ch is None:
        raise SystemExit(f"no character {sys.argv[1]}")
    instance = generate_item(level=2, rarity="common", slot=sys.argv[2], rng=random.Random(4242))
    items = json.loads(ch.items) if ch.items else []
    if not isinstance(items, list):
        items = []
    items.append(instance)
    ch.items = json.dumps(items)
    db.session.commit()
    print(json.dumps(instance))
"""

# Same out-of-process rules as _SEED_SCRIPT (see _seed_procedural_item). A
# potion is a catalogue row, not a generated instance, so this ensures the row
# exists (server.py seeds it at boot, but a database that predates that seed
# would otherwise leave the bag entry unresolvable and the cell unrendered)
# and then puts a stack in the character's bag.
_SEED_POTION_SCRIPT = """
import json, sys
from app import create_app, db
from app.models.models import Character, Item

app = create_app()
with app.app_context():
    ch = db.session.get(Character, int(sys.argv[1]))
    if ch is None:
        raise SystemExit(f"no character {sys.argv[1]}")
    slug, qty = sys.argv[2], int(sys.argv[3])
    if Item.query.filter_by(slug=slug).first() is None:
        db.session.add(Item(slug=slug, name="Potion of Healing", type="potion",
                            description="Restores a small amount of HP.", value_copper=150))
    items = json.loads(ch.items) if ch.items else []
    if not isinstance(items, list):
        items = []
    items = [obj for obj in items if not (isinstance(obj, dict) and obj.get("slug") == slug)]
    items.append({"slug": slug, "qty": qty})
    ch.items = json.dumps(items)
    db.session.commit()
    print(json.dumps({"slug": slug, "qty": qty}))
"""


def _run_seed(script, *args):
    """Run one of the seed scripts above in a subprocess against the server's
    own database. See _seed_procedural_item for why this is out-of-process and
    why DATABASE_URL is passed explicitly rather than inherited."""
    database_url = os.environ.get("DATABASE_URL")
    assert database_url, (
        "DATABASE_URL must be set for the e2e suite to seed, and it must be "
        "the exact database the server under test (ADVENTURE_BASE_URL) was started with -- "
        "see ci.yml's e2e step and _seed_procedural_item's docstring."
    )
    result = subprocess.run(
        [sys.executable, "-c", script, *[str(a) for a in args]],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=30,
        env={**os.environ, "DATABASE_URL": database_url},
    )
    assert result.returncode == 0, f"seeding failed: {result.stderr}"
    return json.loads(result.stdout.strip().splitlines()[-1])


def _seed_potions(char_id, slug="potion-healing", qty=3):
    """Put a stack of drinkable potions in a party member's bag."""
    return _run_seed(_SEED_POTION_SCRIPT, char_id, slug, qty)


def _seed_procedural_item(char_id, slot="hands"):
    """Seed one procedural gear instance directly into a party member's bag.

    Run out-of-process (a subprocess that imports `app` on its own) rather
    than importing `app`/`db` here: this module is a black-box browser test
    against a live server (see the module docstring) and must not import the
    app package or rebind a DB session itself. There is no HTTP route that
    grants gear directly -- app/loot/generator.py:generate_item is the same
    pure function tests/test_procedural_gear_equip.py uses server-side.

    DATABASE_URL is required and passed to the subprocess explicitly (not
    left to ambient inheritance): app/__init__.py imports at module scope
    and raises immediately if DATABASE_URL is unset, so on CI (no .env in
    the checkout, and this pytest step's own env previously carried only
    E2E/ADVENTURE_BASE_URL) the subprocess used to die before it could seed
    anything -- see ci.yml's e2e step, which now sets it to match the
    server's own database. Passing it explicitly rather than relying on
    inheritance also matters locally: a shell with a TEST_DATABASE_URL habit
    can easily have some *other* DATABASE_URL set, pointing at a database the
    running server under test never reads from. That doesn't crash -- it
    seeds silently into the wrong place, and the failure then surfaces as a
    null dereference inside page.evaluate (the bag cell the test looks for
    was never written to the database the server actually queries) instead
    of anything that says "wrong database."

    Returns the seeded instance dict (uid, slot, name, ...).

    Leaves the seeded item in the character's items/gear JSON rather than
    deleting it afterward -- the character itself belongs to this run's own
    throwaway e2e_smoke_<timestamp> account (registered fresh, never reused
    across runs, and nothing else in this file cleans up its own registered
    accounts either), so the marginal cost is one extra key inside already-
    ephemeral test data, not a separately-tracked row that accumulates
    unboundedly on its own.
    """
    return _run_seed(_SEED_SCRIPT, char_id, slot)


@pytest.fixture(scope="module")
def page():
    with playwright_sync.sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        pg = context.new_page()
        deadline = time.time() + 30
        last_err = None
        while time.time() < deadline:
            try:
                pg.goto(f"{BASE_URL}/", timeout=3000)
                break
            except Exception as e:  # server still booting
                last_err = e
                time.sleep(0.5)
        else:
            pytest.fail(f"server not reachable at {BASE_URL}: {last_err}")
        yield pg
        context.close()
        browser.close()


def test_register_and_reach_dashboard(page):
    page.goto(f"{BASE_URL}/register")
    page.fill('input[name="username"]', USERNAME)
    page.fill('input[name="password"]', PASSWORD)
    page.click('button[type="submit"]')
    page.wait_for_load_state("networkidle")
    assert "/register" not in page.url, "registration did not redirect away"
    page.goto(f"{BASE_URL}/dashboard")
    page.wait_for_load_state("networkidle")
    assert "/login" not in page.url, "registration did not produce a session"


def test_autofill_and_deploy_party(page):
    page.goto(f"{BASE_URL}/dashboard")
    page.wait_for_load_state("networkidle")
    if page.locator(".barracks-card[data-id]").count() == 0:
        resp = page.request.post(f"{BASE_URL}/autofill_characters")
        assert resp.ok, f"autofill_characters failed: {resp.status}"
        page.goto(f"{BASE_URL}/dashboard")
        page.wait_for_load_state("networkidle")
    ids = page.evaluate(
        "() => Array.from(document.querySelectorAll('.barracks-card[data-id]'))"
        ".slice(0,4).map(el => el.getAttribute('data-id')).filter(Boolean)"
    )
    assert ids, "no party-selectable characters after autofill"
    body = "form=start_adventure&" + "&".join(f"party_ids={i}" for i in ids)
    resp = page.request.post(
        f"{BASE_URL}/dashboard",
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert resp.ok, f"start_adventure failed: {resp.status}"


def test_adventure_page_renders_map(page):
    page.goto(f"{BASE_URL}/adventure")
    page.wait_for_load_state("networkidle")
    assert "/adventure" in page.url, f"redirected off adventure page to {page.url}"
    # The in-page fetch goes through api-guard.js, so this also proves the
    # CSRF-guard wrapper stamps same-origin GET/POST calls correctly.
    state = page.evaluate(
        """async () => {
            const resp = await fetch('/api/dungeon/map');
            return { status: resp.status, ok: resp.ok };
        }"""
    )
    assert state["ok"], f"/api/dungeon/map returned {state['status']}"


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

    assert (
        metrics["scrollH"] <= metrics["clientH"] + 1
    ), f"page scrolls vertically at 1366x768: {metrics['scrollH']} > {metrics['clientH']}"
    assert metrics["scrollW"] <= metrics["clientW"] + 1, "page scrolls horizontally at 1366x768"
    assert metrics["canvas"]["height"] > 500, "the map did not take the space the chrome gave back"
    assert metrics["canvas"]["width"] > 1200, "the map is not full-bleed"


def test_api_move_via_page_fetch(page):
    result = page.evaluate(
        """async () => {
            const resp = await fetch('/api/dungeon/move', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ direction: 'north' }),
            });
            return { status: resp.status };
        }"""
    )
    # Any non-403 response proves the guard accepted the wrapped call;
    # a blocked move (wall) is still a valid 200/400-class outcome.
    assert result["status"] != 403, "api-guard.js header was not attached"
    assert result["status"] < 500, f"server error on move: {result['status']}"


def test_hud_panels_do_not_cover_the_party_or_each_other(page):
    """Overlays must not sit on the camera's target (HUD spec, constraint 2),
    and must not sit on top of one another.

    Originally this only checked .adv-log and .adv-party-rail by name. That
    hand-listed pair missed a real bug: .adv-actions (the action bar) had no
    CSS relationship to --hud-inset-bottom, so its height was pure content
    size, and at the brief's own button padding it rode up 23px under
    .adv-party-rail -- which, being later in DOM order, won the stacking tie
    and silently ate clicks meant for Search. A hand-listed pair only catches
    regressions in the pair someone remembered to list.

    So instead of naming panels, this discovers them: any direct child of
    .adv-hud that is visible and positioned off the normal document flow
    (absolute/fixed) other than the canvas itself. That is every current
    overlay (.hud-readout, .map-controls, .adv-actions, .adv-log,
    .adv-party-rail; #hotkeys-panel too, when open) and, structurally, any
    future one -- nothing here needs to be remembered and appended to.

    The hotkeys panel is opened first, because "when open" was a promise this
    test used to make and not keep: the panel was anchored in the party rail's
    box at the same z-index, and the rail -- later in DOM -- won the tie, so
    the panel rendered behind four opaque frames and every click aimed at it
    hit .adv-frame-open instead. Discovery skipped it entirely because a
    display: none element has no box.
    """
    page.set_viewport_size({"width": 1366, "height": 768})
    page.goto(f"{BASE_URL}/adventure")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(500)  # let centerOnPlayer settle

    page.click("#btn-show-hotkeys")
    assert (
        page.evaluate("() => getComputedStyle(document.getElementById('hotkeys-panel')).display") != "none"
    ), "one click on #btn-show-hotkeys did not open the panel"

    result = page.evaluate(
        """() => {
            const hud = document.querySelector('.adv-hud');
            const cs = getComputedStyle(hud);
            const left = parseFloat(cs.getPropertyValue('--hud-inset-left'));
            const bottom = parseFloat(cs.getPropertyValue('--hud-inset-bottom'));
            const r = hud.getBoundingClientRect();
            // Where centerOnPlayer puts the party, per dungeon-canvas.js.
            const px = (r.width + left) / 2;
            const py = (r.height - bottom) / 2;

            const panels = Array.from(hud.children).filter((el) => {
                if (el.id === 'dungeon-map') return false; // the canvas, not an overlay
                const pcs = getComputedStyle(el);
                if (pcs.display === 'none' || pcs.visibility === 'hidden') return false;
                if (pcs.position !== 'absolute' && pcs.position !== 'fixed') return false;
                const rect = el.getBoundingClientRect();
                return rect.width > 0 && rect.height > 0;
            });
            const describe = (el) => el.className ? String(el.className) : (el.id || el.tagName);

            const onParty = panels
                .filter((el) => {
                    const b = el.getBoundingClientRect();
                    return px >= b.left && px <= b.right && py >= b.top && py <= b.bottom;
                })
                .map(describe);

            const pairOverlaps = [];
            for (let i = 0; i < panels.length; i++) {
                for (let j = i + 1; j < panels.length; j++) {
                    const a = panels[i].getBoundingClientRect();
                    const b = panels[j].getBoundingClientRect();
                    const overlap = !(a.right <= b.left || a.left >= b.right || a.bottom <= b.top || a.top >= b.bottom);
                    if (overlap) pairOverlaps.push([describe(panels[i]), describe(panels[j])]);
                }
            }

            // The rail reserves its own span from --hud-inset-bottom, so it
            // never overflows the HUD -- but it can overflow itself, and then
            // the fourth frame is only reachable by scrolling a panel that
            // gives no hint it scrolls.
            const rail = hud.querySelector('.adv-party-rail');
            const railOverflow = rail ? rail.scrollHeight - rail.clientHeight : 0;
            const panelNames = panels.map(describe);

            return { panelCount: panels.length, panelNames, onParty, pairOverlaps, railOverflow };
        }"""
    )

    # A sanity floor on panel discovery itself: if this drops to 0 the
    # selector broke (e.g. the HUD markup moved out of .adv-hud) and the
    # checks below would vacuously pass.
    assert result["panelCount"] >= 3, f"HUD panel discovery found too few panels: {result}"
    assert (
        "hotkeys-panel" in result["panelNames"]
    ), f"the open hotkeys panel was not discovered as an overlay: {result['panelNames']}"
    assert not result["onParty"], f"these panels are sitting on the party: {result['onParty']}"
    assert not result["pairOverlaps"], f"these HUD panels overlap each other: {result['pairOverlaps']}"
    # An earlier pass hit this by hand: four frames measured 677px against the
    # 540px the rail has between --space-2 and --hud-inset-bottom. It will
    # recur on a font-size change, a fifth party slot, or an extra stat row.
    assert result["railOverflow"] <= 1, f"the party rail overflows its own box by {result['railOverflow']}px"


def test_character_panel_opens_from_a_party_frame(page):
    """The rail is the character selector, and the panel it opens is the one
    that can equip procedural gear (it posts uid). The old dungeon panel could
    not, which is the defect this chunk exists to fix.

    Everything up to the drag-drop only proves the panel opens in the right
    place with the right scripts loaded -- it would pass unchanged even if
    the drop posted {slug, slot}, posted nothing, or the slot stayed empty.
    The uid assertion at the end is the one that actually proves the defect
    is fixed: a procedural item, seeded directly into a party member's bag
    (there is no route that grants gear), dropped on its slot from this
    panel, sends a request whose body is {"uid": ...} -- not the old
    dungeon panel's {slug, slot}, which 404s for a generated item.
    """
    page.set_viewport_size({"width": 1366, "height": 768})
    page.goto(f"{BASE_URL}/adventure")
    page.wait_for_load_state("networkidle")

    scripts = page.evaluate("() => Array.from(document.scripts).map(s => s.src).filter(Boolean).join(' ')")
    assert "equipment-panel.js" in scripts
    assert "equipment-enhanced.js" not in scripts, "two paper dolls again"
    assert "/equipment.js" not in scripts, "the old dungeon panel is still loaded"

    char_id = page.evaluate("() => document.querySelector('.adv-party-rail .adv-frame-open')?.dataset.charId")
    assert char_id, "no deployed party member to open a panel for"

    page.click(".adv-party-rail .adv-frame-open")
    panel = page.locator(".adv-character")
    panel.wait_for(state="visible", timeout=3000)

    box = panel.bounding_box()
    rail = page.locator(".adv-party-rail").bounding_box()
    assert box["x"] >= rail["x"] + rail["width"] - 1, "the panel is covering the rail it selects from"

    instance = _seed_procedural_item(char_id, slot="hands")
    page.reload()
    page.wait_for_load_state("networkidle")
    page.click(".adv-party-rail .adv-frame-open")
    panel.wait_for(state="visible", timeout=3000)

    with page.expect_request(lambda req: req.url.endswith("/equip") and req.method == "POST") as req_info:
        page.evaluate(
            """([uid, slot]) => {
                const cell = document.querySelector(`.bag-grid-cell[data-item-uid="${uid}"]`);
                const target = document.querySelector(`.equipment-slot[data-slot="${slot}"]`);
                const dt = new DataTransfer();
                cell.dispatchEvent(new DragEvent('dragstart', { bubbles: true, dataTransfer: dt }));
                target.dispatchEvent(new DragEvent('dragover', { bubbles: true, cancelable: true, dataTransfer: dt }));
                target.dispatchEvent(new DragEvent('drop', { bubbles: true, cancelable: true, dataTransfer: dt }));
            }""",
            [instance["uid"], instance["slot"]],
        )
    equip_request = req_info.value
    equip_body = json.loads(equip_request.post_data)
    assert (
        equip_body.get("uid") == instance["uid"]
    ), f"the dungeon panel did not send uid for the dropped item: {equip_body}"
    assert "slug" not in equip_body and "slot" not in equip_body, (
        "this is the old dungeon panel's request shape ({slug, slot}), which 404s for a "
        f"generated item with no catalogue row: {equip_body}"
    )


def test_a_potion_in_the_bag_can_be_drunk_from_the_panel(page):
    """The client's consume path, guarded where it was actually lost.

    Out-of-combat drinking disappeared once already and nothing failed,
    because what went missing was the *panel's* route to /consume, not the
    route itself -- which stayed live and stayed tested the whole time.
    tests/test_bag_potion_consumption.py covers the server round trip, but it
    would still pass with consumeItem deleted from equipment-panel.js, so it
    cannot be the guard against a second silent loss. This is: it clicks the
    cell a player clicks and asserts the request that click must produce.

    The two assertions divide the job. `data-consumable="true"` proves the
    grid still recognises a potion as drinkable rather than wearable -- the
    exact judgement whose absence made a potion click try to *equip* it. The
    expect_request proves the click on that cell reaches /consume with the
    potion's slug, and not /equip, which answers 400 for a slotless item.
    """
    page.set_viewport_size({"width": 1366, "height": 768})
    page.goto(f"{BASE_URL}/adventure")
    page.wait_for_load_state("networkidle")

    char_id = page.evaluate("() => document.querySelector('.adv-party-rail .adv-frame-open')?.dataset.charId")
    assert char_id, "no deployed party member to open a panel for"

    # Seeded rather than taken from the starting kit: most kits carry a
    # healing potion, but which class autofill rolled is not this test's to
    # depend on, and an earlier case in this module may already have drunk it.
    potion = _seed_potions(char_id, qty=3)
    page.reload()
    page.wait_for_load_state("networkidle")
    page.click(".adv-party-rail .adv-frame-open")
    page.locator(".adv-character").wait_for(state="visible", timeout=3000)

    cell = page.locator(f'.bag-grid-cell[data-item-slug="{potion["slug"]}"]').first
    cell.wait_for(state="visible", timeout=3000)
    assert cell.get_attribute("data-consumable") == "true", (
        "the bag grid no longer treats a potion as drinkable, so its cell would "
        "try to equip it -- which is a 400 for an item with no slot"
    )

    with page.expect_request(lambda req: req.url.endswith("/consume") and req.method == "POST") as req_info:
        cell.click()
    body = json.loads(req_info.value.post_data)
    assert body.get("slug") == potion["slug"], f"the panel drank the wrong thing: {body}"

    page.wait_for_timeout(500)
    assert (
        page.locator(f'.bag-grid-cell[data-item-slug="{potion["slug"]}"] .cell-qty').first.inner_text().strip() == "2"
    ), "the panel did not repaint the bag after drinking"


def test_csrf_guard_rejects_bare_mutation(page):
    # page.request bypasses the page's fetch wrapper but shares cookies —
    # exactly what a cross-site forged request looks like to the server.
    resp = page.request.post(
        f"{BASE_URL}/api/dungeon/seed",
        data="{}",
        headers={"Content-Type": "application/json"},
    )
    assert resp.status == 403, f"expected csrf_rejected 403, got {resp.status}"
