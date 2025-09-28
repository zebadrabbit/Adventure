import hashlib

import pytest
from werkzeug.security import check_password_hash

from app import create_app, db
from app.models.models import User


@pytest.fixture()
def app_mem():
    app = create_app()
    app.config.update(TESTING=True, SQLALCHEMY_DATABASE_URI="sqlite:///:memory:")
    with app.app_context():
        db.create_all()
        # Legacy SHA256 hex password
        legacy_pw = hashlib.sha256(b"MySecret!").hexdigest()
        u = User(username="CaseUser", email="case@example.com", password=legacy_pw)
        db.session.add(u)
        db.session.commit()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client_mem(app_mem):
    return app_mem.test_client()


def test_sha256_upgrade_case_insensitive_login(app_mem, client_mem):
    # Use different case in username
    resp = client_mem.post(
        "/login",
        data={"username": "caseuser", "password": "MySecret!"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    with app_mem.app_context():
        u = User.query.filter_by(username="CaseUser").first()
        assert u is not None
        assert u.password != hashlib.sha256(b"MySecret!").hexdigest()
        # Upgraded hash should now be a modern algorithm (pbkdf2 / scrypt / argon2)
        assert u.password.startswith(("pbkdf2:", "scrypt:", "argon2:"))
        assert check_password_hash(u.password, "MySecret!")
