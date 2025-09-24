import json
from app import app, db
from app.models.models import User, Item
from app.models.dungeon_instance import DungeonInstance
from app.server import _run_migrations
from app.loot.generator import generate_loot_for_seed, LootConfig
from app.models.loot import DungeonLoot


def login(client, username='tester'):
    with app.app_context():
        user = User.query.filter_by(username=username).first()
        if not user:
            user = User(username=username, password='x')  # password not hashed for test simplicity
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
        sess['_user_id'] = str(user.id)
        sess['dungeon_instance_id'] = inst.id

    # Simulate simple walkable tiles grid 20x20 minus borders
    walkables = [(x, y) for x in range(1,19) for y in range(1,19)]
    with app.app_context():
        # Baseline count
        initial = DungeonLoot.query.count()
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
    user = login(client, 'apiuser')
    inst = _ensure_instance(user, seed=99999)
    # Authenticate session and bind to dungeon instance
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user.id)
        sess['dungeon_instance_id'] = inst.id

    # Generate some loot manually
    walkables = [(x, y) for x in range(1,10) for y in range(1,10)]
    with app.app_context():
        cfg = LootConfig(avg_party_level=1, width=10, height=10, seed=inst.seed)
        generate_loot_for_seed(cfg, walkables)

    # Hit list endpoint
    rv = client.get('/api/dungeon/loot')
    assert rv.status_code == 200
    data = rv.get_json()
    assert 'loot' in data
    assert any('slug' in l for l in data['loot'])
