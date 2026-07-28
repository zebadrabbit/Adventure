"""Dungeon difficulty must not chase the party's level mid-run.

Playtest finding (2026-07-27): "going down stairs made the mobs go from lvl 1
to lvl 3 and destroyed me". Spawn levels were the party's *current* average,
read fresh the first time each floor was mapped, with elites at +1 and bosses
at +2. Levelling up on floor 0 therefore made floor 1 generate harder than it
would otherwise have been -- the world scaled with the party instead of the
party outgrowing the world, so getting stronger never felt like getting
stronger.

Difficulty is now anchored to the party's level at the moment the run started,
plus a step per floor descended.
"""

import json

import pytest

from app import db
from app.models.models import Character, GameConfig, User
from app.routes.dungeon_api import difficulty_config, floor_monster_level
from tests.factories import create_instance, create_user


@pytest.fixture(autouse=True)
def _default_step():
    GameConfig.query.filter_by(key="difficulty").delete()
    db.session.commit()
    yield
    GameConfig.query.filter_by(key="difficulty").delete()
    db.session.commit()


def _anchored_instance(user, seed, anchor, floor=0):
    inst = create_instance(user, seed=seed)
    inst.dungeon_metadata = {"party_level_at_entry": anchor}
    inst.pos_z = floor
    db.session.commit()
    return inst


def test_difficulty_steps_up_per_floor(test_app):
    user = create_user("curve_step")
    inst = _anchored_instance(user, 8001, anchor=3)
    step = int(difficulty_config()["floor_level_step"])

    levels = []
    for floor in range(3):
        inst.pos_z = floor
        db.session.commit()
        levels.append(floor_monster_level(inst))

    assert levels == [3, 3 + step, 3 + 2 * step]


def test_levelling_up_mid_run_does_not_raise_difficulty(test_app):
    """The exact reported bug."""
    user = create_user("curve_levelup")
    char = Character(
        user_id=user.id,
        name="Climber",
        stats=json.dumps({"str": 10, "con": 10}),
        gear="{}",
        items="[]",
        level=1,
    )
    db.session.add(char)
    db.session.commit()

    inst = _anchored_instance(user, 8002, anchor=1, floor=1)
    before = floor_monster_level(inst)

    # The party grinds floor 0 and gains several levels.
    char.level = 9
    db.session.commit()

    assert floor_monster_level(inst) == before, "descending after levelling must not scale the world up"


def test_missing_anchor_is_computed_once_and_then_frozen(test_app):
    """Instances created before the anchor existed must stop drifting too."""
    user = create_user("curve_legacy")
    char = Character(
        user_id=user.id,
        name="Veteran",
        stats=json.dumps({"str": 10, "con": 10}),
        gear="{}",
        items="[]",
        level=6,
    )
    db.session.add(char)
    db.session.commit()

    inst = create_instance(user, seed=8003)
    inst.dungeon_metadata = {}
    inst.pos_z = 0
    db.session.commit()

    first = floor_monster_level(inst)
    assert first == 6
    assert (inst.dungeon_metadata or {}).get("party_level_at_entry") == 6

    char.level = 20
    db.session.commit()
    assert floor_monster_level(inst) == first, "the anchor must be written once, not recomputed"


def test_step_is_tunable(test_app):
    user = create_user("curve_tunable")
    inst = _anchored_instance(user, 8004, anchor=5, floor=2)
    assert floor_monster_level(inst) == 7

    GameConfig.set("difficulty", json.dumps({"floor_level_step": 3}))
    assert floor_monster_level(inst) == 11


def test_entering_a_run_records_the_anchor(client, test_app):
    """The dashboard is where a run's difficulty gets pinned."""
    from werkzeug.security import generate_password_hash

    user = User(username="curve_entry", password=generate_password_hash("pw"))
    db.session.add(user)
    db.session.commit()
    for name, level in (("A", 4), ("B", 6)):
        db.session.add(
            Character(
                user_id=user.id,
                name=name,
                stats=json.dumps({"str": 10, "con": 10}),
                gear="{}",
                items="[]",
                level=level,
            )
        )
    db.session.commit()
    party_ids = [c.id for c in Character.query.filter_by(user_id=user.id).all()]

    with client.session_transaction() as sess:
        sess["_user_id"] = str(user.id)
        sess["user_id"] = user.id

    resp = client.post(
        "/dashboard",
        data={"form": "start_adventure", "party_ids": [str(i) for i in party_ids], "difficulty_tier": 1},
        follow_redirects=True,
    )
    assert resp.status_code == 200

    with client.session_transaction() as sess:
        inst_id = sess["dungeon_instance_id"]
    from app.models.dungeon_instance import DungeonInstance

    inst = db.session.get(DungeonInstance, inst_id)
    assert (inst.dungeon_metadata or {}).get("party_level_at_entry") == 5  # (4 + 6) // 2
