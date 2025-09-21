from app import create_app, db
from app.models.models import User
import pytest

@pytest.fixture()
def logged_in_client(test_app):
    # Ensure a user exists and log in via session (reuse login route would require form fields; simpler direct session)
    from werkzeug.security import generate_password_hash
    with test_app.app_context():
        db.create_all()
        u = User.query.filter_by(username='cfguser').first()
        if not u:
            u = User(username='cfguser', password=generate_password_hash('pass'))
            db.session.add(u)
            db.session.commit()
        uid = u.id
    c = test_app.test_client()
    c.post('/login', data={'username':'cfguser','password':'pass'}, follow_redirects=True)
    return c

# The existing config_api endpoints are simple getters; we focus on negative auth (unauthenticated access) to document rejection.
# This supplements positive path tests elsewhere and ensures login_required wrappers are enforced.

@pytest.mark.parametrize('endpoint', [
    '/api/config/name_pools',
    '/api/config/starter_items',
    '/api/config/base_stats',
    '/api/config/class_map',
    '/api/config/class_colors'
])
def test_config_api_requires_auth(endpoint, test_app):
    c = test_app.test_client()
    r = c.get(endpoint, follow_redirects=False)
    # Flask-Login redirects to /login (302) when unauthenticated
    assert r.status_code in (302, 401)

@pytest.mark.parametrize('endpoint', [
    '/api/config/name_pools',
    '/api/config/starter_items',
    '/api/config/base_stats',
    '/api/config/class_map',
    '/api/config/class_colors'
])
def test_config_api_success(endpoint, logged_in_client):
    r = logged_in_client.get(endpoint)
    assert r.status_code == 200
    assert r.is_json
    data = r.get_json()
    assert isinstance(data, dict)
    assert len(data) > 0
