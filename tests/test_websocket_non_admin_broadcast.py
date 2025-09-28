import pytest

from app import app, db, socketio
from app.models.models import User


@pytest.fixture()
def non_admin_client():
    from werkzeug.security import generate_password_hash

    with app.app_context():
        db.create_all()
        u = User.query.filter_by(username="regular").first()
        if not u:
            u = User(username="regular", password=generate_password_hash("pass"), role="user")
            db.session.add(u)
            db.session.commit()
    _ = u.id  # noqa: F841
    flask_client = app.test_client()
    flask_client.post(
        "/login",
        data={"username": "regular", "password": "pass"},
        follow_redirects=True,
    )
    test_client = socketio.test_client(app, flask_test_client=flask_client)
    test_client.get_received()  # clear initial
    yield test_client
    if test_client.is_connected():
        test_client.disconnect()


def test_admin_broadcast_noop_for_non_admin(non_admin_client):
    non_admin_client.emit("admin_broadcast", {"target": "admins", "message": "ShouldNotDeliver"})
    rec = non_admin_client.get_received()
    assert not any(p["name"] == "admin_broadcast" for p in rec)
