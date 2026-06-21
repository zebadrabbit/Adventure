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


def setup_extraction_state(char_id):
    """Direct DB setup: the extraction modal only lists characters whose
    `locked_dungeon_id` is set, which the app only does on character death
    (see extraction_service.handle_character_death). Under normal play with
    no deaths, the modal legitimately shows "No characters in dungeon" --
    to get a representative screenshot of the populated modal we mark one
    party character as dead-and-locked, exactly as real combat death does.
    """
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from app import create_app, db
    from app.models.dungeon_instance import DungeonInstance
    from app.models.models import Character
    from app.services import extraction_service

    app = create_app()
    with app.app_context():
        char = db.session.get(Character, char_id)
        if char is None:
            print("[warn] extraction setup: character not found")
            return
        instance = DungeonInstance.query.filter_by(user_id=char.user_id).order_by(DungeonInstance.id.desc()).first()
        if instance is None:
            print("[warn] extraction setup: no dungeon instance found")
            return
        extraction_service.handle_character_death(char, instance)
        db.session.commit()


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
        # Note: SkillTreeSystem.switchTree() is `async` and reads
        # `event.target` *after* an `await fetch(...)` -- by then the
        # browser has already cleared the legacy `window.event` it relied
        # on (only valid synchronously during real dispatch), so every
        # click on a `.tree-selector-btn` throws inside switchTree and is
        # swallowed by its own try/catch, leaving #skillTreeCanvas always
        # empty. This is a pre-existing app bug (app/static/js/skill-tree.js
        # ~line 119), out of scope to fix here. Work around it for the
        # screenshot by driving the same internal calls switchTree() would
        # make, skipping its broken `event.target` line. Picks whichever
        # tree has the most skills, for the most illustrative capture.
        if ids:
            try:
                page.locator(f'.btn-skill-panel[data-char-id="{ids[0]}"]').click()
                page.wait_for_timeout(400)
                page.evaluate(
                    """async () => {
                        const sys = skillTreeSystem;
                        let bestTreeId = null, bestSkills = [];
                        for (const tree of sys.skillTrees) {
                            const resp = await fetch(`/api/skill-trees/${tree.id}/skills`);
                            const skills = await resp.json();
                            if (skills.length > bestSkills.length) {
                                bestSkills = skills;
                                bestTreeId = tree.id;
                            }
                        }
                        sys.currentTreeId = bestTreeId;
                        sys.skills = bestSkills;
                        sys.renderSkillTree();
                    }"""
                )
                page.wait_for_timeout(400)
                shot(page, "skill-tree-modal", selector="#skillTreeCanvas")
            except Exception as e:
                print(f"[warn] skill tree screenshot failed: {e}")

        # 3: Hoard modal
        try:
            page.goto(f"{BASE_URL}/dashboard")
            page.wait_for_load_state("networkidle")
            page.locator("#hub-tab-hoard").click()
            page.wait_for_timeout(300)
            page.locator(".btn-hoard-open").click()
            page.wait_for_timeout(400)
            shot(page, "hoard-modal", full_page=False)
        except Exception as e:
            print(f"[warn] hoard screenshot failed: {e}")

        # 4: Extraction modal (requires an active dungeon instance, which
        # ensure_characters_and_party's start_adventure call established,
        # plus at least one character locked into it -- the app only sets
        # that on death, so setup_extraction_state marks one party member
        # dead-and-locked to produce a representative, populated modal).
        try:
            if ids:
                setup_extraction_state(int(ids[0]))
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
