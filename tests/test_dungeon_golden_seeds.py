from app.dungeon import Dungeon


def test_same_seed_same_grid():
    a = Dungeon(seed=2024, size=(60, 60, 1))
    b = Dungeon(seed=2024, size=(60, 60, 1))
    assert a.to_ascii() == b.to_ascii()
    assert a.metrics["tiles_room"] == b.metrics["tiles_room"]


def test_different_seeds_differ():
    a = Dungeon(seed=1, size=(60, 60, 1))
    b = Dungeon(seed=2, size=(60, 60, 1))
    assert a.to_ascii() != b.to_ascii()


def test_metrics_stable_keys():
    d = Dungeon(seed=99, size=(60, 60, 1))
    for key in (
        "seed",
        "rooms",
        "tiles_room",
        "tiles_wall",
        "tiles_tunnel",
        "tiles_door",
        "unreachable_rooms",
        "teleport_lookup",
        "room_type_counts",
    ):
        assert key in d.metrics, f"missing metric {key}"
    assert d.metrics["unreachable_rooms"] == 0
