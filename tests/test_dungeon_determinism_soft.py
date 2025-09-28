from app.dungeon import Dungeon


def test_deterministic_core_metrics():
    seed = 314159
    runs = [Dungeon(seed=seed) for _ in range(3)]
    rooms_counts = {d.metrics["rooms"] for d in runs}
    tunnel_counts = {d.metrics["tiles_tunnel"] for d in runs}
    wall_counts = {d.metrics["tiles_wall"] for d in runs}
    assert len(rooms_counts) == 1, f"Rooms count nondeterministic: {rooms_counts}"
    assert len(tunnel_counts) == 1, f"Tunnel count nondeterministic: {tunnel_counts}"
    assert len(wall_counts) == 1, f"Wall count nondeterministic: {wall_counts}"
