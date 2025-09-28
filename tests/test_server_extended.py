import builtins
import importlib
import logging
from pathlib import Path

from app import db


def test_admin_shell_help_and_unknown(monkeypatch):
    server = importlib.import_module("app.server")
    inputs = iter(["help", "foo bar", "exit"])  # unknown command
    outputs = []

    def fake_input(prompt=""):
        try:
            return next(inputs)
        except StopIteration:
            raise EOFError

    def fake_print(*a, **k):
        text = " ".join(str(x) for x in a)
        outputs.append(text)

    monkeypatch.setattr(builtins, "input", fake_input)
    monkeypatch.setattr(builtins, "print", fake_print)

    server.admin_shell()

    # Help snippet
    assert any("Available commands:" in o for o in outputs)
    # Unknown command error
    assert any("Unknown or malformed command" in o for o in outputs)


def test_run_migrations_idempotent():
    server = importlib.import_module("app.server")
    with server.app.app_context():
        # Ensure base tables exist first (mirrors real startup sequence)
        server.db.create_all()
        server._run_migrations()
        server._run_migrations()
        # Ensure expected columns exist (role & email on user; xp on character)
        res = db.session.execute(db.text("PRAGMA table_info('user')"))
        cols = {r[1] for r in res}
        assert "email" in cols and "role" in cols


def test_configure_logging_sets_handlers(tmp_path, monkeypatch):
    server = importlib.import_module("app.server")
    # Point instance path to temp so log file goes there
    monkeypatch.setattr(server.app, "instance_path", str(tmp_path))
    with server.app.app_context():
        server._configure_logging()
    root = logging.getLogger()
    # Expect at least one RotatingFileHandler and one StreamHandler
    kinds = {type(h).__name__ for h in root.handlers}
    assert "RotatingFileHandler" in kinds and "StreamHandler" in kinds
    # Log file should have been created
    log_path = Path(tmp_path) / "app.log"
    assert log_path.exists()
