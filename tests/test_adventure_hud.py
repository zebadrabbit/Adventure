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
        # adventure() reads session['party'] (not last_party_ids) to decide
        # whether a party is selected at all; populate it so the route
        # renders instead of redirecting to the dashboard.
        sess["party"] = [
            {"id": c.id, "name": c.name, "class": "Fighter", "level": c.level, "hp": 20, "hp_max": 20} for c in members
        ]
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
    """Extract and Hearth are game actions with consequences, not settings.

    Checking the ids appear *somewhere* in the response would pass just as
    happily if both moved into the account dropdown, which is the exact thing
    this is meant to forbid. The account anchor renders inside <header>, so
    split there and assert against the page body alone.
    """
    html = client.get("/adventure").get_data(as_text=True)

    assert "</header>" in html, "no <header> to split on: the account anchor moved"
    chrome, _, body = html.partition("</header>")

    assert 'id="account-anchor"' in chrome, "split landed in the wrong place"
    for btn in ('id="btn-extract"', 'id="btn-hearth"'):
        assert btn in body, f"{btn} is not on the action bar"
        assert btn not in chrome, f"{btn} moved into the account menu"


def test_dashboard_still_has_full_chrome(client, party):
    """Regression: the flag must not leak to every other page."""
    html = client.get("/dashboard").get_data(as_text=True)

    assert 'id="navbarMain"' in html, "the navbar vanished from the dashboard"
    assert 'data-realm="dungeon"' not in html, "the town screens went cold"


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


def test_log_is_a_floating_collapsible_panel(client, party):
    html = client.get("/adventure").get_data(as_text=True)

    assert 'class="adv-log"' in html
    assert "<details" in html, "collapse should be the native element, not a JS toggle"
    assert 'id="dungeon-output"' in html, "adventure.js grabs the log by this id"


def test_log_keeps_the_inline_search_button_selector(client, party):
    """adventure.js:488 queries '.dungeon-output .inline-search-btn'."""
    html = client.get("/adventure").get_data(as_text=True)

    assert 'class="dungeon-output' in html


def test_action_bar_holds_the_four_game_actions(client, party):
    html = client.get("/adventure").get_data(as_text=True)

    assert 'class="adv-actions"' in html
    for btn in ("btn-search", "btn-camp", "btn-extract", "btn-hearth"):
        assert f'id="{btn}"' in html, f"{btn} fell out of the action bar"
    # btn-party-inventory was the fifth. Deleted: bags are per-character, and
    # per-character encumbrance only binds if every item sits in somebody's
    # bag, so a shared party container is the wrong model here.
    assert 'id="btn-party-inventory"' not in html, "the shared party stash came back"


def test_adventure_mounts_the_character_panel(client, party):
    html = client.get("/adventure").get_data(as_text=True)

    assert 'class="adv-character"' in html, "no mount point for the character panel"
    assert "equipment-panel.js" in html


def test_adventure_no_longer_ships_the_old_panels(client, party):
    """One paper doll, not two -- the point of this chunk."""
    html = client.get("/adventure").get_data(as_text=True)

    assert "equipment-enhanced.js" not in html
    assert "js/equipment.js" not in html


def test_bag_button_is_gone_from_the_frames(client, party):
    """Slots, doll and bag live in one panel, so the frame needs one target."""
    html = client.get("/adventure").get_data(as_text=True)

    assert "btn-bag-panel" not in html
