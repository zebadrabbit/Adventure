import os
import random
import string
import sys

import pytest

# Ensure repository root importable early
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from app import create_app, db  # noqa: E402
from app.dungeon import SECRET_DOOR  # noqa: E402
from app.models.dungeon_instance import DungeonInstance  # noqa: E402
from app.models.models import Character, User  # noqa: E402
from app.routes.dungeon_api import get_cached_dungeon  # noqa: E402


@pytest.fixture(scope="session")
def test_app():
    os.environ.setdefault("DATABASE_URL", "sqlite:///instance/test.db")
    app = create_app()
    app.config.update({"TESTING": True, "WTF_CSRF_ENABLED": False, "LOGIN_DISABLED": False})
    return app


@pytest.fixture(autouse=True)
def _push_app_context(test_app):
    ctx = test_app.app_context()
    ctx.push()
    try:
        yield
    finally:
        ctx.pop()


@pytest.fixture()
def client(test_app):
    return test_app.test_client()


@pytest.fixture
def secret_door_setup(client):
    """Create a user, character, dungeon instance and provide helper to plant a secret door.

    Returns dict with: user, character, instance, dungeon, plant_secret(x,y|auto)->(x,y)
    """
    uname = "secretdoor_user_" + "".join(random.choices(string.ascii_lowercase, k=6))
    u = User(username=uname, role="user")
    u.set_password("pw")
    db.session.add(u)
    db.session.commit()
    with client.session_transaction() as sess:
        sess["user_id"] = u.id
        sess["_user_id"] = str(u.id)
    c = Character(user_id=u.id, name="Hero", stats='{"str":10}')
    db.session.add(c)
    inst = DungeonInstance(user_id=u.id, seed=777777, pos_x=0, pos_y=0, pos_z=0)
    db.session.add(inst)
    db.session.commit()
    with client.session_transaction() as sess:
        sess["dungeon_instance_id"] = inst.id
        sess["dungeon_seed"] = inst.seed
    d = get_cached_dungeon(inst.seed, (75, 75, 1))

    def plant_secret(auto=True, x=None, y=None):
        if auto:
            rx, ry = d.rooms[0].center
            target = None
            for radius in (1, 2, 3):
                if target:
                    break
                for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
                    nx, ny = rx + dx * radius, ry + dy * radius
                    if 0 <= nx < d.config.width and 0 <= ny < d.config.height and d.grid[nx][ny] == "W":
                        target = (nx, ny)
                        break
            if not target:
                for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
                    fx, fy = rx + dx, ry + dy
                    if 0 <= fx < d.config.width and 0 <= fy < d.config.height:
                        target = (fx, fy)
                        break
            tx, ty = target
        else:
            tx, ty = x, y
        d.grid[tx][ty] = SECRET_DOOR
        # Place player adjacent (center) then if distance >2, move closer
        inst.pos_x, inst.pos_y = d.rooms[0].center
        if abs(inst.pos_x - tx) + abs(inst.pos_y - ty) > 2:
            # Nudge player one step toward door to satisfy proximity
            if tx > inst.pos_x:
                inst.pos_x += 1
            elif tx < inst.pos_x:
                inst.pos_x -= 1
            if ty > inst.pos_y:
                inst.pos_y += 1
            elif ty < inst.pos_y:
                inst.pos_y -= 1
        db.session.commit()
        return tx, ty

    return {
        "user": u,
        "character": c,
        "instance": inst,
        "dungeon": d,
        "plant_secret": plant_secret,
    }


def pytest_configure(config):  # register custom marker
    config.addinivalue_line("markers", "db_isolation: force per-test DB rebuild for this test")


@pytest.fixture(autouse=True)
def _conditional_db_isolation(request, test_app):
    """Recreate DB only for tests marked with @pytest.mark.db_isolation.

    Unmarked tests reuse the existing session DB for speed.
    """
    if "db_isolation" in request.keywords:
        with test_app.app_context():
            db.drop_all()
            db.create_all()
            try:
                from app.server import _run_migrations, _seed_game_config, seed_items

                _run_migrations()
                seed_items()
                _seed_game_config()
            except Exception:
                pass
    yield

    # (App context already managed by earlier autouse fixture)


@pytest.fixture()
def auth_client(test_app, client):
    from werkzeug.security import generate_password_hash

    with test_app.app_context():
        try:
            db.create_all()
        except Exception:
            pass
        user = User.query.filter_by(username="tester").first()
        if not user:
            user = User(username="tester", password=generate_password_hash("pass"))
            db.session.add(user)
            db.session.commit()
        else:
            # Always reset password to known value to avoid prior tests altering it
            user.password = generate_password_hash("pass")
            db.session.commit()
        # Ensure at least one character for combat action tests
        from app.models.models import Character as _Char

        char_exists = _Char.query.filter_by(user_id=user.id).first()
        if not char_exists:
            cstats = '{"str":12, "dex":11, "int":10, "con":10, "mana":30}'
            new_char = _Char(user_id=user.id, name="Hero", stats=cstats, gear="{}", items="[]")
            db.session.add(new_char)
            db.session.commit()
        else:
            new_char = char_exists
        inst = DungeonInstance.query.filter_by(user_id=user.id).first()
        if not inst:
            inst = DungeonInstance(user_id=user.id, seed=1234, pos_x=0, pos_y=0, pos_z=0)
            db.session.add(inst)
            db.session.commit()
        inst_id = inst.id
    # Perform actual login so flask-login manages session
    client.post("/login", data={"username": "tester", "password": "pass"}, follow_redirects=True)
    # Ensure dungeon instance id in session
    with client.session_transaction() as sess:
        sess["dungeon_instance_id"] = inst_id
        # Pre-populate last_party_ids with existing character id to ensure Continue flow has seed value
        try:
            sess.setdefault("last_party_ids", [new_char.id])  # type: ignore
        except Exception:
            pass
    return client


# ---------------- Additional autouse cleanup ----------------
@pytest.fixture(autouse=True)
def _clear_websocket_state():
    """Ensure websocket online user state doesn't leak between tests causing role confusion."""
    try:
        import app.websockets.lobby as lobby

        lobby.online.clear()
    except Exception:
        pass
    yield
