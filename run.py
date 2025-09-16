

import sys
import signal
from app.server import start_server, start_admin_shell

if __name__ == '__main__':
    mode = 'admin' if len(sys.argv) > 1 and sys.argv[1] == 'admin' else 'server'
    port = 5000
    host = '0.0.0.0'

    def handle_sigint(sig, frame):
        print("\n[INFO] Shutting down server...")
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_sigint)

    print("""
========================================
   MUD Game Server Bootup
========================================
   Mode:        {mode}
   Host:        {host}
   Port:        {port}
   Database:    sqlite:///mud.db
   WebSockets:  enabled
   Flask-Login: enabled
   Admin Shell: {admin}
========================================
""".format(
        mode=mode.upper(),
        host=host,
        port=port,
        admin='YES' if mode == 'admin' else 'NO'
    ))

    if mode == 'admin':
        start_admin_shell()
    else:
        print("[INFO] Listening for connections... Press Ctrl+C to stop.")
        start_server(host=host, port=port)
