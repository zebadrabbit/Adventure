
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.models.models import Character
from app import db
import json

bp = Blueprint('main', __name__)

@bp.route('/')
def index():
    return render_template('index.html')



@bp.route('/dashboard', methods=['GET', 'POST'])
@login_required
def dashboard():
    if request.method == 'POST':
        name = request.form['name']
        char_class = request.form['char_class']
        # Define base stats for each class
        base_stats = {
            'fighter': {'str': 16, 'con': 15, 'dex': 10, 'cha': 8, 'int': 8, 'wis': 8, 'mana': 5, 'hp': 20},
            'rogue':   {'str': 10, 'con': 10, 'dex': 16, 'cha': 14, 'int': 10, 'wis': 8, 'mana': 8, 'hp': 14},
            'mage':    {'str': 8,  'con': 10, 'dex': 10, 'cha': 10, 'int': 16, 'wis': 15, 'mana': 20, 'hp': 10},
            'cleric':  {'str': 12, 'con': 12, 'dex': 8,  'cha': 10, 'int': 10, 'wis': 16, 'mana': 12, 'hp': 16}
        }
        stats = base_stats.get(char_class, base_stats['fighter'])
        character = Character(
            user_id=current_user.id,
            name=name,
            stats=json.dumps(stats),
            gear=json.dumps([]),
            items=json.dumps([])
        )
        db.session.add(character)
        db.session.commit()
        flash(f'Character {name} the {char_class} created!')
        return redirect(url_for('main.dashboard'))
    characters = Character.query.filter_by(user_id=current_user.id).all()
    # Prepare character data with parsed stats and class
    class_map = {
        'fighter': lambda s: s['str'] >= s['dex'] and s['str'] >= s['int'] and s['str'] >= s['wis'],
        'rogue':   lambda s: s['dex'] >= s['str'] and s['dex'] >= s['int'] and s['dex'] >= s['wis'],
        'mage':    lambda s: s['int'] >= s['str'] and s['int'] >= s['dex'] and s['int'] >= s['wis'],
        'cleric':  lambda s: True  # fallback
    }
    char_list = []
    for c in characters:
        stats = json.loads(c.stats)
        # Determine class
        if class_map['fighter'](stats):
            class_name = 'Fighter'
        elif class_map['rogue'](stats):
            class_name = 'Rogue'
        elif class_map['mage'](stats):            
            class_name = 'Mage'
        else:
            class_name = 'Cleric'
        char_list.append({
            'id': c.id,
            'name': c.name,
            'stats': stats,
            'class_name': class_name
        })
    return render_template('dashboard.html', characters=char_list)

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
