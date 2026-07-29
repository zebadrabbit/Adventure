"""Procedural gear can be equipped, by uid.

Gear instances live in `items` as dicts carrying a `uid`, and equip_item's
gear-instance path triggers only on a uid in the request body. The dungeon's
old panel posted {slug, slot} with no uid branch, so an instance fell to the
legacy path, found no catalogue row for its generated slug, and 404'd --
nothing the dungeon dropped could be equipped until the player extracted.

This covers the server half. That the dungeon's panel now sends a uid is a
browser concern, checked in e2e and by hand.

Spec: docs/superpowers/specs/2026-07-28-character-panel-redesign.md
"""

import json
import random

import pytest

from app import db
from app.loot.generator import generate_item
from app.models.models import Character, User


@pytest.fixture()
def character_with_loot(client):
    from werkzeug.security import generate_password_hash

    user = User.query.filter_by(username="uid_equip_user").first()
    if not user:
        user = User(username="uid_equip_user", password=generate_password_hash("pw"))
        db.session.add(user)
        db.session.commit()
    Character.query.filter_by(user_id=user.id).delete()
    db.session.commit()

    instance = generate_item(level=3, rarity="common", slot="hands", rng=random.Random(1234))
    char = Character(
        user_id=user.id,
        name="Looter",
        stats=json.dumps({"str": 10, "con": 12, "int": 10, "hp": 20, "mana": 8}),
        gear="{}",
        items=json.dumps([instance]),
        level=3,
    )
    db.session.add(char)
    db.session.commit()

    with client.session_transaction() as sess:
        sess["_user_id"] = str(user.id)
        sess["user_id"] = user.id
    return char, instance


def test_generated_gear_carries_a_uid_and_a_canonical_slot(character_with_loot):
    _char, instance = character_with_loot
    from app.loot.data.archetypes import SLOTS

    assert instance.get("uid"), "a procedural instance must carry a uid to be equippable"
    assert instance["slot"] in SLOTS


def test_equipping_by_uid_lands_the_item(client, character_with_loot):
    char, instance = character_with_loot

    resp = client.post(
        f"/api/characters/{char.id}/equip",
        json={"uid": instance["uid"]},
    )

    assert resp.status_code == 200, resp.get_json()
    assert resp.get_json()["slot"] == instance["slot"]

    state = client.get(f"/api/characters/{char.id}").get_json()
    assert state["gear"][instance["slot"]], "the item is not in the slot it claims"
    refreshed = db.session.get(Character, char.id)
    assert not any(
        i.get("uid") == instance["uid"] for i in json.loads(refreshed.items) if isinstance(i, dict)
    ), "the instance should have left the bag"


def test_equipping_by_slug_still_404s_for_a_generated_item(client, character_with_loot):
    """The old dungeon panel's request shape, kept as a regression marker.

    A generated slug has no catalogue row, so the legacy path cannot resolve
    it. This is exactly what the dungeon used to send.

    Note: generate_item()'s returned dict (app/loot/generator.py:322) has no
    "slug" key at all -- its identity fields are uid/base/slot/name -- so
    instance.get("slug") is always None and this falls through to the uid,
    which is exactly the shape the old dungeon panel sent (a value with no
    matching catalogue row). No adaptation from the brief's text was needed.
    """
    char, instance = character_with_loot

    resp = client.post(
        f"/api/characters/{char.id}/equip",
        json={"slug": instance.get("slug") or instance["uid"], "slot": instance["slot"]},
    )

    assert resp.status_code == 404
