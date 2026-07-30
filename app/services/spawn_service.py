"""Monster spawn selection & scaling service.

Provides utilities to select an appropriate monster from `monster_catalog` for a
given dungeon level and party size. Rarity weighting controls relative frequency.

Integrates with enemy archetype system for template-based scaling and dungeon modifiers.

This is intentionally stateless; future caching or region-specific weighting can
layer on top of these primitives.
"""

from __future__ import annotations

import random
import time
from typing import Dict, List, Optional, Tuple

from app.models import GameConfig, MonsterCatalog

RARITY_WEIGHTS = {
    "common": 1.0,
    "uncommon": 0.55,
    "rare": 0.30,
    "elite": 0.15,
    "boss": 0.02,
}

MONSTER_THEME_FAMILIES = ["undead", "humanoid", "beast", "construct", "elemental", "aberration", "demon"]


def pick_monster_family(seed: int) -> str:
    """Deterministically pick a dungeon's enemy theme from its seed.

    Same seed always returns the same family, for the lifetime of that
    dungeon instance. The XOR salt mirrors SpawnManager's own
    independent RNG stream (random.Random(instance.seed ^ 0x5341574E)
    in app/dungeon/spawn_manager.py) -- same idea, different salt, so
    this doesn't collide with or depend on SpawnManager's seeding.
    """
    return random.Random(seed ^ 0x4D4F4E53).choice(MONSTER_THEME_FAMILIES)  # ^ "MONS"


# -------------------------------------------------------------------------------------------------
# Lightweight in-process cache for eligible monster lists to avoid repetitive DB queries.
# Keyed by (level, include_boss). We intentionally DO NOT include party size because the
# eligibility filtering ignores party size; scaling happens after selection. Cache keeps the raw
# MonsterCatalog ORM objects (safe for read-only usage within request scope). A short TTL keeps
# data fresh if seeds / dynamic injections happen later.
# -------------------------------------------------------------------------------------------------
_ELIGIBLE_CACHE: Dict[Tuple[int, bool, Optional[str]], tuple[float, List[MonsterCatalog]]] = {}
_ELIGIBLE_TTL_SECONDS = 30.0


def clear_cache():  # pragma: no cover - utility for tests / admin
    _ELIGIBLE_CACHE.clear()


def _load_rarity_weights() -> dict:
    """Load rarity weights from GameConfig key 'rarity_weights' if present.

    Stored format: JSON object {"common":1.0, ...}. Missing keys fallback to defaults.
    """
    try:
        raw = GameConfig.get("rarity_weights")
        if not raw:
            return dict(RARITY_WEIGHTS)
        import json

        data = json.loads(raw)
        if not isinstance(data, dict):
            return dict(RARITY_WEIGHTS)
        merged = dict(RARITY_WEIGHTS)
        for k, v in data.items():
            try:
                fv = float(v)
                if fv > 0:
                    merged[k] = fv
            except Exception:
                continue
        return merged
    except Exception:
        return dict(RARITY_WEIGHTS)


def _eligible_monsters(level: int, include_boss: bool = False, family: Optional[str] = None) -> List[MonsterCatalog]:
    now = time.time()
    key = (level, include_boss, family)
    cached = _ELIGIBLE_CACHE.get(key)
    if cached:
        ts, rows = cached
        if (now - ts) <= _ELIGIBLE_TTL_SECONDS:
            return rows
    q = MonsterCatalog.query
    if family:
        q = q.filter(MonsterCatalog.family == family)
    rows = q.filter(MonsterCatalog.level_min <= level, MonsterCatalog.level_max >= level).all()

    # Above the catalogue's top band there is nothing to match, and an empty
    # pool makes choose_monster raise -- which populate_spawn_stats swallows
    # into a bare "Trash Monster" stub with no name, loot table or resistances.
    # The catalogue currently stops at level 20 while characters reach 50, so
    # every spawn for a high-level party degraded silently. Fall back to the
    # deepest band that does exist, so a level-40 party fights the nastiest
    # thing in the book rather than a nameless stub.
    #
    # Be clear about what this does NOT do: MonsterCatalog.scaled_instance
    # clamps the requested level into [level_min, level_max] and then emits
    # base_hp/base_damage/armor unchanged -- level scales nothing, only party
    # size does. So a level-45 ambient spawn has a level-20 monster's numbers
    # and reports itself as level 20, which also caps its loot-table lookup.
    # The archetype and tier systems do rescale, but only for boss/elite set
    # pieces, not for this path. Making ambient spawns scale with level is a
    # balance change waiting on a curve decision -- see the TODO.
    # Filter bosses BEFORE testing emptiness, not after. Ordered the other way,
    # a band whose only rows are bosses looked non-empty, skipped the fallback,
    # and was then emptied by this filter -- so choose_monster raised and
    # populate_spawn_stats swallowed it into a nameless "Trash Monster" with no
    # xp and no loot_table. That was live, not hypothetical: humanoid at levels
    # 16-18, and elemental and aberration at 19+, had no non-boss row at all,
    # so every ambient kill in those themed dungeons paid nothing.
    if not include_boss:
        rows = [r for r in rows if not r.boss]

    if not rows:
        # Nearest band that actually has something we can spawn, measured from
        # the requested level. Two distinct holes land here:
        #   * above the catalogue's ceiling, where nothing matches at all; and
        #   * a band whose only rows are bosses while an ordinary monster was
        #     asked for -- which the old "only if level > ceiling" condition
        #     never covered, because such a band sits *below* the ceiling.
        # Nearest rather than deepest matters: falling back to the deepest band
        # would hand a level-11 party the nastiest thing in the book.
        candidates = q.filter(MonsterCatalog.boss.is_(False)).all() if not include_boss else q.all()
        if candidates:

            def _distance(r):
                if level < int(r.level_min or 0):
                    return int(r.level_min) - level
                if level > int(r.level_max or 0):
                    return level - int(r.level_max)
                return 0

            best = min(_distance(r) for r in candidates)
            rows = [r for r in candidates if _distance(r) == best]
    _ELIGIBLE_CACHE[key] = (now, rows)
    # Simple cap (avoid unbounded growth if level range large)
    if len(_ELIGIBLE_CACHE) > 128:
        # Drop oldest by timestamp
        oldest_key = min(_ELIGIBLE_CACHE.items(), key=lambda kv: kv[1][0])[0]
        if oldest_key != key:
            _ELIGIBLE_CACHE.pop(oldest_key, None)
    return rows


def choose_monster(
    level: int,
    party_size: int = 1,
    include_boss: bool = False,
    rng: Optional[random.Random] = None,
    family: Optional[str] = None,
):
    """Return a scaled monster instance dict for target level.

    Selection steps:
      1. Filter by level band (and by family, if given).
      2. Apply rarity weighting.
      3. Randomly choose.
      4. Scale stats for party size.
    Raises ValueError if no eligible monsters.
    """
    rng = rng or random
    pool = _eligible_monsters(level, include_boss=include_boss, family=family)
    if not pool:
        raise ValueError(f"No monsters available for level {level}")
    rarity_weights = _load_rarity_weights()
    weights = []
    for m in pool:
        w = rarity_weights.get(m.rarity, 0.1)
        # Slight bonus weight if monster's level band tightly matches the requested level midpoint
        midpoint = (m.level_min + m.level_max) / 2.0
        dist = abs(midpoint - level)
        if dist <= 0.5:
            w *= 1.15
        # If caller explicitly allows bosses, give them a modest extra weight to reduce flakiness
        if include_boss and m.boss:
            w = max(w, 0.25) * 2.0  # ensure non-negligible weight then double
        weights.append(max(w, 0.0001))
    total = sum(weights)
    pivot = rng.random() * total
    acc = 0.0
    chosen = pool[-1]
    for m, w in zip(pool, weights):
        acc += w
        if pivot <= acc:
            chosen = m
            break
    # Deterministic fallback: if include_boss requested and we selected a non-boss, occasionally force a boss.
    # We keep this extremely lightweight/deterministic for tests: if no boss seen after selection roll
    # and a boss exists in the pool, force the first boss 1 in 3 attempts (or always if only bosses + others low weight).
    if include_boss and not chosen.boss:
        boss_rows = [r for r in pool if r.boss]
        if boss_rows:
            # Use rng for slight variability; with 200 samples probability of zero bosses becomes negligible (~(2/3)^200).
            if rng.random() < 0.35:  # ~35% promotion rate
                chosen = boss_rows[0]
    # Scale instance (clamp to chosen band)
    return chosen.scaled_instance(level=level, party_size=party_size)


def sample_distribution(level: int, samples: int = 200) -> dict:
    """Return frequency count of chosen monster slugs for diagnostics/testing."""
    freq = {}
    for _ in range(samples):
        inst = choose_monster(level)
        slug = inst["slug"]
        freq[slug] = freq.get(slug, 0) + 1
    return freq


def _identity_for_archetype(archetype, level: int, family: Optional[str], rng) -> Optional[MonsterCatalog]:
    """Pick a catalog creature to lend its identity to an archetype spawn.

    The archetype supplies the *stats* (that is its whole job: tier- and
    affix-driven scaling); the catalog supplies who the thing actually is --
    name, slug, family, traits, loot table. Without this an Elite is literally
    called "Elite (L7)".

    Preference order, widening only as far as it must: the dungeon's own family
    at this level, then any family at this level, then nothing (caller falls
    back to the bare archetype label). Boss-rank archetypes look for catalogued
    bosses first, and elite ranks for the rarer end of the catalog, so a set
    piece does not end up wearing a rat's name.
    """
    rank = (getattr(archetype, "rank", "") or "").strip().lower()
    is_boss_rank = rank in ("boss", "miniboss")
    is_elite_rank = rank in ("elite", "champion") or is_boss_rank

    for fam in ([family] if family else []) + [None]:
        # Only set-piece ranks may wear a catalogued boss's identity; a Trash
        # spawn borrowing the Gloom Prince's name would be absurd, and worse,
        # would look like a boss to anything reading the payload.
        rows = _eligible_monsters(level, include_boss=is_elite_rank, family=fam)
        if not rows:
            continue
        pools = []
        if is_boss_rank:
            pools.append([r for r in rows if r.boss])
        if is_elite_rank:
            pools.append([r for r in rows if (r.rarity or "") in ("boss", "elite", "rare")])
        pools.append([r for r in rows if not r.boss])
        pools.append(rows)
        for pool in pools:
            if pool:
                return rng.choice(pool)
    return None


def choose_archetype_monster(
    level: int,
    archetype_name: str = None,
    tier: int = 1,
    affix_ids: List[str] = None,
    party_size: int = 1,
    rng: Optional[random.Random] = None,
    family: Optional[str] = None,
):
    """Choose a monster using enemy archetype system with tier and affix modifiers.

    Args:
        level: Base dungeon level
        archetype_name: Specific archetype (Trash, Elite, Boss, etc.) or None for random weighted
        tier: Dungeon tier (1-7) - adds monster_level_modifier
        affix_ids: List of affix_id strings to apply (e.g., ["frenzied", "volcanic"])
        party_size: Party size for additional scaling
        rng: Random number generator (defaults to module random)

    Returns:
        Monster dict with archetype-scaled stats and applied affixes
    """
    from app.models.dungeon_tier import DungeonAffix, DungeonTier
    from app.models.enemy_archetype import EnemyArchetype

    rng = rng or random

    # Load tier modifiers
    tier_row = DungeonTier.query.filter_by(tier=tier).first()
    if not tier_row:
        tier_row = DungeonTier.query.filter_by(tier=1).first()  # Fallback to T1

    modified_level = level + (tier_row.monster_level_modifier if tier_row else 0)

    # Choose archetype
    if archetype_name:
        archetype = EnemyArchetype.query.filter_by(archetype=archetype_name).first()
        if not archetype:
            raise ValueError(f"Archetype '{archetype_name}' not found")
    else:
        # Weighted random selection based on spawn_weight
        archetypes = EnemyArchetype.query.all()
        if not archetypes:
            raise ValueError("No archetypes available in database")

        weights = [a.spawn_weight for a in archetypes]
        total_weight = sum(weights)
        pivot = rng.random() * total_weight
        acc = 0.0
        archetype = archetypes[-1]  # Fallback
        for a, w in zip(archetypes, weights):
            acc += w
            if pivot <= acc:
                archetype = a
                break

    # Scale to level
    stats = archetype.scale_to_level(modified_level)

    # Apply party size scaling (simple multiplicative for now)
    if party_size > 1:
        stats["hp"] = int(stats["hp"] * (1 + (party_size - 1) * 0.5))
        stats["damage"] = int(stats["damage"] * (1 + (party_size - 1) * 0.3))

    # Apply affixes
    if affix_ids:
        for affix_id in affix_ids:
            affix = DungeonAffix.query.filter_by(affix_id=affix_id).first()
            if affix:
                stats = affix.apply_to_monster_stats(stats)

    # Add tier multipliers
    if tier_row:
        stats["xp"] = int(stats["xp"] * tier_row.xp_multiplier)
        stats["loot_multiplier"] = stats.get("loot_multiplier", 1.0) * (1.0 + tier_row.loot_quality_bonus)

    # Format as expected monster dict. Stats come from the archetype; identity
    # comes from the catalog when a creature fits this level/family.
    monster = {
        "slug": archetype.archetype.lower().replace(" ", "-"),
        "name": f"{archetype.archetype} (L{modified_level})",
        "hp": stats["hp"],
        "damage": stats["damage"],
        "armor_class": stats["armor_class"],
        "xp": stats["xp"],
        "level": modified_level,
        "rank": archetype.rank,
        "loot_multiplier": stats.get("loot_multiplier", 1.0),
        "archetype": archetype.archetype,
    }

    identity = _identity_for_archetype(archetype, modified_level, family, rng)
    if identity is not None:
        monster.update(
            {
                "slug": identity.slug,
                "name": identity.name,
                "family": identity.family,
                "rarity": identity.rarity,
                "traits": identity.traits_list(),
                "loot_table": identity.loot_table,
                "special_drop_slug": identity.special_drop_slug,
                "speed": identity.speed,
                # Deliberately NOT copying identity.boss: whether a spawn counts
                # as the dungeon's boss is the archetype's call (the payload's
                # "archetype" field is what boss_abilities.is_boss reads). An
                # Elite wearing a catalogued boss's name must not unlock
                # extraction.
            }
        )

    return monster
