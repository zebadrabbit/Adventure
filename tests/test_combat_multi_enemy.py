"""Combat phase 1: an encounter fields a pack, not exactly one monster.

`monsters_json` is the source of truth; `monster_json`/`monster_hp` survive as a
denormalised view of the first entry so readers that predate multi-enemy keep
working. Dead monsters are tombstoned in the initiative list rather than removed,
because `active_index` is persisted and echoed to the client -- filtering would
change what a stale index means.
"""

import json

import pytest
from werkzeug.security import generate_password_hash

from app import db
from app.models.models import Character, CombatSession, User
from app.services import combat_service


@pytest.fixture()
def party(test_app):
    user = User.query.filter_by(username="packparty").first()
    if not user:
        user = User(username="packparty", password=generate_password_hash("pw"))
        db.session.add(user)
        db.session.commit()
    if not Character.query.filter_by(user_id=user.id).first():
        for i in range(2):
            db.session.add(
                Character(
                    user_id=user.id,
                    name=f"Packer{i}",
                    stats=json.dumps({"str": 10, "dex": 10, "int": 10, "con": 10, "mana": 30}),
                    gear="{}",
                    items="[]",
                )
            )
        db.session.commit()
    return user


def _mob(name, hp=20, xp=10, speed=1):
    return {"slug": name.lower(), "name": name, "level": 1, "hp": hp, "damage": 3, "speed": speed, "xp": xp}


# ------------------------------------------------------------------ the model


def test_a_pack_is_persisted_with_stable_ids(party):
    session = combat_service.start_session(party.id, [_mob("Goblin"), _mob("Orc"), _mob("Kobold")])

    monsters = combat_service._monsters(session)
    assert [m["id"] for m in monsters] == [0, 1, 2]
    assert [m["name"] for m in monsters] == ["Goblin", "Orc", "Kobold"]
    # The legacy pair is a view of the first entry, so old readers still work.
    assert session.monster()["name"] == "Goblin"
    assert session.monster_hp == 20


def test_a_bare_dict_still_starts_a_session(party):
    """encounters.py and ~50 test call sites pass one monster, not a list."""
    session = combat_service.start_session(party.id, _mob("Lone Goblin"))

    monsters = combat_service._monsters(session)
    assert len(monsters) == 1 and monsters[0]["id"] == 0
    assert session.monster()["name"] == "Lone Goblin"


def test_initiative_carries_one_entry_per_monster(party):
    session = combat_service.start_session(party.id, [_mob("A"), _mob("B"), _mob("C")])

    initiative = json.loads(session.initiative_json)
    monster_ids = sorted(e["id"] for e in initiative if e["type"] == "monster")
    assert monster_ids == [0, 1, 2], initiative


def test_a_legacy_session_still_works(party):
    """Rows written before monsters_json existed have it NULL, and their
    initiative monster entry carries `"id": None` -- monster.get("id") on a spawn
    payload has always been None. If either is mishandled, every combat live at
    deploy time hangs on a monster turn nobody can drive."""
    session = combat_service.start_session(party.id, _mob("Ghost", hp=7))
    session.monsters_json = None
    initiative = json.loads(session.initiative_json)
    for e in initiative:
        if e["type"] == "monster":
            e["id"] = None
    session.initiative_json = json.dumps(initiative)
    db.session.commit()

    monsters = combat_service._monsters(session)
    assert len(monsters) == 1
    assert monsters[0]["hp"] == 7
    assert combat_service._monster_ref(monsters, None) is monsters[0]

    # And the engine can still resolve whose turn it is.
    session.active_index = next(i for i, e in enumerate(initiative) if e["type"] == "monster")
    assert combat_service._is_monster_turn(session) is True
    assert combat_service._active_monster(session) is not None


# ------------------------------------------------------------- the turn order


def test_turn_order_steps_over_dead_monsters(party):
    session = combat_service.start_session(party.id, [_mob("A"), _mob("B"), _mob("C")])
    monsters = combat_service._monsters(session)
    monsters[1]["hp"] = 0
    combat_service._save_monsters(session, monsters)

    initiative = json.loads(session.initiative_json)
    dead_index = next(i for i, e in enumerate(initiative) if e["type"] == "monster" and e["id"] == 1)
    session.active_index = dead_index - 1 if dead_index else len(initiative) - 1

    combat_service._advance_turn(session)

    landed = json.loads(session.initiative_json)[session.active_index]
    assert not (landed["type"] == "monster" and landed["id"] == 1), "the engine stopped on a corpse"


def test_advance_turn_terminates_when_nobody_can_act(party):
    """Every player down and every monster dead: _advance_turn must return
    rather than spin. Pins that `for _ in range(len(initiative))` is the bound."""
    session = combat_service.start_session(party.id, [_mob("A"), _mob("B")])
    monsters = combat_service._monsters(session)
    for m in monsters:
        m["hp"] = 0
    combat_service._save_monsters(session, monsters)
    snapshot = json.loads(session.party_snapshot_json)
    for m in snapshot["members"]:
        m["hp"] = 0
    session.party_snapshot_json = json.dumps(snapshot)

    combat_service._advance_turn(session)  # must not hang


# ------------------------------------------------------------------ the ending


def test_combat_does_not_end_while_any_monster_lives(party, monkeypatch):
    monkeypatch.setattr(combat_service, "roll_loot", lambda monster, *a, **kw: {})
    session = combat_service.start_session(party.id, [_mob("A"), _mob("B")])
    monsters = combat_service._monsters(session)
    monsters[0]["hp"] = 0
    combat_service._save_monsters(session, monsters)

    combat_service._check_end(session)

    assert session.status == "active"
    assert session.rewards_json is None


def test_combat_ends_when_the_last_monster_falls(party, monkeypatch):
    monkeypatch.setattr(combat_service, "roll_loot", lambda monster, *a, **kw: {})
    session = combat_service.start_session(party.id, [_mob("A"), _mob("B")])
    monsters = combat_service._monsters(session)
    for m in monsters:
        m["hp"] = 0
    combat_service._save_monsters(session, monsters)

    combat_service._check_end(session)

    assert session.status == "complete"


def test_a_completed_session_is_never_resolved_twice(party, monkeypatch):
    """Neither end_turn endpoint refuses a completed session, and after a win
    active_index has already stepped onto a player of the same user -- so a
    second end_turn used to re-roll and re-grant the whole loot table."""
    calls = []

    def _roll(monster, *a, **kw):
        calls.append(monster.get("name"))
        return {}

    monkeypatch.setattr(combat_service, "roll_loot", _roll)
    session = combat_service.start_session(party.id, _mob("Solo"))
    session.monster_hp = 0

    combat_service._check_end(session)
    combat_service._check_end(session)

    assert calls == ["Solo"], f"loot rolled {len(calls)} times: {calls}"


def test_xp_is_summed_across_the_pack(party, monkeypatch):
    monkeypatch.setattr(combat_service, "roll_loot", lambda monster, *a, **kw: {})
    session = combat_service.start_session(party.id, [_mob("A", xp=10), _mob("B", xp=30)])
    monsters = combat_service._monsters(session)
    for m in monsters:
        m["hp"] = 0
    combat_service._save_monsters(session, monsters)

    combat_service._check_end(session)

    rewards = json.loads(session.rewards_json or "{}")
    assert rewards.get("xp", {}).get("total") == 40, rewards


def test_two_monsters_dropping_the_same_slug_grant_both(party, monkeypatch):
    monkeypatch.setattr(combat_service, "roll_loot", lambda monster, *a, **kw: {"items": {"potion-heal-l1": 1}})
    session = combat_service.start_session(party.id, [_mob("A"), _mob("B")])
    monsters = combat_service._monsters(session)
    for m in monsters:
        m["hp"] = 0
    combat_service._save_monsters(session, monsters)

    combat_service._check_end(session)

    rewards = json.loads(session.rewards_json or "{}")
    assert rewards.get("items", {}).get("potion-heal-l1") == 2, rewards


def test_an_items_list_only_roll_still_falls_back(party, monkeypatch):
    """roll_loot returns drops twice; the grant is an if/elif chain that must
    consume exactly one. Synthesising `items` from an `items_list`-only roll
    would make the fallback branch unreachable again."""
    monkeypatch.setattr(
        combat_service, "roll_loot", lambda monster, *a, **kw: {"items_list": [{"slug": "potion-heal-l1"}]}
    )
    session = combat_service.start_session(party.id, [_mob("A"), _mob("B")])
    monsters = combat_service._monsters(session)
    for m in monsters:
        m["hp"] = 0
    combat_service._save_monsters(session, monsters)

    combat_service._check_end(session)

    rewards = json.loads(session.rewards_json or "{}")
    assert "items" not in rewards, f"items was synthesised, killing the fallback branch: {rewards}"
    assert len(rewards.get("items_list", [])) == 2, rewards


# ------------------------------------------------------------------ targeting


def test_an_attack_can_name_its_target(party):
    session = combat_service.start_session(party.id, [_mob("A", hp=50), _mob("B", hp=50)])

    combat_service._damage_monster(session, 10, target_id=1)

    monsters = combat_service._monsters(session)
    assert monsters[0]["hp"] == 50, "the wrong monster was hit"
    assert monsters[1]["hp"] == 40


def test_damage_without_a_target_hits_the_first_living_monster(party):
    session = combat_service.start_session(party.id, [_mob("A", hp=50), _mob("B", hp=50)])
    monsters = combat_service._monsters(session)
    monsters[0]["hp"] = 0
    combat_service._save_monsters(session, monsters)

    combat_service._damage_monster(session, 10)

    after = combat_service._monsters(session)
    assert after[1]["hp"] == 40, "damage went to a corpse"


def test_damage_to_a_dead_target_falls_through_to_a_living_one(party):
    session = combat_service.start_session(party.id, [_mob("A", hp=50), _mob("B", hp=50)])
    monsters = combat_service._monsters(session)
    monsters[1]["hp"] = 0
    combat_service._save_monsters(session, monsters)

    combat_service._damage_monster(session, 10, target_id=1)

    after = combat_service._monsters(session)
    assert after[0]["hp"] == 40, "damage was spent on a corpse"


def test_a_session_row_keeps_the_legacy_columns_in_step(party):
    session = combat_service.start_session(party.id, [_mob("A", hp=50), _mob("B", hp=50)])

    combat_service._damage_monster(session, 15, target_id=0)
    db.session.commit()

    fresh = db.session.get(CombatSession, session.id)
    assert fresh.monster_hp == 35, "the denormalised view drifted from the list"
    assert fresh.monster()["hp"] == 35
