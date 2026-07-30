# Combat Phase 1: Multi-Enemy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Combat fields 1–6 monsters instead of exactly one — model, initiative, targeting and screen — so the playtest complaints "its not fun fighting 1 mob at a time" and "4v1 isn't fun" stop being structural. No grid, no zoom; those are phases 2 and 3.

**Spec:** [specs/2026-07-28-tactical-combat-design.md](../specs/2026-07-28-tactical-combat-design.md) — read its "What has to change in the model" and "Phasing" sections first.

**Tech Stack:** Flask, SQLAlchemy, Alembic, vanilla JS, pytest, Playwright.

## Architecture

`monsters_json` becomes the source of truth: a JSON list, one entry per monster,
each an ordinary spawn payload plus three keys — `id` (session-local, stable),
`hp` (current), `hp_max`.

**`monster_json` and `monster_hp` stay real columns.** The spec asks for them as
"read-only accessors over the first entry"; this plan keeps them as columns and
denormalises `monsters[0]` into them from one writer instead. Same guarantee for
readers, without the hazard: `combat_service` *assigns* to those two attributes
in twelve places, several inside `except Exception: logger.debug(...)` blocks, so
converting them to properties first would turn those writes into **silently
swallowed** AttributeErrors.

**Initiative tombstones, it does not filter.** `active_index` is a persisted
column, echoed to the client and used as the turn-ownership key in three server
paths. Removing entries would change what a stale index means, so every
in-flight request would resolve to a different actor, and every HP-write path
would need a before/at/after/wrap fixup. Dead monsters stay in the list and are
skipped by the loop that already skips downed players — one extra predicate. It
also gives the screen the greyed-out corpses the spec wants.

## Global Constraints

- **Every alembic revision guards its DDL with an inspector check.** Startup runs
  `create_all` before `alembic upgrade`, and `db_isolation` tests rebuild the
  schema mid-suite; an unguarded `ADD COLUMN` blocks on other connections' locks
  and hangs the suite at 10+ minutes. Copy
  `migrations/versions/c8f1a2b3d4e5_add_mana_cost_to_skill.py`.
- **No data migration.** The `_monsters()` accessor backfills in Python from the
  legacy pair when `monsters_json` is NULL, which also covers sessions live at
  deploy time.
- **Legacy initiative entries carry `"id": None`** — `monster.get("id")` has
  always been None there. Every id comparison must read None as 0, or combats
  in flight at deploy hang forever on a monster turn nobody can drive.
- **The default encounter stays ONE monster** until Task 14. About a dozen test
  files feed a finite `iter([...])` to `random.randint` and depend on the exact
  roll ordering; `_calc_initiative` spends one roll per combatant, so raising
  pack size early turns them all red at once for unrelated reasons.
- **Bounded loops only.** Never `while True` in turn advancement — a monster path
  that fails to advance becomes an infinite HTTP request.
- **Exactly one loot representation is consumed.** `roll_loot` returns drops
  under both `items` and `items_list`; `_check_end`'s `if/elif` chain depends on
  only one branch running. A merge must not synthesise `items` from an
  `items_list`-only roll, or the fallback branch goes unreachable again.

## Tasks

### Task 1: the column and its migration
- [x] Add `monsters_json = db.Column(db.Text, nullable=True)` to `CombatSession`.
- [x] New revision, `down_revision = "c9405725c1f4"` (current head), inspector-guarded.
- [x] Apply once solo against the test DB before running the suite.

### Task 2: accessors, no behaviour change
- [x] `_monsters(session)` — parse `monsters_json`; when absent, return
      `[{**session.monster(), "id": 0, "hp": session.monster_hp, "hp_max": session.monster().get("hp")}]`.
- [x] `_monster_ref(monsters, mid)` — look up **by id, never by list position**.
- [x] `_save_monsters(session, monsters)` — write `monsters_json` and mirror
      `monsters[0]` into `monster_json`/`monster_hp`.
- [x] Suite stays green: this lands as pure addition.

### Task 3: mint ids at session start
- [x] `start_session` normalises its argument to a list (a bare dict still works —
      51 test call sites and `encounters.py` pass one).
- [x] Assign `id = 0..n-1` once, never reused or compacted; set `hp_max`.

### Task 4: initiative over every combatant
- [x] `_calc_initiative(party, monsters)` appends one entry per monster carrying
      its `id`. Keep accepting a bare dict for one release.

### Task 5: who is acting
- [x] `_active_actor(session)` (range-guarded) and `_active_monster(session)`
      (matches the active entry's id, reading None as 0).
- [x] `_is_monster_turn` keeps its name — three production and four test callers
      only want the bool.

### Task 6: step over corpses
- [x] `_dead_monster_ids(session)` beside `_downed_player_ids`.
- [x] Generalise the **existing** skip loop in `_advance_turn` — one predicate,
      not a second loop. `for _ in range(len(initiative))` stays: it means "at
      most one lap" and is still exactly right.

### Task 7: the re-entry guard (fixes a live bug)
- [x] `_check_end` returns immediately unless `session.status == "active"`.
      Today neither `end_turn` endpoint refuses a completed session, and after a
      win `active_index` has already moved onto a player of the same user — so a
      second `end_turn` re-enters `_check_end` with HP still 0 and **re-rolls and
      re-grants the loot**. Independent of multi-enemy; pin it with a test.

### Task 8: win when all are dead
- [x] `monsters and all(hp <= 0)`. The `monsters and` is required — an empty list
      must never read as "all dead".

### Task 9: loot, XP and kills across the pack
- [x] Roll per monster, merge into one rewards dict before the existing grant
      block; leave the `if/elif` grant untouched. Call the module-global
      `roll_loot(m)` positionally so existing monkeypatches keep working.
- [x] XP is the sum across monsters, then split across members.
- [x] Kill tracking loops per corpse; hoist the "all bosses defeated" unlock
      **out** of the loop or it fires once per boss.
- [x] Death lines move to where HP actually reaches 0, so the player is told
      mid-fight instead of getting four deaths at once at the end.

### Task 10: monsters act as themselves
- [x] `monster_auto_turn` takes the acting monster from `_active_monster`, and
      every write-back goes through `_save_monsters`.
- [x] `last_turn` becomes per-monster — left shared, one monster acting puts the
      whole pack on cooldown and the fight goes quiet.

### Task 11: consecutive monster turns
- [x] `_auto_progress_monster_after_player` loops while it is a monster's turn,
      bounded by `len(initiative)`. Today it runs exactly one, so two adjacent
      monsters leave the client waiting on a turn nobody drives.

### Task 12: targeting
- [x] Offensive player actions take a `target_id`; default to the first living
      monster when omitted, so existing callers and tests keep working.
- [x] Validate: exists, alive, belongs to this session.
- [x] `combat_api` payloads carry it, keeping the `version` optimistic lock.

### Task 13: the screen
- [x] `to_dict` emits a `monsters` list, keeping `monster`/`monster_hp`/
      `monster_max_hp` as the first entry.
- [x] The combat screen lists enemies with name + HP bar, one selected as target,
      corpses greyed. Follow the combat item panel's shape — it is the sibling
      component. Mind that `combat.html` loads `glass-theme.css` in `{% block head %}`,
      a documented wart that has broken class colours on this screen before.

### Task 14: let packs be packs
- [x] The encounter path gathers the monsters adjacent to the trigger and passes
      the whole pack, deleting every one of them from the map.
- [x] **Switched off by default.** `SpawnConfig.combat_pack_max` ships at 1, so
      play is unchanged. Turning it on is a one-line change and a **balance**
      decision, not an engine one: at 3, `tests/test_full_run_e2e.py` wipes the
      party partway through a run. Every monster is costed for a solo
      appearance, there are still no monsters above level 20, and the catalogue
      is 225/229 common, so the party cannot gear into it either. This belongs
      with the tuning verdicts waiting on a playtest.

## Verification

- Full suite green at every task boundary, not just at the end.
- New tests: dead-monster skip; full termination (all players down, all monsters
  dead) does not spin; `monster_auto_turn` acts as the *active* monster, not
  `monsters[0]`; per-monster cooldown; `_check_end` twice grants once; win only
  when all dead; XP summed; two monsters dropping the same slug grant qty 2; an
  `items_list`-only roll still falls back; and a hand-built **legacy** session
  (`monsters_json` NULL, initiative id None) still advances and still lets the
  monster act.
- E2E: extend the existing combat seeding helper to a two-monster session.
