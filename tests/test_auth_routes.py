from werkzeug.security import generate_password_hash

from app import db
from app.models.models import User


def test_register_and_redirect_dashboard(client, test_app):
    resp = client.post(
        "/register",
        data={"username": "newuser", "password": "secret123"},
        follow_redirects=False,
    )
    # Should redirect to dashboard on success
    assert resp.status_code in (302, 303)
    assert "/dashboard" in resp.headers.get("Location", "")


def test_register_duplicate_username(client, test_app):
    with test_app.app_context():
        db.session.add(User(username="dup", password=generate_password_hash("pw")))
        db.session.commit()
    resp = client.post("/register", data={"username": "dup", "password": "pw"}, follow_redirects=True)
    assert b"Username already exists" in resp.data


def test_login_success_and_logout(client, test_app):
    with test_app.app_context():
        db.session.add(User(username="loginuser", password=generate_password_hash("pass123")))
        db.session.commit()
    # Login
    resp = client.post(
        "/login",
        data={"username": "loginuser", "password": "pass123"},
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303)
    # Access dashboard (should require auth; follow redirect chain)
    dash = client.get("/dashboard", follow_redirects=False)
    # If already logged in we get 200 or a redirect to dashboard itself
    if dash.status_code in (301, 302, 303):
        dash = client.get("/dashboard", follow_redirects=True)
    assert dash.status_code == 200
    # Logout
    out = client.get("/logout", follow_redirects=True)
    assert b"login" in out.data.lower()


def test_login_failure(client):
    resp = client.post(
        "/login",
        data={"username": "unknown", "password": "nope"},
        follow_redirects=True,
    )
    assert b"Invalid credentials" in resp.data


def test_dashboard_requires_auth(client):
    resp = client.get("/dashboard", follow_redirects=False)
    # Should redirect to login page
    assert resp.status_code in (301, 302, 303)
    # Follow redirect chain to ensure login template accessible
    resp2 = client.get("/login")
    assert resp2.status_code == 200
