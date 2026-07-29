"""The party frame shows encumbrance, because that is where it bites.

Playtest, 2026-07-28: the player did not know the game had carry weight. It was
computed correctly and displayed only inside a panel you had to go looking for.

Past capacity a dex_penalty applies, and combat movement derives from speed
(8 + DEX // 2), so an overloaded character moves fewer squares. The player has
to see that before the fight, not during it. The weight numbers stay one click
away in the panel; the state goes on the frame.

Spec: docs/superpowers/specs/2026-07-28-character-panel-redesign.md
"""

import json

import pytest

from app import db
from app.models.dungeon_instance import DungeonInstance
from app.models.models import Character, User


@pytest.fixture()
def party(client):
    from werkzeug.security import generate_password_hash

    user = User.query.filter_by(username="enc_user").first()
    if not user:
        user = User(username="enc_user", password=generate_password_hash("pw"))
        db.session.add(user)
        db.session.commit()
    Character.query.filter_by(user_id=user.id).delete()
    db.session.commit()

    members = []
    for name in ("Light", "Heavy"):
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

    instance = DungeonInstance(user_id=user.id, seed=99, pos_x=0, pos_y=0, pos_z=0)
    db.session.add(instance)
    db.session.commit()

    with client.session_transaction() as sess:
        sess["_user_id"] = str(user.id)
        sess["user_id"] = user.id
        sess["dungeon_instance_id"] = instance.id
        sess["last_party_ids"] = [c.id for c in members]
        sess["party"] = [{"id": c.id, "name": c.name, "class": "Fighter", "level": 2} for c in members]
    return user, members


def test_party_payload_carries_encumbrance(client, party):
    user, members = party

    payload = {m["id"]: m for m in client.get("/api/dungeon/party").get_json()["party"]}

    for member in members:
        assert "encumbrance" in payload[member.id], "the frame cannot show what the payload omits"
        assert payload[member.id]["encumbrance"]["status"] in ("normal", "encumbered", "blocked")


def test_an_empty_bag_is_not_encumbered(client, party):
    user, members = party

    payload = {m["id"]: m for m in client.get("/api/dungeon/party").get_json()["party"]}

    assert payload[members[0].id]["encumbrance"]["status"] == "normal"
    assert payload[members[0].id]["encumbrance"]["dex_penalty"] == 0


def test_a_loaded_bag_reports_encumbered_with_its_penalty(client, party):
    """Load one character past capacity and leave the other alone."""
    from app.inventory.utils import compute_capacity, fetch_encumbrance_config

    user, members = party
    heavy = members[1]
    cap = compute_capacity(10, fetch_encumbrance_config())
    # One heavy stack is enough; weight per item comes from the config.
    heavy.items = json.dumps([{"slug": "iron-ingot", "qty": int(cap) * 10}])
    db.session.add(heavy)
    db.session.commit()

    payload = {m["id"]: m for m in client.get("/api/dungeon/party").get_json()["party"]}

    assert payload[heavy.id]["encumbrance"]["status"] != "normal", "an overloaded bag must show on the frame"
    assert payload[heavy.id]["encumbrance"]["dex_penalty"] > 0
    assert payload[members[0].id]["encumbrance"]["status"] == "normal", "the light character is unaffected"
