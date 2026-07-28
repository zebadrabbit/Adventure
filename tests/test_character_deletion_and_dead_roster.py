"""Dead characters must be removable, and must never be conscripted.

Playtest finding (2026-07-27): "delete dead characters. im stuck with some in my
roster and they get auto-added."

Two separate faults:

1. `delete_character` did a bare `db.session.delete(char)`, but ten tables carry
   a foreign key to `character` and none of them cascade. Every character is
   granted a starting skill at creation, so every character had at least one
   `character_skill` row -- meaning delete raised a ForeignKeyViolation for
   essentially the entire roster. Nothing could be dismissed.

2. Party formation took "the first four characters by id", which after a wipe is
   exactly the four corpses. Permadeathed characters were auto-selected into
   parties.
"""

import json

import pytest
from sqlalchemy import text

from app import db
from app.models.models import Character, User
from app.services.character_service import OWNED_TABLES, delete_character, living_characters


@pytest.fixture()
def user(test_app):
    from werkzeug.security import generate_password_hash

    row = User.query.filter_by(username="roster_user").first()
    if not row:
        row = User(username="roster_user", password=generate_password_hash("pw"))
        db.session.add(row)
        db.session.commit()
    Character.query.filter_by(user_id=row.id).delete()
    db.session.commit()
    return row


def _character(user, name, *, permadeath=False, is_dead=False, level=1):
    char = Character(
        user_id=user.id,
        name=name,
        stats=json.dumps({"str": 10, "con": 10, "int": 10}),
        gear="{}",
        items="[]",
        level=level,
        permadeath=permadeath,
        is_dead=is_dead,
    )
    db.session.add(char)
    db.session.commit()
    return char


# ------------------------------------------------------------------ deletion


def test_delete_character_with_dependent_rows(user):
    """The regression: a character with a skill could not be deleted at all."""
    from app.models.skill import CharacterSkill, Skill, SkillTree

    char = _character(user, "Doomed")

    tree = SkillTree.query.filter_by(name="_roster_tree").first()
    if not tree:
        tree = SkillTree(name="_roster_tree", description="fixture")
        db.session.add(tree)
        db.session.commit()
    skill = Skill.query.filter_by(name="_roster_skill").first()
    if not skill:
        skill = Skill(
            tree_id=tree.id,
            name="_roster_skill",
            description="fixture",
            skill_type="active",
            effect_json=json.dumps({"damage": 3}),
        )
        db.session.add(skill)
        db.session.commit()
    db.session.add(CharacterSkill(character_id=char.id, skill_id=skill.id))
    db.session.commit()
    char_id = char.id

    result = delete_character(char)

    assert db.session.get(Character, char_id) is None
    assert result["removed"].get("character_skill") == 1
    assert CharacterSkill.query.filter_by(character_id=char_id).count() == 0


def test_delete_clears_every_owned_table(user):
    """Guard against a new FK being added without updating OWNED_TABLES."""
    char = _character(user, "Thorough")
    char_id = char.id

    delete_character(char)

    for table, column in OWNED_TABLES:
        remaining = db.session.execute(
            text(f"SELECT COUNT(*) FROM {table} WHERE {column} = :cid"), {"cid": char_id}
        ).scalar()
        assert remaining == 0, f"{table} still references the deleted character"


def test_delete_is_atomic_on_failure(user, monkeypatch):
    """A failed delete must not leave the character half-dismantled."""
    char = _character(user, "Stubborn")
    char_id = char.id

    original = db.session.delete

    def boom(obj):
        raise RuntimeError("simulated failure")

    monkeypatch.setattr(db.session, "delete", boom)
    with pytest.raises(RuntimeError):
        delete_character(char)
    monkeypatch.setattr(db.session, "delete", original)

    assert db.session.get(Character, char_id) is not None, "character vanished despite the failure"


def test_delete_route_removes_a_permadeathed_character(client, user):
    char = _character(user, "Fallen", permadeath=True, is_dead=True)
    char_id = char.id
    with client.session_transaction() as sess:
        sess["_user_id"] = str(user.id)
        sess["user_id"] = user.id

    resp = client.post(f"/delete_character/{char_id}", follow_redirects=True)

    assert resp.status_code == 200
    assert db.session.get(Character, char_id) is None


# --------------------------------------------------------------- conscription


def test_living_characters_excludes_the_permadeathed(user):
    _character(user, "Corpse1", permadeath=True)
    _character(user, "Corpse2", permadeath=True)
    alive = _character(user, "Survivor")

    living = living_characters(user.id)

    assert [c.id for c in living] == [alive.id]


def test_downed_but_not_permadeathed_characters_still_count(user):
    """is_dead is recoverable (revive/extract); permadeath is not."""
    downed = _character(user, "Downed", is_dead=True, permadeath=False)
    assert downed.id in [c.id for c in living_characters(user.id)]


def test_autofill_does_not_conscript_the_dead(client, user):
    """The exact reported behaviour: dead characters were auto-added."""
    dead = [_character(user, f"Dead{i}", permadeath=True, is_dead=True) for i in range(4)]
    with client.session_transaction() as sess:
        sess["_user_id"] = str(user.id)
        sess["user_id"] = user.id

    resp = client.post("/autofill_characters")

    # 201 when it had to recruit replacements, 200 when it merely re-selected.
    assert resp.status_code in (200, 201), resp.get_json()
    party_ids = {p["id"] for p in resp.get_json()["party"]}
    assert party_ids.isdisjoint({c.id for c in dead}), "a permadeathed character was put in the party"
    assert len(party_ids) == 4, "autofill should have recruited replacements"


def test_start_adventure_refuses_a_permadeathed_party(client, user):
    dead = _character(user, "Ghost", permadeath=True, is_dead=True)
    with client.session_transaction() as sess:
        sess["_user_id"] = str(user.id)
        sess["user_id"] = user.id

    resp = client.post(
        "/dashboard",
        data={"form": "start_adventure", "party_ids": str(dead.id)},
        follow_redirects=True,
    )

    assert resp.status_code == 200
    with client.session_transaction() as sess:
        party = sess.get("party") or []
    assert dead.id not in [p.get("id") for p in party]
