"""Authentication routes: login, register, logout.

Emits login/logout events to the admin shell via an in-app queue when available.
"""

from flask import Blueprint, render_template, redirect, url_for, request, flash, current_app
from flask_login import login_user, logout_user, login_required
from app.models.models import User
from app import db, login_manager
from werkzeug.security import generate_password_hash, check_password_hash

bp = Blueprint('auth', __name__)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@bp.route('/login', methods=['GET', 'POST'])
def login():
    """Login form; on POST verifies credentials and logs the user in."""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            # Send login event to admin shell if running
            q = current_app.config.get('ADMIN_EVENT_QUEUE')
            if q:
                q.put(f"User '{username}' logged in.")
            return redirect(url_for('main.dashboard'))
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
            return redirect(url_for('main.dashboard'))
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
