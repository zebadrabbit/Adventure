"""Party Management API Routes.

Provides endpoints for party formations, shared inventory, and party buffs.
"""

import json
from datetime import datetime

from flask import Blueprint, jsonify, request

from app import db
from app.inventory.utils import add_item, remove_one
from app.models.models import Character
from app.models.party import Party, PartyBuff, PartyMember, PartySharedInventory

bp_party = Blueprint("party", __name__)


@bp_party.route("/api/party/<int:party_id>", methods=["GET"])
def get_party(party_id):
    """Get complete party data with members, formation, and stats."""
    party = db.session.get(Party, party_id)
    if not party:
        return jsonify({"error": "Party not found"}), 404

    # Get all members with character details
    members = []
    for pm in party.members:
        char = pm.character
        stats = json.loads(char.stats) if char.stats else {}
        members.append(
            {
                "character_id": char.id,
                "character_name": char.name,
                "level": char.level,
                "role": pm.role,
                "position": pm.position,
                "stats": stats,
                "joined_at": pm.joined_at.isoformat() if pm.joined_at else None,
            }
        )

    # Parse formation data
    formation = json.loads(party.formation_json) if party.formation_json else {}

    return jsonify(
        {
            "id": party.id,
            "name": party.name,
            "leader_id": party.leader_id,
            "party_level": party.party_level,
            "shared_gold": party.shared_gold,
            "members": members,
            "formation": formation,
            "is_active": party.is_active,
            "created_at": party.created_at.isoformat() if party.created_at else None,
        }
    )


@bp_party.route("/api/party/<int:party_id>/member/<int:member_id>/position", methods=["PUT"])
def update_member_position(party_id, member_id):
    """Update a party member's formation position."""
    data = request.get_json()
    new_position = data.get("position")

    if new_position not in ["front", "middle", "back"]:
        return jsonify({"error": "Invalid position"}), 400

    party_member = PartyMember.query.filter_by(party_id=party_id, character_id=member_id).first()

    if not party_member:
        return jsonify({"error": "Party member not found"}), 404

    party_member.position = new_position
    db.session.commit()

    return jsonify({"success": True, "character_id": member_id, "new_position": new_position})


@bp_party.route("/api/party/<int:party_id>/member/<int:member_id>/role", methods=["PUT"])
def update_member_role(party_id, member_id):
    """Update a party member's role."""
    data = request.get_json()
    new_role = data.get("role")

    if new_role not in ["tank", "dps", "healer", "support"]:
        return jsonify({"error": "Invalid role"}), 400

    party_member = PartyMember.query.filter_by(party_id=party_id, character_id=member_id).first()

    if not party_member:
        return jsonify({"error": "Party member not found"}), 404

    party_member.role = new_role
    db.session.commit()

    return jsonify({"success": True, "character_id": member_id, "new_role": new_role})


@bp_party.route("/api/party/<int:party_id>/member/<int:member_id>", methods=["DELETE"])
def remove_party_member(party_id, member_id):
    """Remove a character from the party."""
    party_member = PartyMember.query.filter_by(party_id=party_id, character_id=member_id).first()

    if not party_member:
        return jsonify({"error": "Party member not found"}), 404

    db.session.delete(party_member)
    db.session.commit()

    return jsonify({"success": True, "message": "Member removed from party"})


@bp_party.route("/api/party/<int:party_id>/inventory", methods=["GET"])
def get_shared_inventory(party_id):
    """Get party's shared inventory with item details."""
    party = db.session.get(Party, party_id)
    if not party:
        return jsonify({"error": "Party not found"}), 404

    inventory_items = PartySharedInventory.query.filter_by(party_id=party_id).all()

    # Load item data (you'll need to adapt this to your item system)
    items = []
    for inv_item in inventory_items:
        # This is a placeholder - you'll need to load actual item data
        items.append(
            {
                "slug": inv_item.item_slug,
                "name": inv_item.item_slug.replace("-", " ").title(),
                "quantity": inv_item.quantity,
                "rarity": "common",  # Load from actual item data
                "description": "Shared party item",
            }
        )

    return jsonify({"party_id": party_id, "shared_gold": party.shared_gold, "items": items})


@bp_party.route("/api/party/<int:party_id>/inventory/contribute", methods=["POST"])
def contribute_to_shared_inventory(party_id):
    """Contribute an item from character inventory to shared inventory."""
    data = request.get_json()
    character_id = data.get("character_id")
    item_slug = data.get("item_slug")
    quantity = data.get("quantity", 1)

    if not character_id or not item_slug:
        return jsonify({"error": "Missing required fields"}), 400

    # Get character and verify they're in the party
    party_member = PartyMember.query.filter_by(party_id=party_id, character_id=character_id).first()

    if not party_member:
        return jsonify({"error": "Character not in party"}), 403

    character = db.session.get(Character, character_id)
    if not character:
        return jsonify({"error": "Character not found"}), 404

    # Remove item from character's inventory
    if not remove_one(character, item_slug, quantity):
        return jsonify({"error": "Item not found in inventory"}), 400

    # Add to shared inventory
    shared_item = PartySharedInventory.query.filter_by(party_id=party_id, item_slug=item_slug).first()

    if shared_item:
        shared_item.quantity += quantity
    else:
        shared_item = PartySharedInventory(
            party_id=party_id, item_slug=item_slug, quantity=quantity, added_by=character_id
        )
        db.session.add(shared_item)

    db.session.commit()

    return jsonify({"success": True, "message": f"Contributed {quantity}× {item_slug} to party"})


@bp_party.route("/api/party/<int:party_id>/inventory/take", methods=["POST"])
def take_from_shared_inventory(party_id):
    """Take an item from shared inventory to character inventory."""
    data = request.get_json()
    character_id = data.get("character_id")
    item_slug = data.get("item_slug")
    quantity = data.get("quantity", 1)

    if not character_id or not item_slug:
        return jsonify({"error": "Missing required fields"}), 400

    # Verify party membership
    party_member = PartyMember.query.filter_by(party_id=party_id, character_id=character_id).first()

    if not party_member:
        return jsonify({"error": "Character not in party"}), 403

    # Get shared item
    shared_item = PartySharedInventory.query.filter_by(party_id=party_id, item_slug=item_slug).first()

    if not shared_item or shared_item.quantity < quantity:
        return jsonify({"error": "Insufficient quantity in shared inventory"}), 400

    # Add to character inventory
    character = db.session.get(Character, character_id)
    if not character:
        return jsonify({"error": "Character not found"}), 404

    add_item(character, item_slug, quantity)

    # Remove from shared inventory
    shared_item.quantity -= quantity
    if shared_item.quantity <= 0:
        db.session.delete(shared_item)

    db.session.commit()

    return jsonify({"success": True, "message": f"Took {quantity}× {item_slug}"})


@bp_party.route("/api/party/<int:party_id>/inventory/use", methods=["POST"])
def use_shared_item(party_id):
    """Use a consumable item from shared inventory."""
    data = request.get_json()
    item_slug = data.get("item_slug")

    if not item_slug:
        return jsonify({"error": "Missing item_slug"}), 400

    # Get shared item
    shared_item = PartySharedInventory.query.filter_by(party_id=party_id, item_slug=item_slug).first()

    if not shared_item or shared_item.quantity < 1:
        return jsonify({"error": "Item not available"}), 400

    # Apply item effect (placeholder - implement based on your item system)
    # For now, just remove the item
    shared_item.quantity -= 1
    if shared_item.quantity <= 0:
        db.session.delete(shared_item)

    db.session.commit()

    return jsonify({"success": True, "message": f"Used {item_slug}"})


@bp_party.route("/api/party/<int:party_id>/buffs", methods=["GET"])
def get_party_buffs(party_id):
    """Get all active party buffs."""
    party = db.session.get(Party, party_id)
    if not party:
        return jsonify({"error": "Party not found"}), 404

    buffs = PartyBuff.query.filter_by(party_id=party_id).all()

    # Remove expired buffs
    now = datetime.utcnow()
    active_buffs = []

    for buff in buffs:
        if buff.expires_at and buff.expires_at < now:
            db.session.delete(buff)
        else:
            active_buffs.append(
                {
                    "id": buff.id,
                    "buff_type": buff.buff_type,
                    "name": buff.name,
                    "description": buff.description,
                    "effect_json": buff.effect_json,
                    "duration": buff.duration,
                    "expires_at": buff.expires_at.isoformat() if buff.expires_at else None,
                    "source": buff.source,
                }
            )

    db.session.commit()

    return jsonify(active_buffs)


@bp_party.route("/api/party/<int:party_id>/buffs", methods=["POST"])
def add_party_buff(party_id):
    """Add a new buff to the party."""
    data = request.get_json()

    party = db.session.get(Party, party_id)
    if not party:
        return jsonify({"error": "Party not found"}), 404

    buff = PartyBuff(
        party_id=party_id,
        buff_type=data.get("buff_type", "custom"),
        name=data["name"],
        description=data.get("description", ""),
        effect_json=json.dumps(data["effects"]),
        duration=data.get("duration"),
        source=data.get("source", "manual"),
    )

    # Calculate expiration if duration is provided
    if buff.duration:
        # Duration is in game ticks - you'll need to convert to datetime
        # For now, just set a placeholder
        pass

    db.session.add(buff)
    db.session.commit()

    return jsonify({"success": True, "buff_id": buff.id, "message": f"Added buff: {buff.name}"})


@bp_party.route("/api/party/<int:party_id>/gold/contribute", methods=["POST"])
def contribute_gold(party_id):
    """Contribute gold to the party treasury."""
    data = request.get_json()
    character_id = data.get("character_id")
    amount = data.get("amount", 0)

    if amount <= 0:
        return jsonify({"error": "Invalid amount"}), 400

    # Verify party membership
    party_member = PartyMember.query.filter_by(party_id=party_id, character_id=character_id).first()

    if not party_member:
        return jsonify({"error": "Character not in party"}), 403

    character = db.session.get(Character, character_id)
    party = db.session.get(Party, party_id)

    if character.gold < amount:
        return jsonify({"error": "Insufficient gold"}), 400

    # Transfer gold
    character.gold -= amount
    party.shared_gold += amount

    db.session.commit()

    return jsonify(
        {
            "success": True,
            "contributed": amount,
            "new_character_gold": character.gold,
            "new_party_gold": party.shared_gold,
        }
    )


@bp_party.route("/api/party/<int:party_id>/gold/withdraw", methods=["POST"])
def withdraw_gold(party_id):
    """Withdraw gold from the party treasury."""
    data = request.get_json()
    character_id = data.get("character_id")
    amount = data.get("amount", 0)

    if amount <= 0:
        return jsonify({"error": "Invalid amount"}), 400

    # Verify party membership and leader status
    party = db.session.get(Party, party_id)
    if not party:
        return jsonify({"error": "Party not found"}), 404

    # Only leader can withdraw (or implement voting system)
    if party.leader_id != character_id:
        return jsonify({"error": "Only party leader can withdraw gold"}), 403

    if party.shared_gold < amount:
        return jsonify({"error": "Insufficient party gold"}), 400

    character = db.session.get(Character, character_id)

    # Transfer gold
    party.shared_gold -= amount
    character.gold += amount

    db.session.commit()

    return jsonify(
        {
            "success": True,
            "withdrawn": amount,
            "new_character_gold": character.gold,
            "new_party_gold": party.shared_gold,
        }
    )
