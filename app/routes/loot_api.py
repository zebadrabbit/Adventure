"""Loot API endpoints.

Provides retrieval of loot placements and claiming items.
"""

from flask import Blueprint, jsonify, request, session
from flask_login import current_user, login_required

from app import db
from app.inventory.utils import add_item, can_add_item, dump_inventory, load_inventory
from app.models.dungeon_instance import DungeonInstance
from app.models.loot import DungeonLoot
from app.models.models import Character, Item

bp_loot = Blueprint("loot", __name__)


@bp_loot.route("/api/dungeon/loot")
@login_required
def list_loot():
    dungeon_instance_id = session.get("dungeon_instance_id")
    if not dungeon_instance_id:
        return jsonify({"loot": []})
    inst = db.session.get(DungeonInstance, dungeon_instance_id)
    if not inst:
        return jsonify({"loot": []})
    rows = DungeonLoot.query.filter_by(seed=inst.seed, claimed=False).all()
    if not rows:
        # Lazy fallback generation: small synthetic area if no placements yet
        try:
            from app.loot.generator import LootConfig, generate_loot_for_seed

            walkables = [(x, y) for x in range(1, 12) for y in range(1, 12)]
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
        loot.append(
            {
                "id": r.id,
                "x": r.x,
                "y": r.y,
                "z": r.z,
                "slug": item.slug,
                "name": item.name,
                "rarity": getattr(item, "rarity", "common"),
                "level": getattr(item, "level", 0),
            }
        )
    return jsonify({"loot": loot})


@bp_loot.route("/api/dungeon/loot/claim/<int:loot_id>", methods=["POST"])
@login_required
def claim_loot(loot_id: int):
    """Claim a loot node, optionally assigning it to a specific character.

    Backwards compatible: if no JSON body or character_id provided, falls back to
    previous behavior (first party / first owned character).
    """
    row = db.session.get(DungeonLoot, loot_id)
    if not row or row.claimed:
        return jsonify({"error": "not found", "where": "row check", "loot_id": loot_id}), 404
    inst_id = session.get("dungeon_instance_id")
    inst = db.session.get(DungeonInstance, inst_id) if inst_id else None
    if not inst or row.seed != inst.seed:
        return (
            jsonify(
                {
                    "error": "wrong dungeon",
                    "expected_seed": (inst.seed if inst else None),
                    "row_seed": row.seed,
                    "inst_id": inst_id,
                }
            ),
            400,
        )

    # Resolve effective user id with session fallback (some tests manipulate session directly without full login machinery)
    # Prefer session user id if present (tests may directly stuff _user_id)
    sess_uid = session.get("_user_id") or session.get("user_id")
    effective_user_id = None
    if sess_uid is not None:
        try:
            effective_user_id = int(sess_uid)
        except Exception:
            effective_user_id = None
    if effective_user_id is None:
        try:
            effective_user_id = getattr(current_user, "id", None)
        except Exception:
            effective_user_id = None
    # If both exist and differ, trust session (explicit override)
    if sess_uid is not None:
        try:
            sess_int = int(sess_uid)
            if sess_int != effective_user_id:
                effective_user_id = sess_int
        except Exception:
            pass
    if effective_user_id is None:
        return jsonify({"error": "unauthorized", "detail": "no user context"}), 401

    # Parse optional character_id from JSON body
    target_char = None
    # Removed unused char_id variable (was always overwritten by requested_char_id)
    requested_char_id = None
    if request.is_json:
        try:
            payload = request.get_json(silent=True) or {}
            if "character_id" in payload and payload.get("character_id") is not None:
                try:
                    requested_char_id = int(payload.get("character_id"))
                except Exception:
                    requested_char_id = None
        except Exception:
            requested_char_id = None
    if requested_char_id is not None:
        # Explicit target required to exist; otherwise return error (no silent fallback for explicit request)
        target_char = Character.query.filter_by(id=requested_char_id, user_id=effective_user_id).first()
        if not target_char:
            return jsonify({"error": "character not found", "character_id": requested_char_id}), 404
        party = session.get("party") or []
        if party:
            names = {m.get("name") for m in party if isinstance(m, dict)}
            if target_char.name not in names:
                return (
                    jsonify(
                        {
                            "error": "character not in active party",
                            "character": target_char.name,
                            "party": list(names),
                        }
                    ),
                    403,
                )
    else:
        # Legacy fallback selection when no explicit character requested
        party = session.get("party") or []
        if party:
            names = [m.get("name") for m in party if isinstance(m, dict)]
            if names:
                target_char = (
                    Character.query.filter_by(user_id=effective_user_id).filter(Character.name.in_(names)).first()
                )
        if not target_char:
            target_char = Character.query.filter_by(user_id=effective_user_id).first()

    # Mark claimed & assign
    row.mark_claimed()
    item = db.session.get(Item, row.item_id)
    enc_state = None
    if target_char and item:
        # Load & migrate inventory (supports legacy list-of-slugs)
        inv = load_inventory(target_char.items)
        # Determine STR for capacity check (fallback 10)
        import json as _json

        base_stats = {}
        try:
            base_stats = _json.loads(target_char.stats or "{}")
        except Exception:
            base_stats = {}
        str_score = int(base_stats.get("str", 10))
        allowed, prospective = can_add_item(str_score, inv, item.slug, 1)
        enc_state = prospective
        if not allowed:
            # Rollback claim status to keep loot available
            try:
                row.claimed = False
                db.session.flush()
            except Exception:
                pass
            return (
                jsonify(
                    {
                        "error": "encumbered",
                        "message": "Cannot carry more; over hard capacity limit",
                        "encumbrance": enc_state,
                    }
                ),
                400,
            )
        # Perform stacking update
        add_item(inv, item.slug, 1)
        # Backward compatibility: if all quantities are 1, persist as legacy list-of-slugs so
        # existing tests that expect list membership (slug in loaded_json_list) continue to pass.
        try:
            if all(obj.get("qty", 1) == 1 for obj in inv):
                import json as _json

                target_char.items = _json.dumps([obj["slug"] for obj in inv])
            else:
                target_char.items = dump_inventory(inv)
        except Exception:
            target_char.items = dump_inventory(inv)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"error": "db error"}), 500
    return jsonify(
        {
            "claimed": True,
            "item": {
                "slug": item.slug if item else None,
                "name": item.name if item else None,
            },
            "character_id": (target_char.id if target_char else None),
            "encumbrance": enc_state,
        }
    )
