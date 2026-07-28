"""The adventure screen's character cards show live HP/MP.

Playtest finding (2026-07-28): "none of the character panels are updating
either, so their mana/hp is always full.. and wrong".

They were rendered from `session["party"]` -- a payload built once by
`build_party_payload` when the party was selected, then frozen in the session.
Every card therefore showed whatever the character had at selection time (full)
for the entire run, no matter what combat, poison, regeneration or camping did
to the real rows.

`/adventure` now renders from the database, and `/api/dungeon/party` serves the
same payload so the client can refresh after anything that moves those numbers.
"""

import json

import pytest

from app import db
from app.models.dungeon_instance import DungeonInstance
from app.models.models import Character, User


@pytest.fixture()
def party(client, test_app):
    from werkzeug.security import generate_password_hash

    user = User.query.filter_by(username="panel_user").first()
    if not user:
        user = User(username="panel_user", password=generate_password_hash("pw"))
        db.session.add(user)
        db.session.commit()
    Character.query.filter_by(user_id=user.id).delete()
    db.session.commit()

    members = []
    for name in ("Ava", "Bo"):
        char = Character(
            user_id=user.id,
            name=name,
            stats=json.dumps({"str": 10, "con": 12, "int": 12, "hp": 999, "mana": 999}),
            gear="{}",
            items="[]",
            level=3,
        )
        db.session.add(char)
        members.append(char)
    db.session.commit()

    instance = DungeonInstance(user_id=user.id, seed=5150, pos_x=0, pos_y=0, pos_z=0)
    db.session.add(instance)
    db.session.commit()

    with client.session_transaction() as sess:
        sess["_user_id"] = str(user.id)
        sess["user_id"] = user.id
        sess["dungeon_instance_id"] = instance.id
        sess["last_party_ids"] = [c.id for c in members]
        # A deliberately stale snapshot, exactly as the bug had it: full bars,
        # frozen at selection time.
        sess["party"] = [
            {"id": c.id, "name": c.name, "class": "Fighter", "level": 3, "hp": 9999, "hp_max": 9999} for c in members
        ]
    return user, members


def _wound(char, hp, mana):
    stats = json.loads(char.stats)
    stats["hp"] = hp
    stats["mana"] = mana
    stats["current_mana"] = mana
    char.stats = json.dumps(stats)
    db.session.add(char)
    db.session.commit()


def test_party_endpoint_reports_live_values(client, party):
    user, members = party
    _wound(members[0], hp=7, mana=2)

    resp = client.get("/api/dungeon/party")

    assert resp.status_code == 200, resp.get_json()
    payload = {m["id"]: m for m in resp.get_json()["party"]}
    assert payload[members[0].id]["hp"] == 7
    assert payload[members[0].id]["mana"] == 2
    assert payload[members[0].id]["hp_max"] > 7, "a max is still reported alongside the current value"


def test_party_endpoint_tracks_changes(client, party):
    """Two reads either side of damage must differ -- the whole point."""
    user, members = party
    before = {m["id"]: m["hp"] for m in client.get("/api/dungeon/party").get_json()["party"]}

    _wound(members[1], hp=3, mana=1)

    after = {m["id"]: m["hp"] for m in client.get("/api/dungeon/party").get_json()["party"]}
    assert after[members[1].id] == 3
    assert after[members[1].id] != before[members[1].id]


def test_party_order_follows_the_chosen_party(client, party):
    user, members = party
    ids = [m["id"] for m in client.get("/api/dungeon/party").get_json()["party"]]
    assert ids == [c.id for c in members]


def test_adventure_page_ignores_the_stale_session_snapshot(client, party):
    """The regression: the page rendered 9999 HP from a frozen session copy."""
    user, members = party
    _wound(members[0], hp=5, mana=1)

    html = client.get("/adventure").get_data(as_text=True)

    assert "9999" not in html, "the adventure page is still rendering the stale session party"
    assert "data-member-id" in html, "cards need a hook for the client refresh"


def test_party_endpoint_requires_a_party(client, test_app):
    from werkzeug.security import generate_password_hash

    lonely = User.query.filter_by(username="panel_nobody").first()
    if not lonely:
        lonely = User(username="panel_nobody", password=generate_password_hash("pw"))
        db.session.add(lonely)
        db.session.commit()
    with client.session_transaction() as sess:
        sess["_user_id"] = str(lonely.id)
        sess["user_id"] = lonely.id
        sess.pop("last_party_ids", None)
        sess.pop("party", None)

    resp = client.get("/api/dungeon/party")

    assert resp.status_code == 404
    assert resp.get_json()["party"] == []
