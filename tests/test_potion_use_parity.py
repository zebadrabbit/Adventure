"""A potion does the same thing in a fight and out of one.

potion-healing used to heal 25 in combat and 5 outside it, unclamped -- while a
comment in combat_service claimed the two had been aligned deliberately. And
potion_heal_lN was destroyed for zero effect out of combat, because the matcher
looked for the substring "healing" and the catalogue spells it "heal".

These tests compare the two paths against each other and against the
resolver, rather than pinning a number the resolver already owns -- so tuning
the heal table doesn't require an edit here.
"""

import json
import random

import pytest

from app import db
from app.models.models import Character, Item, User
from app.services import combat_service
from app.services.character_stats import compute_hp_mana_max
from app.services.item_effects import REFUSAL_NO_EFFECT, resolve_potion_effect


def _ensure_item(slug, item_type="potion", name=None):
    item = Item.query.filter_by(slug=slug).first()
    if item:
        return item
    item = Item(slug=slug, name=name or slug, type=item_type, description="", value_copper=10)
    db.session.add(item)
    db.session.commit()
    return item


def _simple_monster():
    return {
        "slug": "potion-parity-mob",
        "name": "Training Dummy",
        "level": 1,
        "hp": 500,
        "damage": 10,
        "armor": 0,
        "speed": 8,
        "rarity": "common",
        "family": "test",
        "traits": [],
        "resistances": {},
        "damage_types": [],
        "loot_table": "",
        "special_drop_slug": None,
        "xp": 0,
        "boss": False,
    }


def _fresh_user_and_char(items):
    user = User(username=f"potion-parity-{random.randint(1, 10**9)}", email=None)
    user.set_password("pw")
    db.session.add(user)
    db.session.commit()
    char = Character(
        user_id=user.id,
        name="Hero",
        stats=json.dumps({"str": 12, "dex": 10, "int": 10, "con": 12}),
        gear="{}",
        items=json.dumps(items),
    )
    db.session.add(char)
    db.session.commit()
    return user, char


def _login_as(client, user_id):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
        sess["_user_id"] = str(user_id)


def _start_combat(user_id, monkeypatch):
    # Constant 1 on every randint: player's initiative (speed 13 + 1 = 14)
    # still beats the monster's (speed 8 + 1 = 9), so the player acts first
    # -- and a constant 1 is also a natural-1 accuracy roll, so the monster's
    # follow-up turn (auto-progressed inside player_use_item) always misses.
    # Without that, the monster's swing after the potion is used would land
    # and corrupt the very HP delta this test is trying to isolate.
    monkeypatch.setattr(random, "randint", lambda a, b: 1)
    monkeypatch.setattr(random, "random", lambda: 0.5)
    return combat_service.start_session(user_id, _simple_monster())


@pytest.mark.parametrize("slug", ["potion_heal_l4", "potion-healing"])
def test_potion_restores_the_same_amount_in_and_out_of_combat(client, monkeypatch, slug):
    _ensure_item(slug, name=slug)
    expected = resolve_potion_effect(slug)["amount"]

    # Out of combat, through the HTTP route.
    user, char = _fresh_user_and_char([{"slug": slug, "qty": 1}])
    char_id = char.id
    stats = json.loads(char.stats)
    stats["hp"] = 1
    char.stats = json.dumps(stats)
    db.session.commit()

    _login_as(client, user.id)
    resp = client.post(f"/api/characters/{char_id}/consume", json={"slug": slug})
    assert resp.status_code == 200, resp.get_json()
    # Read the restore off the response, not a before/after diff of the
    # persisted stats: any out-of-combat action also advances the game clock,
    # which can apply its own small passive-regen tick alongside the potion's
    # effect -- a real, unrelated mechanic that would otherwise contaminate
    # this comparison. Combat pauses that clock, so the in-combat side below
    # has no such confound.
    out_of_combat_delta = resp.get_json()["effects"]["hp"]
    assert out_of_combat_delta == expected

    # In combat, through the service the fight uses. Same character, same
    # starting HP, same potion, restocked after the out-of-combat draught
    # above consumed it.
    stats = json.loads(char.stats)
    stats["hp"] = 1
    char.stats = json.dumps(stats)
    char.items = json.dumps([{"slug": slug, "qty": 1}])
    db.session.commit()

    session = _start_combat(user.id, monkeypatch)
    result = combat_service.player_use_item(session.id, user.id, session.version, slug, actor_id=char_id)
    assert result.get("ok"), result
    in_combat_delta = result["state"]["party"]["members"][0]["hp"] - 1
    assert in_combat_delta == expected

    assert in_combat_delta == out_of_combat_delta, "the two paths disagreed on what the same potion does"


def test_out_of_combat_restore_clamps_at_the_characters_max(client):
    """The other half of the old bug: out-of-combat healing didn't clamp at
    all, so a potion used near full health could push a character's stored HP
    past their real max."""
    _ensure_item("potion_heal_l20", name="potion_heal_l20")
    expected = resolve_potion_effect("potion_heal_l20")["amount"]

    user, char = _fresh_user_and_char([{"slug": "potion_heal_l20", "qty": 1}])
    char_id = char.id
    hp_max, _mana_max = compute_hp_mana_max(char)
    deficit = 3
    assert expected > deficit, "the potion must be strong enough to overshoot the deficit for this to prove anything"
    stats = json.loads(char.stats)
    stats["hp"] = hp_max - deficit
    char.stats = json.dumps(stats)
    db.session.commit()

    _login_as(client, user.id)
    resp = client.post(f"/api/characters/{char_id}/consume", json={"slug": "potion_heal_l20"})
    assert resp.status_code == 200, resp.get_json()

    char = db.session.get(Character, char_id)
    assert json.loads(char.stats)["hp"] == hp_max, "healing must clamp at the character's real max, not overshoot it"


def test_unimplemented_potion_is_refused_out_of_combat_and_stays_in_the_bag(client):
    """The regression test for the 127 potions destroyed for zero effect: a
    slug the resolver doesn't recognise must be refused, and the potion must
    still be there afterwards -- not silently removed for nothing."""
    slug = "potion_buff_speed_l3"
    _ensure_item(slug, name="Standard Swiftness Draught")
    assert resolve_potion_effect(slug) is None, "sanity check: this slug must be one the resolver refuses"

    user, char = _fresh_user_and_char([{"slug": slug, "qty": 1}])
    char_id = char.id
    _login_as(client, user.id)

    resp = client.post(f"/api/characters/{char_id}/consume", json={"slug": slug})
    data = resp.get_json()
    assert data.get("error") == "no_effect", data
    assert data.get("message") == REFUSAL_NO_EFFECT, data  # prose, not a machine code

    char = db.session.get(Character, char_id)
    items = json.loads(char.items)
    assert any(o.get("slug") == slug for o in items), "an unimplemented potion must be kept, not consumed for nothing"
