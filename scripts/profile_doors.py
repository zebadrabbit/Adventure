import time
from statistics import mean, pstdev

from app.dungeon import Dungeon

SEEDS = [11, 222, 3333, 4444, 55555, 67890, 72223, 88888, 99999, 123456]
SIZE = (60, 60, 1)


def run():
    runtimes = []
    for s in SEEDS:
        t0 = time.perf_counter()
        d = Dungeon(seed=s, size=SIZE)
        t1 = time.perf_counter()
        rt = (t1 - t0) * 1000
        doors_summary = d.metrics.get("doors", {}) if d.enable_metrics else {}
        print(f"seed={s} ms={rt:.1f} doors={doors_summary}")
        runtimes.append(rt)
    print("\nSummary:")
    print(
        f"count={len(runtimes)} avg_ms={mean(runtimes):.1f} sd_ms={pstdev(runtimes):.1f} min_ms={min(runtimes):.1f} max_ms={max(runtimes):.1f}"
    )


if __name__ == "__main__":
    run()
