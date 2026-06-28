"""Tests for daily/weekly quest API endpoints."""

import json

import pytest

from app import db
from app.models.user_quest_pool import UserQuestPool
from app.services.quest_generator import period_key_daily


@pytest.fixture()
def daily_quest_at_target(client, logged_in_user):
    """Create a daily quest pool with the first quest at target (complete)."""
    from app.services.quest_generator import get_or_generate_daily

    get_or_generate_daily(logged_in_user.id)
    # Force first quest to be complete
    key = period_key_daily()
    pool = UserQuestPool.get_or_none(logged_in_user.id, "daily", key)
    data = json.loads(pool.quests_json)
    data[0]["objective"]["current"] = data[0]["objective"]["target"]
    data[0]["status"] = "complete"
    pool.quests_json = json.dumps(data)
    db.session.commit()
    return data[0]["id"]


def test_get_daily_returns_three(client, logged_in_user):
    resp = client.get("/api/quests/daily")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["quests"]) == 3


def test_get_weekly_returns_one(client, logged_in_user):
    resp = client.get("/api/quests/weekly")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["quest"]["objective"]["type"] == "daily_completions"


def test_claim_daily_requires_completion(client, logged_in_user):
    resp = client.get("/api/quests/daily")
    quest_id = resp.get_json()["quests"][0]["id"]
    resp2 = client.post("/api/quests/daily/claim", json={"quest_id": quest_id})
    # objective.current is 0, target > 0
    assert resp2.status_code == 400
    assert "not complete" in resp2.get_json()["error"].lower()


def test_claim_daily_completed_grants_rewards(client, logged_in_user, daily_quest_at_target):
    quest_id = daily_quest_at_target
    resp = client.post("/api/quests/daily/claim", json={"quest_id": quest_id})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert "rewards" in data


def test_claim_daily_missing_quest_id(client, logged_in_user):
    resp = client.post("/api/quests/daily/claim", json={})
    assert resp.status_code == 400


def test_claim_daily_already_claimed(client, logged_in_user, daily_quest_at_target):
    quest_id = daily_quest_at_target
    # Claim once
    client.post("/api/quests/daily/claim", json={"quest_id": quest_id})
    # Try again
    resp = client.post("/api/quests/daily/claim", json={"quest_id": quest_id})
    assert resp.status_code == 400
    assert "claimed" in resp.get_json()["error"].lower()


def test_claim_weekly_requires_completion(client, logged_in_user):
    # Ensure weekly exists
    client.get("/api/quests/weekly")
    resp = client.post("/api/quests/weekly/claim")
    assert resp.status_code == 400
    assert "not complete" in resp.get_json()["error"].lower()
