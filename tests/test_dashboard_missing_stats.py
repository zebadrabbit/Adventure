import json


def test_dashboard_missing_stat_keys(client, test_app):
    """Dashboard should render even if a character is missing some primary stats (e.g., 'dex').

    Uses existing fixture naming (test_app) consistent with other dashboard tests.
    """
    from app import db
    from app.models.models import User, Character
    from werkzeug.security import generate_password_hash

    with test_app.app_context():
        u = User(username="nostats", password=generate_password_hash("pass"))
        db.session.add(u)
        db.session.commit()
        # Intentionally omit 'dex' and 'wis'
        partial_stats = {"str": 11, "int": 9, "hp": 10, "mana": 4}
        c = Character(
            user_id=u.id,
            name="Broken",
            stats=json.dumps(partial_stats),
            gear=json.dumps({}),
            items=json.dumps([]),
        )
        db.session.add(c)
        db.session.commit()

    # Log in
    resp = client.post("/login", data={"username": "nostats", "password": "pass"}, follow_redirects=True)
    assert resp.status_code == 200
    # Directly hit dashboard (simulates reload after server restart)
    resp2 = client.get("/dashboard")
    assert resp2.status_code == 200, resp2.text
    # Should contain character name and no stack trace
    assert "Broken" in resp2.text
    # A class label should still be inferred somewhere (e.g., Fighter/Cleric fallback)
    assert ("Fighter" in resp2.text) or ("Cleric" in resp2.text)
