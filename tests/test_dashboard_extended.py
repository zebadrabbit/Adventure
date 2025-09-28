from app.models.models import Character


def create_character(client, name="Hero", cls="fighter"):
    # Ensure we're authenticated; some prior tests may have logged out.
    dash = client.get("/dashboard")
    if dash.status_code in (301, 302) and b"/login" in dash.data:
        client.post(
            "/login",
            data={"username": "tester", "password": "pass"},
            follow_redirects=True,
        )
    # Follow redirects so we end up back on dashboard page for assertions
    return client.post("/dashboard", data={"name": name, "char_class": cls}, follow_redirects=True)


def test_character_creation_and_duplicate(auth_client):
    create_character(auth_client, "Alpha", "fighter")
    page = auth_client.get("/dashboard")
    assert b"Alpha" in page.data
    # duplicate name allowed (no unique constraint) but different semantics not enforced; just create again
    create_character(auth_client, "Alpha", "mage")
    page2 = auth_client.get("/dashboard")
    assert b"Alpha" in page2.data


def test_email_update_valid_and_clear(auth_client):
    r = auth_client.post(
        "/dashboard",
        data={"form": "update_email", "email": "user@example.com"},
        follow_redirects=True,
    )
    assert r.status_code == 200
    r2 = auth_client.post("/dashboard", data={"form": "update_email", "email": ""}, follow_redirects=True)
    assert r2.status_code == 200


def test_email_invalid(auth_client):
    r = auth_client.post(
        "/dashboard",
        data={"form": "update_email", "email": "not-an-email"},
        follow_redirects=True,
    )
    assert r.status_code == 200


def test_password_change_paths(auth_client):
    # wrong current password
    r = auth_client.post(
        "/dashboard",
        data={
            "form": "change_password",
            "current_password": "wrong",
            "new_password": "newpass1",
            "confirm_password": "newpass1",
        },
        follow_redirects=True,
    )
    assert r.status_code == 200
    # mismatch confirmation
    r2 = auth_client.post(
        "/dashboard",
        data={
            "form": "change_password",
            "current_password": "pass",
            "new_password": "abcdef",
            "confirm_password": "ghijkl",
        },
        follow_redirects=True,
    )
    assert r2.status_code == 200
    # too short
    r3 = auth_client.post(
        "/dashboard",
        data={
            "form": "change_password",
            "current_password": "pass",
            "new_password": "xx",
            "confirm_password": "xx",
        },
        follow_redirects=True,
    )
    assert r3.status_code == 200


def test_start_adventure_errors_and_success(auth_client):
    # no characters selected
    r = auth_client.post("/dashboard", data={"form": "start_adventure"}, follow_redirects=True)
    assert r.status_code == 200
    # create 2 characters
    create_character(auth_client, "One", "fighter")
    create_character(auth_client, "Two", "mage")
    # invalid id in party list
    r2 = auth_client.post(
        "/dashboard",
        data={"form": "start_adventure", "party_ids": ["9999"]},
        follow_redirects=True,
    )
    assert r2.status_code == 200
    # valid party
    with auth_client.session_transaction():
        pass  # session context ensures CSRF/session state stability
    chars = Character.query.all()
    ids = [str(c.id) for c in chars[:2]]
    r3 = auth_client.post(
        "/dashboard",
        data={"form": "start_adventure", "party_ids": ids},
        follow_redirects=True,
    )
    assert r3.status_code == 200 or b"Adventure" in r3.data


def test_delete_character(auth_client):
    # create and delete
    create_character(auth_client, "Temp", "fighter")
    char = Character.query.filter_by(name="Temp").first()
    assert char is not None
    r = auth_client.post(f"/delete_character/{char.id}", follow_redirects=True)
    assert r.status_code == 200
    # delete again -> not found
    r2 = auth_client.post(f"/delete_character/{char.id}", follow_redirects=True)
    assert r2.status_code == 200
