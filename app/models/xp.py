"""Experience point (XP) progression utilities.

Implements a lightweight D&D 5e–style level progression table with optional
difficulty scaling. Import `xp_for_level` anywhere XP / level gating logic is
needed (character advancement, encounter scaling, UI progress bars, etc.).
"""


def xp_for_level(level: int, difficulty_mod: float = 1.0) -> int:
    """Return cumulative XP required to reach ``level``.

    Args:
        level: 1-based character level target. Values <1 return 0. Values above
            the canonical 20-level table are extrapolated linearly (+50k XP/level).
        difficulty_mod: Scalar applied to the looked-up (or extrapolated) XP.
            Use values >1.0 to make leveling slower (hard mode) or <1.0 to make
            it faster (easy mode).

    Returns:
        Total cumulative XP required for the specified level (already multiplied
        by ``difficulty_mod`` and coerced to int).

    Notes:
        This mirrors the standard D&D 5e progression for levels 1–20. For levels
        beyond 20 we use a simple linear extension to avoid hard caps during
        experimentation. If future epic progression needs a curve change, this
        function can adapt without touching call sites.
    """
    # D&D 5e XP table: level: total XP required to reach that level
    dnd5e_xp = [
        0,  # 1
        300,  # 2
        900,  # 3
        2700,  # 4
        6500,  # 5
        14000,  # 6
        23000,  # 7
        34000,  # 8
        48000,  # 9
        64000,  # 10
        85000,  # 11
        100000,  # 12
        120000,  # 13
        140000,  # 14
        165000,  # 15
        195000,  # 16
        225000,  # 17
        265000,  # 18
        305000,  # 19
        355000,  # 20
    ]
    if level < 1:
        return 0
    if level > 20:
        # Extrapolate: add 50k per level after 20
        base = dnd5e_xp[-1]
        extra = (level - 20) * 50000
        return int((base + extra) * difficulty_mod)
    return int(dnd5e_xp[level - 1] * difficulty_mod)
