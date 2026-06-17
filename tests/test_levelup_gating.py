"""Level-up stat allocation must be gated by earned stat_points."""

import json
import uuid

import pytest

from app import db
from app.services import progression
from tests.factories import create_character, create_user


@pytest.fixture(autouse=True)
def _ensure_tables(test_app):
    # Some db_isolation tests drop/recreate the schema; ensure tables exist for these
    # (unmarked) tests regardless of ordering. create_all is idempotent.
    with test_app.app_context():
        db.create_all()


def _login(client, user):
    with client.session_transaction() as sess:
        sess["_user_id"] = str(user.id)
        sess["user_id"] = user.id


def _char(points=0):
    user = create_user("lu_" + uuid.uuid4().hex[:8])
    char = create_character(user, name="H", items=[])
    char.stat_points = points
    db.session.commit()
    return user, char


def test_grant_xp_awards_stat_points():
    from app.models.models import GameConfig

    GameConfig.set("progression", '{"stat_points_per_level": 2, "talent_points_per_level": 1}')
    _user, char = _char(0)
    progression.grant_xp(char, 300)  # -> level 2 (one level)
    db.session.commit()
    assert char.level == 2
    assert char.stat_points == 2


def test_levelup_rejects_overspend(client):
    user, char = _char(points=2)
    _login(client, user)
    resp = client.post(f"/api/characters/{char.id}/level-up", json={"stat_allocations": {"str": 5}})
    assert resp.status_code == 400, resp.get_json()
    db.session.refresh(char)
    assert char.stat_points == 2  # unchanged


def test_levelup_applies_within_budget_and_decrements(client):
    user, char = _char(points=3)
    _login(client, user)
    base_str = json.loads(char.stats).get("str", 10)
    resp = client.post(f"/api/characters/{char.id}/level-up", json={"stat_allocations": {"str": 2, "con": 1}})
    assert resp.status_code == 200, resp.get_json()
    db.session.refresh(char)
    stats = json.loads(char.stats)
    assert stats["str"] == base_str + 2
    assert char.stat_points == 0  # 3 spent


def test_levelup_rejects_negative(client):
    user, char = _char(points=5)
    _login(client, user)
    resp = client.post(f"/api/characters/{char.id}/level-up", json={"stat_allocations": {"str": -3}})
    assert resp.status_code == 400
