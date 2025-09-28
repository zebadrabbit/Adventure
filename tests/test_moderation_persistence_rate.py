import pytest

from app import app, db, socketio
from app.models.models import User


@pytest.fixture()
def setup_user_flags():
    # Ensure websocket online registry starts clean each test to avoid cross-test leakage
    import app.websockets.lobby as lobby

    lobby.online.clear()
    # Also clear moderation state to ensure deterministic tests
    lobby.banned_usernames.clear()
    lobby.muted_usernames.clear()
    lobby._temp_mute_expiry.clear()
    from werkzeug.security import generate_password_hash

    with app.app_context():
        db.create_all()
        admin = User.query.filter_by(username="admin_actor").first()
        if not admin:
            admin = User(
                username="admin_actor",
                password=generate_password_hash("pass"),
                role="admin",
            )
            db.session.add(admin)
        target = User.query.filter_by(username="flagged_user").first()
        if not target:
            target = User(
                username="flagged_user",
                password=generate_password_hash("pass"),
                role="user",
            )
            db.session.add(target)
        db.session.commit()
    yield


def _login(username):
    with app.app_context():
        user = User.query.filter_by(username=username).first()
    fc = app.test_client()
    with fc.session_transaction() as sess:
        sess["_user_id"] = str(user.id)
    c = socketio.test_client(app, flask_test_client=fc)
    # If banned it may not connect; caller will handle is_connected check
    if c.is_connected():
        c.get_received()
    return c


def test_persistent_ban_flag_blocks_connect(setup_user_flags):
    with app.app_context():
        u = User.query.filter_by(username="flagged_user").first()
        u.banned = True
        db.session.commit()
    _ = _login("flagged_user")  # noqa: F841 (connection attempt documents ban behavior)
    # Some test client backends may still show connected momentarily; request status and ensure user absent
    _ = _login("admin_actor")  # noqa: F841 (admin presence only for status snapshot)
    import app.websockets.lobby as lobby

    # Ensure admin flags for status event
    for sid, info in lobby.online.items():
        if info.get("username") == "admin_actor":
            info["role"] = "admin"
            info["is_auth"] = True
            info["legacy_ok"] = True
    # Use snapshot to avoid relying on websocket emit ordering
    snap = lobby._admin_status_snapshot()
    if snap is None:
        # As a fallback, synthesize admin entry then retry
        lobby.online["__test_admin_fallback"] = {
            "username": "admin_actor",
            "role": "admin",
            "is_auth": True,
            "legacy_ok": True,
        }
        snap = lobby._admin_status_snapshot()
    assert snap is not None, "admin status snapshot unavailable"
    payload = snap
    assert not any(
        u.get("username") == "flagged_user" for u in payload["users"]
    ), "Banned user should not appear in online list"


def test_rate_limit_auto_mute(setup_user_flags, monkeypatch):
    # Lower thresholds for faster test
    import app.websockets.lobby as lobby

    monkeypatch.setattr("app.websockets.lobby.RATE_LIMIT_MAX", 3)
    monkeypatch.setattr("app.websockets.lobby.RATE_LIMIT_WINDOW", 2)
    admin_c = _login("admin_actor")  # admin client used later
    player_c = _login("flagged_user")  # player client used for spam emission
    # Force identify roles (legacy_ok for admin)
    for sid, info in lobby.online.items():
        if info.get("username") == "admin_actor":
            info["role"] = "admin"
            info["is_auth"] = True
            info["legacy_ok"] = True
        if info.get("username") == "flagged_user":
            info["role"] = "user"
            info["is_auth"] = True

    class DummyPlayer:
        role = "user"
        username = "flagged_user"

    monkeypatch.setattr("app.websockets.lobby.current_user", DummyPlayer())
    for i in range(4):
        player_c.emit("lobby_chat_message", {"message": f"spam{i}"})
    # After exceeding limit user should be muted persistently
    with app.app_context():
        u = User.query.filter_by(username="flagged_user").first()
        assert u.muted is True
    # Try another message; should not broadcast
    player_c.get_received()
    admin_c.get_received()
    player_c.emit("lobby_chat_message", {"message": "after-mute"})
    rec_admin = admin_c.get_received()
    muted_msgs = [
        p
        for p in rec_admin
        if p["name"] == "lobby_chat_message" and p["args"] and p["args"][0].get("message") == "after-mute"
    ]
    assert not muted_msgs
