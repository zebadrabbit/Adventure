# Character Progression — Design (Spec 5)

**Date:** 2026-06-16
**Status:** Design only — not yet planned/implemented.
**Part of:** Path A — the soft-extraction looter loop.

## Context

With per-character permadeath (Spec 2), **character-level progression is the
per-character stake** that plays against the persistent account-level hoard: you invest
in a character (XP, levels, stats, skills/spells) knowing they can be permanently lost,
while the hoard endures. This makes runs meaningful without being discouraging.

Substantial scaffolding already exists and is **dormant** — this spec completes and
wires it, like Spec 2 did for extraction:

- `app/models/xp.py::xp_for_level(level, difficulty_mod=1.0)` — cumulative D&D-5e XP
  table (levels 1–20, linear beyond). Ready to use.
- `Character.xp` and `Character.level` columns exist.
- `app/routes/inventory_api.py::level_up_character(cid)` — applies stat allocations,
  recomputes `max_hp`/`max_mana`, heals to full. Exists but must be driven by real XP.
- `app/models/skill.py` — `SkillTree`, `Skill` (with `effect_json`, `skill_type`,
  `required_level`, `required_skill_id`, `cost`), `CharacterSkill` (unlocked skills +
  rank), and `CharacterTalentPoints` (earned/spent/available). Models only; no seed data
  or unlock/use endpoints wired into play.

## Design

### A. XP awards (the missing driver)
- Award XP on meaningful events, into `Character.xp`:
  - **Monster defeat:** in `combat_service` victory resolution, grant per-kill XP
    (scale by monster level/tier; reuse any existing reward fields if present).
  - **Extraction:** a completion bonus in `extraction_service.extract_party` for
    surviving/extracting characters (note: early extraction already applies an XP
    *penalty multiplier* — keep that).
- XP is per-character and at-risk: a permadead character's XP is lost with them (no
  action needed — they're gated out of play).

### B. Level-up detection & rewards
- After XP is granted, compute the highest level whose `xp_for_level(level)` is
  `<= character.xp`. If it exceeds `character.level`, the character has pending level(s).
- On level-up, grant: **stat allocation points** and **talent points**
  (`CharacterTalentPoints.available += per_level`, config-driven). The existing
  `level_up_character` endpoint consumes stat allocations — drive it from real pending
  levels rather than letting it be called arbitrarily (validate the character actually
  has earned the level).
- Config (`GameConfig` key `"progression"`): `xp_difficulty_mod`, `stat_points_per_level`,
  `talent_points_per_level`, per-kill/extraction XP rates.

### C. Skills / spells
- **Seed** a small starter set of `SkillTree` + `Skill` rows (programmatic seeder like
  `seed_merchants.py`, idempotent, wired into `run.py`) — e.g. one tree per class with a
  few passive/active skills and spells.
- **Unlock endpoint:** `POST /api/skills/unlock` — spend `CharacterTalentPoints.available`
  to create a `CharacterSkill`, validating `required_level`, `required_skill_id`
  prerequisite, `cost`, and ownership/auth.
- **Apply effects:** active skills/spells become combat actions; passives modify derived
  stats. Combat already derives stats from `Character.stats` + gear affixes
  (`app/loot/equip.py`); extend that aggregation to also fold in unlocked passive
  `effect_json`. Active skills/spells plug into the combat action handlers in
  `combat_service` / `combat_api` (there's an existing spell/ability surface to follow).

### D. UI (if not folded into Spec 4b)
- Character sheet: level, XP bar (`xp_for_level(level+1)`), stat allocation on level-up,
  and a skill tree view to spend talent points. Account screen already shows level/xp.

### Tests
- `xp_for_level` thresholds drive correct pending-level computation.
- Defeating a monster / extracting grants XP; crossing a threshold yields a level and
  talent points.
- `level_up_character` rejects allocations the character hasn't earned.
- Skill unlock: succeeds with enough points + prerequisites; rejects otherwise; respects
  ownership/auth. Seeder is idempotent and all seeded skills reference valid trees.
- Passive skill effect changes a derived combat stat.

## Suggested decomposition
This is large; plan it as: **5a** XP awards + level-up rewards (A+B), **5b** skills/spells
seed + unlock + effects (C), **5c** UI (D, or merge into Spec 4b). 5a is the smallest
shippable increment and unblocks the rest.

## Affected files (anticipated)
- `app/services/combat_service.py`, `app/services/extraction_service.py`,
  `app/routes/inventory_api.py` (level-up validation), new `app/services/progression.py`
  (pending-level + reward logic), new `app/seed_skills.py`, new `app/routes/skill_*`
  (unlock), `app/loot/equip.py` (passive effects), templates/JS, tests.
- Reuse: `app/models/xp.py`, `app/models/skill.py`, `Character.xp/level`, `GameConfig`.
