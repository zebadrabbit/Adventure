
import eventlet
import threading
import queue
import signal
import sys
from app import app, socketio, db
from app.models.models import User
from werkzeug.security import generate_password_hash

# Global event queue for admin shell
admin_event_queue = queue.Queue()
app.config['ADMIN_EVENT_QUEUE'] = admin_event_queue

def start_server(host='0.0.0.0', port=5000):
    with app.app_context():
        db.create_all()
    try:
        socketio.run(app, host=host, port=port)
    except KeyboardInterrupt:
        print("\n[INFO] Server stopped by user (Ctrl+C)")
        sys.exit(0)

def start_admin_shell():
    with app.app_context():
        db.create_all()
    admin_shell()

def admin_shell():
    """
    Admin shell for server management.
    Commands:
      help                        Show this help message
      exit                        Exit the admin shell
      create user <username> [<password>]
                                Create a new user with optional password (default: changeme)
      list users                  List all registered users
      delete user <username>      Delete a user by username
    """
    print("Admin shell. Type 'help' for commands. Type 'exit' to quit.")

    def event_printer():
        while True:
            msg = admin_event_queue.get()
            if msg == '__exit__':
                break
            print(f"\n[EVENT] {msg}")
            print('> ', end='', flush=True)

    printer_thread = threading.Thread(target=event_printer, daemon=True)
    printer_thread.start()

    def print_help():
        print("""
Available commands:
  help                        Show this help message
  exit                        Exit the admin shell
  create user <username> [<password>]
                              Create a new user with optional password (default: changeme)
  list users                  List all registered users
  delete user <username>      Delete a user by username
Examples:
  create user alice secret123
  list users
  delete user alice
""")

    while True:
        try:
            cmd = input('> ').strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting admin shell.")
            admin_event_queue.put('__exit__')
            break
        if not cmd:
            continue
        parts = cmd.split()
        if parts[0] == 'exit':
            admin_event_queue.put('__exit__')
            break
        elif parts[0] == 'help':
            print_help()
            continue
        elif parts[0] == 'create' and len(parts) >= 3 and parts[1] == 'user':
            username = parts[2]
            password = parts[3] if len(parts) > 3 else 'changeme'
            with app.app_context():
                if User.query.filter_by(username=username).first():
                    print(f"[ERROR] User '{username}' already exists.")
                else:
                    user = User(username=username, password=generate_password_hash(password))
                    db.session.add(user)
                    db.session.commit()
                    print(f"[OK] User '{username}' created with password '{password}'.")
            continue
        elif parts[0] == 'list' and len(parts) == 2 and parts[1] == 'users':
            with app.app_context():
                users = User.query.all()
                if not users:
                    print("[INFO] No users found.")
                else:
                    print("Registered users:")
                    for u in users:
                        print(f"  - {u.username}")
            continue
        elif parts[0] == 'delete' and len(parts) == 3 and parts[1] == 'user':
            username = parts[2]
            with app.app_context():
                user = User.query.filter_by(username=username).first()
                if not user:
                    print(f"[ERROR] User '{username}' does not exist.")
                else:
                    db.session.delete(user)
                    db.session.commit()
                    print(f"[OK] User '{username}' deleted.")
            continue
        else:
            print("[ERROR] Unknown or malformed command. Type 'help' for a list of commands.")