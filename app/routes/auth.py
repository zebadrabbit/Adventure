"""Authentication routes: login, register, logout.

Emits login/logout events to the admin shell via an in-app queue when available.
"""

from flask import Blueprint, render_template, redirect, url_for, request, flash, current_app
from flask_login import login_user, logout_user, login_required
from app.models.models import User
from app import db, login_manager
from werkzeug.security import generate_password_hash, check_password_hash
import hashlib, logging

bp = Blueprint('auth', __name__)

@login_manager.user_loader
def load_user(user_id):
    from app import db
    return db.session.get(User, int(user_id))

@bp.route('/login', methods=['GET', 'POST'])
def login():
    """Login form; supports username OR email; auto-upgrades legacy plaintext passwords.

    Backward compatibility:
      Older accounts stored a raw plaintext password (rare, but possible if created
      prior to hashing enforcement). If detected (hash check fails & stored value
      lacks a hash prefix), we hash the provided password if it matches exactly and
      persist the upgrade transparently.
    """
    if request.method == 'POST':
        ident = request.form['username'].strip()
        password = request.form['password']
        # Case-insensitive username/email lookup
        from sqlalchemy import func
        user = User.query.filter(func.lower(User.username) == ident.lower()).first()
        if not user and '@' in ident:
            user = User.query.filter(func.lower(User.email) == ident.lower()).first()
        if user:
            stored = user.password or ''
            # Detect probable legacy plaintext (Werkzeug hashes start with method prefix like 'pbkdf2:')
            is_legacy_plain = not stored.startswith('pbkdf2:') and not stored.startswith('scrypt:') and not stored.startswith('argon2:')
            # Detect legacy hex SHA256 (64 hex chars) and upgrade if matches hash(password)
            is_legacy_hex = False
            if is_legacy_plain and len(stored) == 64:
                try:
                    int(stored, 16)
                    is_legacy_hex = True
                except ValueError:
                    is_legacy_hex = False
            if is_legacy_plain:
                if stored == password:
                    user.password = generate_password_hash(password)
                    db.session.commit()
                    stored = user.password
                elif is_legacy_hex:
                    if hashlib.sha256(password.encode('utf-8')).hexdigest() == stored:
                        user.password = generate_password_hash(password)
                        db.session.commit()
                        stored = user.password
            if stored.startswith(('pbkdf2:','scrypt:','argon2:')) and check_password_hash(stored, password):
                login_user(user)
                q = current_app.config.get('ADMIN_EVENT_QUEUE')
                if q:
                    q.put(f"User '{user.username}' logged in.")
                return redirect(url_for('dashboard.dashboard'))
        else:
            logging.info("Login failed: user not found for identifier=%s", ident)
        flash('Invalid credentials')
    return render_template('login.html')

@bp.route('/register', methods=['GET', 'POST'])
def register():
    """Registration form; on POST creates a new user and logs them in."""
    if request.method == 'POST':
        username = request.form['username']
        password = generate_password_hash(request.form['password'])
        if User.query.filter_by(username=username).first():
            flash('Username already exists')
        else:
            user = User(username=username, password=password)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            return redirect(url_for('dashboard.dashboard'))
    return render_template('register.html')

@bp.route('/logout')
@login_required
def logout():
    """Logs the current user out and redirects to the login page."""
    username = None
    if hasattr(current_app, 'login_manager') and hasattr(current_app.login_manager, '_login_callback'):
        # Try to get username for event
        from flask_login import current_user
        if current_user.is_authenticated:
            username = current_user.username
    logout_user()
    # Send logout event to admin shell if running
    q = current_app.config.get('ADMIN_EVENT_QUEUE')
    if q and username:
        q.put(f"User '{username}' logged out.")
    return redirect(url_for('auth.login'))
