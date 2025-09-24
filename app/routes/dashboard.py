"""
project: Adventure MUD
module: dashboard.py
https://github.com/zebadrabbit/Adventure
License: MIT

Dashboard and character management routes for Adventure MUD.

This module provides the dashboard view, character creation, party selection,
autofill, and character deletion logic. All routes require authentication.
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask import jsonify
from flask_login import login_required, current_user
from app.models.models import Character, User
from app.models.xp import xp_for_level
from app import db
import json

bp_dashboard = Blueprint('dashboard', __name__)


@bp_dashboard.route('/dashboard', methods=['GET', 'POST'])
@login_required
def dashboard():
    """
    Display the user's characters and handle character creation and party selection.

    GET: Show all characters for the current user, with class, stats, and inventory.
    POST: Handle character creation, party selection, email/password update, and adventure start.
    """
    import hashlib
    import random
    # POST: handle form submissions
    if request.method == 'POST':
        # Defensive: capture a stable user id even if the underlying SQLAlchemy instance
        # becomes detached between test requests. Instead of force-logging the user out
        # (which caused a regression where subsequent API calls received 302 redirects),
        # fall back to the session stored _user_id / user_id value when possible.
        current_user_id = None
        try:  # happy path: attached user object
            current_user_id = getattr(current_user, 'id', None)
        except Exception:  # detached or other access error
            current_user_id = None
        if current_user_id is None:
            # Fallback to session keys used by flask-login / our tests
            sid = session.get('_user_id') or session.get('user_id')
            if sid is not None:
                try:
                    current_user_id = int(sid)
                except (TypeError, ValueError):
                    current_user_id = None
        if current_user_id is None:
            # As a last resort, redirect to login (rare)
            from flask_login import logout_user
            logout_user()
            return redirect(url_for('auth.login'))
        form_type = request.form.get('form')
        if form_type == 'update_email':
            new_email = request.form.get('email', '').strip() or None
            if new_email and ('@' not in new_email or '.' not in new_email):
                flash('Please enter a valid email address.', 'warning')
            else:
                user = db.session.get(User, current_user_id)
                user.email = new_email
                db.session.commit()
                flash('Email updated.' if new_email else 'Email cleared.')
            return redirect(url_for('dashboard.dashboard'))
        elif form_type == 'change_password':
            from werkzeug.security import check_password_hash, generate_password_hash
            current_pw = request.form.get('current_password', '')
            new_pw = request.form.get('new_password', '')
            confirm_pw = request.form.get('confirm_password', '')
            if not new_pw or len(new_pw) < 6:
                flash('New password must be at least 6 characters.', 'warning')
                return redirect(url_for('dashboard.dashboard'))
            if new_pw != confirm_pw:
                flash('New password and confirmation do not match.', 'warning')
                return redirect(url_for('dashboard.dashboard'))
            user = db.session.get(User, current_user_id)
            if not check_password_hash(user.password, current_pw):
                flash('Current password is incorrect.', 'danger')
                return redirect(url_for('dashboard.dashboard'))
            user.password = generate_password_hash(new_pw)
            db.session.commit()
            flash('Password changed successfully.')
            return redirect(url_for('dashboard.dashboard'))
        elif form_type == 'start_adventure':
            # Preserve existing dungeon seed & instance if already set via /api/dungeon/seed.
            # Only clear transient non-persistent structures.
            session.pop('party', None)
            session.pop('dungeon', None)
            session.pop('dungeon_pos', None)
            ids = request.form.getlist('party_ids')
            try:
                party_ids = list({int(i) for i in ids})
            except ValueError:
                party_ids = []
            if not (1 <= len(party_ids) <= 4):
                flash('Select between 1 and 4 characters to begin the adventure.', 'warning')
                return redirect(url_for('dashboard.dashboard'))
            chars = Character.query.filter(Character.id.in_(party_ids), Character.user_id == current_user_id).all()
            if len(chars) != len(party_ids):
                flash('One or more selected characters are invalid.', 'danger')
                return redirect(url_for('dashboard.dashboard'))
            party = []
            for c in chars:
                s = json.loads(c.stats)
                cls = s.get('class') or 'unknown'
                party.append({
                    'id': c.id,
                    'name': c.name,
                    'class': cls.capitalize(),
                    'hp': s.get('hp', 0),
                    'mana': s.get('mana', 0)
                })
            session['party'] = party
            from app.models.dungeon_instance import DungeonInstance
            seed = session.get('dungeon_seed')
            dungeon_instance_id = session.get('dungeon_instance_id')
            instance = None
            if dungeon_instance_id:
                instance = db.session.get(DungeonInstance, dungeon_instance_id)
            if instance is None:
                # If no existing instance (user never touched seed widget/API), fallback to random seed here.
                import random
                seed = seed or random.randint(1, 1_000_000)
                instance = DungeonInstance(user_id=current_user_id, seed=seed, pos_x=0, pos_y=0, pos_z=0)
                db.session.add(instance)
                db.session.commit()
                session['dungeon_instance_id'] = instance.id
                session['dungeon_seed'] = instance.seed
            return redirect(url_for('dungeon.adventure'))
        # Default: character creation form
        name = request.form['name']
        char_class = request.form['char_class']
        from app.routes.main import BASE_STATS, STARTER_ITEMS
        stats = BASE_STATS.get(char_class, BASE_STATS['fighter'])
        coins = {'gold': 5, 'silver': 20, 'copper': 50}
        items = STARTER_ITEMS.get(char_class, STARTER_ITEMS['fighter'])
        character = Character(
            user_id=current_user_id,
            name=name,
            stats=json.dumps({**stats, **coins, 'class': char_class}),
            gear=json.dumps({}),
            items=json.dumps(items),
            xp=0,
            level=1
        )
        db.session.add(character)
        db.session.commit()
        flash(f'Character {name} the {char_class} created!')
        return redirect(url_for('dashboard.dashboard'))
    # GET: show dashboard
    try:
        uid = current_user.id
    except Exception:
        from flask_login import logout_user
        logout_user()
        return redirect(url_for('auth.login'))
    characters = Character.query.filter_by(user_id=uid).all()
    class_map = {
        'fighter': lambda s: s['str'] >= s['dex'] and s['str'] >= s['int'] and s['str'] >= s['wis'],
        'mage':    lambda s: s['int'] >= s['str'] and s['int'] >= s['dex'] and s['int'] >= s['wis'],
        'druid':   lambda s: s['wis'] >= s['str'] and s['wis'] >= s['dex'] and s['wis'] >= s['int'],
        'ranger':  lambda s: s['dex'] >= s['str'] and s['wis'] >= s['int'],
        'rogue':   lambda s: s['dex'] >= s['str'] and s['dex'] >= s['int'] and s['dex'] >= s['wis'],
        'cleric':  lambda s: True
    }
    char_list = []
    _backfilled = False
    for c in characters:
        stats = json.loads(c.stats)
        stats_class = stats.pop('class', None)
        coins = {
            'gold': stats.pop('gold', 0),
            'silver': stats.pop('silver', 0),
            'copper': stats.pop('copper', 0)
        }
        try:
            item_slugs = json.loads(c.items) if c.items else []
        except Exception:
            item_slugs = []
        from app.models.models import Item
        items = Item.query.filter(Item.slug.in_(item_slugs)).all() if item_slugs else []
        items_by_slug = {i.slug: i for i in items}
        inventory = []
        for slug in item_slugs:
            it = items_by_slug.get(slug)
            if it:
                inventory.append({'slug': it.slug, 'name': it.name, 'type': it.type})
        if stats_class:
            class_name = stats_class.capitalize()
        else:
            if 'herbal-pouch' in item_slugs:
                class_name = 'Druid'
            elif 'hunting-bow' in item_slugs:
                class_name = 'Ranger'
            else:
                if class_map['fighter'](stats):
                    class_name = 'Fighter'
                elif class_map['mage'](stats):
                    class_name = 'Mage'
                elif class_map['druid'](stats):
                    class_name = 'Druid'
                elif class_map['ranger'](stats):
                    class_name = 'Ranger'
                elif class_map['rogue'](stats):
                    class_name = 'Rogue'
                else:
                    class_name = 'Cleric'
            new_stats = dict(stats)
            new_stats.update(coins)
            new_stats['class'] = class_name.lower()
            c.stats = json.dumps(new_stats)
            _backfilled = True
        char_list.append({
            'id': c.id,
            'name': c.name,
            'stats': stats,
            'coins': coins,
            'inventory': inventory,
            'class_name': class_name,
            'xp': getattr(c, 'xp', 0),
            'level': getattr(c, 'level', 1),
            'xp_next': xp_for_level(getattr(c, 'level', 1) + 1)
        })
    if _backfilled:
        db.session.commit()
    user_email = None
    try:
        user_obj = db.session.get(User, current_user.id)
        user_email = getattr(user_obj, 'email', None)
    except Exception:
        user_email = None
    # Pre-fill dungeon seed if present in session
    dungeon_seed = session.get('dungeon_seed', '')
    return render_template('dashboard.html', characters=char_list, user_email=user_email, dungeon_seed=dungeon_seed)

@bp_dashboard.route('/delete_character/<int:char_id>', methods=['POST'])
def delete_character(char_id):
    """Delete a character by id and redirect to dashboard."""
    from flask_login import current_user
    from app.models.models import Character
    c = Character.query.filter_by(id=char_id, user_id=current_user.id).first()
    if c:
        from app import db
        db.session.delete(c)
        db.session.commit()
        from flask import flash
        flash(f'Character {c.name} deleted.', 'info')
    else:
        from flask import flash
        flash('Character not found or not yours.', 'warning')
    from flask import redirect, url_for
    return redirect(url_for('dashboard.dashboard'))

# Route to autofill party with random characters if user has fewer than 4
# POST /autofill_characters
# Returns: {"created": <number>}
@bp_dashboard.route('/autofill_characters', methods=['POST'])
@login_required
def autofill_characters():
    """Autofill the user's roster up to 4 characters with random class/name.

    Response JSON:
        { "created": <int>, "total": <int>, "characters": [ {id,name,class,level}, ... ] }
    Status Codes:
        201 when one or more characters were created
        200 when no creation was necessary (already had 4)
    """
    # Explicit guard (in addition to @login_required) to defend against any test that toggles LOGIN_DISABLED
    if not current_user.is_authenticated or not session.get('_user_id'):
        # If this looks like an AJAX/fetch request prefer JSON 401, else redirect
        wants_json = request.headers.get('X-Requested-With') == 'fetch' or 'application/json' in (request.headers.get('Accept') or '')
        if wants_json:
            return jsonify({'error':'unauthorized'}), 401
        return redirect(url_for('auth.login'))
    current_user_id = current_user.id

    from app.routes.main import BASE_STATS, STARTER_ITEMS, NAME_POOLS
    import random, json as _json

    existing = Character.query.filter_by(user_id=current_user_id).all()
    needed = max(0, 4 - len(existing))
    created = []
    if needed:
        classes = list(BASE_STATS.keys())
        for _ in range(needed):
            cls = random.choice(classes)
            # Pick a name from pool; if exhausted or missing, synthesize one
            pool = NAME_POOLS.get(cls, [])
            base_name = random.choice(pool) if pool else cls.capitalize()
            # Add a short randomized suffix to avoid accidental duplicates
            suffix = random.randint(100, 999)
            name = f"{base_name}{suffix}"
            # Ensure uniqueness for this user (retry a few times if collision)
            attempts = 0
            while attempts < 5 and (any(c.name == name for c in existing) or any(c.name == name for c in created)):
                suffix = random.randint(100, 999)
                name = f"{base_name}{suffix}"
                attempts += 1
            stats = BASE_STATS.get(cls, BASE_STATS['fighter'])
            coins = {'gold': 5, 'silver': 20, 'copper': 50}
            items = STARTER_ITEMS.get(cls, STARTER_ITEMS['fighter'])
            character = Character(
                user_id=current_user_id,
                name=name,
                stats=_json.dumps({**stats, **coins, 'class': cls}),
                gear=_json.dumps({}),
                items=_json.dumps(items),
                xp=0,
                level=1
            )
            db.session.add(character)
            created.append(character)
        db.session.commit()
        existing.extend(created)

    # Prepare response payload
    payload_chars = []
    from app.models.models import Item
    for c in existing:
        try:
            s = json.loads(c.stats)
        except Exception:
            s = {}
        coins = {k: s.get(k, 0) for k in ('gold','silver','copper')}
        cls_name = (s.get('class') or 'unknown').capitalize()
        # Inventory expansion
        try:
            item_slugs = json.loads(c.items) if c.items else []
        except Exception:
            item_slugs = []
        items = []
        if item_slugs:
            db_items = Item.query.filter(Item.slug.in_(item_slugs)).all()
            by_slug = {i.slug: i for i in db_items}
            for slug in item_slugs:
                it = by_slug.get(slug)
                if it:
                    items.append({'slug': it.slug, 'name': it.name, 'type': it.type})
        # Remove coin/class keys from stats copy for clarity
        stats_copy = {k:v for k,v in s.items() if k not in ('gold','silver','copper','class')}
        payload_chars.append({
            'id': c.id,
            'name': c.name,
            'class': cls_name,
            'level': getattr(c, 'level', 1),
            'coins': coins,
            'stats': stats_copy,
            'inventory': items
        })
    status = 201 if created else 200
    return jsonify({'created': len(created), 'total': len(existing), 'characters': payload_chars}), status

# Route to delete a character by id (POST)
# POST /delete_character/<int:char_id>
# Redirects to dashboard after deletion

# Add other dashboard/character management routes here

# Add other dashboard/character management routes here
