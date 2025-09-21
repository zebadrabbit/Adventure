"""Seed management API routes.

Provides a centralized endpoint to create/update the active dungeon seed
for the current user session and DungeonInstance.
"""
from flask import Blueprint, request, jsonify, session
from flask_login import login_required, current_user
from app import db
from app.models.dungeon_instance import DungeonInstance
import hashlib, random

bp_seed = Blueprint('seed_api', __name__)

SQLITE_MAX_INT = 9223372036854775807


def _coerce_seed(payload_seed):
    """Convert provided seed (int or str) into bounded 64-bit signed int."""
    if payload_seed is None:
        return random.randint(1, 1_000_000)
    if isinstance(payload_seed, int):
        return payload_seed % SQLITE_MAX_INT
    if isinstance(payload_seed, str):
        s = payload_seed.strip()
        if not s:
            return random.randint(1, 1_000_000)
        if s.isdigit():
            return int(s) % SQLITE_MAX_INT
        h = hashlib.sha256(s.encode('utf-8')).digest()
        return int.from_bytes(h[:8], 'big') % SQLITE_MAX_INT
    # Fallback
    return random.randint(1, 1_000_000)


@bp_seed.route('/api/dungeon/seed', methods=['POST'])
@login_required
def set_seed():
    """Set (or generate) the dungeon seed.

    Body JSON (all optional):
      { "seed": <int|str|null>, "regenerate": <bool> }
    - If seed omitted or null and regenerate true => random seed.
    - If seed provided (int or string) => deterministic hashing.
    - Updates existing DungeonInstance or creates a new one if missing.

    Response: { "seed": <int>, "dungeon_instance_id": <id> }
    """
    data = request.get_json(silent=True) or {}
    regenerate = data.get('regenerate')
    provided = data.get('seed', None)
    if regenerate and provided is None:
        seed = _coerce_seed(None)
    else:
        seed = _coerce_seed(provided)

    dungeon_instance_id = session.get('dungeon_instance_id')
    instance = None
    if dungeon_instance_id:
        instance = db.session.get(DungeonInstance, dungeon_instance_id)

    if instance is None:
        instance = DungeonInstance(user_id=current_user.id, seed=seed, pos_x=0, pos_y=0, pos_z=0)
        db.session.add(instance)
        db.session.commit()
        session['dungeon_instance_id'] = instance.id
    else:
        instance.seed = seed
        # Reset position to 0,0,0 so next map call relocates to entrance
        instance.pos_x = instance.pos_y = instance.pos_z = 0
        db.session.commit()

    session['dungeon_seed'] = seed
    return jsonify({"seed": seed, "dungeon_instance_id": instance.id})
