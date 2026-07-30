"""Character lifecycle operations that span more than one table.

Character has ten foreign keys pointing at it and the model declares no
relationships or cascades, so a bare ``db.session.delete(char)`` raises a
ForeignKeyViolation for any character that has ever done anything -- which is
all of them, since every character is granted a starting skill at creation.
Deleting a character therefore has to clear what points at it first.
"""

from __future__ import annotations

import structlog
from sqlalchemy import text

from app import db
from app.models.models import Character

logger = structlog.get_logger(__name__)

# Rows owned by the character: meaningless once it is gone, so they go with it.
# (table, column) pairs rather than ORM models because several of these have no
# relationship defined on Character and importing eight models here to delete
# rows would be more coupling than the job needs.
OWNED_TABLES = (
    ("character_skill", "character_id"),
    ("character_talent_points", "character_id"),
    ("character_status_effect", "character_id"),
    ("character_achievement", "character_id"),
    ("quest_log", "character_id"),
    ("quest_progress", "character_id"),
    ("party_member", "character_id"),
    # The character's own purchase/sale records. NOT NULL, so they cannot be
    # orphaned; a dismissed character's ledger goes with them.
    ("trade_transaction", "character_id"),
)

# References that survive the character, and are nullable, so they are cleared
# rather than deleted: a party outlives its leader.
# (party_shared_inventory.added_by was here until the shared party inventory was
# removed -- bags are per-character. This list is executed as raw SQL against
# literal table names, so an entry for a dropped table raises UndefinedTable on
# every character deletion.)
CLEARED_REFERENCES = (("party", "leader_id"),)


def delete_character(char: Character) -> dict:
    """Delete a character and everything that depends on it.

    Returns a summary of what was removed, for logging and tests. Commits on
    success; rolls back and re-raises on failure, so a partial delete can never
    be left behind.
    """
    char_id = char.id
    name = char.name
    removed: dict[str, int] = {}

    try:
        for table, column in OWNED_TABLES:
            result = db.session.execute(
                text(f"DELETE FROM {table} WHERE {column} = :cid"),  # noqa: S608 - table names are literals above
                {"cid": char_id},
            )
            if result.rowcount:
                removed[table] = result.rowcount

        for table, column in CLEARED_REFERENCES:
            result = db.session.execute(
                text(f"UPDATE {table} SET {column} = NULL WHERE {column} = :cid"),  # noqa: S608
                {"cid": char_id},
            )
            if result.rowcount:
                removed[f"{table}.{column} cleared"] = result.rowcount

        db.session.delete(char)
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.error("character_delete_failed", char_id=char_id, name=name, exc_info=True)
        raise

    logger.info("character_deleted", char_id=char_id, name=name, removed=removed)
    return {"character_id": char_id, "name": name, "removed": removed}


# Rows owned by a user account. Same story as OWNED_TABLES above: seven tables
# carry a foreign key to `user` and none of them cascade, so deleting an account
# that has ever played raised a ForeignKeyViolation. Characters are handled
# separately (they own rows of their own), and themes a user authored outlive
# them.
USER_OWNED_TABLES = (
    ("dungeon_instance", "user_id"),
    ("combat_session", "user_id"),
    ("hoard", "user_id"),
    ("user_pref", "user_id"),
    ("user_quest_pool", "user_id"),
)

USER_CLEARED_REFERENCES = (("theme", "created_by"),)


def delete_user(user) -> dict:
    """Delete a user account and everything that depends on it.

    Deletes the account's characters through delete_character (each owns ten
    tables of its own), then the account-scoped rows, then the user. Themes the
    user authored survive with a null author -- they may be in use by others.
    """
    from app.models.models import Character

    user_id = user.id
    username = user.username
    removed: dict[str, int] = {}

    try:
        for char in Character.query.filter_by(user_id=user_id).all():
            result = delete_character(char)
            for table, count in result["removed"].items():
                removed[table] = removed.get(table, 0) + count
            removed["character"] = removed.get("character", 0) + 1

        for table, column in USER_OWNED_TABLES:
            res = db.session.execute(
                text(f"DELETE FROM {table} WHERE {column} = :uid"),  # noqa: S608 - literal table names above
                {"uid": user_id},
            )
            if res.rowcount:
                removed[table] = removed.get(table, 0) + res.rowcount

        for table, column in USER_CLEARED_REFERENCES:
            res = db.session.execute(
                text(f"UPDATE {table} SET {column} = NULL WHERE {column} = :uid"),  # noqa: S608
                {"uid": user_id},
            )
            if res.rowcount:
                removed[f"{table}.{column} cleared"] = res.rowcount

        db.session.delete(user)
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.error("user_delete_failed", user_id=user_id, username=username, exc_info=True)
        raise

    logger.info("user_deleted", user_id=user_id, username=username, removed=removed)
    return {"user_id": user_id, "username": username, "removed": removed}


def living_characters(user_id: int):
    """The user's characters that can still be sent into a dungeon.

    Permadeathed characters stay in the roster so the player can see who they
    lost and dismiss them, but they must never be picked for a party -- party
    formation used to take "the first four by id", which after a wipe is exactly
    the corpses.
    """
    return (
        Character.query.filter_by(user_id=user_id)
        .filter(Character.permadeath.is_(False))
        .order_by(Character.id.asc())
        .all()
    )
