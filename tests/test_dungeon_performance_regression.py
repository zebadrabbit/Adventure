import statistics, pytest
from app.dungeon import Dungeon

# NOTE: This test is intentionally lightweight: it does not assert an absolute
# micro-optimized bound, only that average generation time remains within a
# sane envelope for the consolidated final pass. If performance work lowers
# times further, feel free to tighten the threshold.
#
# If this test begins to fail intermittently in CI (resource contention), you
# can raise or mark xfail temporarily, but investigate any real regressions.

SEEDS = [0, 7, 13, 42, 12345]
SIZE = (60, 60, 1)  # slightly smaller than full map to reduce test time
# Baseline threshold (ms) chosen after observing typical ~40-55ms on CI (variable runners) with
# occasional single outliers ~110ms under contention. We:
#   1. Compute median and mean (after dropping top outlier) for stability.
#   2. Require median < MEDIAN_MAX_MS (tighter, less sensitive to one spike).
#   3. Require trimmed mean < TRIMMED_MEAN_MAX_MS.
#   4. Ensure no runtime exceeds EXTREME_MAX_MULT * median (extreme explosion guard).
MEDIAN_MAX_MS = 70.0
TRIMMED_MEAN_MAX_MS = 75.0
EXTREME_MAX_MULT = 2.5  # allow up to 2.5x median for a single worst-case outlier

@pytest.mark.performance
def test_dungeon_generation_average_runtime_ms():
    runtimes = []
    for s in SEEDS:
        d = Dungeon(seed=s, size=SIZE)
        # runtime_ms metric always present when metrics enabled (default True)
        runtimes.append(d.metrics.get('runtime_ms', 0.0))
    median_rt = statistics.median(runtimes)
    # Trim: drop highest single runtime to reduce noise impact
    trimmed = sorted(runtimes)[:-1] if len(runtimes) > 2 else runtimes
    trimmed_mean = statistics.mean(trimmed)
    # Guards
    assert median_rt < MEDIAN_MAX_MS, (
        f"Median runtime {median_rt}ms exceeded {MEDIAN_MAX_MS}ms (runtimes={runtimes})" )
    assert trimmed_mean < TRIMMED_MEAN_MAX_MS, (
        f"Trimmed mean {trimmed_mean}ms exceeded {TRIMMED_MEAN_MAX_MS}ms (runtimes={runtimes})")
    assert all(rt <= median_rt * EXTREME_MAX_MULT for rt in runtimes), (
        f"Extreme outlier (> {EXTREME_MAX_MULT}x median) detected: median={median_rt} runtimes={runtimes}")
