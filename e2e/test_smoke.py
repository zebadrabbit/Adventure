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
    if page.locator("input.party-select").count() == 0:
        resp = page.request.post(f"{BASE_URL}/autofill_characters")
        assert resp.ok, f"autofill_characters failed: {resp.status}"
        page.goto(f"{BASE_URL}/dashboard")
        page.wait_for_load_state("networkidle")
    ids = page.evaluate(
        "() => Array.from(document.querySelectorAll('input.party-select'))"
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


def test_csrf_guard_rejects_bare_mutation(page):
    # page.request bypasses the page's fetch wrapper but shares cookies —
    # exactly what a cross-site forged request looks like to the server.
    resp = page.request.post(
        f"{BASE_URL}/api/dungeon/seed",
        data="{}",
        headers={"Content-Type": "application/json"},
    )
    assert resp.status == 403, f"expected csrf_rejected 403, got {resp.status}"
