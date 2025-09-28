# XP progression logic for D&D 5e style leveling
# Can be imported anywhere XP/level checks are needed


def xp_for_level(level, difficulty_mod=1.0):
    """
    Returns the total XP required to reach a given level, using D&D 5e progression.
    Optionally applies a difficulty modifier (e.g., 1.5 for hard, 0.5 for easy).
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
