import importlib
import runpy
import sys
from pathlib import Path
import types

import pytest

# We will import run.py as a module and exercise parse_args + main with patched
# start_server / start_admin_shell so we do not actually start networking.

@pytest.fixture()
def run_module(monkeypatch):
    # Ensure a clean import each time (important because run.py reads VERSION once)
    if 'run' in sys.modules:
        del sys.modules['run']
    mod = importlib.import_module('run')
    return mod


def test_version_flag_outputs_version(run_module, capsys):
    ver = run_module.__version__
    # argparse handles --version and exits by raising SystemExit
    with pytest.raises(SystemExit) as exc:
        run_module.parse_args(['--version'])  # parse_args triggers version action
    assert exc.value.code == 0
    captured = capsys.readouterr().out
    assert ver in captured
    assert 'Adventure MUD Server' in captured


def test_default_command_is_server(run_module):
    ns = run_module.parse_args([])
    assert ns.command == 'server'


def test_server_main_invokes_start_server(monkeypatch, run_module, capsys):
    calls = {}

    def fake_start_server(host, port, debug):  # signature match
        calls['called'] = True
        calls['host'] = host
        calls['port'] = port
        calls['debug'] = debug

    def fake_start_admin_shell():  # not used here
        calls['admin_called'] = True

    monkeypatch.setenv('PORT', '5555')  # ensure env port path is exercised
    monkeypatch.setenv('HOST', '127.0.0.1')

    # Patch after import of run_module but before main() dynamic import inside it.
    # We patch app.server symbols so that when run.main imports them they are replaced.
    import app.server as server_mod
    monkeypatch.setattr(server_mod, 'start_server', fake_start_server)
    monkeypatch.setattr(server_mod, 'start_admin_shell', fake_start_admin_shell)

    exit_code = run_module.main(['server'])
    assert exit_code == 0
    assert calls.get('called') is True
    assert calls.get('host') == '127.0.0.1'
    assert calls.get('port') == 5555
    assert calls.get('debug') is False


def test_server_main_debug_flag(monkeypatch, run_module):
    calls = {}
    def fake_start_server(host, port, debug):
        calls['debug'] = debug
    def fake_start_admin_shell():
        pass
    import app.server as server_mod
    monkeypatch.setattr(server_mod, 'start_server', fake_start_server)
    monkeypatch.setattr(server_mod, 'start_admin_shell', fake_start_admin_shell)
    run_module.main(['server', '--debug'])
    assert calls['debug'] is True


def test_admin_mode_invokes_shell(monkeypatch, run_module):
    called = {}
    def fake_start_server(*a, **k):
        called['server'] = True
    def fake_start_admin_shell():
        called['admin'] = True
    import app.server as server_mod
    monkeypatch.setattr(server_mod, 'start_server', fake_start_server)
    monkeypatch.setattr(server_mod, 'start_admin_shell', fake_start_admin_shell)
    run_module.main(['admin'])
    assert 'admin' in called and 'server' not in called


def test_env_file_argument(monkeypatch, tmp_path, run_module):
    # Create a temporary .env file to ensure load_dotenv path is executed if package present.
    # If python-dotenv is not installed, the code path is skipped under pragma: no cover, so we
    # simply ensure no exception occurs.
    env_file = tmp_path / '.env'
    env_file.write_text('HOST=0.0.0.0\nPORT=6001\n')

    calls = {}
    def fake_start_server(host, port, debug):
        calls['host'] = host
        calls['port'] = port
    def fake_start_admin_shell():
        pass
    import app.server as server_mod
    monkeypatch.setattr(server_mod, 'start_server', fake_start_server)
    monkeypatch.setattr(server_mod, 'start_admin_shell', fake_start_admin_shell)

    run_module.main(['--env-file', str(env_file), 'server'])
    # We don't assert host/port because python-dotenv may or may not be installed.
    # Just ensure start_server was invoked.
    assert 'host' in calls and 'port' in calls
