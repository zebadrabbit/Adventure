import json
from app import db
from app.models.models import User, Character
from werkzeug.security import generate_password_hash
import pytest

@pytest.fixture()
def client_authed(client, test_app):
    with test_app.app_context():
        user = User.query.filter_by(username='dashuser').first()
        if not user:
            user = User(username='dashuser', password=generate_password_hash('pw123456'))
            db.session.add(user)
            db.session.commit()
    client.post('/login', data={'username': 'dashuser', 'password': 'pw123456'})
    return client


def _create_character(user_id, name='Hero', cls='fighter'):
    from app.routes.main import BASE_STATS, STARTER_ITEMS
    stats = BASE_STATS[cls]
    character = Character(
        user_id=user_id,
        name=name,
        stats=json.dumps({**stats, 'gold':5,'silver':2,'copper':1,'class':cls}),
        gear=json.dumps([]),
        items=json.dumps(STARTER_ITEMS[cls]),
        xp=0,
        level=1,
    )
    db.session.add(character)


def test_dashboard_get_authed(client_authed):
    resp = client_authed.get('/dashboard')
    assert resp.status_code == 200
    assert b'dashboard' in resp.data.lower()


def test_character_creation_flow(client_authed):
    resp = client_authed.post('/dashboard', data={'name': 'Auron', 'char_class': 'fighter'}, follow_redirects=True)
    assert b'Character Auron the fighter created!' in resp.data
    # Character appears in subsequent GET
    page = client_authed.get('/dashboard')
    assert b'Auron' in page.data


def test_email_update_and_clear(client_authed):
    # Set email
    resp = client_authed.post('/dashboard', data={'form':'update_email','email':'user@example.com'}, follow_redirects=True)
    assert b'Email updated.' in resp.data
    # Clear email
    resp2 = client_authed.post('/dashboard', data={'form':'update_email','email':''}, follow_redirects=True)
    assert b'Email cleared.' in resp2.data


def test_change_password_validation(client_authed):
    # Too short new password
    resp = client_authed.post('/dashboard', data={'form':'change_password','current_password':'pw123456','new_password':'abc','confirm_password':'abc'}, follow_redirects=True)
    assert b'New password must be at least 6 characters.' in resp.data
    # Mismatch
    resp2 = client_authed.post('/dashboard', data={'form':'change_password','current_password':'pw123456','new_password':'abcdef','confirm_password':'ghijkl'}, follow_redirects=True)
    assert b'New password and confirmation do not match.' in resp2.data


def test_change_password_success(client_authed):
    resp = client_authed.post('/dashboard', data={'form':'change_password','current_password':'pw123456','new_password':'newstrong','confirm_password':'newstrong'}, follow_redirects=True)
    assert b'Password changed successfully.' in resp.data
    # Re-login with new password to confirm
    client_authed.get('/logout')
    login2 = client_authed.post('/login', data={'username': 'dashuser', 'password': 'newstrong'}, follow_redirects=True)
    assert b'dashboard' in login2.data.lower()


def test_start_adventure_party_validation(client_authed):
    # Create two characters manually
    from flask import current_app
    with current_app.app_context():
        user = User.query.filter_by(username='dashuser').first()
        _create_character(user.id, name='Hero1')
        _create_character(user.id, name='Hero2')
        db.session.commit()
        user_id = user.id
    # Submit with invalid (none selected)
    resp = client_authed.post('/dashboard', data={'form':'start_adventure'}, follow_redirects=True)
    assert b'Select between 1 and 4 characters' in resp.data or b'Select between 1 and 4 characters' in resp.data
    # Submit with 1 valid id
    from flask import current_app
    with current_app.app_context():
        chars = Character.query.filter_by(user_id=user_id).all()
        first_id = chars[0].id
    resp2 = client_authed.post('/dashboard', data={'form':'start_adventure','party_ids':str(first_id)}, follow_redirects=False)
    # Should redirect to /adventure (dungeon) route
    assert resp2.status_code in (302, 303)
