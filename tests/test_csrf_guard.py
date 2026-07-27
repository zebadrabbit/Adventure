"""CSRF header guard on mutating /api/ requests.

The guard (`_require_api_header` in app/__init__.py) is exempt while
TESTING is set, so these tests flip TESTING off for the duration of the
request to exercise the real enforcement path.
"""

import pytest


@pytest.fixture()
def enforcing_app(test_app):
    """Temporarily disable the TESTING exemption so the guard enforces."""
    test_app.config["TESTING"] = False
    try:
        yield test_app
    finally:
        test_app.config["TESTING"] = True


def test_mutating_api_without_header_rejected(enforcing_app, auth_client):
    resp = auth_client.post("/api/dungeon/seed", json={})
    assert resp.status_code == 403
    assert resp.get_json()["error"] == "csrf_rejected"


def test_mutating_api_with_header_allowed(enforcing_app, auth_client):
    resp = auth_client.post(
        "/api/dungeon/seed",
        json={},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert resp.status_code != 403


def test_get_api_without_header_allowed(enforcing_app, auth_client):
    resp = auth_client.get("/api/characters/state")
    assert resp.status_code != 403


def test_non_api_post_without_header_allowed(enforcing_app, client):
    # Non-/api/ routes (e.g. login form posts) are covered by SameSite=Lax,
    # not the header gate.
    resp = client.post("/login", data={"username": "nobody", "password": "wrong"})
    assert resp.status_code != 403
