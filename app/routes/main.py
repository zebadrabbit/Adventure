"""Core application routes: home page and character dashboard."""

from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_required, current_user
from app.models.models import Character, User
from app import db
import json
from werkzeug.security import check_password_hash, generate_password_hash

bp = Blueprint('main', __name__)

@bp.route('/')
def index():
    return render_template('index.html')



@bp.route('/dashboard', methods=['GET', 'POST'])
@login_required
def dashboard():
    """Display the user's characters and handle character creation.

    On POST: create a character with base stats inferred from the chosen class.
    On GET: list existing characters with a derived class label based on stats.
    """
    if request.method == 'POST':
        # Distinguish which form was submitted using a hidden field 'form'
        form_type = request.form.get('form')
        if form_type == 'update_email':
            new_email = request.form.get('email', '').strip() or None
            # Basic sanity check; allow empty to clear
            if new_email and ('@' not in new_email or '.' not in new_email):
                flash('Please enter a valid email address.', 'warning')
            else:
                user = User.query.get(current_user.id)
                user.email = new_email
                db.session.commit()
                flash('Email updated.' if new_email else 'Email cleared.')
            return redirect(url_for('main.dashboard'))
        elif form_type == 'change_password':
            current_pw = request.form.get('current_password', '')
            new_pw = request.form.get('new_password', '')
            confirm_pw = request.form.get('confirm_password', '')
            if not new_pw or len(new_pw) < 6:
                flash('New password must be at least 6 characters.', 'warning')
                return redirect(url_for('main.dashboard'))
            if new_pw != confirm_pw:
                flash('New password and confirmation do not match.', 'warning')
                return redirect(url_for('main.dashboard'))
            user = User.query.get(current_user.id)
            if not check_password_hash(user.password, current_pw):
                flash('Current password is incorrect.', 'danger')
                return redirect(url_for('main.dashboard'))
            user.password = generate_password_hash(new_pw)
            db.session.commit()
            flash('Password changed successfully.')
            return redirect(url_for('main.dashboard'))
        elif form_type == 'start_adventure':
            # Collect selected party ids (can be multiple values for 'party_ids')
            ids = request.form.getlist('party_ids')
            # Deduplicate and filter invalid values
            try:
                party_ids = list({int(i) for i in ids})
            except ValueError:
                party_ids = []
            if not (1 <= len(party_ids) <= 4):
                flash('Select between 1 and 4 characters to begin the adventure.', 'warning')
                return redirect(url_for('main.dashboard'))
            # Ensure all belong to current user
            chars = Character.query.filter(Character.id.in_(party_ids), Character.user_id == current_user.id).all()
            if len(chars) != len(party_ids):
                flash('One or more selected characters are invalid.', 'danger')
                return redirect(url_for('main.dashboard'))
            # Prepare a lightweight session payload
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
            return redirect(url_for('main.adventure'))
        # Default: character creation form
        name = request.form['name']
        char_class = request.form['char_class']
        # Define base stats for each class
        base_stats = {
            'fighter': {'str': 16, 'con': 15, 'dex': 10, 'cha': 8,  'int': 8,  'wis': 8,  'mana': 5,  'hp': 20},
            'rogue':   {'str': 10, 'con': 10, 'dex': 16, 'cha': 14, 'int': 10, 'wis': 8,  'mana': 8,  'hp': 14},
            'mage':    {'str': 8,  'con': 10, 'dex': 10, 'cha': 10, 'int': 16, 'wis': 15, 'mana': 20, 'hp': 10},
            'cleric':  {'str': 12, 'con': 12, 'dex': 8,  'cha': 10, 'int': 10, 'wis': 16, 'mana': 12, 'hp': 16},
            'ranger':  {'str': 12, 'con': 12, 'dex': 16, 'cha': 10, 'int': 10, 'wis': 14, 'mana': 8,  'hp': 16},
            'druid':   {'str': 10, 'con': 12, 'dex': 10, 'cha': 10, 'int': 12, 'wis': 16, 'mana': 16, 'hp': 14}
        }
        stats = base_stats.get(char_class, base_stats['fighter'])
        # Starting coins: gold/silver/copper
        coins = {'gold': 5, 'silver': 20, 'copper': 50}
        # Starter items by class (slugs refer to Item.slug)
        starter_items = {
            'fighter': ['short-sword', 'wooden-shield', 'potion-healing'],
            'rogue':   ['dagger', 'lockpicks', 'potion-healing'],
            'mage':    ['oak-staff', 'potion-mana', 'potion-mana'],
            'cleric':  ['oak-staff', 'potion-healing', 'potion-mana'],
            'ranger':  ['hunting-bow', 'dagger', 'potion-healing'],
            'druid':   ['herbal-pouch', 'potion-healing', 'potion-mana']
        }
        items = starter_items.get(char_class, starter_items['fighter'])
        character = Character(
            user_id=current_user.id,
            name=name,
            # Store selected class explicitly alongside coins to avoid
            # heuristic misclassification when rendering later
            stats=json.dumps({**stats, **coins, 'class': char_class}),
            gear=json.dumps([]),
            items=json.dumps(items)
        )
        db.session.add(character)
        db.session.commit()
        flash(f'Character {name} the {char_class} created!')
        return redirect(url_for('main.dashboard'))
    characters = Character.query.filter_by(user_id=current_user.id).all()
    # Prepare character data with parsed stats and class
    class_map = {
        'fighter': lambda s: s['str'] >= s['dex'] and s['str'] >= s['int'] and s['str'] >= s['wis'],
        'mage':    lambda s: s['int'] >= s['str'] and s['int'] >= s['dex'] and s['int'] >= s['wis'],
        'druid':   lambda s: s['wis'] >= s['str'] and s['wis'] >= s['dex'] and s['wis'] >= s['int'],
        'ranger':  lambda s: s['dex'] >= s['str'] and s['wis'] >= s['int'],
        'rogue':   lambda s: s['dex'] >= s['str'] and s['dex'] >= s['int'] and s['dex'] >= s['wis'],
        'cleric':  lambda s: True  # fallback
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
        # Resolve inventory items
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
        # Prefer the explicitly stored class; otherwise use inventory hints then heuristics
        if stats_class:
            class_name = stats_class.capitalize()
        else:
            # Inventory hints (unique starters)
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
            # Backfill the explicit class label into stored stats for consistency
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
            'class_name': class_name
        })
    if _backfilled:
        db.session.commit()
    # Fetch user info for settings section
    user_email = None
    try:
        user_obj = User.query.get(current_user.id)
        user_email = getattr(user_obj, 'email', None)
    except Exception:
        user_email = None
    return render_template('dashboard.html', characters=char_list, user_email=user_email)

# Route to delete a character
@bp.route('/delete_character/<int:char_id>', methods=['POST'])
@login_required
def delete_character(char_id):
    character = Character.query.filter_by(id=char_id, user_id=current_user.id).first()
    if character:
        db.session.delete(character)
        db.session.commit()
        flash('Character deleted.')
    else:
        flash('Character not found or not authorized.')
    return redirect(url_for('main.dashboard'))


@bp.route('/adventure')
@login_required
def adventure():
    party = session.get('party', [])
    # Compute a tiny summary, like average level (not tracked), so just counts/roles
    return render_template('adventure.html', party=party)
