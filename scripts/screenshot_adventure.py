#!/usr/bin/env python3
import os
import subprocess
import sys
import time
from datetime import datetime
from urllib.parse import urlencode

from playwright.sync_api import TimeoutError as PWTimeout
from playwright.sync_api import sync_playwright


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


BASE_URL = os.environ.get("ADVENTURE_BASE_URL", "http://localhost:5000")
USERNAME = os.environ.get("ADVENTURE_DEMO_USER", f"demo_{int(time.time())}")
PASSWORD = os.environ.get("ADVENTURE_DEMO_PASS", "demo12345")

SCREEN_DIR = os.path.join(os.getcwd(), "instance", "screenshots")
os.makedirs(SCREEN_DIR, exist_ok=True)


def start_server_if_needed(page):
    """Start the Flask server as a subprocess if BASE_URL is not reachable.

    Returns a Popen process if started, else None.
    """
    if wait_for_server(page, timeout_sec=1):
        return None
    # Start server quietly using the same interpreter as this script
    python_exe = sys.executable or "python"
    try:
        proc = subprocess.Popen(
            [python_exe, "run.py"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        return None
    # Wait until reachable
    if not wait_for_server(page, timeout_sec=30):
        try:
            proc.terminate()
        except Exception:
            pass
        return None
    return proc


def stop_server(proc):
    if not proc:
        return
    try:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()
    except Exception:
        pass


def upsert_user(page):
    # Try register first
    page.goto(f"{BASE_URL}/register")
    try:
        page.fill('input[name="username"]', USERNAME)
        page.fill('input[name="password"]', PASSWORD)
        page.click('button[type="submit"]')
        # Either redirect to login or dashboard
        page.wait_for_load_state("networkidle")
        if page.url.endswith("/register"):
            # likely validation failed (user exists) — try login
            raise PWTimeout("register failed")
    except Exception:
        # Login path
        page.goto(f"{BASE_URL}/login")
        page.fill('input[name="username"]', USERNAME)
        page.fill('input[name="password"]', PASSWORD)
        page.click('button[type="submit"]')
        page.wait_for_load_state("networkidle")


def ensure_characters_and_party(page):
    # Hit dashboard; if no characters, call autofill API
    page.goto(f"{BASE_URL}/dashboard")
    page.wait_for_load_state("networkidle")
    # Try to detect character cards
    cards = page.locator(".character-card")
    if cards.count() == 0:
        # call autofill to create up to 4 characters
        try:
            page.request.post(f"{BASE_URL}/autofill_characters")
            page.goto(f"{BASE_URL}/dashboard")
            page.wait_for_load_state("networkidle")
        except Exception:
            pass
    # Collect up to 4 character ids from checkboxes (.party-select)
    ids = []
    try:
        ids = page.evaluate(
            """() => Array.from(document.querySelectorAll('input.party-select')).slice(0,4).map(el => el.getAttribute('data-id')).filter(Boolean)"""
        )
    except Exception:
        ids = []
    # If none found, try to reload dashboard and query again
    if not ids:
        page.goto(f"{BASE_URL}/dashboard")
        page.wait_for_load_state("networkidle")
        try:
            ids = page.evaluate(
                """() => Array.from(document.querySelectorAll('input.party-select')).slice(0,4).map(el => el.getAttribute('data-id')).filter(Boolean)"""
            )
        except Exception:
            ids = []
    # Directly POST start_adventure to establish session party and dungeon instance
    if ids:
        try:
            payload = [("form", "start_adventure")] + [("party_ids", i) for i in ids]
            data = urlencode(payload)
            page.request.post(
                f"{BASE_URL}/dashboard",
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        except Exception:
            pass
    # Navigate to adventure
    page.goto(f"{BASE_URL}/adventure")
    page.wait_for_load_state("networkidle")


def navigate_to_adventure(page):
    # Try to navigate; if redirected to login, re-auth then retry party setup
    page.goto(f"{BASE_URL}/adventure")
    page.wait_for_load_state("networkidle")
    if "/login" in page.url or "/register" in page.url:
        upsert_user(page)
        ensure_characters_and_party(page)
        page.goto(f"{BASE_URL}/adventure")
        page.wait_for_load_state("networkidle")
    # Wait for map element (or controls) with longer timeout
    try:
        page.wait_for_selector("#dungeon-map", timeout=20000)
    except Exception:
        page.wait_for_selector("#dungeon-controls", timeout=5000)


def try_find_loot(page, max_steps=30):
    # Press movement buttons until Search is enabled or attempts exhausted
    directions = ["#btn-move-n", "#btn-move-e", "#btn-move-s", "#btn-move-w"]
    for i in range(max_steps):
        for sel in directions:
            try:
                btn = page.locator(sel)
                if awaitable_enabled(btn):
                    btn.click()
                    page.wait_for_timeout(150)
                    if is_search_enabled(page):
                        return True
            except Exception:
                pass
    return is_search_enabled(page)


def awaitable_enabled(locator):
    try:
        return locator.is_enabled()
    except Exception:
        return False


def is_search_enabled(page):
    try:
        return page.locator("#btn-search").is_enabled()
    except Exception:
        return False


def click_search_and_screenshot(page):
    # Click search
    try:
        if is_search_enabled(page):
            page.click("#btn-search")
            # Give time for results to render
            page.wait_for_timeout(300)
    except Exception:
        pass
    # Screenshot the controls + log panel
    ts = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    path = os.path.join(SCREEN_DIR, f"adventure-{ts}.png")
    try:
        ctrl = page.locator("#dungeon-controls")
        ctrl.screenshot(path=path)
    except Exception:
        # fallback: full page
        page.screenshot(path=path, full_page=True)
    print(path)


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        proc = start_server_if_needed(page)
        if not wait_for_server(page):
            print("Server not reachable at", BASE_URL)
            stop_server(proc)
            return
        upsert_user(page)
        ensure_characters_and_party(page)
        navigate_to_adventure(page)
        try_find_loot(page)
        click_search_and_screenshot(page)
        context.close()
        browser.close()
        stop_server(proc)


if __name__ == "__main__":
    main()
