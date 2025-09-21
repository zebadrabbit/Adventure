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
    os.environ.setdefault("DATABASE_URL", "sqlite:///instance/test.db")
    app = create_app()
    app.config.update({
        "TESTING": True,
        "WTF_CSRF_ENABLED": False,
        "LOGIN_DISABLED": False,
    })
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


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
