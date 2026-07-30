"""The levelling curve's shape, pinned against the real monster catalogue.

The point of these tests is *not* the XP numbers -- those are derived and may be
re-derived. It is the shape: **every level must cost more fights than the one
before it**, measured in kills against the monsters actually available at that
level. That is what levelling feels like, and it is what the old curve got
wrong.

The old curve was D&D 5e's for 1-20 plus a flat +50,000/level to a cap of 50.
Monster `xp_base` grows about 27x from level 5 to 20 while 5e's requirement
grows about 10x, so levelling got *easier* the deeper you went: the hardest
level was 6 -> 7 at ~571 kills and the easiest was 16 -> 17 at ~92. Nothing
caught that, because nothing was measuring the curve against the catalogue.

Reads the seed file rather than the database: `db_isolation` rebuilds leave only
a minimal catalogue mid-suite, so asserting against the live table makes these
order-dependent (docs/TESTING.md, and see test_monster_catalogue_coverage.py).
"""

import re
import statistics
from pathlib import Path

from app.models.xp import MAX_LEVEL, xp_for_level

SEED = Path(__file__).resolve().parent.parent / "sql" / "monsters_seed.sql"
PARTY_SIZE = 4  # XP is split across the party (combat_service._check_end)

_ROW = re.compile(r"^\s*\('(?P<slug>[^']+)',\s*'?(?P<rest>.*?)\)\s*[,;]\s*$")


def _monsters():
    """(level_min, level_max, xp_base, is_boss) per row of the seed file."""
    out = []
    for line in SEED.read_text(encoding="utf-8").splitlines():
        m = _ROW.match(line)
        if not m:
            continue
        fields = [f.strip().strip("'") for f in m.group("rest").split(",")]
        ints = [f for f in fields if f.lstrip("-").isdigit()]
        if len(ints) < 2:
            continue
        out.append((int(ints[0]), int(ints[1]), int(ints[-1]), fields[-1].lower() == "true"))
    return out


def _kills_for_level(level, monsters):
    """How many ordinary kills the step from ``level`` to ``level + 1`` costs."""
    pool = [m[2] for m in monsters if m[0] <= level <= m[1] and not m[3]]
    assert pool, f"no ordinary monster at level {level} to price the curve against"
    share = statistics.median(pool) / PARTY_SIZE
    need = xp_for_level(level + 1) - xp_for_level(level)
    return need / share


def test_the_cap_is_twenty():
    assert MAX_LEVEL == 20
    assert xp_for_level(MAX_LEVEL + 5) == xp_for_level(MAX_LEVEL), "there is no level past the cap to charge for"


def test_the_requirement_never_decreases():
    """Cumulative XP must be strictly increasing -- the 5e table this replaced
    was not: reaching 12 cost 15,000 over level 11, while 11 cost 21,000."""
    totals = [xp_for_level(lvl) for lvl in range(1, MAX_LEVEL + 1)]
    for lvl, (a, b) in enumerate(zip(totals, totals[1:]), start=1):
        assert b > a, f"level {lvl + 1} costs no more than level {lvl}"


def test_every_level_costs_more_fights_than_the_last():
    """The whole design goal, in one assertion."""
    monsters = _monsters()
    kills = [(lvl, _kills_for_level(lvl, monsters)) for lvl in range(1, MAX_LEVEL)]

    dips = [
        f"{lvl}->{lvl + 1} costs {k:.0f} kills, down from {kills[i - 1][1]:.0f}"
        for i, (lvl, k) in enumerate(kills)
        if i and k < kills[i - 1][1]
    ]
    assert not dips, "levelling gets easier as it goes:\n  " + "\n  ".join(dips)


def test_the_first_levels_are_quick_and_the_last_is_the_long_haul():
    """Shape, with room to move: the exact numbers are tuning, but a first level
    that takes 100 fights or a last one that takes 20 is a different game."""
    monsters = _monsters()
    first = _kills_for_level(1, monsters)
    last = _kills_for_level(MAX_LEVEL - 1, monsters)

    assert first <= 40, f"the first level takes {first:.0f} kills -- too slow to hook anyone"
    assert last >= 100, f"the last level takes {last:.0f} kills -- the cap should be earned"
    assert last / first >= 4, f"only a {last / first:.1f}x spread from first level to last; the climb is too flat"


def test_the_whole_ladder_is_a_sane_length():
    """A full 1 -> cap run, in fights. The old curve needed ~4,475 kills to
    reach 20 and then 30 more flat levels on top."""
    monsters = _monsters()
    total = sum(_kills_for_level(lvl, monsters) for lvl in range(1, MAX_LEVEL))

    assert 800 <= total <= 3000, f"a full run is {total:,.0f} kills, which is out of the intended range"


def test_difficulty_mod_scales_the_whole_curve():
    assert xp_for_level(10, 2.0) == xp_for_level(10) * 2
    assert xp_for_level(10, 0.5) == xp_for_level(10) // 2
