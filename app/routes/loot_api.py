"""Loot API endpoints.

Provides retrieval of loot placements and claiming items.
"""
from flask import Blueprint, jsonify, session
from flask_login import login_required, current_user
from app import db
from app.models.loot import DungeonLoot
from app.models.models import Item
from app.models.dungeon_instance import DungeonInstance
from app.models.models import Character

bp_loot = Blueprint('loot', __name__)

@bp_loot.route('/api/dungeon/loot')
@login_required
def list_loot():
    dungeon_instance_id = session.get('dungeon_instance_id')
    if not dungeon_instance_id:
        return jsonify({'loot': []})
    inst = db.session.get(DungeonInstance, dungeon_instance_id)
    if not inst:
        return jsonify({'loot': []})
    rows = DungeonLoot.query.filter_by(seed=inst.seed, claimed=False).all()
    if not rows:
        # Lazy fallback generation: small synthetic area if no placements yet
        try:
            from app.loot.generator import generate_loot_for_seed, LootConfig
            walkables = [(x,y) for x in range(1,12) for y in range(1,12)]
            cfg = LootConfig(avg_party_level=1, width=10, height=10, seed=inst.seed)
            generate_loot_for_seed(cfg, walkables)
            rows = DungeonLoot.query.filter_by(seed=inst.seed, claimed=False).all()
        except Exception:
            pass
    loot = []
    for r in rows:
        item = db.session.get(Item, r.item_id)
        if not item:
            continue
        loot.append({
            'id': r.id,
            'x': r.x,
            'y': r.y,
            'z': r.z,
            'slug': item.slug,
            'name': item.name,
            'rarity': getattr(item, 'rarity', 'common'),
            'level': getattr(item, 'level', 0),
        })
    return jsonify({'loot': loot})

@bp_loot.route('/api/dungeon/loot/claim/<int:loot_id>', methods=['POST'])
@login_required
def claim_loot(loot_id: int):
    row = db.session.get(DungeonLoot, loot_id)
    if not row or row.claimed:
        return jsonify({'error': 'not found'}), 404
    inst_id = session.get('dungeon_instance_id')
    inst = db.session.get(DungeonInstance, inst_id) if inst_id else None
    if not inst or row.seed != inst.seed:
        return jsonify({'error': 'wrong dungeon'}), 400
    # TODO: distance / adjacency checks can be added here
    row.mark_claimed()
    item = db.session.get(Item, row.item_id)
    # Add to the first party character's inventory if any; else skip silently
    party = session.get('party') or []
    target_char = None
    if party:
        # match by name first, else first character owned by user
        names = [m.get('name') for m in party if isinstance(m, dict)]
        if names:
            target_char = Character.query.filter_by(user_id=current_user.id).filter(Character.name.in_(names)).first()
    if not target_char:
        target_char = Character.query.filter_by(user_id=current_user.id).first()
    if target_char and item:
        try:
            import json as _json
            slugs = []
            if target_char.items:
                try:
                    slugs = _json.loads(target_char.items)
                except Exception:
                    slugs = []
            if item.slug not in slugs:
                slugs.append(item.slug)
            target_char.items = _json.dumps(slugs)
        except Exception:
            pass
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
    return jsonify({'claimed': True, 'item': {'slug': item.slug if item else None, 'name': item.name if item else None}})
