import builtins
import io
from contextlib import redirect_stdout

from werkzeug.security import generate_password_hash

from app import app, db
from app.models.models import User
from app.server import admin_shell


def run_shell_script(commands):
    """Run admin_shell with a scripted list of commands, capturing stdout.
    We simulate user input by patching builtins.input to pop from commands list.
    """
    output = io.StringIO()
    commands_iter = iter(commands)

    def fake_input(prompt=""):
        try:
            return next(commands_iter)
        except StopIteration:
            raise KeyboardInterrupt  # end shell

    orig_input = builtins.input
    builtins.input = fake_input
    try:
        with app.app_context():
            db.create_all()
            if not User.query.filter_by(username="base").first():
                db.session.add(User(username="base", password=generate_password_hash("x")))
                db.session.commit()
        with redirect_stdout(output):
            try:
                admin_shell()
            except SystemExit:
                pass
            except KeyboardInterrupt:
                pass
    finally:
        builtins.input = orig_input
    return output.getvalue()


def test_admin_shell_full_flow():
    script = [
        "help",
        "create user alice secret",
        # duplicate
        "create user alice secret",
        "list users",
        "set role alice admin",
        # invalid role
        "set role alice superuser",
        "ban alice Being loud",
        "list banned",
        "show user alice",
        "note user alice First note",
        # empty note error
        "note user alice",
        "unban alice",
        "set email alice alice@example.com",
        "show user alice",
        "delete user alice",
        # unknown command
        "frobnicate",
        "exit",
    ]
    out = run_shell_script(script)
    # Assertions for key outputs
    assert "Available commands:" in out
    assert "User 'alice' created" in out
    assert "already exists" in out
    assert "Registered users:" in out
    assert "Role for" in out and "admin" in out
    assert "Role must be one of" in out  # invalid role
    assert "banned. Reason: Being loud" in out
    assert "Banned users:" in out
    assert "User: alice" in out and "Banned: True" in out
    assert "Note added for" in out
    assert "Note text required." in out  # empty note error
    assert "unbanned" in out
    assert "Email for" in out and "alice@example.com" in out
    assert "deleted" in out
    assert "Unknown or malformed command" in out
