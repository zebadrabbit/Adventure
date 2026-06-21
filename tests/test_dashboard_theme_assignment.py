"""Tests that starting an adventure assigns a deterministic
monster_family theme to a newly-created DungeonInstance row."""

from app import db
from app.models.dungeon_instance import DungeonInstance
from app.models.models import Character
from app.services.spawn_service import MONSTER_THEME_FAMILIES, pick_monster_family


def test_start_adventure_assigns_theme_to_new_instance(auth_client, test_app):
    with test_app.app_context():
        hero = Character.query.filter_by(name="Hero").first()
        assert hero is not None, "auth_client fixture should have created a 'Hero' character"
        hero_id = hero.id

    with auth_client.session_transaction() as sess:
        # Force the dashboard route's "if instance is None" branch to
        # actually create a fresh DungeonInstance, instead of reusing
        # the one auth_client's fixture already seeded.
        sess.pop("dungeon_instance_id", None)
        sess.pop("dungeon_seed", None)

    resp = auth_client.post(
        "/dashboard",
        data={"form": "start_adventure", "party_ids": str(hero_id)},
        follow_redirects=True,
    )
    assert resp.status_code == 200

    with auth_client.session_transaction() as sess:
        instance_id = sess.get("dungeon_instance_id")
    assert instance_id is not None

    with test_app.app_context():
        inst = db.session.get(DungeonInstance, instance_id)
        assert inst.monster_family in MONSTER_THEME_FAMILIES
        assert inst.monster_family == pick_monster_family(inst.seed)
