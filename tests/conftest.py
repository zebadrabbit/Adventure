import os
import sys
import pytest

# Ensure repository root is on sys.path so 'import app' works reliably when
# tests are invoked from differing working directories or via tooling.
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from app import create_app, db
from app.models.models import User
from app.models.dungeon_instance import DungeonInstance


@pytest.fixture(scope="session")
def test_app():
    """Create a single Flask app object for the test session.

    Database schema/data will NOT persist across tests; a function-scoped fixture
    will rebuild and seed the database before each test for isolation.
    """
    os.environ.setdefault("DATABASE_URL", "sqlite:///instance/test.db")
    app = create_app()
    app.config.update({
        "TESTING": True,
        "WTF_CSRF_ENABLED": False,
        "LOGIN_DISABLED": False,
    })
    return app


def pytest_configure(config):  # register custom marker
    config.addinivalue_line("markers", "db_isolation: force per-test DB rebuild for this test")


@pytest.fixture(autouse=True)
def _conditional_db_isolation(request, test_app):
    """Recreate DB only for tests marked with @pytest.mark.db_isolation.

    Unmarked tests reuse the existing session DB for speed.
    """
    if 'db_isolation' in request.keywords:
        with test_app.app_context():
            db.drop_all()
            db.create_all()
            try:
                from app.server import seed_items, _seed_game_config, _run_migrations
                _run_migrations()
                seed_items()
                _seed_game_config()
            except Exception:
                pass
    yield


@pytest.fixture(autouse=True)
def _push_app_context(test_app):
    """Automatically push a Flask app context for each test.

    Many existing tests rely on implicit application context (legacy pattern from
    earlier session-scoped fixture). Function-scoped DB isolation removed that
    persistent context, so we reintroduce it per test here.
    """
    ctx = test_app.app_context()
    ctx.push()
    try:
        yield
    finally:
        ctx.pop()


@pytest.fixture()
def client(test_app):
    return test_app.test_client()


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
        inst = DungeonInstance.query.filter_by(user_id=user.id).first()
        if not inst:
            inst = DungeonInstance(user_id=user.id, seed=1234, pos_x=0, pos_y=0, pos_z=0)
            db.session.add(inst)
            db.session.commit()
        inst_id = inst.id
    # Perform actual login so flask-login manages session
    client.post('/login', data={'username': 'tester', 'password': 'pass'}, follow_redirects=True)
    # Ensure dungeon instance id in session
    with client.session_transaction() as sess:
        sess['dungeon_instance_id'] = inst_id
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
