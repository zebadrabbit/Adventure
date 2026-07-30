"""Experience point (XP) progression utilities.

Import `xp_for_level` anywhere XP / level gating logic is needed (character
advancement, encounter scaling, UI progress bars, etc.).

The curve
---------
Twenty levels, and the cost of each one rises. That is the whole design goal,
and it is deliberately measured in **kills**, not XP: XP is an implementation
detail the player never sees, while "how many fights is the next level" is what
levelling actually feels like.

Against the real monster catalogue (`sql/monsters_seed.sql`, median non-boss
`xp_base` at each level, XP split across a four-character party) this table
produces a smooth climb:

    level  1 ->  2     22 kills
    level  5 ->  6     32
    level 10 -> 11     75
    level 15 -> 16    125
    level 19 -> 20    179

Monotonic the whole way: every level costs more fights than the one before.

What this replaced, and why
---------------------------
The old table was D&D 5e's for 1-20 and then a flat +50,000/level to a cap of
50. Two things were wrong with it, both measured rather than assumed:

* **It was inverted.** Monster `xp_base` grows about 27x from level 5 to 20
  while 5e's requirement grows about 10x, so levelling got *easier* the further
  you went. The hardest level in the game was 6 -> 7 at ~571 kills; the easiest
  was 16 -> 17 at ~92. 5e's table is balanced against a DM handing out
  encounters, not against a monster catalogue that scales itself.
* **81% of the game was a flat grind with no content behind it.** Levels 21-50
  were 30 identical 50,000 XP steps -- 1.5M of the 1.855M total -- and the
  monster catalogue stops at 20, so every one of those levels was fought against
  clamped level-20 monsters.

The cap is now 20 and the whole ladder is ~1,557 kills for a four-party, against
~4,475 to reach level 20 alone before. Depth after that is the dungeon tier
ladder's job -- rifts, not level numbers.
"""

# Cumulative XP required to reach each level. Index 0 is level 1.
#
# The values are round because they are derived, not sacred: each step is
# (target kills for this level) x (median monster XP share at this level),
# rounded to something readable. Re-derive rather than nudge -- if the monster
# catalogue's XP changes, the pacing here changes with it, and the numbers to
# re-check are the kill counts in the module docstring, not these totals.
_LEVEL_XP = [
    0,  # 1
    100,  # 2
    200,  # 3
    300,  # 4
    700,  # 5
    1_200,  # 6
    1_900,  # 7
    4_000,  # 8
    6_500,  # 9
    9_500,  # 10
    16_000,  # 11
    23_500,  # 12
    31_500,  # 13
    46_500,  # 14
    63_000,  # 15
    81_500,  # 16
    125_000,  # 17
    173_000,  # 18
    225_000,  # 19
    300_000,  # 20
]

MAX_LEVEL = len(_LEVEL_XP)  # 20


def xp_for_level(level: int, difficulty_mod: float = 1.0) -> int:
    """Return cumulative XP required to reach ``level``.

    Args:
        level: 1-based character level target. Values below 1 return 0. Values
            above ``MAX_LEVEL`` clamp to the cap's requirement -- there is no
            level past it, so there is no further requirement to report. Callers
            showing a "next level" figure should compare against ``MAX_LEVEL``
            and say *maxed* rather than render a bar that can never fill.
        difficulty_mod: Scalar applied to the requirement. Above 1.0 levelling
            is slower, below 1.0 faster. Comes from
            ``GameConfig['progression'].xp_difficulty_mod``.

    Returns:
        Cumulative XP for the level, multiplied by ``difficulty_mod``.
    """
    if level < 1:
        return 0
    if level >= MAX_LEVEL:
        return int(_LEVEL_XP[MAX_LEVEL - 1] * difficulty_mod)
    return int(_LEVEL_XP[level - 1] * difficulty_mod)
