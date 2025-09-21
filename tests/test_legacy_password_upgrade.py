from werkzeug.security import generate_password_hash, check_password_hash
from app import db, create_app
from app.models.models import User
import pytest

@pytest.fixture()
def legacy_app():
    app = create_app()
    app.config.update(TESTING=True, SQLALCHEMY_DATABASE_URI='sqlite:///:memory:')
    with app.app_context():
        db.create_all()
        # Legacy plaintext user
        u1 = User(username='legacy', password='plainpass', email='legacy@example.com')
        db.session.add(u1)
        # Proper hashed user
        u2 = User(username='hashed', password=generate_password_hash('secret123'), email='h@example.com')
        db.session.add(u2)
        db.session.commit()
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture()
def legacy_client(legacy_app):
    return legacy_app.test_client()


def test_legacy_plaintext_upgrade(legacy_app, legacy_client):
    # Before: stored plaintext
    with legacy_app.app_context():
        user = User.query.filter_by(username='legacy').first()
        assert user.password == 'plainpass'
    resp = legacy_client.post('/login', data={'username': 'legacy', 'password': 'plainpass'}, follow_redirects=True)
    assert resp.status_code == 200
    # After: password should be upgraded (hashed) and no longer equal raw
    with legacy_app.app_context():
        user = User.query.filter_by(username='legacy').first()
        assert user.password != 'plainpass'
        assert user.password.startswith('pbkdf2:') or user.password.startswith('scrypt:') or user.password.startswith('argon2:')


def test_login_with_email(legacy_client):
    resp = legacy_client.post('/login', data={'username': 'h@example.com', 'password': 'secret123'}, follow_redirects=True)
    assert resp.status_code == 200
    assert b'Invalid credentials' not in resp.data


def test_invalid_credentials(legacy_client):
    resp = legacy_client.post('/login', data={'username': 'hashed', 'password': 'wrong'}, follow_redirects=True)
    assert b'Invalid credentials' in resp.data
