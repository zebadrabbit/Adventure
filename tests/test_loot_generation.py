from app import app, db
from app.loot.generator import LootConfig, generate_loot_for_seed
from app.models.dungeon_instance import DungeonInstance
from app.models.loot import DungeonLoot
from app.models.models import Item, User
from app.server import _run_migrations


def login(client, username="tester"):
    with app.app_context():
        user = User.query.filter_by(username=username).first()
        if not user:
            user = User(username=username, password="x")  # password not hashed for test simplicity
            db.session.add(user)
            db.session.commit()
        return user


def _ensure_instance(user, seed=123456):
    with app.app_context():
        inst = DungeonInstance.query.filter_by(user_id=user.id, seed=seed).first()
        if not inst:
            _run_migrations()
            inst = DungeonInstance(user_id=user.id, seed=seed, pos_x=0, pos_y=0, pos_z=0)
            db.session.add(inst)
            db.session.commit()
        return inst


def test_loot_generation_idempotent(client):
    user = login(client)
    # Ensure dungeon instance exists BEFORE mutating session
    inst = _ensure_instance(user)
    # Populate session with keys Flask-Login expects; `_user_id` is the canonical key
    with client.session_transaction() as sess:
        sess["_user_id"] = str(user.id)
        sess["dungeon_instance_id"] = inst.id

    # Simulate simple walkable tiles grid 20x20 minus borders
    walkables = [(x, y) for x in range(1, 19) for y in range(1, 19)]
    with app.app_context():
        # Baseline count
        _ = DungeonLoot.query.count()  # noqa: F841 baseline count captured but unused
        cfg = LootConfig(avg_party_level=1, width=20, height=20, seed=inst.seed)
        created_first = generate_loot_for_seed(cfg, walkables)
        created_second = generate_loot_for_seed(cfg, walkables)
        assert created_first >= 1
        assert created_second == 0  # idempotent
        # No duplicates at identical coords
        coords = set()
        for row in DungeonLoot.query.filter_by(seed=inst.seed).all():
            c = (row.x, row.y, row.z)
            assert c not in coords
            coords.add(c)


def test_loot_api_list(client):
    user = login(client, "apiuser")
    inst = _ensure_instance(user, seed=99999)
    # Authenticate session and bind to dungeon instance
    with client.session_transaction() as sess:
        sess["_user_id"] = str(user.id)
        sess["dungeon_instance_id"] = inst.id

    # Generate some loot manually
    walkables = [(x, y) for x in range(1, 10) for y in range(1, 10)]
    with app.app_context():
        cfg = LootConfig(avg_party_level=1, width=10, height=10, seed=inst.seed)
        generate_loot_for_seed(cfg, walkables)

    # Hit list endpoint
    rv = client.get("/api/dungeon/loot")
    assert rv.status_code == 200, f"claim response: {rv.get_json()}"
    data = rv.get_json()
    assert "loot" in data
    assert any("slug" in loot_entry for loot_entry in data["loot"])  # E741 addressed


def test_loot_claim_with_character_assignment(client):
    """Claim loot specifying a character_id and ensure item slug appears in that character's inventory list."""
    user = login(client, "chooser")
    inst = _ensure_instance(user, seed=424242)
    # Create two characters for the user
    from app.models.models import Character

    with app.app_context():
        if Character.query.filter_by(user_id=user.id).count() < 2:
            # Minimal required fields: user_id, name, stats JSON strings. gear/items optional.
            c1 = Character(user_id=user.id, name="Alpha", stats="{}", items="[]", gear="{}")
            c2 = Character(user_id=user.id, name="Beta", stats="{}", items="[]", gear="{}")
            db.session.add_all([c1, c2])
            db.session.commit()
        chars = Character.query.filter_by(user_id=user.id).all()
        char_map = {c.name: c for c in chars}
    with client.session_transaction() as sess:
        sess["_user_id"] = str(user.id)
        sess["dungeon_instance_id"] = inst.id
        # Simulate party containing both characters
        sess["party"] = [{"name": c.name} for c in char_map.values()]

    # Generate loot
    walkables = [(x, y) for x in range(1, 8) for y in range(1, 8)]
    with app.app_context():
        cfg = LootConfig(avg_party_level=1, width=7, height=7, seed=inst.seed)
        generate_loot_for_seed(cfg, walkables)
        loot_row = DungeonLoot.query.filter_by(seed=inst.seed, claimed=False).first()
        assert loot_row is not None
        item_obj = db.session.get(Item, loot_row.item_id)
        assert item_obj is not None

    # Target first (lexicographically) character explicitly
    target = sorted(char_map.values(), key=lambda c: c.name)[0]
    rv = client.post(f"/api/dungeon/loot/claim/{loot_row.id}", json={"character_id": target.id})
    assert rv.status_code == 200
    data = rv.get_json()
    assert data.get("claimed") is True
    assert data.get("character_id") == target.id
    # Verify inventory updated
    with app.app_context():
        refreshed = db.session.get(Character, target.id)
        import json as _json

        slugs = _json.loads(refreshed.items) if refreshed.items else []
        assert item_obj.slug in slugs
