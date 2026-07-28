"""The end-of-combat loot distribution dialog has to be clickable.

Playtest finding (2026-07-28): "loot distribution doesnt seem to work at the end
of combat. the screen comes up but i cannot select a character."

Nothing was wrong with the data. The dialog built its click handlers as inline
attributes with the ids interpolated straight in:

    onclick="lootDistribution.selectItem(${item.id})"

Loot ids are *strings*, built server-side as `${slug}_${index}`, so that
rendered as `selectItem(potion-healing_0)` -- unquoted. JavaScript parses that
as the expression `potion - healing_0` and throws ReferenceError before the
handler runs. Selecting an item, quick-assigning and choosing a character were
all dead. Replaced with event delegation over data attributes, which cannot be
broken by the shape of a value.

The dialog also labelled every character "Unknown": it read `class` from the
combat snapshot, which stores `char_class`.
"""

import json
import re
from pathlib import Path

import pytest

from app import db
from app.models.models import Character, CombatSession, Item, User

JS = Path(__file__).resolve().parent.parent / "app" / "static" / "js" / "loot-distribution.js"


@pytest.fixture()
def looted_combat(client, test_app):
    from werkzeug.security import generate_password_hash

    user = User.query.filter_by(username="loot_dialog_user").first()
    if not user:
        user = User(username="loot_dialog_user", password=generate_password_hash("pw"))
        db.session.add(user)
        db.session.commit()
    Character.query.filter_by(user_id=user.id).delete()
    db.session.commit()

    char = Character(
        user_id=user.id,
        name="Runa",
        stats=json.dumps({"str": 10, "con": 10, "int": 14, "class": "mage"}),
        gear="{}",
        items="[]",
        level=4,
    )
    db.session.add(char)
    db.session.commit()

    item = Item.query.filter_by(type="potion").first()
    if item is None:
        item = Item(
            slug="_loot_dialog_potion",
            name="Dialog Potion",
            type="potion",
            description="fixture",
            value_copper=50,
            level=1,
            rarity="common",
            weight=0.5,
        )
        db.session.add(item)
        db.session.commit()

    session_row = CombatSession(
        user_id=user.id,
        monster_json=json.dumps({"slug": "x", "name": "X", "hp": 1}),
        status="complete",
        party_snapshot_json=json.dumps(
            {"members": [{"char_id": char.id, "name": "Runa", "char_class": "mage", "level": 4, "hp": 10}]}
        ),
        rewards_json=json.dumps({"items": {item.slug: 2}}),
        monster_hp=0,
    )
    db.session.add(session_row)
    db.session.commit()

    with client.session_transaction() as sess:
        sess["_user_id"] = str(user.id)
        sess["user_id"] = user.id
    return user, char, session_row, item


def test_pending_loot_returns_the_party(client, looted_combat):
    user, char, combat, item = looted_combat

    payload = client.get(f"/api/loot/pending?combat_id={combat.id}").get_json()

    assert payload["loot"], "no loot offered for a combat that rewarded items"
    assert [m["id"] for m in payload["party"]] == [char.id]


def test_party_members_carry_their_real_class(client, looted_combat):
    """They were all "Unknown": the snapshot key is char_class, not class."""
    user, char, combat, item = looted_combat

    payload = client.get(f"/api/loot/pending?combat_id={combat.id}").get_json()

    assert payload["party"][0]["class"] == "mage"


def test_loot_ids_are_strings(client, looted_combat):
    """The shape that broke the inline handlers -- pin it so it stays known."""
    user, char, combat, item = looted_combat

    payload = client.get(f"/api/loot/pending?combat_id={combat.id}").get_json()

    for entry in payload["loot"]:
        assert isinstance(entry["id"], str)
        assert not entry["id"].isdigit(), "a bare number would have hidden the quoting bug"


# ------------------------------------------------------- the client contract


def test_no_inline_handler_interpolates_a_value():
    """An onclick built by string interpolation is how this broke.

    `onclick="fn(${x})"` is only safe when x is always a number. Loot ids are
    slugs, so the call rendered unquoted and threw. Delegation via data
    attributes is used instead; keep it that way.
    """
    # Strip line comments first: the fix documents the old broken form in a
    # comment, and matching that would be a false positive.
    code = "\n".join(line for line in JS.read_text().splitlines() if not line.strip().startswith("//"))
    offenders = re.findall(r'onclick="[^"]*\$\{[^"]*"', code)
    assert not offenders, "inline onclick with an interpolated value: " + "; ".join(offenders)


def test_click_targets_are_addressable_by_data_attribute():
    source = JS.read_text()
    for attribute in ("data-item-id", "data-assign-item", "data-assign-member"):
        assert attribute in source, f"{attribute} is what delegation binds to"
    assert "addEventListener('click'" in source
