import json

from app import db
from app.models import CharacterStatusEffect
from app.models.models import Character, User
from app.services import combat_service


def _give_character_poison(auth_client, remaining=3, damage=4):
    # The test DB is shared across the whole suite (no per-test isolation by
    # default), and many other tests create their own "Hero"-named character
    # under randomly-generated usernames. `Character.query.filter_by(name=
    # "Hero").first()` is therefore non-deterministic -- it can return some
    # unrelated, possibly-dead character from a different test/user instead of
    # the "tester" user's own character that `auth_client` actually logged in
    # as. Scope the lookup through the "tester" user to make it deterministic.
    user = User.query.filter_by(username="tester").first()
    assert user is not None
    char = Character.query.filter_by(name="Hero", user_id=user.id).first()
    assert char is not None
    # Clear any poison left over from a previous test in this file (the shared
    # test DB is not reset between tests by default), so each test starts from
    # exactly one known poison effect instead of accumulating stacked rows.
    CharacterStatusEffect.query.filter_by(character_id=char.id, name="poison").delete()
    db.session.add(
        CharacterStatusEffect(
            character_id=char.id, name="poison", remaining=remaining, data=json.dumps({"damage": damage})
        )
    )
    db.session.commit()
    return char


def test_persisted_poison_loads_into_combat_snapshot(auth_client):
    char = _give_character_poison(auth_client)

    session = combat_service.start_session(
        user_id=char.user_id,
        monster={"name": "Rat", "hp": 10, "armor": 0, "speed": 5, "xp": 5},
    )

    party = json.loads(session.party_snapshot_json)
    member = next(m for m in party["members"] if m.get("char_id") == char.id)
    assert any(e["name"] == "poison" for e in member.get("effects", []))


def test_poison_damages_player_on_their_turn(auth_client):
    char = _give_character_poison(auth_client, remaining=3, damage=4)

    session = combat_service.start_session(
        user_id=char.user_id,
        monster={"name": "Rat", "hp": 10, "armor": 0, "speed": 5, "xp": 5},
    )
    party = json.loads(session.party_snapshot_json)
    member = next(m for m in party["members"] if m.get("char_id") == char.id)
    # auth_client clears any persisted current-hp each test, so the combat
    # snapshot's hp (derived fresh from max_hp) is the authoritative starting
    # point here -- char.stats itself has no "hp" key to read at this point.
    starting_hp = member["hp"]

    skip_result = combat_service._skip_if_unconscious(session, party, char.id)

    assert skip_result is None  # character is conscious, not skipped
    member = next(m for m in party["members"] if m.get("char_id") == char.id)
    assert member["hp"] == starting_hp - 4


def test_remaining_poison_persists_after_combat_ends(auth_client):
    char = _give_character_poison(auth_client, remaining=10, damage=1)

    session = combat_service.start_session(
        user_id=char.user_id,
        monster={"name": "Rat", "hp": 10, "armor": 0, "speed": 5, "xp": 5},
    )
    combat_service.player_flee(session.id, char.user_id, session.version, actor_id=char.id)

    # Flee has a 50% chance; retry a few times against fresh sessions if it failed.
    reloaded = combat_service._load_session(session.id)
    attempts = 0
    while reloaded.status != "complete" and attempts < 20:
        session = combat_service.start_session(
            user_id=char.user_id,
            monster={"name": "Rat", "hp": 10, "armor": 0, "speed": 5, "xp": 5},
        )
        combat_service.player_flee(session.id, char.user_id, session.version, actor_id=char.id)
        reloaded = combat_service._load_session(session.id)
        attempts += 1
    assert reloaded.status == "complete"

    remaining_effect = CharacterStatusEffect.query.filter_by(character_id=char.id, name="poison").first()
    assert remaining_effect is not None
    assert remaining_effect.remaining > 0
    # The persisted remaining count must reflect in-combat ticks (started at 10),
    # not just "the original pre-combat row was never touched" -- at least one
    # turn of combat happened before fleeing succeeded.
    assert remaining_effect.remaining < 10
