import json
import uuid

from app import db
from app.economy import hoard_service
from app.models.hoard import Hoard


def _login(client, user):
    with client.session_transaction() as sess:
        sess["_user_id"] = str(user.id)
        sess["user_id"] = user.id


def test_get_hoard_returns_items_and_display(client):
    from tests.factories import create_user

    user = create_user("hapi_a_" + uuid.uuid4().hex[:8])
    hoard = Hoard.get_or_create(user.id)
    hoard_service.deposit_copper(hoard, 12345)
    db.session.commit()
    _login(client, user)
    resp = client.get("/api/hoard")
    assert resp.status_code == 200, resp.get_json()
    data = resp.get_json()
    assert data["copper"] == 12345
    assert data["copper_display"] == "1g 23s 45c"


def test_withdraw_instance_to_character(client):
    from tests.factories import create_character, create_user

    user = create_user("hapi_b_" + uuid.uuid4().hex[:8])
    char = create_character(user, name="Mule", items=[])
    hoard = Hoard.get_or_create(user.id)
    hoard_service.deposit_items(hoard, [{"uid": "wx", "name": "Bow", "value": 90}])
    db.session.commit()
    _login(client, user)
    resp = client.post("/api/hoard/withdraw", json={"character_id": char.id, "uid": "wx"})
    assert resp.status_code == 200, resp.get_json()
    db.session.refresh(char)
    assert any(i.get("uid") == "wx" for i in json.loads(char.items))
