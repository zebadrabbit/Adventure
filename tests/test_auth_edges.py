from werkzeug.security import generate_password_hash

from app import db
from app.models.models import User


def test_login_get(client):
    r = client.get("/login")
    assert r.status_code == 200


def test_login_invalid_credentials(client):
    r = client.post("/login", data={"username": "nope", "password": "x"}, follow_redirects=True)
    assert b"Invalid credentials" in r.data


def test_dashboard_password_change_flow(auth_client):
    # Successful password change path after creating a user with known password is covered indirectly.
    # First set a known password for tester
    user = User.query.filter_by(username="tester").first()
    # Force a known starting password independent of prior tests
    user.password = generate_password_hash("initialPW")
    db.session.commit()
    old_pw_hash = user.password
    new_password = "changedPW1"
    # Need to re-login with updated password since fixture logged in using old hash
    auth_client.post("/logout", follow_redirects=True)
    auth_client.post(
        "/login",
        data={"username": "tester", "password": "initialPW"},
        follow_redirects=True,
    )
    r = auth_client.post(
        "/dashboard",
        data={
            "form": "change_password",
            "current_password": "initialPW",
            "new_password": new_password,
            "confirm_password": new_password,
        },
        follow_redirects=True,
    )
    assert r.status_code == 200
    db.session.refresh(user)
    assert user.password != old_pw_hash
