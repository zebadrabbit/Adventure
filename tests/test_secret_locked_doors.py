import pytest
from app.dungeon import Dungeon, DungeonConfig, SECRET_DOOR, LOCKED_DOOR, DOOR


def test_secret_or_locked_present_probability():
    """Across a range of seeds we should see at least one secret and one locked door produced.
    This is probabilistic; use a reasonable range to avoid flakes. """
    found_secret = False
    found_locked = False
    for s in range(60, 110):
        d = Dungeon(DungeonConfig(seed=s, width=50, height=50, min_rooms=6, max_rooms=10))
        grid = d.grid
        w = d.config.width; h = d.config.height
        for x in range(w):
            for y in range(h):
                if grid[x][y] == SECRET_DOOR:
                    found_secret = True
                elif grid[x][y] == LOCKED_DOOR:
                    found_locked = True
        if found_secret and found_locked:
            break
    assert found_secret, "Expected at least one secret door across seed sweep"
    assert found_locked, "Expected at least one locked door across seed sweep"


def test_secret_door_reveal_changes_tile():
    d = Dungeon(DungeonConfig(seed=1234))
    # find a secret door; if none, skip (rare if parameters small)
    secret_positions = []
    for x in range(d.config.width):
        for y in range(d.config.height):
            if d.grid[x][y] == SECRET_DOOR:
                secret_positions.append((x,y))
    if not secret_positions:
        pytest.skip("No secret door generated for this seed; probability-based")
    x,y = secret_positions[0]
    changed = d.reveal_secret_door(x,y)
    assert changed, "Reveal should report True on first reveal"
    assert d.grid[x][y] == DOOR, "Secret door should convert to normal DOOR after reveal"
    # second call should be False
    assert not d.reveal_secret_door(x,y)


def test_locked_doors_walkable():
    d = Dungeon(DungeonConfig(seed=9876))
    # ensure any locked door is treated as walkable by is_walkable
    any_locked = False
    for x in range(d.config.width):
        for y in range(d.config.height):
            if d.grid[x][y] == LOCKED_DOOR:
                any_locked = True
                assert d.is_walkable(x,y), "Locked door should be walkable"
    if not any_locked:
        pytest.skip("No locked door generated for this seed; probability-based placement")
