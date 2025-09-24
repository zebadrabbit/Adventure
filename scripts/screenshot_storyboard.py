#!/usr/bin/env python3
import os
import sys
import time
import subprocess
from datetime import datetime
from urllib.parse import urlencode

from playwright.sync_api import sync_playwright

BASE_URL = os.environ.get("ADVENTURE_BASE_URL", "http://localhost:5000")
USERNAME = os.environ.get("ADVENTURE_DEMO_USER", f"demo_{int(time.time())}")
PASSWORD = os.environ.get("ADVENTURE_DEMO_PASS", "demo12345")


def out_dir():
    root = os.path.join(os.getcwd(), "instance", "screenshots", f"storyboard-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}")
    os.makedirs(root, exist_ok=True)
    return root


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


def start_server_if_needed(page):
    if wait_for_server(page, timeout_sec=1):
        return None
    python_exe = sys.executable or "python"
    try:
        proc = subprocess.Popen(
            [python_exe, "run.py"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        return None
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
    page.goto(f"{BASE_URL}/register")
    try:
        page.fill('input[name="username"]', USERNAME)
        page.fill('input[name="password"]', PASSWORD)
        page.click('button[type="submit"]')
        page.wait_for_load_state('networkidle')
        if page.url.endswith('/register'):
            raise RuntimeError('register failed (likely exists)')
    except Exception:
        page.goto(f"{BASE_URL}/login")
        page.fill('input[name="username"]', USERNAME)
        page.fill('input[name="password"]', PASSWORD)
        page.click('button[type="submit"]')
        page.wait_for_load_state('networkidle')


def ensure_characters_and_party(page):
    page.goto(f"{BASE_URL}/dashboard")
    page.wait_for_load_state('networkidle')
    # Create up to 4 via autofill if none present
    try:
        cards = page.locator('.character-card')
        if cards.count() == 0:
            page.request.post(f"{BASE_URL}/autofill_characters")
            page.goto(f"{BASE_URL}/dashboard")
            page.wait_for_load_state('networkidle')
    except Exception:
        pass
    # Collect ids and post start adventure
    try:
        ids = page.evaluate('''() => Array.from(document.querySelectorAll('input.party-select')).slice(0,4).map(el => el.getAttribute('data-id')).filter(Boolean)''')
    except Exception:
        ids = []
    if ids:
        try:
            payload = [('form','start_adventure')] + [('party_ids', i) for i in ids]
            data = urlencode(payload)
            page.request.post(f"{BASE_URL}/dashboard", data=data, headers={'Content-Type': 'application/x-www-form-urlencoded'})
        except Exception:
            pass


def wait_adventure_ready(page):
    page.goto(f"{BASE_URL}/adventure")
    page.wait_for_load_state('networkidle')
    # If redirected, re-auth and retry
    if '/login' in page.url or '/register' in page.url:
        upsert_user(page)
        ensure_characters_and_party(page)
        page.goto(f"{BASE_URL}/adventure")
        page.wait_for_load_state('networkidle')
    try:
        page.wait_for_selector('#dungeon-map', timeout=20000)
    except Exception:
        page.wait_for_selector('#dungeon-controls', timeout=5000)


def try_find_loot(page, max_steps=36):
    directions = ['#btn-move-n', '#btn-move-e', '#btn-move-s', '#btn-move-w']
    for _ in range(max_steps):
        for sel in directions:
            try:
                btn = page.locator(sel)
                if btn.is_enabled():
                    btn.click()
                    page.wait_for_timeout(150)
                    # Search enabled indicates notice marker exists
                    if page.locator('#btn-search').is_enabled():
                        return True
            except Exception:
                pass
    try:
        return page.locator('#btn-search').is_enabled()
    except Exception:
        return False


def shot(loc, page, selector=None, name='scene', full_page=False):
    ts = datetime.utcnow().strftime('%H%M%S')
    path = os.path.join(loc, f"{name}-{ts}.png")
    try:
        if selector:
            page.locator(selector).screenshot(path=path)
        else:
            page.screenshot(path=path, full_page=full_page)
        print(path)
    except Exception as e:
        print(f"[warn] screenshot failed {name}: {e}")
    return path


def main():
    out = out_dir()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        proc = start_server_if_needed(page)
        if not wait_for_server(page):
            print("Server not reachable at", BASE_URL)
            stop_server(proc)
            return

        # 01: Login page
        page.goto(f"{BASE_URL}/login")
        page.wait_for_load_state('networkidle')
        shot(out, page, selector='.auth-card', name='01-login')

        # 02: Register page
        page.goto(f"{BASE_URL}/register")
        page.wait_for_load_state('networkidle')
        shot(out, page, selector='.auth-card', name='02-register')

        # 03: Dashboard (after upsert/login)
        upsert_user(page)
        page.goto(f"{BASE_URL}/dashboard")
        page.wait_for_load_state('networkidle')
        shot(out, page, name='03-dashboard', full_page=True)

        # 04: Dashboard party selection (ensure party and show enabled Begin button)
        ensure_characters_and_party(page)
        page.goto(f"{BASE_URL}/dashboard")
        page.wait_for_load_state('networkidle')
        # Try to enable button by selecting a few checkboxes in UI (for visual)
        try:
            boxes = page.locator('input.party-select')
            count = min(4, boxes.count())
            for i in range(count):
                boxes.nth(i).check()
                page.wait_for_timeout(50)
        except Exception:
            pass
        shot(out, page, selector='#begin-adventure-form', name='04-party-form')

        # 05: Adventure initial
        wait_adventure_ready(page)
        shot(out, page, name='05-adventure-initial', full_page=True)

        # 06: Move until notice (search enabled)
        try_find_loot(page)
        shot(out, page, selector='#dungeon-controls', name='06-notice-controls')

        # 07: Search results with loot links
        try:
            if page.locator('#btn-search').is_enabled():
                page.click('#btn-search')
                page.wait_for_timeout(300)
        except Exception:
            pass
        shot(out, page, selector='#dungeon-controls', name='07-search-results')

        # 08: Tooltip over first loot link
        try:
            first_link = page.locator('.loot-link').first
            first_link.hover()
            page.wait_for_timeout(150)
        except Exception:
            pass
        shot(out, page, selector='#dungeon-controls', name='08-tooltip')

        # 09: Claim first loot link and capture confirmation
        try:
            page.locator('.loot-link').first.click()
            page.wait_for_timeout(250)
        except Exception:
            pass
        shot(out, page, selector='#dungeon-controls', name='09-claimed')

        # 10: Back to dashboard inventory
        page.goto(f"{BASE_URL}/dashboard")
        page.wait_for_load_state('networkidle')
        # Capture first character card including Inventory
        try:
            card = page.locator('.character-card').first
            path = os.path.join(out, f"10-inventory-{datetime.utcnow().strftime('%H%M%S')}.png")
            card.screenshot(path=path)
            print(path)
        except Exception as e:
            print(f"[warn] inventory screenshot failed: {e}")

        context.close()
        browser.close()
        stop_server(proc)


if __name__ == '__main__':
    main()
