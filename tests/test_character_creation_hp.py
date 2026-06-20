import json
import uuid

from app.models.models import User, db


def test_autofilled_character_starts_at_full_hp(test_app):
    with test_app.app_context():
        from app.routes.dashboard_helpers import handle_autofill

        u = User(username=f"hp-autofill-{uuid.uuid4().hex[:8]}", email=f"{uuid.uuid4().hex[:8]}@test.local")
        u.set_password("pw")
        db.session.add(u)
        db.session.commit()

        _existing, created = handle_autofill([], u.id)
        assert created, "expected at least one character to be autofilled"

        for char in created:
            stats = json.loads(char.stats)
            con = int(stats.get("con", 10))
            hp_max = 50 + con * 2 + char.level * 5
            assert stats["hp"] == hp_max, (
                f"{char.name}: expected fresh character's stats['hp'] to equal computed "
                f"hp_max ({hp_max}), got {stats['hp']}"
            )
