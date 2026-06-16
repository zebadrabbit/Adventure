from app import db
from app.models.hoard import Hoard
from tests.factories import create_user


def test_get_or_create_is_idempotent():
    user = create_user("hoarder_a")
    h1 = Hoard.get_or_create(user.id)
    db.session.commit()
    h2 = Hoard.get_or_create(user.id)
    assert h1.id == h2.id
    assert h1.copper == 0
    assert h1.items_json == "[]"


def test_hoard_one_row_per_user():
    user = create_user("hoarder_b")
    Hoard.get_or_create(user.id)
    db.session.commit()
    Hoard.get_or_create(user.id)
    db.session.commit()
    assert Hoard.query.filter_by(user_id=user.id).count() == 1
