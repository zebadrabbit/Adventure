import json
import pytest
from app import db
from app.models.models import Character, Item, User


def _mk_stats(**overrides):
    base = dict(str=10, con=10, dex=10, cha=10, int=10, wis=10, mana=5, hp=10, gold=3, silver=2, copper=1)
    base.update(overrides)
    return json.dumps(base)

@pytest.fixture()
def ensure_items(test_app):
    with test_app.app_context():
        # Minimal items so inventory inference path (herbal-pouch / hunting-bow) builds inventory entries
        for slug, name, type_ in [
            ("herbal-pouch", "Herbal Pouch", "tool"),
            ("hunting-bow", "Hunting Bow", "weapon"),
        ]:
            from app.models.models import Item
            if not Item.query.filter_by(slug=slug).first():
                db.session.add(Item(slug=slug, name=name, type=type_))
        db.session.commit()
    yield


def test_dashboard_backfills_missing_class(auth_client, ensure_items):
    # Create characters directly with missing 'class' in stats to trigger backfill logic.
    with auth_client.application.app_context():
        user = User.query.filter_by(username='tester').first()
        # Druid via item slug herbal-pouch
        c1 = Character(user_id=user.id, name='NoClassDruid', stats=_mk_stats(wis=14, int=9, dex=9, str=8), items=json.dumps(['herbal-pouch']), gear=json.dumps([]))
        # Ranger via item slug hunting-bow
        c2 = Character(user_id=user.id, name='NoClassRanger', stats=_mk_stats(dex=14, wis=12, str=9, int=8), items=json.dumps(['hunting-bow']), gear=json.dumps([]))
        # Fighter via highest STR
        c3 = Character(user_id=user.id, name='NoClassFighter', stats=_mk_stats(str=16, dex=10, int=9, wis=8), items=json.dumps([]), gear=json.dumps([]))
        # Mage via highest INT (avoid fighter by making str lower)
        c4 = Character(user_id=user.id, name='NoClassMage', stats=_mk_stats(int=16, str=8, dex=9, wis=10), items=json.dumps([]), gear=json.dumps([]))
        # Rogue via highest DEX path
        c5 = Character(user_id=user.id, name='NoClassRogue', stats=_mk_stats(dex=16, str=8, int=9, wis=7), items=json.dumps([]), gear=json.dumps([]))
        db.session.add_all([c1, c2, c3, c4, c5])
        db.session.commit()
    # Hit dashboard to trigger backfill & commit
    r = auth_client.get('/dashboard')
    assert r.status_code == 200
    with auth_client.application.app_context():
        updated = {c.name: json.loads(Character.query.filter_by(name=c.name).first().stats) for c in [c1, c2, c3, c4, c5]}
    # Assertions: class inferred & lowercase, coins preserved
    assert updated['NoClassDruid']['class'] == 'druid'
    assert updated['NoClassRanger']['class'] == 'ranger'
    assert updated['NoClassFighter']['class'] == 'fighter'
    assert updated['NoClassMage']['class'] == 'mage'
    assert updated['NoClassRogue']['class'] == 'rogue'
    for v in updated.values():
        # coin keys still present
        assert all(k in v for k in ('gold','silver','copper'))
    # Second request should not change already backfilled stats (idempotent)
    r2 = auth_client.get('/dashboard')
    assert r2.status_code == 200
    with auth_client.application.app_context():
        updated2 = {c.name: json.loads(Character.query.filter_by(name=c.name).first().stats) for c in [c1, c2, c3, c4, c5]}
    assert updated == updated2
