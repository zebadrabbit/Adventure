import os
import random
import string
import sys

import pytest

# Ensure repository root importable early
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# Snapshot what the *caller's shell* explicitly set, BEFORE importing `app`.
# This must happen before the import because `app/__init__.py` calls
# load_dotenv() as a side effect, which silently populates os.environ
# ["DATABASE_URL"] from the repo's .env (the real dev database) even when
# neither var was actually exported by the caller. The test_app fixture below
# trusts only this pre-import snapshot for its safety check — re-reading
# os.getenv("DATABASE_URL") after the app import would see the leaked dev
# value and wrongly treat it as an explicit, intentional test DB (this
# previously caused `db.drop_all()` to silently wipe the real dev DB whenever
# pytest ran with no TEST_DATABASE_URL/DATABASE_URL exported in the shell).
_explicit_test_db_url = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL")
if _explicit_test_db_url:
    os.environ["DATABASE_URL"] = _explicit_test_db_url

from app import create_app, db  # noqa: E402
from app.dungeon import SECRET_DOOR  # noqa: E402
from app.models.dungeon_instance import DungeonInstance  # noqa: E402
from app.models.models import Character, User  # noqa: E402
from app.routes.dungeon_api import get_cached_dungeon  # noqa: E402


@pytest.fixture(scope="session")
def test_app():
    # Use the pre-import snapshot, not a fresh os.getenv call — see comment above.
    test_db_url = _explicit_test_db_url
    if not test_db_url:
        raise ValueError(
            "DATABASE_URL or TEST_DATABASE_URL environment variable is required for tests. "
            "Set it explicitly in your shell (a .env file's DATABASE_URL is not trusted "
            "here, to avoid silently wiping a real dev database). "
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


@pytest.fixture(autouse=True)
def _db_transaction_rollback(request, test_app, _push_app_context):
    """Wrap each test in a transaction and roll back everything afterward.

    The suite used to share one session-long DB: any test that called
    db.session.commit() (directly, or indirectly via a route under
    test_client()) permanently wrote rows that later tests could observe,
    which is why several fixtures above (_reset_volatile_game_config,
    auth_client's password/character reset, etc.) exist purely to manually
    undo specific known leaks. This fixture makes that whole category of
    leak impossible.

    An earlier version of this fixture tried to rebind db.session to a new
    scoped session constructed with bind=connection in session_options.
    That silently did nothing: Flask-SQLAlchemy 3.x's Session.get_bind()
    (flask_sqlalchemy/session.py) resolves every query through
    self._db.engines[bind_key], never consulting a sessionmaker-level
    bind= kwarg. db.session kept talking to the real pooled engine the
    whole time, committing for real on every test -- invisible to pytest's
    pass/fail output because test usernames were unique enough to avoid
    visible collisions, but permanently polluting the test database.

    Fix part 1: patch Session.get_bind itself (class-level, for every
    Flask-SQLAlchemy Session instance, including ones created in nested
    `with app.app_context():` blocks -- see auth_client and
    test_cache_flow.py for that pattern) to always return our externally
    managed Connection. A tempting alternative -- swapping db.engines[None]
    to the Connection instead -- looked equivalent but broke
    app/seed_items.py and tests/test_monsters.py, both of which call
    db.engine.raw_connection() directly; db.engine is also sourced from
    db.engines[None], so that swap silently replaced the real Engine
    wherever raw (non-ORM) access expected one. Patching get_bind leaves
    db.engine/db.engines[None] untouched, affecting only ORM Session
    traffic.

    Fix part 2: get_bind alone isn't sufficient, because several existing
    test files (e.g. tests/test_extraction.py's local `setup_database`
    autouse fixture) call db.session.rollback() / db.session.remove()
    directly in their own teardown. Once get_bind correctly routes those
    calls to our connection, db.session.remove() discards the one Session
    instance we could attach a SAVEPOINT-restart listener to (the classic
    "join an external transaction" recipe) -- the next db.session.x access
    creates a brand new Session instance with no such protection, and a
    real commit from that instance ends our transaction for good (silent
    SAWarning: "transaction already deassociated from connection" later,
    plus the connection drifting back towards the pool's bookkeeping while
    we still hold and reuse it -- eventually exhausting the pool a few
    hundred tests in and hanging every later test's db.engine.connect()).
    A SAVEPOINT reattached per Session instance only protects that one
    instance, not the ones created after a mid-test db.session.remove().

    A first attempt at fix part 2 made do_commit a flat no-op at the
    dialect-class level (below the ORM entirely, so Session churn doesn't
    matter). That stopped the pool exhaustion, but introduced a worse bug:
    with commit() doing *nothing* durable, any later rollback() from
    completely unrelated code (e.g. tests/test_admin_actions.py's
    `player_client` fixture goes through Flask-SocketIO's test client,
    which triggers its own app-context teardown and a real
    session.rollback() somewhere inside) discarded every prior write in
    the test, not just the current unit of work -- e.g. a fixture commits
    "admin_actor" into existence, a later unrelated rollback() wipes it
    out, and the test fails with the user mysteriously gone.

    The actual fix: give commit() and rollback() SAVEPOINT semantics at the
    dialect level instead of skipping them outright. A SAVEPOINT is
    created once, immediately, on the raw connection. do_commit is
    patched to RELEASE that savepoint and immediately open a new one
    (advancing the checkpoint without ever telling Postgres to really
    commit). do_rollback is patched to roll back *to* that savepoint
    instead of rolling back the whole transaction. The result: every
    commit() call -- regardless of which Session instance issued it --
    advances a durable-for-the-rest-of-the-test checkpoint; every
    rollback() call undoes only what happened since the last checkpoint,
    exactly matching what application/test code assumes commit/rollback
    mean. Nothing ever reaches disk because the checkpoint itself is a
    SAVEPOINT, not a real COMMIT. After the test, both methods are
    restored and one real connection.rollback() + connection.close()
    discards everything, checkpoints included.

    Tests marked @pytest.mark.db_isolation skip this: they call
    db.drop_all()/create_all() directly (DDL), which would fight an open
    transaction. They already get full isolation from
    _conditional_db_isolation's rebuild, so they don't need this too.
    """
    if "db_isolation" in request.keywords:
        yield
        return

    import flask_sqlalchemy.session as _fsa_session

    connection = db.engine.connect()
    raw = connection.connection.dbapi_connection
    cur = raw.cursor()
    cur.execute("SAVEPOINT test_checkpoint")
    cur.close()

    # do_commit/do_rollback are patched at the dialect *class* level, which
    # is shared by every connection the engine hands out -- not just ours.
    # Other code (e.g. db.create_all() during this same test) opens its own
    # separate pooled connection and commits it normally; that connection
    # never got our SAVEPOINT, so redirecting its commit/rollback the same
    # way raises "savepoint does not exist". Gate on dbapi_connection
    # identity so only our connection gets the SAVEPOINT treatment; every
    # other connection falls through to the real implementation.
    dialect_cls = type(connection.dialect)
    original_do_commit = dialect_cls.do_commit
    original_do_rollback = dialect_cls.do_rollback

    def _is_ours(dbapi_connection):
        return getattr(dbapi_connection, "dbapi_connection", dbapi_connection) is raw

    def _do_commit(self, dbapi_connection):
        if not _is_ours(dbapi_connection):
            return original_do_commit(self, dbapi_connection)
        c = dbapi_connection.cursor()
        c.execute("RELEASE SAVEPOINT test_checkpoint")
        c.execute("SAVEPOINT test_checkpoint")
        c.close()

    def _do_rollback(self, dbapi_connection):
        if not _is_ours(dbapi_connection):
            return original_do_rollback(self, dbapi_connection)
        c = dbapi_connection.cursor()
        c.execute("ROLLBACK TO SAVEPOINT test_checkpoint")
        c.close()

    dialect_cls.do_commit = _do_commit
    dialect_cls.do_rollback = _do_rollback

    original_get_bind = _fsa_session.Session.get_bind

    def _get_bind(self, mapper=None, clause=None, bind=None, **kwargs):
        return connection

    _fsa_session.Session.get_bind = _get_bind

    try:
        yield
    finally:
        db.session.remove()
        _fsa_session.Session.get_bind = original_get_bind
        dialect_cls.do_commit = original_do_commit
        dialect_cls.do_rollback = original_do_rollback
        connection.rollback()
        connection.close()


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
            # Use reflected metadata so unknown/orphan tables (e.g. from removed
            # models) are also dropped cleanly on Postgres.
            from sqlalchemy import MetaData

            try:
                with db.engine.begin() as conn:
                    reflected = MetaData()
                    reflected.reflect(conn)
                    reflected.drop_all(conn)
            except Exception:
                db.drop_all()
            db.create_all()
            try:
                from app import _ensure_schema
                from app.server import _seed_game_config, seed_items

                _ensure_schema()
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
        "rarity_weights",
        "monster_ai",
        "regen_rates",
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


@pytest.fixture()
def logged_in_user(client):
    """Create and log in a user."""
    import uuid
    from tests.factories import create_user

    user = create_user("test_user_" + uuid.uuid4().hex[:8])
    with client.session_transaction() as sess:
        sess["_user_id"] = str(user.id)
        sess["user_id"] = user.id
    return user


@pytest.fixture()
def test_character(logged_in_user):
    """Create a basic test character with no coins."""
    import json
    import uuid
    from tests.factories import create_character

    char = create_character(logged_in_user, name="TestChar_" + uuid.uuid4().hex[:8], items=[])
    # Ensure stats have no coins
    stats = json.loads(char.stats)
    stats.pop("gold", None)
    stats.pop("silver", None)
    stats.pop("copper", None)
    char.stats = json.dumps(stats)
    db.session.commit()
    return char


@pytest.fixture()
def test_character_with_coins(logged_in_user):
    """Create a test character with 2 gold, 0 silver, 0 copper."""
    import json
    import uuid
    from tests.factories import create_character

    char = create_character(logged_in_user, name="TestCharCoins_" + uuid.uuid4().hex[:8], items=[])
    stats = json.loads(char.stats)
    stats["gold"] = 2
    stats["silver"] = 0
    stats["copper"] = 0
    char.stats = json.dumps(stats)
    db.session.commit()
    return char


@pytest.fixture()
def test_hoard_with_copper(logged_in_user):
    """Create a hoard for the user with 5000 copper (50 silver)."""
    from app.models.hoard import Hoard

    hoard = Hoard.get_or_create(logged_in_user.id)
    hoard.copper = 5000
    db.session.commit()
    return hoard
