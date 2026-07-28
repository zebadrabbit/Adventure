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

import os
import time

import pytest

pytestmark = pytest.mark.skipif(os.getenv("E2E") != "1", reason="E2E=1 not set")

playwright_sync = pytest.importorskip("playwright.sync_api")

BASE_URL = os.environ.get("ADVENTURE_BASE_URL", "http://localhost:5000")
USERNAME = f"e2e_smoke_{int(time.time())}"
PASSWORD = "e2e-smoke-pass-1"


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
    """
    page.set_viewport_size({"width": 1366, "height": 768})
    page.goto(f"{BASE_URL}/adventure")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(500)  # let centerOnPlayer settle

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

            return { panelCount: panels.length, onParty, pairOverlaps };
        }"""
    )

    # A sanity floor on panel discovery itself: if this drops to 0 the
    # selector broke (e.g. the HUD markup moved out of .adv-hud) and the
    # checks below would vacuously pass.
    assert result["panelCount"] >= 3, f"HUD panel discovery found too few panels: {result}"
    assert not result["onParty"], f"these panels are sitting on the party: {result['onParty']}"
    assert not result["pairOverlaps"], f"these HUD panels overlap each other: {result['pairOverlaps']}"


def test_csrf_guard_rejects_bare_mutation(page):
    # page.request bypasses the page's fetch wrapper but shares cookies —
    # exactly what a cross-site forged request looks like to the server.
    resp = page.request.post(
        f"{BASE_URL}/api/dungeon/seed",
        data="{}",
        headers={"Content-Type": "application/json"},
    )
    assert resp.status == 403, f"expected csrf_rejected 403, got {resp.status}"
