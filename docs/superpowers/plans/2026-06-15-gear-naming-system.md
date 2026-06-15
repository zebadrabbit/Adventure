# Gear & Naming System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the dormant/hasty item data with a deep, procedural gear system — base archetypes rolled up with rarity + single-stat prefixes + themed stat-package suffixes — whose composed names and stat bonuses actually affect combat.

**Architecture:** Code-defined data modules (`app/loot/data/`) feed a pure roll engine (`app/loot/generator.py`) that emits self-contained JSON item instances. Equipped instances are summed by a `gear_bonuses` helper folded into combat and dashboard stat derivation. The real drop path (`roll_loot`) emits instances. Infra (item-seed fix + Postgres) lands first.

**Tech Stack:** Python 3.12, Flask, SQLAlchemy, pytest, PostgreSQL (target) / SQLite (fallback). RNG via `random.Random` (injectable for tests).

**Spec:** `docs/superpowers/specs/2026-06-15-gear-naming-system-design.md`

**Conventions for every task below:**
- Tests run with a DB URL. Use: `DATABASE_URL=postgresql://adventure:changeme@localhost:5434/adventure_test .venv/bin/python -m pytest <args>` (or the SQLite fallback `DATABASE_URL=sqlite:////home/winter/work/Adventure/instance/test_gear.db`). Pure-logic tests under `tests/test_gear_*` do not hit the DB and run with plain `.venv/bin/python -m pytest`.
- Pre-commit hooks (black, ruff) auto-format and ABORT the commit on changes; re-`git add` and re-commit. Never use `--no-verify`.
- Stats vocabulary used throughout: attributes `str, dex, int, wis, con, cha`; derived `damage, armor, crit, resist, speed, mana, max_hp`.

---

## Phase 0 — Infra first

### Task 0.1: Remove the hand-tiered weapon/armor/jewelry catalog

**Files:**
- Delete: `sql/items_weapons.sql`, `sql/items_armor.sql`
- Delete (if present): `sql/items_jewelry.sql`
- Modify: `app/seed_items.py` (the `ITEM_FILES_ORDER` list, ~lines 36-41)

- [ ] **Step 1: Confirm what references the tiered files**

Run: `grep -rn "items_weapons\|items_armor\|items_jewelry" app/ tests/ scripts/`
Expected: references in `app/seed_items.py::ITEM_FILES_ORDER` (and possibly tests). Note them.

- [ ] **Step 2: Delete the tiered SQL files**

```bash
git rm sql/items_weapons.sql sql/items_armor.sql
git rm sql/items_jewelry.sql 2>/dev/null || true
```

- [ ] **Step 3: Trim `ITEM_FILES_ORDER` to consumables/misc only**

In `app/seed_items.py`, change `ITEM_FILES_ORDER` to keep only files that still exist:

```python
ITEM_FILES_ORDER = [
    "items_potions.sql",
    "items_misc.sql",
]
```

- [ ] **Step 4: Verify reseed loads clean on a fresh SQLite DB**

Run:
```bash
rm -f instance/seedcheck.db
DATABASE_URL="sqlite:////home/winter/work/Adventure/instance/seedcheck.db" .venv/bin/python run.py reseed-items
```
Expected: completes without `NOT NULL constraint failed: item.level`; prints item count.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "chore(seed): remove hand-tiered weapon/armor/jewelry catalog (superseded by archetypes)"
```

---

### Task 0.2: Harden the item seed so `level` is always supplied

**Files:**
- Modify: `app/seed_items.py` (augmentation block, ~lines 146-170)
- Test: `tests/test_seed_items_level.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_seed_items_level.py
from app.seed_items import _augment_item_level_default


def test_insert_without_level_gets_default_zero():
    line = "('potion-x','Potion X','potion','desc',10),"
    out = _augment_item_level_default(line, has_level=False)
    assert ", 0, 'common', 1.0)" in out


def test_insert_with_level_untouched():
    line = "('weapon-x','Sword','weapon','desc',10,5,'rare',2.0),"
    out = _augment_item_level_default(line, has_level=True)
    assert out == line
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_seed_items_level.py -v`
Expected: FAIL with `ImportError`/`AttributeError` (`_augment_item_level_default` not defined).

- [ ] **Step 3: Extract the augmentation into a tested helper**

In `app/seed_items.py`, add this module-level function and call it from `execute_sql_file` where the inline tuple augmentation currently lives:

```python
def _augment_item_level_default(line: str, has_level: bool) -> str:
    """Ensure an item VALUES tuple carries (level, rarity, weight).

    If the insert header already includes level/rarity/weight (`has_level`),
    return the line unchanged. Otherwise append `, 0, 'common', 1.0` before the
    closing paren, preserving any trailing comma/semicolon and indentation.
    """
    if has_level:
        return line
    stripped = line.strip()
    if not stripped.startswith("("):
        return line
    closing = stripped[-1]
    trailer = closing if closing in {",", ";"} else ""
    inner = stripped[:-1] if trailer else stripped
    idx = inner.rfind(")")
    if idx == -1:
        return line
    inner = inner[:idx] + ", 0, 'common', 1.0" + inner[idx:]
    prefix_ws = line[: len(line) - len(line.lstrip(" "))]
    return prefix_ws + inner + trailer
```

Then replace the inline augmentation in the `for line in cleaned_lines:` loop so each candidate tuple line is produced by `_augment_item_level_default(raw_line, has_level=in_item_insert_has_level)`, where `in_item_insert_has_level` is set `True` when the detected header already contains `level` and `False` when the header was extended. (Keep the existing header-extension logic that rewrites `(slug, name, type, description, value_copper)` → `(... , level, rarity, weight)`.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_seed_items_level.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Re-verify full reseed on fresh SQLite**

Run:
```bash
rm -f instance/seedcheck.db
DATABASE_URL="sqlite:////home/winter/work/Adventure/instance/seedcheck.db" .venv/bin/python run.py reseed-items
```
Expected: completes cleanly.

- [ ] **Step 6: Commit**

```bash
git add app/seed_items.py tests/test_seed_items_level.py
git commit -m "fix(seed): always supply item.level default via tested helper"
```

---

### Task 0.3: One-command Postgres bootstrap

**Files:**
- Create: `scripts/bootstrap_db.sh`
- Modify: `docs/TESTING.md` (append a "Postgres bootstrap" section)

- [ ] **Step 1: Write the bootstrap script**

```bash
# scripts/bootstrap_db.sh
#!/usr/bin/env bash
# Create/seed a clean Adventure database. Usage:
#   DATABASE_URL=postgresql://adventure:changeme@localhost:5434/adventure ./scripts/bootstrap_db.sh
set -euo pipefail
cd "$(dirname "$0")/.."
: "${DATABASE_URL:?set DATABASE_URL to the target database}"
echo "Bootstrapping $DATABASE_URL"
.venv/bin/python - <<'PY'
from app import app, db
with app.app_context():
    db.create_all()
    try:
        from app.server import _run_migrations, _seed_game_config
        _run_migrations()
        _seed_game_config()
    except Exception as e:
        print("migration/config warning:", e)
print("schema + config ready")
PY
.venv/bin/python run.py reseed-items
echo "Bootstrap complete."
```

- [ ] **Step 2: Make it executable and run against a throwaway Postgres**

Run:
```bash
chmod +x scripts/bootstrap_db.sh
docker ps --format '{{.Names}}' | grep -q adv_pg || docker run -d --rm --name adv_pg \
  -e POSTGRES_DB=adventure -e POSTGRES_USER=adventure -e POSTGRES_PASSWORD=changeme \
  -p 5434:5432 postgres:15-alpine
sleep 4
DATABASE_URL=postgresql://adventure:changeme@localhost:5434/adventure ./scripts/bootstrap_db.sh
```
Expected: "Bootstrap complete." with no traceback.

- [ ] **Step 3: Run the full suite on Postgres to confirm green**

Run: `DATABASE_URL=postgresql://adventure:changeme@localhost:5434/adventure_test .venv/bin/python -m pytest -q`
Expected: all pass (baseline 261 passed, 3 skipped, 1 xpassed).

- [ ] **Step 4: Document and commit**

Append to `docs/TESTING.md` a short "Postgres bootstrap" section showing the docker run + `scripts/bootstrap_db.sh` usage. Then:

```bash
git add scripts/bootstrap_db.sh docs/TESTING.md
git commit -m "feat(infra): one-command Postgres bootstrap script + docs"
```

---

## Phase 1 — Data modules

All data lives under `app/loot/data/`. Create `app/loot/data/__init__.py` (empty) first if absent.

### Task 1.1: Rarity table

**Files:**
- Create: `app/loot/data/rarities.py`
- Test: `tests/test_gear_rarities.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_gear_rarities.py
from app.loot.data.rarities import RARITIES, rarity_affix_range, RARITY_ORDER


def test_order_complete():
    assert RARITY_ORDER == ["common", "uncommon", "rare", "epic", "legendary", "mythic"]


def test_each_rarity_has_color_and_range():
    for r in RARITY_ORDER:
        spec = RARITIES[r]
        assert spec["color"].startswith("#")
        lo, hi = spec["affixes"]
        assert 0 <= lo <= hi <= 6


def test_affix_range_helper():
    assert rarity_affix_range("rare") == (2, 3)
    assert rarity_affix_range("nonsense") == (0, 1)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_gear_rarities.py -v`
Expected: FAIL (`ModuleNotFoundError: app.loot.data.rarities`).

- [ ] **Step 3: Implement the rarity table**

```python
# app/loot/data/rarities.py
"""Rarity tiers: affix-count ranges + UI colors."""

RARITIES = {
    "common":    {"affixes": (0, 1), "color": "#9d9d9d", "value_mult": 1.0},
    "uncommon":  {"affixes": (1, 2), "color": "#1eff00", "value_mult": 1.6},
    "rare":      {"affixes": (2, 3), "color": "#0070dd", "value_mult": 2.6},
    "epic":      {"affixes": (3, 4), "color": "#a335ee", "value_mult": 4.2},
    "legendary": {"affixes": (3, 5), "color": "#ff8000", "value_mult": 7.0},
    "mythic":    {"affixes": (4, 6), "color": "#e6cc80", "value_mult": 12.0},
}

RARITY_ORDER = ["common", "uncommon", "rare", "epic", "legendary", "mythic"]


def rarity_affix_range(rarity: str) -> tuple[int, int]:
    return RARITIES.get(rarity, {"affixes": (0, 1)})["affixes"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_gear_rarities.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add app/loot/data/__init__.py app/loot/data/rarities.py tests/test_gear_rarities.py
git commit -m "feat(gear): rarity tiers data module"
```

---

### Task 1.2: Archetype table (base items)

**Files:**
- Create: `app/loot/data/archetypes.py`
- Test: `tests/test_gear_archetypes.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_gear_archetypes.py
from app.loot.data.archetypes import ARCHETYPES, archetypes_for_slot, SLOTS


def test_eight_slots_present():
    assert set(SLOTS) == {"weapon", "offhand", "head", "chest", "hands", "feet", "ring", "amulet"}
    for slot in SLOTS:
        assert archetypes_for_slot(slot), f"no archetypes for {slot}"


def test_archetype_shape():
    for key, a in ARCHETYPES.items():
        assert a["slot"] in SLOTS
        assert a["base_name"]
        assert a["category"]
        # weapons have a damage range, armor has an armor base, jewelry neither
        if a["slot"] == "weapon":
            assert a["damage"][0] <= a["damage"][1]


def test_shortsword_exists():
    assert ARCHETYPES["shortsword"]["slot"] == "weapon"
    assert ARCHETYPES["shortsword"]["category"] == "blade"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_gear_archetypes.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implement the archetype table**

```python
# app/loot/data/archetypes.py
"""Base item archetypes. Variety comes from rarity + affix rolls, not pre-tiers.

Each archetype: slot, category, optional `damage` (min,max) for weapons,
optional `armor` base for armor, `attack_speed` for weapons, and `affinity`
(attribute tags that bias which themed affixes fit).
"""

SLOTS = ["weapon", "offhand", "head", "chest", "hands", "feet", "ring", "amulet"]

ARCHETYPES = {
    # --- Weapons ---
    "dagger":     {"slot": "weapon", "base_name": "Dagger",     "category": "blade",  "damage": (2, 5),  "attack_speed": 1.4, "affinity": ["dex"]},
    "shortsword": {"slot": "weapon", "base_name": "Shortsword", "category": "blade",  "damage": (4, 7),  "attack_speed": 1.0, "affinity": ["str", "dex"]},
    "longsword":  {"slot": "weapon", "base_name": "Longsword",  "category": "blade",  "damage": (6, 11), "attack_speed": 0.9, "affinity": ["str"]},
    "greatsword": {"slot": "weapon", "base_name": "Greatsword", "category": "blade",  "damage": (9, 16), "attack_speed": 0.7, "affinity": ["str"]},
    "mace":       {"slot": "weapon", "base_name": "Mace",       "category": "blunt",  "damage": (5, 9),  "attack_speed": 0.9, "affinity": ["str"]},
    "warhammer":  {"slot": "weapon", "base_name": "Warhammer",  "category": "blunt",  "damage": (9, 15), "attack_speed": 0.7, "affinity": ["str"]},
    "greataxe":   {"slot": "weapon", "base_name": "Greataxe",   "category": "axe",    "damage": (10, 17),"attack_speed": 0.7, "affinity": ["str"]},
    "spear":      {"slot": "weapon", "base_name": "Spear",      "category": "polearm","damage": (6, 10), "attack_speed": 0.9, "affinity": ["str", "dex"]},
    "bow":        {"slot": "weapon", "base_name": "Bow",        "category": "ranged", "damage": (5, 9),  "attack_speed": 1.0, "affinity": ["dex"]},
    "crossbow":   {"slot": "weapon", "base_name": "Crossbow",   "category": "ranged", "damage": (7, 12), "attack_speed": 0.8, "affinity": ["dex"]},
    "staff":      {"slot": "weapon", "base_name": "Staff",      "category": "caster", "damage": (4, 8),  "attack_speed": 0.9, "affinity": ["int", "wis"]},
    "wand":       {"slot": "weapon", "base_name": "Wand",       "category": "caster", "damage": (3, 6),  "attack_speed": 1.2, "affinity": ["int"]},
    # --- Offhand ---
    "shield":     {"slot": "offhand", "base_name": "Shield", "category": "shield", "armor": (4, 9), "affinity": ["str", "con"]},
    "tome":       {"slot": "offhand", "base_name": "Tome",   "category": "caster", "armor": (0, 1), "affinity": ["int", "wis"]},
    "orb":        {"slot": "offhand", "base_name": "Orb",    "category": "caster", "armor": (0, 1), "affinity": ["int"]},
    # --- Armor (material -> base armor) ---
    "cloth_hood":    {"slot": "head",  "base_name": "Cloth Hood",     "category": "cloth",   "armor": (1, 2), "affinity": ["int", "wis"]},
    "leather_cap":   {"slot": "head",  "base_name": "Leather Cap",    "category": "leather", "armor": (2, 4), "affinity": ["dex"]},
    "mail_coif":     {"slot": "head",  "base_name": "Mail Coif",      "category": "mail",    "armor": (3, 6), "affinity": ["str", "dex"]},
    "plate_helm":    {"slot": "head",  "base_name": "Plate Helm",     "category": "plate",   "armor": (5, 9), "affinity": ["str", "con"]},
    "cloth_robe":    {"slot": "chest", "base_name": "Cloth Robe",     "category": "cloth",   "armor": (2, 4), "affinity": ["int", "wis"]},
    "leather_tunic": {"slot": "chest", "base_name": "Leather Tunic",  "category": "leather", "armor": (4, 7), "affinity": ["dex"]},
    "mail_hauberk":  {"slot": "chest", "base_name": "Mail Hauberk",   "category": "mail",    "armor": (6, 11),"affinity": ["str", "dex"]},
    "plate_cuirass": {"slot": "chest", "base_name": "Plate Cuirass",  "category": "plate",   "armor": (9, 16),"affinity": ["str", "con"]},
    "cloth_gloves":  {"slot": "hands", "base_name": "Cloth Gloves",   "category": "cloth",   "armor": (1, 2), "affinity": ["int"]},
    "leather_gloves":{"slot": "hands", "base_name": "Leather Gloves", "category": "leather", "armor": (2, 4), "affinity": ["dex"]},
    "mail_gauntlets":{"slot": "hands", "base_name": "Mail Gauntlets", "category": "mail",    "armor": (3, 6), "affinity": ["str"]},
    "plate_gauntlets":{"slot": "hands","base_name": "Plate Gauntlets","category": "plate",   "armor": (4, 8), "affinity": ["str"]},
    "cloth_slippers":{"slot": "feet",  "base_name": "Cloth Slippers", "category": "cloth",   "armor": (1, 2), "affinity": ["int"]},
    "leather_boots": {"slot": "feet",  "base_name": "Leather Boots",  "category": "leather", "armor": (2, 4), "affinity": ["dex"]},
    "mail_boots":    {"slot": "feet",  "base_name": "Mail Boots",     "category": "mail",    "armor": (3, 6), "affinity": ["str"]},
    "plate_boots":   {"slot": "feet",  "base_name": "Plate Boots",    "category": "plate",   "armor": (4, 8), "affinity": ["str", "con"]},
    # --- Jewelry (pure affix carriers) ---
    "ring":   {"slot": "ring",   "base_name": "Ring",   "category": "jewelry", "affinity": ["str", "dex", "int", "wis", "con", "cha"]},
    "amulet": {"slot": "amulet", "base_name": "Amulet", "category": "jewelry", "affinity": ["str", "dex", "int", "wis", "con", "cha"]},
}


def archetypes_for_slot(slot: str) -> list[str]:
    return [k for k, a in ARCHETYPES.items() if a["slot"] == slot]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_gear_archetypes.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add app/loot/data/archetypes.py tests/test_gear_archetypes.py
git commit -m "feat(gear): base item archetype table (8 slots)"
```

---

### Task 1.3: Prefix table (single-stat, tiered)

**Files:**
- Create: `app/loot/data/prefixes.py`
- Test: `tests/test_gear_prefixes.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_gear_prefixes.py
from app.loot.data.prefixes import PREFIXES, prefixes_for


def test_prefix_shape():
    for p in PREFIXES:
        assert p["name"]
        assert p["stat"] in {"damage", "armor", "speed", "crit", "resist", "lifesteal"}
        assert p["min"] <= p["max"]
        assert p["weight"] > 0
        assert isinstance(p["slots"], (list, tuple))


def test_filter_by_slot_and_category():
    weapon_dmg = prefixes_for("weapon", "blade")
    assert any(p["stat"] == "damage" for p in weapon_dmg)
    # 'Sturdy' (+armor) should not apply to a caster wand's damage-only prefixes set
    head = prefixes_for("head", "plate")
    assert any(p["stat"] == "armor" for p in head)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_gear_prefixes.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implement the prefix table**

```python
# app/loot/data/prefixes.py
"""Single-stat prefixes. `slots`/`categories` gate eligibility; `weight` biases
selection; values scale with item level in the generator."""

# Each: name, stat, (min,max) base value, scaling_per_level, weight,
# slots (which equipment slots), categories (None = any category in those slots).
PREFIXES = [
    # weapon damage tiers (share stat 'damage'; tier implied by value/weight)
    {"name": "Sharp",      "stat": "damage", "min": 1, "max": 3,  "scale": 0.3, "weight": 120, "slots": ["weapon"], "categories": None},
    {"name": "Keen",       "stat": "damage", "min": 2, "max": 5,  "scale": 0.4, "weight": 90,  "slots": ["weapon"], "categories": None},
    {"name": "Brutal",     "stat": "damage", "min": 4, "max": 8,  "scale": 0.6, "weight": 60,  "slots": ["weapon"], "categories": None},
    {"name": "Savage",     "stat": "damage", "min": 6, "max": 12, "scale": 0.8, "weight": 35,  "slots": ["weapon"], "categories": None},
    {"name": "Cruel",      "stat": "damage", "min": 9, "max": 16, "scale": 1.0, "weight": 18,  "slots": ["weapon"], "categories": None},
    # armor
    {"name": "Sturdy",     "stat": "armor",  "min": 2, "max": 5,  "scale": 0.3, "weight": 110, "slots": ["offhand", "head", "chest", "hands", "feet"], "categories": None},
    {"name": "Reinforced", "stat": "armor",  "min": 4, "max": 9,  "scale": 0.5, "weight": 60,  "slots": ["offhand", "head", "chest", "hands", "feet"], "categories": None},
    # speed / crit / utility
    {"name": "Quick",      "stat": "speed",  "min": 1, "max": 3,  "scale": 0.1, "weight": 70,  "slots": ["weapon", "feet"], "categories": None},
    {"name": "Deadly",     "stat": "crit",   "min": 1, "max": 4,  "scale": 0.2, "weight": 55,  "slots": ["weapon", "ring", "amulet"], "categories": None},
    {"name": "Warding",    "stat": "resist", "min": 2, "max": 6,  "scale": 0.3, "weight": 60,  "slots": ["offhand", "head", "chest", "hands", "feet", "ring", "amulet"], "categories": None},
    {"name": "Vampiric",   "stat": "lifesteal", "min": 1, "max": 3, "scale": 0.1, "weight": 25, "slots": ["weapon"], "categories": None},
    # elemental damage (use 'damage' stat; flavor via name)
    {"name": "Flaming",    "stat": "damage", "min": 2, "max": 6,  "scale": 0.4, "weight": 40,  "slots": ["weapon"], "categories": None},
    {"name": "Frozen",     "stat": "damage", "min": 2, "max": 6,  "scale": 0.4, "weight": 40,  "slots": ["weapon"], "categories": None},
    {"name": "Shocking",   "stat": "damage", "min": 2, "max": 6,  "scale": 0.4, "weight": 40,  "slots": ["weapon"], "categories": None},
]


def prefixes_for(slot: str, category: str) -> list[dict]:
    out = []
    for p in PREFIXES:
        if slot not in p["slots"]:
            continue
        if p["categories"] is not None and category not in p["categories"]:
            continue
        out.append(p)
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_gear_prefixes.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add app/loot/data/prefixes.py tests/test_gear_prefixes.py
git commit -m "feat(gear): single-stat prefix table"
```

---

### Task 1.4: Suffix table (themed stat packages)

**Files:**
- Create: `app/loot/data/suffixes.py`
- Test: `tests/test_gear_suffixes.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_gear_suffixes.py
from app.loot.data.suffixes import SUFFIXES, suffixes_for

ATTRS = {"str", "dex", "int", "wis", "con", "cha", "crit", "resist", "mana", "max_hp"}


def test_suffix_shape():
    for s in SUFFIXES:
        assert s["name"].startswith("of ")
        assert s["stats"], "suffix must grant at least one stat"
        for stat, weight in s["stats"].items():
            assert stat in ATTRS
            assert weight > 0
        assert s["weight"] > 0


def test_hawk_is_dex_con():
    hawk = next(s for s in SUFFIXES if s["name"] == "of the Hawk")
    assert set(hawk["stats"].keys()) == {"dex", "con"}


def test_eligibility_by_affinity():
    # 'of the Hawk' (dex) should be eligible for a dex archetype
    elig = suffixes_for(["dex"])
    assert any(s["name"] == "of the Hawk" for s in elig)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_gear_suffixes.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implement the suffix table**

The starter set below is functional and demonstrates the pattern. **Expand this to ~40-60 entries** following the same shape (more animal/role themes mapping to the attribute set) as a content pass — see Task 1.5.

```python
# app/loot/data/suffixes.py
"""Themed stat-package suffixes ("of the X"). Each maps to a dict of
{stat: relative_weight}; the generator splits the rolled budget across them.
`affinity` lists attribute tags an archetype must share for eligibility
(empty/global means always eligible)."""

SUFFIXES = [
    {"name": "of the Hawk",          "stats": {"dex": 2, "con": 1}, "affinity": ["dex"],        "weight": 100},
    {"name": "of the Bear",          "stats": {"str": 2, "con": 1}, "affinity": ["str"],        "weight": 100},
    {"name": "of the Eagle",         "stats": {"int": 2, "con": 1}, "affinity": ["int"],        "weight": 100},
    {"name": "of the Owl",           "stats": {"int": 2, "wis": 1}, "affinity": ["int", "wis"], "weight": 90},
    {"name": "of the Tiger",         "stats": {"str": 1, "dex": 1}, "affinity": ["str", "dex"], "weight": 90},
    {"name": "of the Whale",         "stats": {"con": 3},           "affinity": [],             "weight": 80},
    {"name": "of the Wolf",          "stats": {"dex": 2, "wis": 1}, "affinity": ["dex"],        "weight": 80},
    {"name": "of the Gorilla",       "stats": {"str": 2, "int": 1}, "affinity": ["str", "int"], "weight": 60},
    {"name": "of the Monkey",        "stats": {"str": 1, "dex": 2}, "affinity": ["dex"],        "weight": 70},
    {"name": "of the Falcon",        "stats": {"dex": 2, "str": 1}, "affinity": ["dex", "str"], "weight": 70},
    {"name": "of the Boar",          "stats": {"str": 2, "wis": 1}, "affinity": ["str"],        "weight": 60},
    {"name": "of the Sorcerer",      "stats": {"int": 2, "crit": 1},"affinity": ["int"],        "weight": 55},
    {"name": "of the Mind",          "stats": {"int": 2, "mana": 2},"affinity": ["int", "wis"], "weight": 55},
    {"name": "of the Bandit",        "stats": {"dex": 2, "cha": 1}, "affinity": ["dex"],        "weight": 50},
    {"name": "of the Champion",      "stats": {"str": 1, "con": 1, "dex": 1}, "affinity": ["str", "dex"], "weight": 30},
    {"name": "of the Elder",         "stats": {"wis": 2, "con": 1}, "affinity": ["wis"],        "weight": 60},
    {"name": "of Vitality",          "stats": {"max_hp": 3},        "affinity": [],             "weight": 90},
    {"name": "of Warding",           "stats": {"resist": 3},        "affinity": [],             "weight": 70},
]


def suffixes_for(affinity: list[str]) -> list[dict]:
    aff = set(affinity)
    out = []
    for s in SUFFIXES:
        if not s["affinity"] or aff.intersection(s["affinity"]):
            out.append(s)
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_gear_suffixes.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add app/loot/data/suffixes.py tests/test_gear_suffixes.py
git commit -m "feat(gear): themed stat-package suffix table"
```

---

### Task 1.5: Content pass — expand the suffix/prefix breadth

**Files:**
- Modify: `app/loot/data/suffixes.py`, `app/loot/data/prefixes.py`

- [ ] **Step 1: Expand suffixes to ~40-60 entries**

Add more themed suffixes following the existing dict shape (animal/role themes mapping to `{stat: weight}` over `str/dex/int/wis/con/cha/crit/resist/mana/max_hp`). Aim for coverage of every attribute and several two/three-stat combos. Examples to add: `of the Lion` (str+cha), `of the Fox` (dex+int), `of the Serpent` (dex+crit), `of the Ox` (str+con big), `of the Raven` (int+dex), `of the Stag` (con+wis), `of the Phoenix` (int+max_hp), `of the Colossus` (str+armor via con), `of Precision` (crit), `of the Magus` (int+mana), `of Sanctuary` (resist+max_hp), etc.

- [ ] **Step 2: Add a couple more prefix flavors if desired**

Optional: add `Heavy` (+armor), `Honed` (+crit), `Swift` (+speed) following the prefix dict shape.

- [ ] **Step 3: Re-run the data tests (shape still valid)**

Run: `.venv/bin/python -m pytest tests/test_gear_suffixes.py tests/test_gear_prefixes.py -v`
Expected: PASS (existing tests still green; new entries conform to shape).

- [ ] **Step 4: Commit**

```bash
git add app/loot/data/suffixes.py app/loot/data/prefixes.py
git commit -m "content(gear): expand themed suffixes and prefixes"
```

---

## Phase 2 — Roll engine

### Task 2.1: Name composition

**Files:**
- Create: `app/loot/naming.py`
- Test: `tests/test_gear_naming.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_gear_naming.py
from app.loot.naming import compose_name


def test_prefix_base_suffix():
    assert compose_name("Brutal", "Shortsword", "of the Hawk") == "Brutal Shortsword of the Hawk"


def test_bare_base():
    assert compose_name(None, "Shortsword", None) == "Shortsword"


def test_prefix_only():
    assert compose_name("Sturdy", "Plate Helm", None) == "Sturdy Plate Helm"


def test_suffix_only():
    assert compose_name(None, "Oak Wand", "of the Owl") == "Oak Wand of the Owl"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_gear_naming.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implement name composition**

```python
# app/loot/naming.py
"""Compose item display names from prefix + base + suffix."""


def compose_name(prefix: str | None, base: str, suffix: str | None) -> str:
    parts = []
    if prefix:
        parts.append(prefix)
    parts.append(base)
    name = " ".join(parts)
    if suffix:
        name = f"{name} {suffix}"
    return name
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_gear_naming.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add app/loot/naming.py tests/test_gear_naming.py
git commit -m "feat(gear): item name composition"
```

---

### Task 2.2: The generator (`generate_item`)

**Files:**
- Create: `app/loot/generator.py`
- Test: `tests/test_gear_generator.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_gear_generator.py
import random
from app.loot.generator import generate_item
from app.loot.data.rarities import rarity_affix_range


def _rng(seed=1):
    return random.Random(seed)


def test_returns_instance_shape():
    it = generate_item(level=5, rarity="rare", rng=_rng())
    for key in ("uid", "base", "slot", "name", "rarity", "ilvl", "affixes", "value"):
        assert key in it
    assert it["rarity"] == "rare"
    assert it["ilvl"] == 5


def test_affix_count_at_least_rarity_min():
    # affixes include the innate base stat block, so the rarity range is a FLOOR
    for rarity in ("common", "rare", "mythic"):
        lo, hi = rarity_affix_range(rarity)
        for s in range(20):
            it = generate_item(level=10, rarity=rarity, rng=_rng(s))
            assert len(it["affixes"]) >= lo


def test_slot_filter_respected():
    it = generate_item(level=5, slot="weapon", rng=_rng(3))
    assert it["slot"] == "weapon"


def test_affix_stats_are_known():
    known = {"str","dex","int","wis","con","cha","damage","armor","crit","resist","speed","mana","max_hp","lifesteal"}
    it = generate_item(level=8, rarity="epic", rng=_rng(7))
    for a in it["affixes"]:
        assert a["stat"] in known
        assert a["val"] >= 1


def test_deterministic_under_seed():
    a = generate_item(level=6, rarity="rare", slot="weapon", rng=_rng(42))
    b = generate_item(level=6, rarity="rare", slot="weapon", rng=_rng(42))
    assert a["name"] == b["name"] and a["affixes"] == b["affixes"]


def test_value_scales_with_rarity():
    common = generate_item(level=10, rarity="common", slot="ring", rng=_rng(1))
    myth = generate_item(level=10, rarity="mythic", slot="ring", rng=_rng(1))
    assert myth["value"] > common["value"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_gear_generator.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implement the generator**

```python
# app/loot/generator.py
"""Procedural item generator: archetype + rarity + prefix/suffix -> instance."""

from __future__ import annotations

import random
import uuid

from app.loot.data.archetypes import ARCHETYPES, SLOTS, archetypes_for_slot
from app.loot.data.prefixes import prefixes_for
from app.loot.data.suffixes import suffixes_for
from app.loot.data.rarities import RARITIES, RARITY_ORDER, rarity_affix_range
from app.loot.naming import compose_name

# default rarity weighting when none requested
_DEFAULT_RARITY_WEIGHTS = {
    "common": 600, "uncommon": 250, "rare": 100, "epic": 35, "legendary": 13, "mythic": 2,
}


def _weighted_choice(rng: random.Random, items: list, weight_key):
    total = sum(weight_key(i) for i in items)
    if total <= 0:
        return rng.choice(items)
    pivot = rng.random() * total
    acc = 0.0
    for i in items:
        acc += weight_key(i)
        if pivot <= acc:
            return i
    return items[-1]


def _roll_rarity(rng: random.Random) -> str:
    pairs = [(r, _DEFAULT_RARITY_WEIGHTS[r]) for r in RARITY_ORDER]
    return _weighted_choice(rng, pairs, lambda p: p[1])[0]


def _base_stat_block(arch: dict, level: int, rng: random.Random) -> list[dict]:
    """Innate stat from the archetype (weapon damage / armor)."""
    out = []
    if "damage" in arch:
        lo, hi = arch["damage"]
        out.append({"stat": "damage", "val": rng.randint(lo, hi) + level // 3})
    if "armor" in arch and arch["armor"][1] > 0:
        lo, hi = arch["armor"]
        out.append({"stat": "armor", "val": rng.randint(lo, hi) + level // 4})
    return out


def _roll_prefix(arch: dict, level: int, rng: random.Random):
    pool = prefixes_for(arch["slot"], arch["category"])
    if not pool:
        return None, None
    p = _weighted_choice(rng, pool, lambda x: x["weight"])
    val = rng.randint(p["min"], p["max"]) + int(p["scale"] * max(0, level - 1))
    return p["name"], {"stat": p["stat"], "val": max(1, int(val))}


def _roll_suffix(arch: dict, level: int, rng: random.Random):
    pool = suffixes_for(arch.get("affinity", []))
    if not pool:
        return None, []
    s = _weighted_choice(rng, pool, lambda x: x["weight"])
    # Budget scales with level; split across the theme's stats by weight.
    budget = 3 + level // 2
    wsum = sum(s["stats"].values())
    affixes = []
    for stat, w in s["stats"].items():
        val = max(1, round(budget * w / wsum))
        affixes.append({"stat": stat, "val": val})
    return s["name"], affixes


def generate_item(level: int, rarity: str | None = None, slot: str | None = None,
                  rng: random.Random | None = None) -> dict:
    rng = rng or random.Random()
    rarity = rarity if rarity in RARITIES else _roll_rarity(rng)
    slot = slot if slot in SLOTS else rng.choice(SLOTS)
    arch_key = rng.choice(archetypes_for_slot(slot))
    arch = ARCHETYPES[arch_key]

    affixes = _base_stat_block(arch, level, rng)
    n_affixes = rng.randint(*rarity_affix_range(rarity))

    prefix_name = suffix_name = None
    remaining = n_affixes
    # Alternate: try a suffix (theme) then a prefix, up to remaining budget.
    if remaining > 0:
        suffix_name, suffix_affixes = _roll_suffix(arch, level, rng)
        if suffix_name:
            affixes.extend(suffix_affixes)
            remaining -= 1
    if remaining > 0:
        prefix_name, prefix_affix = _roll_prefix(arch, level, rng)
        if prefix_affix:
            affixes.append(prefix_affix)
            remaining -= 1
    # Any further affixes become extra prefixes (single-stat).
    while remaining > 0:
        _, extra = _roll_prefix(arch, level, rng)
        if not extra:
            break
        affixes.append(extra)
        remaining -= 1

    name = compose_name(prefix_name, arch["base_name"], suffix_name)
    base_value = 8 + level * 4
    value = int((base_value + sum(a["val"] for a in affixes) * 3) * RARITIES[rarity]["value_mult"])

    return {
        "uid": uuid.uuid4().hex[:12],
        "base": arch_key,
        "slot": slot,
        "name": name,
        "rarity": rarity,
        "ilvl": level,
        "affixes": affixes,
        "value": value,
    }
```

Note: `affixes` includes the innate base stat block (weapon damage / armor), so the rarity affix-count range acts as a *floor* on the total — which is exactly what `test_affix_count_at_least_rarity_min` asserts.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_gear_generator.py -v`
Expected: PASS (6 passed).

- [ ] **Step 5: Commit**

```bash
git add app/loot/generator.py tests/test_gear_generator.py
git commit -m "feat(gear): procedural item generator (archetype+rarity+affixes)"
```

---

## Phase 3 — Item instances & stat application

### Task 3.1: `gear_bonuses` helper

**Files:**
- Create: `app/loot/equip.py`
- Test: `tests/test_gear_equip.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_gear_equip.py
from app.loot.equip import gear_bonuses


def test_sums_equipped_affixes():
    gear = {
        "weapon": {"slot": "weapon", "affixes": [{"stat": "damage", "val": 4}, {"stat": "dex", "val": 8}]},
        "amulet": {"slot": "amulet", "affixes": [{"stat": "dex", "val": 3}, {"stat": "con", "val": 5}]},
    }
    b = gear_bonuses(gear)
    assert b["dex"] == 11
    assert b["damage"] == 4
    assert b["con"] == 5


def test_empty_gear():
    assert gear_bonuses({}) == {}
    assert gear_bonuses(None) == {}


def test_ignores_malformed_entries():
    gear = {"weapon": "not-a-dict", "head": {"affixes": "bad"}}
    assert gear_bonuses(gear) == {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_gear_equip.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implement the helper**

```python
# app/loot/equip.py
"""Aggregate equipped item-instance affixes into a stat-bonus dict."""

from __future__ import annotations


def gear_bonuses(gear: dict | None) -> dict:
    """Sum affix values across all equipped instances -> {stat: total}."""
    totals: dict[str, float] = {}
    if not isinstance(gear, dict):
        return totals
    for inst in gear.values():
        if not isinstance(inst, dict):
            continue
        affixes = inst.get("affixes")
        if not isinstance(affixes, list):
            continue
        for a in affixes:
            if not isinstance(a, dict):
                continue
            stat = a.get("stat")
            val = a.get("val")
            if not stat or not isinstance(val, (int, float)):
                continue
            totals[stat] = totals.get(stat, 0) + val
    # normalize ints
    return {k: (int(v) if float(v).is_integer() else v) for k, v in totals.items()}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_gear_equip.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add app/loot/equip.py tests/test_gear_equip.py
git commit -m "feat(gear): gear_bonuses stat aggregation helper"
```

---

### Task 3.2: Wire gear bonuses into combat stat derivation

**Files:**
- Modify: `app/services/combat_service.py` (`_derive_stats`, ~lines 64-154)
- Test: `tests/test_gear_combat_integration.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_gear_combat_integration.py
import json
from app import db
from app.models.models import Character, User
from app.services.combat_service import _derive_stats


def test_equipped_dex_raises_derived_dex(test_app):
    with test_app.app_context():
        u = User.query.filter_by(username="geartester").first()
        if not u:
            u = User(username="geartester", password="x")
            db.session.add(u); db.session.commit()
        gear = {"weapon": {"slot": "weapon", "affixes": [{"stat": "dex", "val": 10}]}}
        c = Character(user_id=u.id, name="GearHero",
                      stats=json.dumps({"str": 10, "dex": 10, "int": 10, "con": 10}),
                      gear=json.dumps(gear), items="[]")
        db.session.add(c); db.session.commit()
        derived = _derive_stats(c)
        assert derived["dex_stat"] == 20  # 10 base + 10 from gear
```

- [ ] **Step 2: Run test to verify it fails**

Run: `DATABASE_URL=postgresql://adventure:changeme@localhost:5434/adventure_test .venv/bin/python -m pytest tests/test_gear_combat_integration.py -v`
Expected: FAIL (`dex_stat == 10`, gear ignored).

- [ ] **Step 3: Apply gear bonuses inside `_derive_stats`**

In `app/services/combat_service.py::_derive_stats`, after the base `STR/DEX/INT/CON/WIS/CHA` are parsed (right after line ~81 where `CHA` is set), insert gear aggregation and fold attribute bonuses into the attribute values BEFORE derived stats (`max_hp`, `attack`, etc.) are computed:

```python
    # Fold equipped gear affixes into attributes + derived stats.
    from app.loot.equip import gear_bonuses
    try:
        _gear = json.loads(char.gear) if getattr(char, "gear", None) else {}
    except Exception:
        _gear = {}
    _gb = gear_bonuses(_gear)
    STR += int(_gb.get("str", 0))
    DEX += int(_gb.get("dex", 0))
    INT += int(_gb.get("int", 0))
    CON += int(_gb.get("con", 0))
    WIS += int(_gb.get("wis", 0))
    CHA += int(_gb.get("cha", 0))
```

Then, after the derived stats are computed (after line ~86 `mana_max = ...`), add the derived-stat gear bonuses:

```python
    max_hp += int(_gb.get("max_hp", 0))
    attack += int(_gb.get("damage", 0))
    defense += int(_gb.get("armor", 0))
    speed += int(_gb.get("speed", 0))
    mana_max += int(_gb.get("mana", 0))
```

(Keep the existing `hp`/`mana` clamps after these adjustments so current HP can't exceed the new max.)

- [ ] **Step 4: Run test to verify it passes**

Run: `DATABASE_URL=postgresql://adventure:changeme@localhost:5434/adventure_test .venv/bin/python -m pytest tests/test_gear_combat_integration.py -v`
Expected: PASS.

- [ ] **Step 5: Run the combat suite for regressions**

Run: `DATABASE_URL=postgresql://adventure:changeme@localhost:5434/adventure_test .venv/bin/python -m pytest tests/test_combat_actions.py tests/test_combat_service.py -q`
Expected: PASS (no regressions).

- [ ] **Step 6: Commit**

```bash
git add app/services/combat_service.py tests/test_gear_combat_integration.py
git commit -m "feat(gear): equipped affixes modify combat-derived stats"
```

---

### Task 3.3: Surface gear bonuses in the dashboard party payload

**Files:**
- Modify: `app/routes/dashboard_helpers.py` (`build_party_payload`, ~lines 196-232)
- Test: `tests/test_gear_party_payload.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_gear_party_payload.py
import json
from app.routes.dashboard_helpers import build_party_payload


class _C:
    def __init__(self, stats, gear):
        self.id = 1; self.name = "P"; self.level = 1
        self.stats = json.dumps(stats); self.gear = json.dumps(gear)


def test_payload_reflects_gear_hp(test_app):
    with test_app.app_context():
        c = _C({"con": 10, "int": 10}, {"chest": {"slot": "chest", "affixes": [{"stat": "max_hp", "val": 25}]}})
        payload = build_party_payload([c])
        # base hp_max = 50 + con*2 + level*5 = 50+20+5 = 75; +25 gear = 100
        assert payload[0]["hp_max"] == 100
```

- [ ] **Step 2: Run test to verify it fails**

Run: `DATABASE_URL=postgresql://adventure:changeme@localhost:5434/adventure_test .venv/bin/python -m pytest tests/test_gear_party_payload.py -v`
Expected: FAIL (`hp_max == 75`).

- [ ] **Step 3: Fold gear bonuses into `build_party_payload`**

In `app/routes/dashboard_helpers.py::build_party_payload`, after `hp_max` and `mana_max` are computed and `con`/`intelligence` parsed, add:

```python
        from app.loot.equip import gear_bonuses
        try:
            gear = json.loads(c.gear) if getattr(c, "gear", None) else {}
        except Exception:
            gear = {}
        gb = gear_bonuses(gear)
        hp_max += int(gb.get("max_hp", 0)) + int(gb.get("con", 0)) * 2
        mana_max += int(gb.get("mana", 0)) + int(gb.get("int", 0)) * 2
```

(Place this before the `party.append(...)` dict is built so the adjusted `hp_max`/`mana_max` are used.)

- [ ] **Step 4: Run test to verify it passes**

Run: `DATABASE_URL=postgresql://adventure:changeme@localhost:5434/adventure_test .venv/bin/python -m pytest tests/test_gear_party_payload.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/routes/dashboard_helpers.py tests/test_gear_party_payload.py
git commit -m "feat(gear): dashboard party payload reflects equipped gear"
```

---

## Phase 4 — Loot integration & equip API

### Task 4.1: `roll_loot` emits item instances

**Files:**
- Modify: `app/services/loot_service.py` (`roll_loot`, ~lines 77-160)
- Test: `tests/test_loot_instances.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_loot_instances.py
import random
from app.services.loot_service import roll_loot


def _monster(level=5, boss=False):
    return {"slug": "m", "name": "M", "level": level, "boss": boss,
            "loot_table": "", "special_drop_slug": None}


def test_roll_loot_includes_generated_gear():
    out = roll_loot(_monster(level=8), rng=random.Random(1))
    gear = out.get("gear", [])
    assert isinstance(gear, list)
    assert gear and all("affixes" in g and "slot" in g for g in gear)


def test_boss_skews_higher_rarity():
    from app.loot.data.rarities import RARITY_ORDER
    idx = {r: i for i, r in enumerate(RARITY_ORDER)}
    boss_max = 0
    for s in range(30):
        out = roll_loot(_monster(level=15, boss=True), rng=random.Random(s))
        for g in out.get("gear", []):
            boss_max = max(boss_max, idx[g["rarity"]])
    assert boss_max >= idx["rare"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `DATABASE_URL=postgresql://adventure:changeme@localhost:5434/adventure_test .venv/bin/python -m pytest tests/test_loot_instances.py -v`
Expected: FAIL (no `gear` key).

- [ ] **Step 3: Add gear generation to `roll_loot`**

In `app/services/loot_service.py::roll_loot`, before the final `return`, generate gear instances and add them to the result dict (keep existing `items`/`items_list` for consumables):

```python
    # Procedural gear drops (instances with affixes).
    from app.loot.generator import generate_item
    level = int(monster.get("level", 1) or 1)
    n_gear = 1
    rarity_hint = None
    if is_boss:
        n_gear = 2
        rarity_hint = rng.choice(["rare", "epic", "legendary"])
    gear_drops = [generate_item(level=level, rarity=rarity_hint, rng=rng) for _ in range(n_gear)]
```

Then change the return to include it:

```python
    return {"items": qty_map, "items_list": drops, "gear": gear_drops, "rolls": rolls_meta}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `DATABASE_URL=postgresql://adventure:changeme@localhost:5434/adventure_test .venv/bin/python -m pytest tests/test_loot_instances.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Run existing loot tests for regressions**

Run: `DATABASE_URL=postgresql://adventure:changeme@localhost:5434/adventure_test .venv/bin/python -m pytest tests/test_loot_generation.py tests/test_encounter_config.py -q`
Expected: PASS (existing keys `items`/`items_list` unchanged).

- [ ] **Step 6: Commit**

```bash
git add app/services/loot_service.py tests/test_loot_instances.py
git commit -m "feat(gear): roll_loot emits procedural gear instances"
```

---

### Task 4.2: Store gear instances into inventory on claim/reward

**Files:**
- Modify: `app/dungeon/api_helpers/treasure.py` (`claim_treasure_entity`, the loot-roll/store section)
- Modify: `app/services/combat_service.py` (reward-grant section, ~lines 574-590)
- Test: `tests/test_gear_reward_storage.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_gear_reward_storage.py
import json
from app.loot.inventory import add_gear_to_character


class _Char:
    def __init__(self): self.items = "[]"


def test_add_gear_appends_instance():
    c = _Char()
    inst = {"uid": "abc", "slot": "weapon", "name": "Brutal Shortsword", "affixes": []}
    add_gear_to_character(c, [inst])
    items = json.loads(c.items)
    assert any(isinstance(i, dict) and i.get("uid") == "abc" for i in items)


def test_add_gear_preserves_existing_consumables():
    c = _Char(); c.items = json.dumps([{"slug": "potion-healing", "qty": 2}])
    add_gear_to_character(c, [{"uid": "z", "slot": "ring", "affixes": []}])
    items = json.loads(c.items)
    assert any(i.get("slug") == "potion-healing" for i in items)
    assert any(i.get("uid") == "z" for i in items)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_gear_reward_storage.py -v`
Expected: FAIL (`ModuleNotFoundError: app.loot.inventory`).

- [ ] **Step 3: Implement the inventory helper and wire it in**

Create `app/loot/inventory.py`:

```python
# app/loot/inventory.py
"""Helpers to merge generated gear instances into a character's JSON inventory."""

from __future__ import annotations

import json


def add_gear_to_character(character, instances: list[dict]) -> None:
    """Append gear instances to character.items (JSON list), preserving existing."""
    try:
        items = json.loads(character.items) if character.items else []
        if not isinstance(items, list):
            items = []
    except Exception:
        items = []
    for inst in instances or []:
        if isinstance(inst, dict) and inst.get("uid"):
            items.append(inst)
    character.items = json.dumps(items)
```

Then call `add_gear_to_character(char, loot.get("gear", []))` in both reward paths:
- `app/dungeon/api_helpers/treasure.py` where `roll_loot`/loot items are granted, and
- `app/services/combat_service.py` reward section (~line 574) where `rewards.get("items")` is added to the first character's inventory.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_gear_reward_storage.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add app/loot/inventory.py app/dungeon/api_helpers/treasure.py app/services/combat_service.py tests/test_gear_reward_storage.py
git commit -m "feat(gear): store generated gear instances in inventory on reward/claim"
```

---

### Task 4.3: Equip / unequip API for the 8 slots

**Files:**
- Modify: `app/routes/inventory_api.py` (add equip/unequip endpoints)
- Test: `tests/test_gear_equip_api.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_gear_equip_api.py
import json
from app import db
from app.models.models import Character, User


def _login(client, app):
    with app.app_context():
        u = User.query.filter_by(username="equipper").first()
        if not u:
            u = User(username="equipper", password="x"); db.session.add(u); db.session.commit()
        inst = {"uid": "sword1", "slot": "weapon", "name": "Brutal Shortsword", "rarity": "rare", "affixes": [{"stat": "dex", "val": 5}]}
        c = Character.query.filter_by(user_id=u.id).first()
        if not c:
            c = Character(user_id=u.id, name="EQ", stats='{"dex":10}', gear="{}", items=json.dumps([inst]))
            db.session.add(c); db.session.commit()
        cid = c.id; uid = u.id
    with client.session_transaction() as s:
        s["user_id"] = uid; s["_user_id"] = str(uid)
    return cid


def test_equip_moves_instance_from_items_to_gear(client, test_app):
    cid = _login(client, test_app)
    r = client.post("/api/characters/%d/equip" % cid, json={"uid": "sword1"})
    assert r.status_code == 200, r.get_json()
    with test_app.app_context():
        c = db.session.get(Character, cid)
        gear = json.loads(c.gear); items = json.loads(c.items)
        assert gear["weapon"]["uid"] == "sword1"
        assert all(i.get("uid") != "sword1" for i in items if isinstance(i, dict))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `DATABASE_URL=postgresql://adventure:changeme@localhost:5434/adventure_test .venv/bin/python -m pytest tests/test_gear_equip_api.py -v`
Expected: FAIL (404, endpoint missing).

- [ ] **Step 3: Implement equip/unequip endpoints**

In `app/routes/inventory_api.py`, add (using the existing blueprint object in that file — confirm its name with `grep -n "Blueprint" app/routes/inventory_api.py`):

```python
@bp_inventory.route("/api/characters/<int:char_id>/equip", methods=["POST"])
@login_required
def equip_item(char_id: int):
    from app.loot.data.archetypes import SLOTS
    char = db.session.get(Character, char_id)
    if not char or char.user_id != current_user.id:
        return jsonify({"error": "not_found"}), 404
    uid = (request.get_json(silent=True) or {}).get("uid")
    items = json.loads(char.items) if char.items else []
    gear = json.loads(char.gear) if char.gear else {}
    inst = next((i for i in items if isinstance(i, dict) and i.get("uid") == uid), None)
    if not inst:
        return jsonify({"error": "not_in_inventory"}), 400
    slot = inst.get("slot")
    if slot not in SLOTS:
        return jsonify({"error": "bad_slot"}), 400
    # swap any currently-equipped item in that slot back into items
    if gear.get(slot):
        items.append(gear[slot])
    gear[slot] = inst
    items = [i for i in items if not (isinstance(i, dict) and i.get("uid") == uid)]
    char.gear = json.dumps(gear); char.items = json.dumps(items)
    db.session.commit()
    return jsonify({"ok": True, "slot": slot, "gear": gear})


@bp_inventory.route("/api/characters/<int:char_id>/unequip", methods=["POST"])
@login_required
def unequip_item(char_id: int):
    char = db.session.get(Character, char_id)
    if not char or char.user_id != current_user.id:
        return jsonify({"error": "not_found"}), 404
    slot = (request.get_json(silent=True) or {}).get("slot")
    gear = json.loads(char.gear) if char.gear else {}
    items = json.loads(char.items) if char.items else []
    if gear.get(slot):
        items.append(gear.pop(slot))
        char.gear = json.dumps(gear); char.items = json.dumps(items)
        db.session.commit()
    return jsonify({"ok": True, "gear": gear})
```

Ensure `request`, `jsonify`, `current_user`, `login_required`, `db`, `json`, and `Character` are imported in the file (add missing imports).

- [ ] **Step 4: Run test to verify it passes**

Run: `DATABASE_URL=postgresql://adventure:changeme@localhost:5434/adventure_test .venv/bin/python -m pytest tests/test_gear_equip_api.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/routes/inventory_api.py tests/test_gear_equip_api.py
git commit -m "feat(gear): equip/unequip API for the 8 gear slots"
```

---

### Task 4.4: Retire the dormant DB-backed affix system (spec §6)

**Files:**
- Delete: `app/loot/affix_generator.py`, `app/models/affix.py`, `sql/procedural_affixes_seed.sql`
- Modify: `app/models/__init__.py` (drop `ProceduralAffix`/`ItemAffix` exports), `app/seed_items.py` (drop `AFFIX_FILES` + its load loop), `app/routes/loot_api.py` (remove or repoint references)

- [ ] **Step 1: Inventory the references**

Run: `grep -rn "affix_generator\|ProceduralAffix\|ItemAffix\|procedural_affixes_seed\|AFFIX_FILES" app/ tests/`
Expected: references in the files listed above. Read `app/routes/loot_api.py` to see how it uses them.

- [ ] **Step 2: Decide loot_api disposition**

If `loot_api.py` endpoints are unused by the frontend (`grep -rn "loot_api\|/api/loot" app/static app/templates`), remove the dead endpoints. If still referenced, repoint them at `app/loot/generator.py::generate_item` (return instances) and drop the `ItemAffix` usage.

- [ ] **Step 3: Delete the dead modules and clean exports**

```bash
git rm app/loot/affix_generator.py app/models/affix.py sql/procedural_affixes_seed.sql
```
Remove `ProceduralAffix`/`ItemAffix` from `app/models/__init__.py`, and remove `AFFIX_FILES` (and its load loop) from `app/seed_items.py`.

- [ ] **Step 4: Verify nothing imports the removed code**

Run: `grep -rn "affix_generator\|ProceduralAffix\|ItemAffix\|procedural_affixes_seed\|AFFIX_FILES" app/ tests/`
Expected: no matches.

- [ ] **Step 5: Run the full suite**

Run: `DATABASE_URL=postgresql://adventure:changeme@localhost:5434/adventure_test .venv/bin/python -m pytest -q`
Expected: green (no import errors from the removal).

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "chore(gear): retire dormant DB-backed affix system (superseded by code-defined generator)"
```

---

## Phase 5 — UI (light touch)

### Task 5.1: Rarity colors + affix tooltips in inventory

**Files:**
- Modify: `app/static/js/inventory*.js` or the dashboard inventory renderer (locate with `grep -rln "inventory" app/static/js`)
- Modify: relevant CSS (`app/static/css/`) for rarity color classes
- Test: manual (UI)

- [ ] **Step 1: Add rarity color classes**

Add CSS classes matching `app/loot/data/rarities.py` colors:
`.rarity-common{color:#9d9d9d}.rarity-uncommon{color:#1eff00}.rarity-rare{color:#0070dd}.rarity-epic{color:#a335ee}.rarity-legendary{color:#ff8000}.rarity-mythic{color:#e6cc80}`

- [ ] **Step 2: Render instance items with color + affix tooltip**

In the inventory renderer, when an item is an instance (`item.affixes` present), render `item.name` with class `rarity-<item.rarity>` and a tooltip listing each affix as `+val stat` (e.g., "+8 DEX, +5 CON"). Stackable consumables (with `slug`/`qty`) keep their existing rendering.

- [ ] **Step 3: Verify in the running app**

Launch the server (see `docs/TESTING.md` / `scripts/bootstrap_db.sh`), log in, claim a treasure or win a fight, open inventory, confirm colored names + tooltips.

- [ ] **Step 4: Commit**

```bash
git add app/static/js app/static/css
git commit -m "feat(gear-ui): rarity colors and affix tooltips in inventory"
```

---

### Task 5.2: 8-slot equip UI (paper doll)

**Files:**
- Modify: dashboard/character template + JS (locate equip UI with `grep -rln "gear\|equip" app/templates app/static/js`)
- Test: manual (UI)

- [ ] **Step 1: Render 8 equip slots**

Show the 8 slots (Weapon, Offhand, Head, Chest, Hands, Feet, Ring, Amulet) for the selected character, each showing the equipped instance (colored by rarity) or empty.

- [ ] **Step 2: Wire equip/unequip buttons to the API**

Inventory instances get an "Equip" action calling `POST /api/characters/<id>/equip {uid}`; equipped slots get "Unequip" calling `POST /api/characters/<id>/unequip {slot}`. Refresh party stats after (HP/mana reflect gear via Task 3.3).

- [ ] **Step 3: Verify in the running app**

Equip an "of the Hawk" weapon; confirm the slot fills, the name is colored, and the character's derived stats/HP update.

- [ ] **Step 4: Commit**

```bash
git add app/templates app/static/js
git commit -m "feat(gear-ui): 8-slot equipment paper doll"
```

---

## Final verification

- [ ] **Run the full suite on Postgres**

Run: `DATABASE_URL=postgresql://adventure:changeme@localhost:5434/adventure_test .venv/bin/python -m pytest -q`
Expected: all green (prior 261 baseline + new gear tests).

- [ ] **Playtest**

Bootstrap a fresh DB, launch the server, run an adventure: confirm drops have composed names + rarities, equipping changes combat outcomes, and the loop is fun.

- [ ] **Finish the branch**

Use `superpowers:finishing-a-development-branch` to merge `gear-system` → `main`.
