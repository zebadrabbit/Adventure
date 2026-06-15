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
    # Use in-memory PostgreSQL for tests if available, otherwise require DATABASE_URL
    test_db_url = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not test_db_url:
        raise ValueError(
            "DATABASE_URL or TEST_DATABASE_URL environment variable is required for tests. "
            "Set it to a PostgreSQL connection string."
        )
    os.environ["DATABASE_URL"] = test_db_url
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
        # Normalize baseline transient resource fields each test to prevent order-dependent leakage
        try:
            import json as _json

            stats_obj = _json.loads(new_char.stats) if new_char.stats else {}
            # Drop any persisted current-hp so combat sessions re-derive a full,
            # consistent max each test. Leaving a stale hp (e.g. 0 from a prior
            # combat death) leaks across the shared session DB and breaks tests
            # that expect a healthy party member.
            stats_obj.pop("hp", None)
            # Ensure current_mana key mirrors mana baseline if absent
            if "current_mana" in stats_obj:
                stats_obj["current_mana"] = int(stats_obj.get("current_mana", stats_obj.get("mana", 30)))
            new_char.stats = _json.dumps(stats_obj)
            db.session.add(new_char)
            db.session.commit()
        except Exception:
            db.session.rollback()
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


@pytest.fixture(autouse=True)
def _reset_volatile_game_config(test_app):
    """Clear tunable GameConfig keys that individual tests mutate.

    Several tests call GameConfig.set(...) to force encounter rates, rarity
    weights, or monster AI behavior. Because the test suite shares one session
    DB, those rows otherwise leak into later tests (e.g. an encounter rate of
    1.0 forcing combat where none is expected). All affected readers fall back
    to sane defaults when the key is absent, so deleting them between tests
    restores baseline behavior without needing a full DB rebuild.
    """
    VOLATILE_KEYS = (
        "encounter_spawn",
        "rarity_weights",
        "game_rules.encounter_spawn_rate",
        "monster_ai",
        "debug_encounters",
    )

    def _purge():
        try:
            from app import db
            from app.models import GameConfig, GameClock

            GameConfig.query.filter(GameConfig.key.in_(VOLATILE_KEYS)).delete(synchronize_session=False)
            # Clear a combat-paused clock left behind by a test whose combat
            # never completed; otherwise non-combat actions stop advancing time.
            clock = db.session.get(GameClock, 1)
            if clock is not None and clock.combat:
                clock.combat = False
                db.session.add(clock)
            db.session.commit()
        except Exception:
            try:
                from app import db as _db

                _db.session.rollback()
            except Exception:
                pass

    _purge()
    yield
    _purge()


@pytest.fixture(autouse=True)
def _ensure_db_session_cleanup(test_app):
    """Force database session rollback and cleanup after each test to prevent state leakage."""
    yield
    try:
        from app import db

        db.session.remove()
        db.session.rollback()
    except Exception:
        pass
