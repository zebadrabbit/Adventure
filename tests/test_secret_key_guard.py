"""Guard: refuse to start in production with the default SECRET_KEY.

See app.__init__._check_secret_key for the production/dev detection
convention this relies on (FLASK_ENV=production, matching docker-compose.yml,
Dockerfile, and .env.example).
"""

import pytest

from app import _check_secret_key, DEFAULT_SECRET_KEY


def test_default_key_in_production_raises():
    with pytest.raises(RuntimeError):
        _check_secret_key(DEFAULT_SECRET_KEY, "production")


def test_default_key_in_dev_does_not_raise():
    _check_secret_key(DEFAULT_SECRET_KEY, "development")
    _check_secret_key(DEFAULT_SECRET_KEY, "")


def test_custom_key_in_production_does_not_raise():
    _check_secret_key("a-real-secret", "production")
