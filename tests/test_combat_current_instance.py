"""combat_service._current_instance_for_user must resolve the instance the
user is actually in (session['dungeon_instance_id'], the canonical pointer
used by every dungeon route), not guess via "most recent DungeonInstance row
for this user" — a user can have multiple instance rows (e.g. an older,
abandoned run) and "most recent by id" can diverge from where they actually
are, silently locking death/extraction effects to the wrong instance.
"""

from app.services import combat_service
from tests.factories import create_instance, create_user


def test_current_instance_prefers_session_pointer_over_most_recent_row(test_app):
    with test_app.app_context():
        user = create_user("instance-pointer-test")
        old_inst = create_instance(user, seed=111)
        new_inst = create_instance(user, seed=222)
        assert new_inst.id > old_inst.id, "fixture must produce a newer row to expose the bug"

        with test_app.test_request_context():
            from flask import session as flask_session

            flask_session["dungeon_instance_id"] = old_inst.id
            resolved = combat_service._current_instance_for_user(user.id)

        assert resolved is not None
        assert resolved.id == old_inst.id, (
            f"resolved instance {resolved.id} should match the session's current "
            f"instance {old_inst.id}, not the most recent row {new_inst.id}"
        )


def test_current_instance_falls_back_to_most_recent_outside_request_context(test_app):
    """Direct service-level calls (no Flask request, e.g. some test/service
    contexts) have no session to read — fall back to the old behavior rather
    than erroring."""
    with test_app.app_context():
        user = create_user("instance-pointer-fallback")
        create_instance(user, seed=333)
        newest = create_instance(user, seed=444)

        resolved = combat_service._current_instance_for_user(user.id)

        assert resolved is not None
        assert resolved.id == newest.id
