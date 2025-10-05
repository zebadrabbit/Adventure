from app.dungeon.entity_stream import build_snapshot, fetch_missing, record_delta


def test_delta_sequence_monotonic():
    # Start clean instance id (assuming isolated test process)
    inst = 99901
    d1 = record_delta(inst, 10, {"monsters_changed": [{"slug": "a", "x": 1, "y": 2}]})
    d2 = record_delta(inst, 11, {"treasures_changed": [{"id": 5, "x": 2, "y": 3}]})
    assert d2["seq"] == d1["seq"] + 1
    assert d1["event"] == "entities_delta"


def test_snapshot_advances_seq_and_resets_replay():
    inst = 99902
    d1 = record_delta(inst, 1, {"monsters_changed": []})
    snap = build_snapshot(inst, tick=2, monsters=[], treasures=[])
    assert snap["seq"] == d1["seq"] + 1
    d2 = record_delta(inst, 3, {"treasures_removed": [7]})
    assert d2["seq"] == snap["seq"] + 1


def test_fetch_missing_replay_and_gap():
    inst = 99903
    d1 = record_delta(inst, 1, {"monsters_changed": []})
    d2 = record_delta(inst, 2, {"monsters_changed": []})
    # Replay from first seq-1 should return both
    replay = fetch_missing(inst, d1["seq"] - 1)
    assert [r["seq"] for r in replay] == [d1["seq"], d2["seq"]]
    # Replay from d1 seq should return only d2
    replay2 = fetch_missing(inst, d1["seq"])
    assert [r["seq"] for r in replay2] == [d2["seq"]]
    # Gap: ask for way too old
    old = fetch_missing(inst, d1["seq"] - 100)
    assert old is None
