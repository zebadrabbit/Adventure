"""A potion won in a fight is the same potion out of the fight.

Combat rewards used to be appended to Character.items as bare strings, into a
list that is canonical ``{"slug", "qty"}`` dicts for any character who has ever
equipped or consumed anything. load_inventory picks its branch by sniffing
``data[0]`` alone and discards every entry of the other kind, so the reward was
counted by combat's own parser -- it showed up in the item panel and could be
drunk mid-fight -- while being invisible to the bag grid, invisible to the
dashboard, refused by /consume as "item not in bag", and destroyed outright by
the next load/dump round-trip.

These tests pin both halves: the shape-matching helper directly, and the reward
grant end to end through load_inventory, which is the reader that used to drop
the item.
"""

import json
import random

import pytest

from app import db
from app.inventory.utils import dump_inventory, load_inventory
from app.models.models import Character, Item, User
from app.services import combat_service
from app.services.combat_service import _grant_slug_to_inventory

REWARD_SLUG = "potion_heal_l3"


def _gear_instance(uid="abc123def456"):
    """A procedural gear instance as app/loot/generator.py emits it: a uid, a
    base, a slot and a name -- and no "slug" at all."""
    return {
        "uid": uid,
        "base": "sword",
        "slot": "weapon",
        "name": "Rusty Sword",
        "rarity": "common",
        "ilvl": 1,
        "affixes": [],
        "value": 12,
        "durability": 50,
        "max_durability": 50,
    }


# --------------------------------------------------------------------------
# The helper, against every shape a bag is actually stored in.
# --------------------------------------------------------------------------


def test_grant_merges_into_an_existing_canonical_stack():
    inv = [{"slug": REWARD_SLUG, "qty": 2}]
    _grant_slug_to_inventory(inv, REWARD_SLUG, 3)
    assert inv == [{"slug": REWARD_SLUG, "qty": 5}]


def test_grant_appends_a_canonical_stack_to_a_bag_holding_gear():
    inv = [_gear_instance()]
    _grant_slug_to_inventory(inv, REWARD_SLUG, 1)
    assert inv[0] == _gear_instance(), "the gear instance must survive untouched"
    assert inv[1] == {"slug": REWARD_SLUG, "qty": 1}
    # The reader that used to drop it now sees both.
    assert load_inventory(json.dumps(inv)) == inv


def test_grant_never_merges_into_a_gear_instance():
    """Instances are not stacks and carry no qty; a slug that happened to match
    one must still become its own entry."""
    inst = dict(_gear_instance(), slug=REWARD_SLUG)  # defensive: an instance that also carries a slug
    inv = [inst]
    _grant_slug_to_inventory(inv, REWARD_SLUG, 1)
    assert inv[0] is inst and "qty" not in inv[0]
    assert inv[1] == {"slug": REWARD_SLUG, "qty": 1}


def test_grant_keeps_a_legacy_bag_legacy():
    """A list of bare slugs must stay a list of bare slugs: load_inventory's
    legacy branch would drop a dict appended here, so imposing the canonical
    shape on this list destroys the reward just as surely as the other way
    round."""
    inv = ["potion-healing", "potion-healing"]
    _grant_slug_to_inventory(inv, REWARD_SLUG, 2)
    assert inv == ["potion-healing", "potion-healing", REWARD_SLUG, REWARD_SLUG]
    assert {"slug": REWARD_SLUG, "qty": 2} in load_inventory(json.dumps(inv))


def test_grant_treats_an_empty_bag_as_canonical():
    inv = []
    _grant_slug_to_inventory(inv, REWARD_SLUG, 1)
    assert inv == [{"slug": REWARD_SLUG, "qty": 1}]


@pytest.mark.parametrize("qty", [0, -1])
def test_grant_ignores_a_non_positive_quantity(qty):
    inv = [{"slug": REWARD_SLUG, "qty": 1}]
    _grant_slug_to_inventory(inv, REWARD_SLUG, qty)
    assert inv == [{"slug": REWARD_SLUG, "qty": 1}]


# --------------------------------------------------------------------------
# The grant itself, through the code path a won fight takes.
# --------------------------------------------------------------------------


def _monster():
    return {
        "slug": "reward-shape-mob",
        "name": "Training Dummy",
        "level": 1,
        "hp": 1,
        "damage": 1,
        "armor": 0,
        "speed": 1,
        "rarity": "common",
        "family": "test",
        "traits": [],
        "resistances": {},
        "damage_types": [],
        "loot_table": "",
        "special_drop_slug": None,
        "xp": 10,
        "boss": False,
    }


def _fresh_user_and_char(items):
    user = User(username=f"reward-shape-{random.randint(1, 10**9)}", email=None)
    user.set_password("pw")
    db.session.add(user)
    db.session.commit()
    char = Character(
        user_id=user.id,
        name="Hero",
        stats=json.dumps({"str": 12, "dex": 10, "int": 10, "con": 12, "hp": 40}),
        gear="{}",
        items=json.dumps(items),
    )
    db.session.add(char)
    db.session.commit()
    return user, char


def _win_a_fight_dropping(user_id, monkeypatch, slug):
    """Run a session to the monster-defeat path with a single guaranteed drop."""
    if not Item.query.filter_by(slug=slug).first():
        db.session.add(Item(slug=slug, name="Standard Healing Potion", type="potion", description="", value_copper=10))
        db.session.commit()
    monkeypatch.setattr(random, "randint", lambda a, b: 1)
    session = combat_service.start_session(user_id, _monster())
    # Only "items" -- not the "items_list" mirror roll_loot also returns -- so
    # this test pins the shape of the grant, not the size of a loot roll.
    monkeypatch.setattr(combat_service, "roll_loot", lambda monster, *a, **kw: {"items": {slug: 1}})
    session.monster_hp = 0
    combat_service._check_end(session)
    db.session.commit()
    return session


def test_reward_dropped_into_a_canonical_bag_is_visible_out_of_combat(client, monkeypatch):
    """The bug in full: win a fight that drops a potion, and the potion must be
    in the bag the character panel reads -- not only in the one combat reads."""
    user, char = _fresh_user_and_char([_gear_instance(), {"slug": "potion-mana", "qty": 1}])
    char_id = char.id

    _win_a_fight_dropping(user.id, monkeypatch, REWARD_SLUG)

    char = db.session.get(Character, char_id)
    bag = load_inventory(char.items)
    assert {"slug": REWARD_SLUG, "qty": 1} in bag, "the reward must survive the reader the bag grid uses"
    assert any(o.get("uid") for o in bag), "the procedural gear instance must not have been dropped"
    assert {"slug": "potion-mana", "qty": 1} in bag

    # ...and it must still be there after the load/dump round-trip that any
    # later inventory write performs, which is what used to delete it for real.
    char.items = dump_inventory(bag)
    db.session.commit()
    assert {"slug": REWARD_SLUG, "qty": 1} in load_inventory(db.session.get(Character, char_id).items)


def test_reward_is_counted_the_same_by_combat_and_by_the_bag(client, monkeypatch):
    """Combat's own parser and load_inventory must agree on the count, which is
    the branch's central claim. They disagreed before: combat saw the reward,
    the bag did not."""
    user, char = _fresh_user_and_char([{"slug": REWARD_SLUG, "qty": 1}])
    char_id = char.id

    _win_a_fight_dropping(user.id, monkeypatch, REWARD_SLUG)

    char = db.session.get(Character, char_id)
    combat_count = combat_service._item_counts_by_character([char])[REWARD_SLUG][str(char_id)]
    bag_count = next(o["qty"] for o in load_inventory(char.items) if o.get("slug") == REWARD_SLUG)
    assert combat_count == bag_count == 2, "one carried plus one won, seen identically by both readers"


def test_reward_dropped_into_a_legacy_bag_survives(client, monkeypatch):
    """The mirror case: a bag still in the legacy bare-slug shape must not have
    a dict appended to it, which load_inventory's legacy branch would drop."""
    user, char = _fresh_user_and_char(["potion-healing"])
    char_id = char.id

    _win_a_fight_dropping(user.id, monkeypatch, REWARD_SLUG)

    char = db.session.get(Character, char_id)
    bag = load_inventory(char.items)
    assert {"slug": REWARD_SLUG, "qty": 1} in bag
    assert {"slug": "potion-healing", "qty": 1} in bag
