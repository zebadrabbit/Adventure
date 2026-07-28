# Adventure — Open work

Only open items live here. The full completed history (Specs 1–5, the UI
redesign phases, the test-isolation saga, the 2026-07 maintenance passes)
moved to [TODO_ARCHIVE.md](TODO_ARCHIVE.md). The 2026-07-27 repo audit that
drove the `repo-health` branch is at
[plans/2026-07-27-repo-health-review.md](plans/2026-07-27-repo-health-review.md).

## Playtest 2026-07-27 (seed 733064)
Full triage with code pointers:
[plans/2026-07-27-playtest-triage.md](plans/2026-07-27-playtest-triage.md).
- [x] ~~Monsters focused one character~~ — weighted target picker.
- [x] ~~Downed characters still took a turn~~ — `_advance_turn` steps over them.
- [x] ~~Dead characters stuck in the roster and auto-added to parties~~ —
      delete was FK-blocked by 10 no-cascade tables; party formation took
      "first four by id" which after a wipe is the corpses.
- [ ] Party Stash button is a `coming soon` alert.
- [ ] **Item usage in combat** — the service knows 3 hardcoded slugs and the
      UI offers 2 buttons, against 154 potions in the catalogue, so looted
      potions cannot be used in a fight (`potion-regen` is implemented but
      has no button at all). Spec:
      [specs/2026-07-28-combat-item-usage-design.md](specs/2026-07-28-combat-item-usage-design.md).
- [x] ~~Camping is unlimited~~ — costs a campfire kit, 40-tick cooldown, 25%
      ambush; also stopped clamping healthy characters down to 100 HP.
- [x] ~~Floor difficulty rubber-bands to party level~~ — anchored at run start,
      `floor_level_step` per floor (`GameConfig["difficulty"]`).
- [x] ~~Monster `loot_table` values resolve to nothing~~ — named tables now
      resolve through `app/loot/tables.py` (tier from the name suffix, filtered
      by type/rarity/level, separated by value percentile).
- [x] ~~Monster catalogue stops at level 20~~ — *mitigated*: spawns above the
      ceiling clamp to the deepest band instead of degrading to nameless
      stubs. The content gap (no monsters for levels 21-50) is still open.
- [ ] Author monsters for levels 21-50, and give the item catalogue some
      rarity spread: it is currently 225/229 common, almost all level 0-2,
      so loot tiers can only be separated by price.
- [x] ~~Audit spell/skill damage vs plain attack~~ — confirmed: spells scaled
      with INT but not level, skills with nothing; the party snapshot never
      carried `level`. Fixed via `_spell_power`; re-measure with
      `scripts/audit_combat_damage.py`.
- [ ] Maze too spiralling: tune `dead_end_keep` / `extra_connection_chance` /
      `straight_max`.
- [ ] Map readability: wall/floor contrast, props, coordinate + floor readout.
- [ ] Adventure UX: log window too restrictive for looting, static character
      panels, D&D lingo throughout.
- [ ] **Combat overhaul** — designed: combat is its own screen and zooms into the
      map tile the party occupies, 4 vs 1-6 on a grid. Phased in
      [specs/2026-07-28-tactical-combat-design.md](specs/2026-07-28-tactical-combat-design.md);
      phase 1 (multi-enemy, no grid) is the biggest win and unblocks raising
      `SpawnConfig.group_size_max` above its current cap of 3.
- [ ] **Adventure HUD** — full-bleed map, no navbar, account anchor top-right,
      party frames left, floating log, no movement pad:
      [specs/2026-07-28-adventure-hud-layout-design.md](specs/2026-07-28-adventure-hud-layout-design.md).

## Gameplay — waiting on playtest verdicts
- [ ] Tune `EVENT_TUNING` (app/dungeon/room_events.py): shrine/trap/ambush
      counts, trap damage/DC, ambush pack size, respawn interval/cap.
- [ ] Mana economy: skill costs 4/8/12 vs mana potion +5 — potion likely
      wants a buff now that casting drains.
- [ ] Spawn density / `aggro_radius` play-feel tuning.
- [ ] Combat-screen visual redesign (deliberately deferred to a live
      session with the user).
- [ ] Live-browser confirmation of room events: shrine icon on canvas,
      trap message on step, ambush pack appearing, respawn trickle.

## Engineering
- [ ] Shrine/camp write `stats["mana"]` instead of `current_mana`
      (pre-existing camp convention) — post-combat characters may not see
      the restore; small cleanup.
- [ ] Multi-worker Socket.IO (sticky sessions + message queue) — only if
      `--workers > 1` ever becomes real.
- [ ] Application-factory refactor: kill import-time side effects
      (load_dotenv/DB/migrations/seeds on `import app`). Spec:
      [specs/2026-07-27-app-factory-refactor-design.md](specs/2026-07-27-app-factory-refactor-design.md).
- [ ] Exception-handling ratchet: 62 silent handlers remain (CI enforces
      via `fix_exception_handling.py --check --max-count 62`). Lower the
      number as modules get cleaned; never raise it.
- [ ] Opportunistic god-file splits: `dungeon_api.py` (~1.8k lines),
      `combat_service.py` (~1.7k), `admin_new.py` (~1k), `adventure.js`,
      `combat.js` — extract when next touched for a feature.
- [x] ~~Remove dead `glass-theme.css` purple body-class rules~~ — already
      gone (removed in an earlier cleanup; the file's remaining rules are
      live on combat/admin/account pages).
- [x] ~~Dedupe `equipment.js` vs `equipment-enhanced.js`~~ — shared logic
      (encumbrance classification, affix totaling) extracted to
      `equipment-shared.js`; both files are live (adventure vs dashboard)
      and keep their own DOM templates.
- [ ] `.pre-commit-config.yaml`'s `optimize_svgs` hook never runs: its
      `files: '\\.(svg)$'` regex is the same doubled-backslash bug class
      documented in pyproject.toml's black include. Fixing the regex will
      make it rewrite every SVG on the next run — do it as its own commit
      and eyeball the asset diff.
- [x] ~~Fold the duplicated HP/mana-cap math onto `compute_hp_mana_max`~~ —
      `build_party_payload` folded (was byte-identical);
      `combat_service._derive_stats` stays inline deliberately (derives
      attack/defense/speed in the same pass; legacy CON→STR fallback
      differs) — documented at the formula block.

## How to run the suite
```bash
export TEST_DATABASE_URL=postgresql://adventure:changeme@localhost:5433/adventure_test
.venv/bin/python -m pytest tests/ -q
```
E2E browser smoke (needs a running server):
```bash
E2E=1 ADVENTURE_BASE_URL=http://localhost:5000 pytest e2e -q
```
