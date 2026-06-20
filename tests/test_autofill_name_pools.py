"""Autofilled character names should use the curated fantasy NAME_POOLS
unsuffixed when possible, instead of always appending a numeric suffix
(e.g. "Barbarian735") which defeats the purpose of having a name pool.
"""

import re

from werkzeug.security import generate_password_hash

from app import db
from app.models.models import Character, User
from app.routes.main import BASE_STATS, NAME_POOLS


def test_every_class_has_a_name_pool():
    missing = [cls for cls in BASE_STATS if cls not in NAME_POOLS or not NAME_POOLS[cls]]
    assert missing == [], f"classes missing a NAME_POOLS entry: {missing}"


def test_autofill_uses_unsuffixed_pool_names(client, test_app):
    with test_app.app_context():
        user = User.query.filter_by(username="autofill-names").first()
        if not user:
            user = User(username="autofill-names", password=generate_password_hash("pw123456"))
            db.session.add(user)
            db.session.commit()
        Character.query.filter_by(user_id=user.id).delete()
        db.session.commit()

    client.post("/login", data={"username": "autofill-names", "password": "pw123456"})
    r = client.post("/autofill_characters")
    assert r.status_code in (200, 201)
    data = r.get_json()

    all_pool_names = {name for pool in NAME_POOLS.values() for name in pool}
    for ch in data["characters"]:
        name = ch["name"]
        # A name with a trailing numeric suffix glued onto a known pool name
        # (e.g. "Brakus735") means the bug is still present.
        stripped = re.sub(r"\d+$", "", name)
        if stripped != name:
            assert stripped not in all_pool_names, (
                f"name {name!r} suffixed a pool name {stripped!r} instead of using it directly"
            )
