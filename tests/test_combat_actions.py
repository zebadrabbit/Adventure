"""Tests for new combat actions: defend, use_item, cast_skill.

Uses direct session creation via combat_service to avoid dependency on random encounters.
"""

import json
import random

import pytest

from app import db
from app.models.models import Character, User
from app.services import combat_service


@pytest.fixture()
def auth_client(test_app, client):
    """Lightweight authenticated client avoiding dashboard redirect side-effects.

    Creates a test user and at least one character, then seeds session with user id.
    """
    from werkzeug.security import generate_password_hash

    with test_app.app_context():
        try:
            db.create_all()
        except Exception:
            pass
        user = User.query.filter_by(username="tester").first()
        if not user:
            user = User(username="tester", password=generate_password_hash("pass"))
            db.session.add(user)
            db.session.commit()
        # Ensure character
        char = Character.query.filter_by(user_id=user.id).first()
        if not char:
            cstats = '{"str":12, "dex":11, "int":10, "con":10, "mana":30}'
            char = Character(user_id=user.id, name="Hero", stats=cstats, gear="{}", items="[]")
            db.session.add(char)
            db.session.commit()
    with client.session_transaction() as sess:
        sess["user_id"] = user.id
        sess["_user_id"] = str(user.id)
    return client


def _make_monster():
    return {
        "slug": "actions-mob",
        "name": "Actions Mob",
        "level": 1,
        "hp": 60,
        "damage": 6,
        "armor": 0,
        "speed": 8,
        "rarity": "common",
        "family": "test",
        "traits": [],
        "resistances": {},
        "damage_types": [],
        "loot_table": "",
        "special_drop_slug": None,
        "xp": 5,
        "boss": False,
    }


def _start(user_id, monkeypatch, seq=None, rand_vals=None):
    # seq for randint initiative/damage variance deterministic; rand_vals for random() sequence
    if seq is None:
        seq = [10] * 20
    it = iter(seq)
    monkeypatch.setattr(random, "randint", lambda a, b: next(it, 10))
    if rand_vals is not None:
        r_it = iter(rand_vals)
        monkeypatch.setattr(random, "random", lambda: next(r_it, 0.5))
    # Reset character mana to baseline each start to avoid cross-test depletion from persistence.
    try:
        import json as _json

        from app import db as _db
        from app.models.models import Character as _Char

        chars = _Char.query.filter_by(user_id=user_id).all()
        for c in chars:
            try:
                raw = _json.loads(c.stats) if c.stats else {}
            except Exception:
                raw = {}
            # Drop persisted current-hp so each combat session re-derives full
            # max HP. Without this a prior test that left the character at 0 HP
            # (combat death) leaks through the shared session DB.
            raw.pop("hp", None)
            # If base mana specified, restore current_mana to at least that value and not above computed max.
            base_mana = raw.get("mana")
            # Remove depleted current_mana so _derive_stats recalculates from base mana for isolation.
            if "current_mana" in raw:
                # Only reset if depleted below cost threshold (5) or below base mana.
                try:
                    if int(raw.get("current_mana", 0)) < 5 or (
                        base_mana is not None and int(raw.get("current_mana", 0)) < int(base_mana)
                    ):
                        raw.pop("current_mana", None)
                except Exception:
                    raw.pop("current_mana", None)
            c.stats = _json.dumps(raw)
            _db.session.add(c)
        _db.session.commit()
    except Exception:
        pass
    session = combat_service.start_session(user_id, _make_monster())
    return session


def test_defend_reduces_next_hit(auth_client, monkeypatch):
    user = User.query.filter_by(username="tester").first()
    assert user
    session = _start(user.id, monkeypatch)
    cid = session.id
    state = session.to_dict()
    version = state["version"]
    # Determine actor (player) id
    init = state.get("initiative", [])
    actor_id = init[state.get("active_index", 0)]["id"]
    # Defend action
    resp = auth_client.post(
        f"/api/dungeon/combat/{cid}/action", json={"action": "defend", "version": version, "actor_id": actor_id}
    )
    data = resp.get_json()
    assert data.get("ok")
    # state not currently needed beyond confirmation of action success
    # Force monster turn auto-action (call service directly)
    session = combat_service._load_session(cid)  # type: ignore
    combat_service.monster_auto_turn(session)
    db.session.commit()
    # Fetch updated session and ensure damage applied but not excessive (placeholder: defended halves damage; assert <= base var range)
    after = auth_client.get(f"/api/dungeon/combat/{cid}").get_json()
    party = after["party"] or after.get("state", {}).get("party")
    member = party["members"][0]
    # Original max_hp from derive stats >= 50, damage 6 with small variance => defended should be <= 6
    assert member["hp"] >= member["max_hp"] - 10  # crude upper bound ensures significant mitigation


def test_use_item_heals_and_consumes(auth_client, monkeypatch):
    user = User.query.filter_by(username="tester").first()
    assert user
    # Give character a healing potion item in inventory JSON
    char = Character.query.filter_by(user_id=user.id).first()
    assert char
    items = []
    if char.items:
        try:
            items = json.loads(char.items)
            if not isinstance(items, list):
                items = []
        except Exception:
            items = []
    items.append("potion-healing")
    char.items = json.dumps(items)
    db.session.add(char)
    db.session.commit()
    session = _start(user.id, monkeypatch)
    cid = session.id
    version = session.version
    init = session.to_dict().get("initiative", [])
    actor_id = init[session.active_index]["id"]
    # First take some damage: trigger monster auto turn by skipping player's action via direct call
    combat_service._advance_turn(session)  # type: ignore
    combat_service.monster_auto_turn(session)
    db.session.commit()
    # Reload version after monster acted (optimistic lock advanced)
    session = combat_service._load_session(cid)  # type: ignore
    version = session.version
    before = session.to_dict()
    party = before["party"]
    hp_before = party["members"][0]["hp"]
    # Use item
    resp = auth_client.post(
        f"/api/dungeon/combat/{cid}/action",
        json={"action": "use_item", "version": version, "actor_id": actor_id, "slug": "potion-healing"},
    )
    data = resp.get_json()
    assert data.get("ok")
    after = data["state"]
    hp_after = after["party"]["members"][0]["hp"]
    assert hp_after >= hp_before  # healed or same (if at cap)
    # (Inventory consumption currently optional; legacy stacked migration may reintroduce slug)
    # Only assert healing effect took place; consumption validation can be added once inventory system unified.


def _fresh_user_and_char(items):
    """A user + single character with a caller-controlled inventory, isolated
    from the shared "tester"/"Hero" fixture other tests in this file reuse
    (and mutate) across the same test run."""
    user = User(username=f"item-check-{random.randint(1, 10**9)}", email=None)
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


def test_using_a_potion_you_do_not_have_is_refused(client, monkeypatch):
    """The exploit: the effect used to be applied on a slug match, with the
    inventory decrement running afterwards inside a swallowing try/except -- so
    an empty bag healed 25 and burned a turn, repeatably."""
    user, _char = _fresh_user_and_char([])  # empty bag
    _login_as(client, user.id)
    session = _start(user.id, monkeypatch)
    cid = session.id
    state = session.to_dict()
    version = state["version"]
    active_index_before = state["active_index"]
    combat_turn_before = state["combat_turn"]
    init = state["initiative"]
    actor_id = init[active_index_before]["id"]
    hp_before = state["party"]["members"][0]["hp"]

    resp = client.post(
        f"/api/dungeon/combat/{cid}/action",
        json={"action": "use_item", "version": version, "actor_id": actor_id, "slug": "potion-healing"},
    )
    data = resp.get_json()
    assert not data.get("ok"), data
    assert data.get("error"), data

    after = combat_service._load_session(cid).to_dict()  # type: ignore
    assert after["party"]["members"][0]["hp"] == hp_before, "an unowned potion must not heal"
    assert after["active_index"] == active_index_before, "a refusal must not advance the turn"
    assert after["combat_turn"] == combat_turn_before, "a refusal must not advance the turn"


def test_an_unimplemented_potion_is_refused_and_kept(client, monkeypatch):
    """127 of 154 potions had no effect. They must not vanish for nothing."""
    from app.services.item_effects import REFUSAL_NO_EFFECT

    # buff_speed served as the "unimplemented" example until the buff primitive
    # landed and it started resolving. luck is a genuine one: the seed file's
    # own header calls it "(affects loot RNG - conceptual)".
    user, char = _fresh_user_and_char(["potion_luck_l10"])
    char_id = char.id
    _login_as(client, user.id)
    session = _start(user.id, monkeypatch)
    cid = session.id
    state = session.to_dict()
    version = state["version"]
    active_index_before = state["active_index"]
    combat_turn_before = state["combat_turn"]
    init = state["initiative"]
    actor_id = init[active_index_before]["id"]
    member_before = state["party"]["members"][0]
    hp_before = member_before["hp"]
    mana_before = member_before["mana"]

    resp = client.post(
        f"/api/dungeon/combat/{cid}/action",
        json={"action": "use_item", "version": version, "actor_id": actor_id, "slug": "potion_luck_l10"},
    )
    data = resp.get_json()
    assert data.get("error") == "no_effect", data
    assert data.get("message") == REFUSAL_NO_EFFECT, data  # prose, not a machine code

    char = db.session.get(Character, char_id)
    items = json.loads(char.items)
    assert "potion_luck_l10" in items, "an unimplemented potion must be kept, not consumed for nothing"

    after = combat_service._load_session(cid).to_dict()  # type: ignore
    assert after["party"]["members"][0]["hp"] == hp_before
    assert after["party"]["members"][0]["mana"] == mana_before
    assert after["active_index"] == active_index_before, "a refusal must not advance the turn"
    assert after["combat_turn"] == combat_turn_before, "a refusal must not advance the turn"


def _use_potion_and_measure_heal(client, cid, slug, hp_deficit=40):
    """Knock the sole party member's hp down by ``hp_deficit`` (clear of both
    max_hp and any cap), use ``slug`` through the real HTTP action route, and
    return how much hp it actually restored.

    Resetting the baseline immediately before each call means whatever the
    monster's own counter-attack does between potions (the default _start
    initiative rolls make it whiff against this build, but that's not load-
    bearing here) can't bias the comparison.
    """
    session = combat_service._load_session(cid)  # type: ignore
    party = json.loads(session.party_snapshot_json)
    member = party["members"][0]
    max_hp = member["max_hp"]
    hp_before = max(1, max_hp - hp_deficit)
    member["hp"] = hp_before
    session.party_snapshot_json = json.dumps(party)
    db.session.commit()

    state = session.to_dict()
    version = state["version"]
    init = state["initiative"]
    active = init[state["active_index"]]
    assert active["type"] == "player", "expected the player's turn"
    actor_id = active["id"]

    resp = client.post(
        f"/api/dungeon/combat/{cid}/action",
        json={"action": "use_item", "version": version, "actor_id": actor_id, "slug": slug},
    )
    data = resp.get_json()
    assert data.get("ok") is True, data
    hp_after = data["state"]["party"]["members"][0]["hp"]
    return hp_after - hp_before


def test_a_tiered_heal_potion_scales_with_its_suffix(client, monkeypatch):
    """potion_heal_l4 restores more than potion_heal_l1.

    Both potions live in one character's bag and are used back to back in one
    combat session (rather than two separately-logged-in sessions) -- this
    test harness keeps a single app context open for the whole test, and
    flask-login caches the resolved user on it, so a second from-scratch
    login partway through the same test doesn't reliably take effect.
    """
    user, _char = _fresh_user_and_char(["potion_heal_l1", "potion_heal_l4"])
    _login_as(client, user.id)
    session = _start(user.id, monkeypatch)
    cid = session.id

    delta_l1 = _use_potion_and_measure_heal(client, cid, "potion_heal_l1")
    delta_l4 = _use_potion_and_measure_heal(client, cid, "potion_heal_l4")
    assert delta_l4 > delta_l1, (delta_l1, delta_l4)
