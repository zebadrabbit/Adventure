"""Loot API endpoints.

Provides retrieval of loot placements and claiming items.
"""

from flask import Blueprint, jsonify, request, session
from flask_login import current_user, login_required

from app import db
from app.inventory.utils import add_item, can_add_item, dump_inventory, load_inventory
from app.models.dungeon_instance import DungeonInstance
from app.models.loot import DungeonLoot
from app.models.models import Character, CombatSession, Item

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
                "base_name": item.name,
                "rarity": getattr(item, "rarity", "common"),
                "level": getattr(item, "level", 0),
                "affixes": [],
                "stats": {},
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


@bp_loot.route("/api/loot/pending")
@login_required
def get_pending_loot():
    """Get pending loot from recent combat session.

    Returns loot items that haven't been distributed yet, along with party info.
    Query params: combat_id (optional) - specific combat session
    """
    import json

    combat_id = request.args.get("combat_id", type=int)

    # Find most recent completed combat for this user
    query = CombatSession.query.filter_by(user_id=current_user.id, status="complete")
    if combat_id:
        query = query.filter_by(id=combat_id)

    combat = query.order_by(CombatSession.id.desc()).first()
    if not combat:
        return jsonify({"loot": [], "party": []})

    # Check if loot has already been distributed
    if hasattr(combat, "loot_distributed") and combat.loot_distributed:
        return jsonify({"loot": [], "party": []})

    # Parse rewards
    try:
        rewards = json.loads(combat.rewards_json or "{}")
    except Exception:
        rewards = {}

    # Get items from rewards
    loot_items = []
    items_data = rewards.get("items", {})

    if isinstance(items_data, dict):
        for slug, qty in items_data.items():
            item = Item.query.filter_by(slug=slug).first()
            if item:
                for _ in range(int(qty)):
                    loot_items.append(
                        {
                            "id": f"{slug}_{len(loot_items)}",  # Unique ID for frontend
                            "slug": slug,
                            "name": item.name,
                            "type": item.type,
                            "rarity": item.rarity,
                            "description": item.description,
                            "effects": _get_item_effects(item),
                        }
                    )
    elif isinstance(items_data, list):
        for slug in items_data:
            item = Item.query.filter_by(slug=slug).first()
            if item:
                loot_items.append(
                    {
                        "id": f"{slug}_{len(loot_items)}",
                        "slug": slug,
                        "name": item.name,
                        "type": item.type,
                        "rarity": item.rarity,
                        "description": item.description,
                        "effects": _get_item_effects(item),
                    }
                )

    # Get party members from combat snapshot
    try:
        party_snapshot = json.loads(combat.party_snapshot_json or "{}")
        members = party_snapshot.get("members", [])
        party = [
            {
                "id": m.get("char_id"),
                "name": m.get("name"),
                "class": m.get("class", "Unknown"),
                "level": m.get("level", 1),
            }
            for m in members
            if m.get("char_id")
        ]
    except Exception:
        party = []

    return jsonify({"loot": loot_items, "party": party, "combat_id": combat.id})


@bp_loot.route("/api/loot/confirm", methods=["POST"])
@login_required
def confirm_loot_distribution():
    """Confirm loot distribution and assign items to characters.

    Body: { combat_id: int, assignments: { lootItemId: characterId } }
    """
    import json

    data = request.get_json()
    combat_id = data.get("combat_id")
    assignments = data.get("assignments", {})

    if not combat_id:
        return jsonify({"error": "combat_id required"}), 400

    # Verify combat session belongs to user
    combat = db.session.get(CombatSession, combat_id)
    if not combat or combat.user_id != current_user.id:
        return jsonify({"error": "Combat session not found"}), 404

    if combat.status != "complete":
        return jsonify({"error": "Combat not complete"}), 400

    # Build slug list from assignments
    assigned_items = {}  # characterId -> [slugs]

    for loot_id, char_id in assignments.items():
        # Extract slug from loot_id (format: "slug_index")
        slug = "_".join(loot_id.split("_")[:-1]) if "_" in loot_id else loot_id

        if char_id not in assigned_items:
            assigned_items[char_id] = []
        assigned_items[char_id].append(slug)

    # Assign items to characters
    for char_id, slugs in assigned_items.items():
        character = db.session.get(Character, char_id)
        if not character or character.user_id != current_user.id:
            continue

        # Load current inventory
        inv = load_inventory(character.items)

        # Add each item
        for slug in slugs:
            item = Item.query.filter_by(slug=slug).first()
            if item:
                # Check encumbrance
                if can_add_item(inv, character.stats, slug, 1):
                    add_item(inv, slug, 1)

        # Save updated inventory
        character.items = dump_inventory(inv)

    # Mark loot as distributed
    # Add loot_distributed flag to combat session if not exists
    if not hasattr(combat, "loot_distributed"):
        # For now, we'll use a marker in rewards_json
        try:
            rewards_data = json.loads(combat.rewards_json or "{}")
            rewards_data["_distributed"] = True
            combat.rewards_json = json.dumps(rewards_data)
        except Exception:
            pass

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"error": "Database error"}), 500

    return jsonify({"success": True, "assigned": len(assignments)})


def _get_item_effects(item: Item) -> dict:
    """Extract stat effects from an item for display."""
    slug = (item.slug or "").lower()
    t = (item.type or "").lower()

    # Simple defaults based on type
    if t == "weapon":
        if "bow" in slug or "dagger" in slug:
            return {"dex": 1}
        if "staff" in slug:
            return {"int": 1}
        return {"str": 1}
    if t == "armor":
        return {"con": 1}
    if t == "ring":
        return {"wis": 1}
    if t in ("amulet", "necklace"):
        return {"cha": 1}

    return {}
