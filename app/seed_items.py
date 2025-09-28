"""Utility helpers for (re)seeding Item catalog data from raw SQL files.

Provides a programmatic way to clear existing item rows for the canonical
seed categories (weapons, armor, potions, misc) and then execute the SQL
files in the `sql/` directory. Each SQL file is expected to be idempotent
and contain its own DELETE guards, but we also offer an optional explicit
pre-clear for safety and to catch schema mismatches early.

Usage (programmatic):
    from app.seed_items import reseed_items
    reseed_items(clear_first=True)

CLI (after wiring in run.py):
    python run.py reseed-items --clear

Notes:
 - Runs inside a single SQLAlchemy connection/transaction per file to
   preserve the transactional semantics expressed in each .sql file.
 - Skips missing files gracefully.
 - Raises on first error (rolls back current file) and reports which file
   failed for easier debugging.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from sqlalchemy import text

from app import app as flask_app
from app import db

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"

ITEM_FILES_ORDER = [
    "items_weapons.sql",
    "items_armor.sql",
    "items_potions.sql",
    "items_misc.sql",
]


def _existing_sql_files(files: Iterable[str]):
    for name in files:
        p = SQL_DIR / name
        if p.exists() and p.is_file():
            yield p


def clear_item_categories() -> int:
    """Delete all Item rows whose type matches seeded categories.

    Returns number of rows deleted (best-effort; SQLite rowcount applies).
    """
    # NOTE: rely on simple type match; if schema evolves adjust accordingly.
    categories = ("weapon", "armor", "potion", "misc")
    # SQLAlchemy / SQLite requires expanding the IN; use tuple positional style
    stmt = text("DELETE FROM item WHERE type IN (%s)" % ",".join([f":c{i}" for i, _ in enumerate(categories)]))
    params = {f"c{i}": cat for i, cat in enumerate(categories)}
    result = db.session.execute(stmt, params)
    db.session.commit()
    return int(result.rowcount or 0)


def execute_sql_file(path: Path) -> None:
    """Execute a raw .sql file using the SQLAlchemy connection.

    The file may contain multiple statements and its own BEGIN/COMMIT.
    We read the whole file and feed it directly into the underlying DBAPI
    cursor via connection.exec_driver_sql for maximum compatibility with
    semicolon-delimited statements.
    """
    raw = path.read_text(encoding="utf-8")
    # Remove the malformed early single-row INSERT residue if present.
    cleaned_lines = []
    pending_insert_header = None
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            if pending_insert_header is not None:
                # still waiting for a tuple line; keep blank in buffer
                pass
            cleaned_lines.append(line)
            continue
        if stripped.startswith("--"):
            cleaned_lines.append(line)
            continue
        # Drop the malformed lone values line
        if stripped.startswith('"weapon_sword_l1"') or stripped.startswith("'weapon_sword_l1'"):
            # This was the only data line for the malformed early insert - skip
            continue
        upper = stripped.upper()
        if upper.startswith("INSERT INTO") and "VALUES" in upper:
            # Tentatively store header; decide to keep only if a tuple row follows
            pending_insert_header = line
            continue
        # If we were holding an INSERT header, decide whether to emit or drop
        if pending_insert_header is not None:
            if stripped.startswith("("):
                cleaned_lines.append(pending_insert_header)
                cleaned_lines.append(line)
            else:
                # No tuple followed; drop header and process this line normally
                cleaned_lines.append(line)
            pending_insert_header = None
        else:
            cleaned_lines.append(line)
    # Line-wise augmentation of old seed format lacking level/rarity/weight
    import re

    transformed: list[str] = []
    in_item_insert = False
    for line in cleaned_lines:
        raw_line = line
        stripped = raw_line.strip()
        upper = stripped.upper()
        if upper.startswith("INSERT INTO ITEM"):
            if "(slug, name, type, description, value_copper, level, rarity, weight)" in upper:
                in_item_insert = True
                transformed.append(raw_line)
                continue
            if "(SLUG, NAME, TYPE, DESCRIPTION, VALUE_COPPER)" in upper:
                # extend header
                raw_line = raw_line.replace(
                    "(slug, name, type, description, value_copper)",
                    "(slug, name, type, description, value_copper, level, rarity, weight)",
                )
                in_item_insert = True
                transformed.append(raw_line)
                continue
        if in_item_insert and stripped.startswith("(") and ",'common'," not in stripped:
            # Only augment tuple lines that haven't already been extended
            m = re.match(r"\('(.*?)'", stripped)
            level = 0
            if m:
                slug = m.group(1)
                lvl_match = re.search(r"_l(\d+)$", slug)
                if lvl_match:
                    level = int(lvl_match.group(1))
            # Insert before final ')' (keeping trailing comma or semicolon)
            closing = stripped[-1]
            trailer = ""
            if closing in {",", ";"}:
                trailer = closing
                inner = stripped[:-1]
            else:
                inner = stripped
            # find last ')'
            idx = inner.rfind(")")
            if idx != -1:
                inner = inner[:idx] + f", {level}, 'common', 1.0" + inner[idx:]
            new_line = inner + trailer
            # preserve original indentation
            prefix_ws = raw_line[: len(raw_line) - len(raw_line.lstrip(" "))]
            transformed.append(prefix_ws + new_line)
        else:
            transformed.append(raw_line)
        if stripped.endswith(";"):
            in_item_insert = False

    sql_text = "\n".join(transformed)
    # Use underlying sqlite3 executescript for multi-statement execution.
    raw_conn = db.engine.raw_connection()  # type: ignore[attr-defined]
    try:
        raw_conn.executescript(sql_text)
        raw_conn.commit()
    finally:  # pragma: no cover - safety cleanup
        raw_conn.close()


def reseed_items(clear_first: bool = False, verbose: bool = True) -> None:
    """Re-seed the Item table from sql/*.sql.

    Args:
        clear_first: If True, delete existing categorized rows before import.
        verbose: Print per-file progress messages (stdout).
    """
    with flask_app.app_context():
        if clear_first:
            deleted = clear_item_categories()
            if verbose:
                print(f"[reseed] Cleared {deleted} existing categorized item rows.")

        for path in _existing_sql_files(ITEM_FILES_ORDER):
            if verbose:
                print(f"[reseed] Loading {path.name} ...", end="")
            try:
                execute_sql_file(path)
            except Exception as e:  # pragma: no cover - surfaced to caller
                if verbose:
                    print(" ERROR")
                raise RuntimeError(f"Failed loading {path.name}: {e}") from e
            else:
                if verbose:
                    print(" OK")

        if verbose:
            # Quick count summary
            from app.models.models import Item

            total = db.session.query(Item).count()
            print(f"[reseed] Done. Item table now has {total} rows.")


__all__ = [
    "reseed_items",
    "clear_item_categories",
]
