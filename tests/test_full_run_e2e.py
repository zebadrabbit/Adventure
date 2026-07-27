"""End-to-end dungeon run over the real HTTP API.

Every other extraction/boss test fabricates the win state on the instance row
(``bosses_defeated = 1``, ``extraction_available = True``) and calls a service
directly. This one plays the run: start the adventure from the dashboard,
explore floor 0, walk into a monster and fight it, ride the stairs down and
back up, kill the boss on the deepest floor, watch the sealed loot room open,
claim treasure, step onto the portal and extract -- all through the endpoints
the browser calls.

Deliberately one long test: the mechanics are sequential (you cannot reach the
boss without descending, or the loot room without the boss), so splitting it
would just mean re-walking the dungeon per assertion.
"""

import json
from collections import deque

import pytest

from app import db
from app.dungeon.api_helpers.movement import effective_unlocked_doors
from app.models.dungeon_instance import DungeonInstance
from app.models.entities import DungeonEntity
from app.models.models import Character
from app.routes.dungeon_api import get_instance_dungeon
from app.services import rate_limiter
from tests.factories import create_character, create_user

SEED = 424242
TIER = 3  # dashboard caps difficulty at 3 -> num_floors_for_tier(3) == 3
DELTAS = {"n": (0, 1), "s": (0, -1), "e": (1, 0), "w": (-1, 0)}


# ---------------------------------------------------------------- navigation


def _path(dungeon, unlocked, start, goal):
    """Directions from start to goal, or None if sealed off.

    Uses dungeon.is_walkable with the same unlocked-door set the movement
    endpoint uses, so "the test can get there" and "the player can get there"
    are the same question.
    """
    if start == goal:
        return []
    prev = {start: None}
    q = deque([start])
    while q:
        cur = q.popleft()
        for d, (dx, dy) in DELTAS.items():
            nxt = (cur[0] + dx, cur[1] + dy)
            if nxt in prev or not dungeon.is_walkable(nxt[0], nxt[1], unlocked):
                continue
            # Stairs are one-way doors to another floor: never route *through*
            # them, only to them.
            if nxt != goal and dungeon.grid[nxt[0]][nxt[1]] in ("<", ">"):
                continue
            prev[nxt] = (cur, d)
            if nxt == goal:
                dirs = []
                node = nxt
                while prev[node] is not None:
                    node, d2 = prev[node]
                    dirs.append(d2)
                return list(reversed(dirs))
            q.append(nxt)
    return None


def _instance(inst_id):
    inst = db.session.get(DungeonInstance, inst_id)
    db.session.refresh(inst)
    return inst


def _walk_to(client, inst_id, goal, *, fights):
    """Walk to goal one endpoint call at a time, fighting anything met.

    The path is recomputed each step because combat, patrols and floor changes
    can all move the world underneath us. Returns the last move response.
    """
    resp = None
    for _ in range(1500):
        inst = _instance(inst_id)
        pos = (inst.pos_x, inst.pos_y)
        if pos == goal:
            return resp
        dungeon = get_instance_dungeon(inst)
        dirs = _path(dungeon, effective_unlocked_doors(inst, dungeon), pos, goal)
        assert dirs, f"no route from {pos} to {goal} on floor {inst.pos_z}"
        # A whole run is thousands of moves; the 300/min movement limit is
        # about abuse, not about how fast a test can walk.
        rate_limiter._counters.clear()
        r = client.post("/api/dungeon/move", json={"dir": dirs[0]})
        assert r.status_code == 200, r.get_json()
        resp = r.get_json()
        assert resp["moved"], resp
        if resp.get("combat_started"):
            state = _resolve_combat(client, resp["combat_id"])
            fights.append(state)
            if _party_wiped(state):
                return resp
            _heal_party(inst.user_id)
        if resp.get("floor_changed"):
            # Stepping on stairs ends the walk: the goal coordinates belong to
            # the floor we just left.
            return resp
    pytest.fail(f"never reached {goal}")


# ------------------------------------------------------------------- combat


def _party_wiped(state):
    members = (state.get("party") or {}).get("members", [])
    return bool(members) and all(m.get("hp", 0) <= 0 for m in members)


def _heal_party(user_id):
    """Top the party back up between fights.

    Deliberate cheat: dropping the persisted current-hp makes _derive_stats
    fall back to full. Attrition over a whole three-floor run is a balance
    question; this test is about whether the mechanics fire at all, and a
    wipe halfway down would just mean testing the wipe path again.
    """
    for char in Character.query.filter_by(user_id=user_id).all():
        if char.permadeath:
            continue  # a wipe is permanent; nothing to heal
        stats = json.loads(char.stats or "{}")
        stats.pop("hp", None)
        char.stats = json.dumps(stats)
        char.is_dead = False
        db.session.add(char)
    db.session.commit()


def _resolve_combat(client, combat_id):
    """Fight to the end. Returns the final combat state."""
    for _ in range(400):
        # This endpoint also advances the monster's turn, which is how a real
        # client gets unstuck when the monster wins initiative.
        body = client.get(f"/api/combat/{combat_id}/state").get_json()
        state = body.get("state", body)
        assert "status" in state, body
        if state["status"] != "active":
            return state
        actor = state["initiative"][state["active_index"]]
        if actor["type"] != "player":
            continue
        body = client.post(
            f"/api/dungeon/combat/{combat_id}/action",
            json={
                "action": "attack",
                "version": state["version"],
                "actor_id": actor["id"],
            },
        ).get_json()
        assert "state" in body, body
    pytest.fail("combat never resolved")


# ------------------------------------------------------------------- entry


def _enter_dungeon(client, username, *, seed=SEED, level=30, names=("Alia", "Brix", "Cade", "Dov")):
    """Roll a party, log in, and start a run from the dashboard.

    Returns (user, party_ids, instance_id).
    """
    user = create_user(username)
    for name in names:
        char = create_character(user, name=name, char_class="fighter", items=[])
        char.level = level
        if level > 1:
            # Veterans: the run is about the mechanics, not about surviving the RNG.
            char.stats = char.stats.replace('"con": 12', '"con": 30').replace('"str": 12', '"str": 30')
        char.gold = 100
    db.session.commit()
    with client.session_transaction() as sess:
        sess["_user_id"] = str(user.id)
        sess["user_id"] = user.id
        sess["dungeon_seed"] = seed
    party_ids = [c.id for c in Character.query.filter_by(user_id=user.id).all()]

    r = client.post(
        "/dashboard",
        data={
            "form": "start_adventure",
            "party_ids": [str(i) for i in party_ids],
            "difficulty_tier": TIER,
        },
        follow_redirects=True,
    )
    assert r.status_code == 200
    with client.session_transaction() as sess:
        inst_id = sess["dungeon_instance_id"]
    return user, party_ids, inst_id


# --------------------------------------------------------------------- tests


@pytest.mark.db_isolation
def test_full_dungeon_run(client, test_app):
    user, party_ids, inst_id = _enter_dungeon(client, "e2erun_" + str(SEED))
    inst = _instance(inst_id)
    assert inst.seed == SEED and inst.tier == TIER

    # The party is committed to this run: extraction is what gets them out.
    locked = Character.query.filter_by(user_id=user.id, locked_dungeon_id=inst_id).count()
    assert locked == len(party_ids), "entering a dungeon must lock the party into it"

    # /map is what seeds spawns, treasure and room events for a floor.
    assert client.get("/api/dungeon/map").status_code == 200
    inst = _instance(inst_id)
    assert inst.bosses_total == 1 and not inst.extraction_available
    floor0 = get_instance_dungeon(inst)
    assert floor0.config.num_floors == 3
    assert (inst.pos_x, inst.pos_y) == floor0.entry_point

    fights = []

    # --- explore into a monster -------------------------------------------
    mob = _reachable_monster(inst, floor0)
    assert mob is not None, "floor 0 spawned no reachable monster"
    mob_id, mob_tile = mob
    _walk_to(client, inst_id, mob_tile, fights=fights)
    assert fights, "walking onto a monster must start combat"
    assert fights[-1]["status"] == "complete"
    assert db.session.get(DungeonEntity, mob_id) is None, "defeated spawn must not linger"
    inst = _instance(inst_id)
    assert inst.monsters_defeated + inst.elites_defeated >= 1, "kills must be tracked on the instance"

    # --- descend, and back up, and down again ------------------------------
    inst = _instance(inst_id)
    resp = _walk_to(client, inst_id, floor0.stairs_down, fights=fights)
    assert resp["floor_changed"] and resp["pos"][2] == 1
    assert client.get("/api/dungeon/map").status_code == 200

    inst = _instance(inst_id)
    floor1 = get_instance_dungeon(inst)
    assert (
        inst.pos_x,
        inst.pos_y,
    ) == floor1.stairs_up, "descending lands on the floor below's up-stairs"

    # Step off the up-stairs and back onto them: that is the way home.
    step_off = _neighbour(floor1, inst, floor1.stairs_up)
    _walk_to(client, inst_id, step_off, fights=fights)
    resp = _walk_to(client, inst_id, floor1.stairs_up, fights=fights)
    assert resp["floor_changed"] and resp["pos"][2] == 0

    # ...and straight back down.
    inst = _instance(inst_id)
    assert (inst.pos_x, inst.pos_y) == floor0.stairs_down
    step_off = _neighbour(floor0, inst, floor0.stairs_down)
    _walk_to(client, inst_id, step_off, fights=fights)
    resp = _walk_to(client, inst_id, floor0.stairs_down, fights=fights)
    assert resp["pos"][2] == 1

    resp = _walk_to(client, inst_id, floor1.stairs_down, fights=fights)
    assert resp["floor_changed"] and resp["pos"][2] == 2
    assert client.get("/api/dungeon/map").status_code == 200

    # --- deepest floor: loot room is sealed until the boss falls -----------
    inst = _instance(inst_id)
    deepest = get_instance_dungeon(inst)
    assert deepest.is_deepest and deepest.portal and deepest.loot_room_doors
    unlocked = effective_unlocked_doors(inst, deepest)
    assert (
        _path(deepest, unlocked, (inst.pos_x, inst.pos_y), deepest.portal) is None
    ), "the exit portal must be unreachable before the boss dies"

    boss = DungeonEntity.query.filter(
        DungeonEntity.instance_id == inst_id,
        DungeonEntity.type == "monster",
        DungeonEntity.z == 2,
        DungeonEntity.data.contains('"archetype": "Boss"'),
    ).first()
    assert boss is not None, "deepest floor must hold a boss"

    _walk_to(client, inst_id, (boss.x, boss.y), fights=fights)
    assert fights[-1]["status"] == "complete"
    inst = _instance(inst_id)
    assert inst.bosses_defeated == 1
    assert inst.extraction_available, "the final boss kill unlocks extraction"

    # --- loot --------------------------------------------------------------
    deepest = get_instance_dungeon(inst)
    unlocked = effective_unlocked_doors(inst, deepest)
    treasure = _nearest_treasure(inst, deepest, unlocked)
    assert treasure is not None, "deepest floor must hold claimable treasure"
    t_id, t_tile = treasure
    _walk_to(client, inst_id, t_tile, fights=fights)
    claim = client.post(f"/api/dungeon/treasure/claim/{t_id}")
    assert claim.status_code == 200, claim.get_json()
    assert claim.get_json()["claimed"] is True

    # --- leave -------------------------------------------------------------
    inst = _instance(inst_id)
    resp = _walk_to(client, inst_id, deepest.portal, fights=fights)
    assert resp.get("portal") is True and resp.get("extraction_available") is True, resp

    status = client.get("/api/dungeon/extraction/status").get_json()
    assert status["extraction_available"] is True and status["all_bosses_defeated"] is True

    out = client.post(
        "/api/dungeon/extraction/extract",
        json={"instance_id": inst_id, "character_ids": party_ids},
    )
    assert out.status_code == 200, out.get_json()
    result = out.get_json()["result"]
    assert sorted(result["extracted"]) == sorted(["Alia", "Brix", "Cade", "Dov"])
    assert not result["left_behind"]

    for char in Character.query.filter_by(user_id=user.id).all():
        assert char.locked_dungeon_id is None
        assert not char.permadeath
        assert char.xp > 0, "extraction awards XP"

    assert len(fights) >= 2, "a full run should have involved several fights"


@pytest.mark.db_isolation
def test_party_wipe_ends_the_run_for_good(client, test_app):
    """A wipe is terminal: the party is gone forever and the dungeon is reset.

    Whatever they carried in dies with them, and the player has to build a new
    party before they can run anything again -- there is no dungeon left to
    resume into.
    """
    user, party_ids, inst_id = _enter_dungeon(client, "e2ewipe", level=1, names=("Doomed",))
    assert client.get("/api/dungeon/map").status_code == 200
    inst = _instance(inst_id)
    floor0 = get_instance_dungeon(inst)

    # Walk into something well out of their depth, so the wipe is the outcome
    # under test rather than a coin flip.
    mob_id, mob_tile = _reachable_monster(inst, floor0)
    mob = db.session.get(DungeonEntity, mob_id)
    mob.hp_current = 9999
    mob.data = json.dumps({**json.loads(mob.data or "{}"), "hp": 9999, "damage": 500})
    db.session.commit()

    fights = []
    _walk_to(client, inst_id, mob_tile, fights=fights)
    assert fights and _party_wiped(fights[-1]), fights[-1]["log"][-5:]

    for char in Character.query.filter_by(user_id=user.id).all():
        assert char.is_dead and char.permadeath, f"{char.name} must be gone for good"
        assert char.locked_dungeon_id is None, "no lock may outlive the dungeon"

    assert db.session.get(DungeonInstance, inst_id) is None, "a wipe resets the dungeon"
    with client.session_transaction() as sess:
        assert "dungeon_instance_id" not in sess
    assert client.post("/api/dungeon/move", json={"dir": "n"}).get_json()["error"] == "no_instance"

    # The player recruits a replacement and gets a *new* dungeon, not the old one.
    replacement = create_character(user, name="Rookie", char_class="fighter", items=[])
    db.session.commit()
    r = client.post(
        "/dashboard",
        data={"form": "start_adventure", "party_ids": [str(replacement.id)], "difficulty_tier": TIER},
        follow_redirects=True,
    )
    assert r.status_code == 200
    with client.session_transaction() as sess:
        assert sess["dungeon_instance_id"] != inst_id


@pytest.mark.db_isolation
def test_hearthstone_abandons_the_run_without_losses(client, test_app):
    """Abandoning is no-fault: keep the party and the haul, lose the dungeon."""
    user, party_ids, inst_id = _enter_dungeon(client, "e2ehearth")
    assert client.get("/api/dungeon/map").status_code == 200

    before = {c.id: (c.xp, c.gold, c.items, c.level) for c in Character.query.filter_by(user_id=user.id).all()}

    fights = []
    inst = _instance(inst_id)
    floor0 = get_instance_dungeon(inst)
    _walk_to(client, inst_id, _neighbour(floor0, inst, floor0.entry_point), fights=fights)

    r = client.post("/api/dungeon/hearth")
    assert r.status_code == 200, r.get_json()
    assert r.get_json()["characters_released"] == len(party_ids)

    for char in Character.query.filter_by(user_id=user.id).all():
        assert not char.permadeath and not char.is_dead, "abandoning costs no lives"
        assert not char.locked_in_dungeon and char.locked_dungeon_id is None
        xp, gold, items, level = before[char.id]
        assert char.gold == gold and char.items == items, "the haul is theirs to keep"
        assert char.xp >= xp and char.level >= level, "abandoning must not claw back progress"

    assert db.session.get(DungeonInstance, inst_id) is None, "abandoning resets the dungeon"
    with client.session_transaction() as sess:
        assert "dungeon_instance_id" not in sess

    # Next trip is a fresh dungeon, not a resume.
    r = client.post(
        "/dashboard",
        data={"form": "start_adventure", "party_ids": [str(i) for i in party_ids], "difficulty_tier": TIER},
        follow_redirects=True,
    )
    assert r.status_code == 200
    with client.session_transaction() as sess:
        assert sess["dungeon_instance_id"] != inst_id


# ---------------------------------------------------------------- lookups


def _neighbour(dungeon, inst, tile):
    """A walkable tile adjacent to `tile` (somewhere to step off stairs to)."""
    unlocked = effective_unlocked_doors(inst, dungeon)
    for dx, dy in DELTAS.values():
        cand = (tile[0] + dx, tile[1] + dy)
        if dungeon.is_walkable(cand[0], cand[1], unlocked):
            return cand
    pytest.fail(f"{tile} has no walkable neighbour")


def _reachable_monster(inst, dungeon):
    unlocked = effective_unlocked_doors(inst, dungeon)
    start = (inst.pos_x, inst.pos_y)
    rows = DungeonEntity.query.filter_by(instance_id=inst.id, type="monster", z=0).all()
    reachable = [(r.id, (r.x, r.y)) for r in rows if _path(dungeon, unlocked, start, (r.x, r.y)) is not None]
    return min(reachable, key=lambda e: abs(e[1][0] - start[0]) + abs(e[1][1] - start[1])) if reachable else None


def _nearest_treasure(inst, dungeon, unlocked):
    start = (inst.pos_x, inst.pos_y)
    rows = DungeonEntity.query.filter_by(instance_id=inst.id, type="treasure", z=inst.pos_z).all()
    reachable = [(r.id, (r.x, r.y)) for r in rows if _path(dungeon, unlocked, start, (r.x, r.y)) is not None]
    return min(reachable, key=lambda e: abs(e[1][0] - start[0]) + abs(e[1][1] - start[1])) if reachable else None
