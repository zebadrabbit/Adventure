import json

from app import db
from app.models.models import Character, User


def _login(client, app):
    with app.app_context():
        u = User.query.filter_by(username="equipper").first()
        if not u:
            u = User(username="equipper", password="x")
            db.session.add(u)
            db.session.commit()
        inst = {
            "uid": "sword1",
            "slot": "weapon",
            "name": "Brutal Shortsword",
            "rarity": "rare",
            "affixes": [{"stat": "dex", "val": 5}],
        }
        c = Character.query.filter_by(user_id=u.id).first()
        if not c:
            c = Character(
                user_id=u.id,
                name="EQ",
                stats='{"dex":10}',
                gear="{}",
                items=json.dumps([inst]),
            )
            db.session.add(c)
        else:
            # Reset to known state so test is idempotent
            c.gear = "{}"
            c.items = json.dumps([inst])
        db.session.commit()
        cid = c.id
        uid = u.id
    with client.session_transaction() as s:
        s["user_id"] = uid
        s["_user_id"] = str(uid)
    return cid


def test_equip_moves_instance_from_items_to_gear(client, test_app):
    cid = _login(client, test_app)
    r = client.post("/api/characters/%d/equip" % cid, json={"uid": "sword1"})
    assert r.status_code == 200, r.get_json()
    with test_app.app_context():
        c = db.session.get(Character, cid)
        gear = json.loads(c.gear)
        items = json.loads(c.items)
        assert gear["weapon"]["uid"] == "sword1"
        assert all(i.get("uid") != "sword1" for i in items if isinstance(i, dict))
