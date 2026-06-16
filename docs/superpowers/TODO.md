# Adventure — Remaining Work (handoff TODO)

A running list of what's left on **Path A** (the soft-extraction looter loop) plus known
issues. Specs live in `docs/superpowers/specs/`. Suggested workflow per item: read the
spec → write an implementation plan (TDD, small tasks) → implement → verify → merge.

## Done so far
- **Spec 1 — Economy foundation** ✅ merged: copper-based currency w/ 3-tier display,
  trading bug fixes, programmatic merchant seeding (`run.py seed-merchants`).
- **Spec 2 — Extraction economy & the Hoard** ✅ merged: per-user `Hoard` (persistent
  gear + copper), at-risk run-purse (`Character.gold`), death/wipe permadeath wired into
  combat, extract pools haul → hoard, loot-the-body, trading repointed to hoard w/ auth.
- **Spec 3 — Procedural floor loot** ✅ merged: `DungeonLoot` holds gear instances,
  config-driven `procedural_gear_chance` + rarity weights (deterministic), claim into bag.

## Remaining

### Spec 4 — Durability, Repair & UI  (`specs/2026-06-16-durability-repair-ui-design.md`)
- [ ] **4a Durability (backend):** add `durability`/`max_durability` to generated gear;
      gentle config-driven loss per fight; broken = reduced (not destroyed) bonuses;
      `POST /api/trade/repair` paid from the hoard. Tests.
- [ ] **4b UI:** inventory/equipment panel (affixes, durability bar, encumbrance bar),
      hoard/stash screen, vendor screen (buy/sell/repair, 3-tier currency), run/extraction
      surface (floor-loot pickup, extraction, loot-body). Brainstorm 4b with the visual
      companion; verify via the `run`/`verify` skills.

### Spec 5 — Character progression  (`specs/2026-06-16-progression-design.md`)
- [x] **5a XP + levels** ✅ (this session): `app/services/progression.py`
      (`level_for_xp`, `grant_xp` → levels + talent points, canonical xp curve). Combat
      kills and extraction now award XP through it; combat's old divergent quadratic curve
      removed. Tests: `tests/test_progression.py`.
      - [ ] Still TODO: gate `inventory_api.level_up_character` to *earned* levels (needs a
            stat-point ledger — currently allocations aren't bounded by earned points).
- [~] **5b Skills/spells:** the endpoints already existed (`app/routes/skill_api.py`:
      unlock/use/grant/reset). This session **secured them**: unlock/use/reset are now
      `@login_required` + owner-checked; `grant_talent_points` is admin-only (was an
      unlimited-point cheat). Tests: `tests/test_skill_unlock.py`. Still TODO:
      - [ ] Seed starter `SkillTree`/`Skill` rows (idempotent seeder + `run.py` command).
      - [ ] Apply passive `effect_json` to derived combat stats (fold into
            `app/loot/equip.py` aggregation); wire active skills as combat actions.
- [ ] **5c Progression UI:** character sheet (level/XP bar, stat allocation, skill tree).

## Known issues / cleanup (not blockers)
- [ ] **Test-DB targeting quirk:** `tests/conftest.py` imports `app` before setting
      `DATABASE_URL`, so pytest can hit the **dev** DB. Until fixed, always run with BOTH:
      `DATABASE_URL=...adventure_test TEST_DATABASE_URL=...adventure_test .venv/bin/pytest`.
      Proper fix: set `os.environ["DATABASE_URL"]` before `from app import ...` in conftest.
- [ ] **Flaky tests (pre-existing, not from Path A):**
      - `tests/test_combat_persistence.py` — ~50% failure even alone; a race in the combat
        engine's background turn advancement. Needs a combat-scheduler fix.
      - `tests/test_encounter_config.py` — fails only under shared-session DB contamination
        (passes alone). Symptom of the suite lacking per-test DB isolation.
- [ ] **Test isolation generally:** the suite reuses one session DB (only
      `@pytest.mark.db_isolation` tests reset). New tests should use unique usernames
      (uuid) and unique seeds to avoid accumulation. A global per-test rollback/reset would
      remove a whole class of flakiness.
- [ ] **Tracked bytecode:** `app/__pycache__/__init__.cpython-312.pyc` is committed and
      keeps showing as dirty. Add `__pycache__/` to `.gitignore` and `git rm --cached` it.
- [ ] **loot-body has no same-run guard** (`app/routes/hoard_api.py`): transfers a downed
      ally's bag to any owned character. Enforcing "same run" needs a notion of which run a
      *living* character is in (only downed characters get `locked_dungeon_id`).
- [ ] **Combat instance resolution** uses "most recent DungeonInstance for the user"
      (`combat_service._current_instance_for_user`) — fragile with multiple instances.
- [ ] **Migrations vs dev DB:** the dev `adventure` DB is in a `create_all` state, so
      `alembic upgrade` fails on older migrations. Stamp/realign before relying on
      migrations in dev (`alembic stamp head` after a clean `create_all`, or rebuild).

## How to run the suite
```bash
export DATABASE_URL=postgresql://adventure:changeme@localhost:5433/adventure_test
export TEST_DATABASE_URL=$DATABASE_URL
# fresh schema (mimics CI):
.venv/bin/python -c "from app import create_app, db; app=create_app()
with app.app_context():
    db.drop_all(); db.create_all()"
.venv/bin/python -m pytest tests/ -q --deselect tests/test_combat_persistence.py
```
