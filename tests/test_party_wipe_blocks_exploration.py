"""A full party wipe must stop dungeon exploration, not just end combat.

Combat already correctly marks every character is_dead=True on a full wipe
(combat_service.resolve_party_defeat_if_any). But nothing in the dungeon
movement path checked that — players could keep walking around after losing.
"""

import pytest

from app import db
from app.models.models import Character


@pytest.fixture(autouse=True)
def _revive_shared_tester_character(auth_client):
    """auth_client's "tester" character/user persists across the whole shared
    session DB. Tests in this module mark it is_dead=True; revive it both
    before (in case a prior test left it dead) and after (so later test
    files in the same run aren't affected)."""

    def _revive():
        with auth_client.session_transaction() as sess:
            party_ids = sess.get("last_party_ids") or []
        if party_ids:
            for c in Character.query.filter(Character.id.in_(party_ids)).all():
                c.is_dead = False
            db.session.commit()

    _revive()
    yield
    _revive()


def _mark_party_dead(auth_client):
    with auth_client.session_transaction() as sess:
        party_ids = sess["last_party_ids"]
        # adventure() reads session['party'] (not last_party_ids) to decide whether a
        # party is selected at all; populate it so we exercise the wipe check itself
        # rather than the unrelated "no party selected" redirect.
        sess["party"] = [{"id": pid, "name": "Hero", "hp": 0, "hp_max": 100, "class": "fighter"} for pid in party_ids]
    chars = Character.query.filter(Character.id.in_(party_ids)).all()
    for c in chars:
        c.is_dead = True
    db.session.commit()
    return party_ids


def test_dungeon_move_blocked_after_party_wipe(auth_client):
    _mark_party_dead(auth_client)
    r = auth_client.post("/api/dungeon/move", json={"dir": "n"})
    data = r.get_json()
    assert data.get("error") == "party_defeated", data
    assert data.get("moved") is not True, data


def test_dungeon_move_still_works_when_party_alive(auth_client):
    # Sanity check: the new guard doesn't block normal movement.
    r = auth_client.post("/api/dungeon/move", json={"dir": "n"})
    data = r.get_json()
    assert data.get("error") != "party_defeated", data


def test_adventure_page_redirects_after_party_wipe(auth_client):
    _mark_party_dead(auth_client)
    r = auth_client.get("/adventure", follow_redirects=False)
    assert r.status_code in (301, 302, 303, 307, 308), (r.status_code, r.get_data(as_text=True)[:200])
    assert "/dashboard" in (r.headers.get("Location") or "")
