import pytest

from app import db
from app.models.models import Character, User


@pytest.fixture()
def fallback_client(test_app):
    from werkzeug.security import generate_password_hash

    with test_app.app_context():
        db.create_all()
        u = User.query.filter_by(username="fbuser").first()
        if not u:
            u = User(username="fbuser", password=generate_password_hash("pass"))
            db.session.add(u)
            db.session.commit()
    _ = u.id  # noqa: F841
    c = test_app.test_client()
    c.post("/login", data={"username": "fbuser", "password": "pass"}, follow_redirects=True)
    return c


def test_dashboard_fallback_user_id(fallback_client, monkeypatch):
    # Force attribute access on current_user.id to raise to trigger fallback path using session _user_id
    class BadUser:
        @property
        def id(self):
            raise RuntimeError("detached")

    monkeypatch.setattr("app.routes.dashboard.current_user", BadUser())
    # Character creation POST
    r = fallback_client.post(
        "/dashboard",
        data={"name": "FBChar", "char_class": "fighter"},
        follow_redirects=True,
    )
    assert r.status_code == 200
    # Ensure character was created for logged in user
    with fallback_client.application.app_context():
        u = User.query.filter_by(username="fbuser").first()
        char = Character.query.filter_by(name="FBChar", user_id=u.id).first()
        assert char is not None
