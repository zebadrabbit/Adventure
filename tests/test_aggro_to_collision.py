"""End-to-end integration test for the chase-to-collision seam: a
proximity-aggroed spawn moves onto the player's tile via
SpawnManager.update_spawns, and trigger_collision_combat then starts
combat and deletes the DungeonEntity (finite-pool depletion).

Unlike test_spawn_aggro.py (pure SpawnManager/SpawnEntry, no DB) and
test_collision_combat.py (hand-placed DungeonEntity already co-located
with the player, no movement), this test exercises both pieces
together against a real Dungeon and real DB-backed DungeonInstance/
DungeonEntity rows.
"""

from app import db
from app.dungeon.api_helpers import encounters
from app.dungeon.dungeon import Dungeon
from app.dungeon.spawn_manager import SpawnBehavior, SpawnConfig, SpawnEntry, SpawnManager
from app.models.entities import DungeonEntity
from tests.factories import create_instance, create_user


def _small_dungeon(seed=42):
    return Dungeon(seed=seed, size=(30, 30, 1))


def test_aggroed_spawn_chases_to_player_tile_and_triggers_combat(test_app):
    with test_app.app_context():
        user = create_user("aggro_collision_1")
        inst = create_instance(user, seed=4242)

        dungeon = _small_dungeon(seed=4242)
        manager = SpawnManager(dungeon, inst, config=SpawnConfig(aggro_radius=10_000))
        walkable = manager._get_walkable_tiles()
        assert len(walkable) >= 2, "test dungeon too small/empty to place two adjacent tiles"

        player_tile = walkable[0]
        # Find a walkable tile exactly one cardinal step from the player tile
        # so a single update_spawns tick is guaranteed to close the gap
        # (see _move_toward_player: greedily reduces the larger-distance
        # axis by one step per tick).
        px, py = player_tile
        candidates = [(px + 1, py), (px - 1, py), (px, py + 1), (px, py - 1)]
        walkable_set = set(walkable)
        spawn_tile = next((c for c in candidates if c in walkable_set), None)
        assert spawn_tile is not None, "no walkable tile adjacent to chosen player tile"

        inst.pos_x, inst.pos_y, inst.pos_z = px, py, 0
        db.session.commit()

        spawn = SpawnEntry(
            x=spawn_tile[0],
            y=spawn_tile[1],
            behavior=SpawnBehavior.PATROL,
            slug="test-chaser",
            name="Test Chaser",
        )
        manager.spawns = [spawn]

        entity = DungeonEntity(
            user_id=user.id,
            instance_id=inst.id,
            seed=inst.seed,
            type="monster",
            slug="test-chaser",
            name="Test Chaser",
            x=spawn_tile[0],
            y=spawn_tile[1],
            z=0,
            hp_current=20,
            data='{"hp": 20, "damage": 4, "speed": 8}',
        )
        db.session.add(entity)
        db.session.commit()
        entity_id = entity.id

        manager.update_spawns(current_tick=1)

        # The chase should have closed the 1-tile gap in a single tick.
        assert (spawn.x, spawn.y) == (px, py)

        # Mirror what run_monster_patrols does: persist the moved spawn's
        # position, then check for collision.
        entity.x = spawn.x
        entity.y = spawn.y
        db.session.commit()

        result = encounters.trigger_collision_combat(inst)

        assert result is not None
        assert result["monster"]["slug"] == "test-chaser"
        assert "combat_id" in result
        assert db.session.get(DungeonEntity, entity_id) is None
