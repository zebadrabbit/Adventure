"""Equipment cannot be changed mid-fight.

Rules set 2026-07-28: weapon swaps are allowed in combat but cost an action;
armour swaps are not allowed at all; item use is allowed and costs an action;
everything else is out-of-combat only.

`inventory_api.equip_item` and `unequip_item` had no combat guard whatsoever, so
a character could swap armour -- or anything -- during a fight, unlimited and
free, straight through the API. Weapons are locked here too, deliberately: a
swap is meant to cost an action and this endpoint cannot charge one, so allowing
it would be a free swap-to-best-weapon-every-turn exploit, which is worse than
not allowing it at all. Weapon swapping returns as a combat action in phase 1 of
the combat work.

Out of combat nothing changes: equip, unequip and trading all behave as before.
"""

import json

import pytest

from app import db
from app.models.models import Character, CombatSession, Item, User


@pytest.fixture()
def armoured(client, test_app):
    from werkzeug.security import generate_password_hash

    user = User.query.filter_by(username="equip_lock_user").first()
    if not user:
        user = User(username="equip_lock_user", password=generate_password_hash("pw"))
        db.session.add(user)
        db.session.commit()
    Character.query.filter_by(user_id=user.id).delete()
    CombatSession.query.filter_by(user_id=user.id).delete()
    db.session.commit()

    for slug, name, itype in (("_lock_armour", "Test Mail", "armor"), ("_lock_blade", "Test Blade", "weapon")):
        if not Item.query.filter_by(slug=slug).first():
            db.session.add(
                Item(
                    slug=slug,
                    name=name,
                    type=itype,
                    description="fixture",
                    value_copper=100,
                    level=1,
                    rarity="common",
                    weight=1.0,
                )
            )
    db.session.commit()

    char = Character(
        user_id=user.id,
        name="Bracer",
        stats=json.dumps({"str": 14, "dex": 10, "con": 12, "int": 10}),
        gear=json.dumps({}),
        items=json.dumps(["_lock_armour", "_lock_blade"]),
        level=3,
    )
    db.session.add(char)
    db.session.commit()

    with client.session_transaction() as sess:
        sess["_user_id"] = str(user.id)
        sess["user_id"] = user.id
    return user, char


def _start_combat(user):
    row = CombatSession(
        user_id=user.id,
        monster_json=json.dumps({"slug": "m", "name": "M", "hp": 10}),
        status="active",
        party_snapshot_json=json.dumps({"members": []}),
        monster_hp=10,
    )
    db.session.add(row)
    db.session.commit()
    return row


# ------------------------------------------------------------ out of combat


def test_equipping_works_normally_outside_combat(client, armoured):
    user, char = armoured

    resp = client.post(f"/api/characters/{char.id}/equip", json={"slug": "_lock_armour"})

    assert resp.status_code == 200, resp.get_json()
    db.session.refresh(char)
    assert "_lock_armour" in json.dumps(char.gear)


def test_unequipping_works_normally_outside_combat(client, armoured):
    user, char = armoured
    assert client.post(f"/api/characters/{char.id}/equip", json={"slug": "_lock_armour"}).status_code == 200

    resp = client.post(f"/api/characters/{char.id}/unequip", json={"slot": "chest"})

    assert resp.status_code == 200, resp.get_json()


# ---------------------------------------------------------------- in combat


def test_armour_cannot_be_equipped_during_a_fight(client, armoured):
    """The loophole: unlimited free armour swapping mid-combat."""
    user, char = armoured
    _start_combat(user)

    resp = client.post(f"/api/characters/{char.id}/equip", json={"slug": "_lock_armour"})

    assert resp.status_code == 400
    assert resp.get_json()["error"] == "in_combat"


def test_weapons_cannot_be_swapped_through_the_inventory_api_during_a_fight(client, armoured):
    """Allowed as a combat action later; free through this endpoint is an exploit."""
    user, char = armoured
    _start_combat(user)

    resp = client.post(f"/api/characters/{char.id}/equip", json={"slug": "_lock_blade"})

    assert resp.status_code == 400
    assert resp.get_json()["error"] == "in_combat"


def test_armour_cannot_be_removed_during_a_fight(client, armoured):
    """Unequipping is the same exploit wearing a different hat."""
    user, char = armoured
    assert client.post(f"/api/characters/{char.id}/equip", json={"slug": "_lock_armour"}).status_code == 200
    _start_combat(user)

    resp = client.post(f"/api/characters/{char.id}/unequip", json={"slot": "chest"})

    assert resp.status_code == 400
    assert resp.get_json()["error"] == "in_combat"


def test_gear_is_unchanged_after_a_refused_swap(client, armoured):
    user, char = armoured
    assert client.post(f"/api/characters/{char.id}/equip", json={"slug": "_lock_armour"}).status_code == 200
    db.session.refresh(char)
    before = char.gear
    _start_combat(user)

    client.post(f"/api/characters/{char.id}/equip", json={"slug": "_lock_blade"})

    db.session.refresh(char)
    assert char.gear == before, "a refused swap still changed the character's gear"


def test_a_finished_fight_releases_the_lock(client, armoured):
    user, char = armoured
    combat = _start_combat(user)
    assert client.post(f"/api/characters/{char.id}/equip", json={"slug": "_lock_armour"}).status_code == 400

    combat.status = "complete"
    db.session.commit()

    resp = client.post(f"/api/characters/{char.id}/equip", json={"slug": "_lock_armour"})
    assert resp.status_code == 200, resp.get_json()


def test_another_users_fight_does_not_lock_your_gear(client, armoured, test_app):
    """The lock is scoped to the owner, not to combat existing anywhere."""
    from werkzeug.security import generate_password_hash

    user, char = armoured
    stranger = User.query.filter_by(username="equip_lock_stranger").first()
    if not stranger:
        stranger = User(username="equip_lock_stranger", password=generate_password_hash("pw"))
        db.session.add(stranger)
        db.session.commit()
    _start_combat(stranger)

    resp = client.post(f"/api/characters/{char.id}/equip", json={"slug": "_lock_armour"})

    assert resp.status_code == 200, resp.get_json()
