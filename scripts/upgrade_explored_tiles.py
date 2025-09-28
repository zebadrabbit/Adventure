"""One-off upgrade script to ensure 'explored_tiles' column exists.

Usage:
  python scripts/upgrade_explored_tiles.py

The application already performs a lazy migration at startup via _run_migrations();
this script is provided for environments where you prefer to run migrations
explicitly (e.g., CI/CD deploy step) without starting the web server.

Idempotent: Safe to run multiple times.
"""

from sqlalchemy import inspect, text

from app import create_app, db


def ensure_explored_tiles_column():
    inspector = inspect(db.engine)
    user_cols = {c["name"] for c in inspector.get_columns("user")}
    if "explored_tiles" in user_cols:
        print("[OK] 'explored_tiles' column already present.")
        return False
    try:
        db.session.execute(text("ALTER TABLE user ADD COLUMN explored_tiles TEXT"))
        db.session.commit()
        print("[OK] Added 'explored_tiles' column to user table.")
        return True
    except Exception as e:  # pragma: no cover - defensive
        db.session.rollback()
        print(f"[ERROR] Failed to add column: {e}")
        return False


def main():  # pragma: no cover - script entry
    app = create_app()
    with app.app_context():
        created = ensure_explored_tiles_column()
        if created:
            # Optionally backfill existing users with empty structure (no-op as NULL acceptable)
            print("[INFO] Migration complete.")
        else:
            print("[INFO] No changes required.")


if __name__ == "__main__":  # pragma: no cover
    main()
