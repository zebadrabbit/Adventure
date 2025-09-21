import os, sqlite3
from app import create_app, db


def test_lazy_migration_adds_explored_tiles(tmp_path):
    # Create temp DB without explored_tiles column manually
    db_file = tmp_path / 'pre_migration.db'
    conn = sqlite3.connect(db_file)
    c = conn.cursor()
    c.execute("CREATE TABLE user (id INTEGER PRIMARY KEY, username VARCHAR(80) UNIQUE NOT NULL, password VARCHAR(200) NOT NULL)")
    conn.commit()
    conn.close()

    os.environ['DATABASE_URL'] = f'sqlite:///{db_file}'
    app = create_app()
    app.config.update(TESTING=True)
    with app.app_context():
        # If SQLAlchemy cannot see the table yet, create a minimal placeholder using execute
        conn2 = db.engine.raw_connection()
        try:
            cur = conn2.cursor()
            cur.execute("SELECT 1 FROM user LIMIT 1")
        except Exception:
            cur = conn2.cursor()
            cur.execute("CREATE TABLE user (id INTEGER PRIMARY KEY, username VARCHAR(80) UNIQUE NOT NULL, password VARCHAR(200) NOT NULL)")
            conn2.commit()
        finally:
            conn2.close()
        from app.server import _run_migrations
        _run_migrations()
        res = db.session.execute(db.text("PRAGMA table_info(user)")).fetchall()
        assert any(row[1] == 'explored_tiles' for row in res)
