import time
import pytest
from app.dungeon import Dungeon

# Simple performance guardrail. Not a strict micro-benchmark; aims to catch large regressions.
# Adjust thresholds if CI hardware differs significantly.

@pytest.mark.performance
def test_dungeon_generation_medium_seeds():
    size = (75,75,1)
    seeds = [10101, 20202, 30303]
    max_seconds_per = 1.2  # generous threshold; tune as needed
    timings = []
    for s in seeds:
        start = time.perf_counter()
        d = Dungeon(seed=s, size=size)
        elapsed = time.perf_counter() - start
        timings.append(elapsed)
        assert d.grid is not None
        assert elapsed < max_seconds_per, f"Seed {s} took {elapsed:.3f}s (> {max_seconds_per}s)"
    # Optional: aggregate sanity check
    avg = sum(timings)/len(timings)
    assert avg < max_seconds_per * 0.85, f"Average generation {avg:.3f}s too high"
