import builtins
import importlib
from contextlib import contextmanager
import types

from app import db
from app.models.models import User

# NOTE: We purposefully avoid starting the real socket server; we exercise
# helper functions inside server.py that are safe under app context.

def test_seed_items_idempotent():
    server = importlib.import_module('app.server')
    with server.app.app_context():
        # First seed (may populate table if empty)
        server.seed_items()
        first = server.db.session.execute(db.text('select count(*) from item')).scalar()
        assert first >= 0
        # Second seed should not increase count
        server.seed_items()
        second = server.db.session.execute(db.text('select count(*) from item')).scalar()
        assert first == second


def test_admin_shell_command_create_list_delete(monkeypatch):
    server = importlib.import_module('app.server')
    inputs = iter([
        'create user testuser secret',
        'list users',
        'delete user testuser',
        'list users',
        'exit'
    ])
    outputs = []

    def fake_input(prompt=''):
        try:
            return next(inputs)
        except StopIteration:
            raise EOFError

    def fake_print(*a, **k):
        # capture outputs for assertions
        text = ' '.join(str(x) for x in a)
        outputs.append(text)

    monkeypatch.setattr(builtins, 'input', fake_input)
    monkeypatch.setattr(builtins, 'print', fake_print)

    # Run shell (will exit after commands)
    server.admin_shell()

    # Validate that create/delete messages appear
    assert any("User 'testuser' created" in o for o in outputs)
    assert any("User 'testuser' deleted" in o for o in outputs)


def test_admin_shell_password_reset_and_role(monkeypatch):
    server = importlib.import_module('app.server')
    inputs = iter([
        'create user alice secret',
        'reset password alice newpass',
        'set role alice admin',
        'passwd alice newer',
        'delete user alice',
        'exit'
    ])
    outputs = []

    def fake_input(prompt=''):
        try:
            return next(inputs)
        except StopIteration:
            raise EOFError

    def fake_print(*a, **k):
        text = ' '.join(str(x) for x in a)
        outputs.append(text)

    monkeypatch.setattr(builtins, 'input', fake_input)
    monkeypatch.setattr(builtins, 'print', fake_print)

    server.admin_shell()

    assert any("User 'alice' created" in o for o in outputs)
    assert any('Password for \'alice\' has been reset.' in o for o in outputs)
    assert any('Role for \'alice\' set to admin.' in o for o in outputs)
    assert any("User 'alice' deleted" in o for o in outputs)
