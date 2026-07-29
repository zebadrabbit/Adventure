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
- [ ] Adventure UX: ~~log window too restrictive for looting~~ (floating,
      collapsible, resizable now), ~~static character panels~~ (live HP/MP,
      encumbrance, clickable to the paper doll) — **D&D lingo throughout is
      still open**, and "Party Stash" is the design system's own worked example
      of what not to say (`DESIGN_SYSTEM.md` rule 8).
- [ ] **Combat overhaul** — designed: combat is its own screen and zooms into the
      map tile the party occupies, 4 vs 1-6 on a grid. Phased in
      [specs/2026-07-28-tactical-combat-design.md](specs/2026-07-28-tactical-combat-design.md);
      phase 1 (multi-enemy, no grid) is the biggest win and unblocks raising
      `SpawnConfig.group_size_max` above its current cap of 3.
- [x] ~~**Adventure HUD**~~ — full-bleed map, chrome="minimal" render flag,
      account anchor top-right, party frames left, floating collapsible log,
      action bar bottom-left. Plan:
      [plans/2026-07-28-adventure-hud-shell.md](plans/2026-07-28-adventure-hud-shell.md).
      Not built: log tabs (one stream exists on this screen), and the paper
      doll behind the frame click — next chunk,
      [specs/2026-07-28-character-panel-redesign.md](specs/2026-07-28-character-panel-redesign.md).
- [x] ~~**Character panels & paper doll**~~ — one `equipment-panel.js` mounted
      two ways (HUD panel beside the party rail in the dungeon, modal on the
      dashboard); `equipment.js`, `equipment-enhanced.js` and
      `equipment-shared.js` deleted. Restyled onto the token system.
      Encumbrance state now shows on the party frame. Plan:
      [plans/2026-07-28-paper-doll-consolidation.md](plans/2026-07-28-paper-doll-consolidation.md).

## Found during the 2026-07-28 UI chunks

Turned up by review while building the HUD, the slot unification and the paper
doll. None blocked those merges; all are real. Grouped by whether they
misbehave today.

### Live defects

- [ ] **`unequip_item` destroys a malformed gear value.** The legacy branch
      (`inventory_api.py:577-581`) calls `add_item(inv, <dict>, 1)`, producing
      `{"slug": {...}, "qty": 1}`, which `load_inventory` then discards because
      `slug` is not a string. One click, item gone. The gear-slot migration was
      hardened against exactly this shape; the live app path was not.
- [ ] **`consume` has no HP clamp.** `inventory_api.py:626` adds HP without
      capping at max, so drinking at full HP burns the potion for nothing — now
      one click away in the bag grid, where a mis-click costs a potion.
- [ ] **Server refusals are machine codes.** Only the in-combat lock
      (`inventory_api.py:454`) sends a human `message`; the other ~10
      (`item not equippable`, `bad_slot`, `not_in_inventory`, `empty slot`,
      `item not in bag`, `not consumable`, …) are bare codes. The panel now
      shows the player whatever it gets, so these are player-facing strings and
      fall under the D&D-register rule.
- [ ] **Resize-then-zoom snaps the camera off-centre.** `resizeCanvas` calls
      `centerOnPlayer`, which writes `offsetX/Y` without syncing
      `targetOffsetX/Y`, so the next zoom eases back toward the pre-resize
      target. Pre-existing in kind — `onMouseMove` and `onWheel` diverge the
      same way, so drag-then-zoom has always snapped.
- [ ] **`adventure.js:842`'s `.character-card` selector is dead**, so the
      per-character "last roll" readout has never worked on the party rail —
      every roll silently takes the fallback above the log. Now load-bearing:
      the encumbrance marker occupies that row, so repairing the selector means
      re-measuring the rail budget. Warning comments are at both sites.
- [ ] **The floating log collides with the zoom controls below a 705px viewport
      height.** The log's ceiling is a constant ~421px, so it is outside the
      768px design floor but reachable on a 768px physical screen once
      scrollback fills.

### One vocabulary, four times over

- [ ] **Class colours have four sources.** `tokens.css`'s `--class-*`,
      `class-badges.css`, `equipment.css`'s `.eq-class-bg-*`, and — the live one
      — a runtime injector (`adventure.js:112-148` with
      `config_api.py:257-270`) that stamps `--class-{slug}-bg/-fg/-border` and
      `!important` rules onto `document.documentElement` on every `/adventure`
      load. It hides from grep because the property name is built by
      template-literal interpolation, so `--class-fighter-bg` never appears as a
      searchable string. This is the same shape as the gear-slot vocabularies
      and deserves the same treatment: spec, single source, migration if needed.
- [ ] `party-management.css`'s `.rarity-*` block was `!important` and defeated
      the rarity tokens on both screens — fixed, but the same `!important`
      pattern is worth sweeping for elsewhere.
- [ ] `--info` is a literal alias of `--accent` (`tokens.css:191`), so
      `tactical-btn-info` and `-primary` share a hue and differ only by fill vs
      wash. Decide whether info deserves its own hue or the alias is intended.
- [ ] Hover glows are inconsistent: `--glow-accent`/`--glow-danger` exist at
      14px/30%, `-info`/`-success` hand-roll 12px/15%, and `-danger`'s own hover
      uses a raw `rgba()`. Add `--glow-info`/`--glow-success` and point all four
      at tokens.

### Interaction and accessibility

- [ ] Bag-grid cells are focusable but arrow keys still move the party — grid
      arrow-navigation is the natural follow-up now that the grid is a
      keyboard target.
- [ ] The character panel ignores the tooltip preference. `tooltips.js`
      persists `mudTooltipMode` (`rich`/`plain`/`off`) and the deleted
      `equipment.js` honoured it; `equipment-panel.js` shows its comparison
      tooltip unconditionally, so a player who set tooltips off gets them back
      inside the panel. Bag cells also carry both a native `title` and the
      custom tooltip, so hovering fires two.
- [ ] 257px of residual scroll in the character panel at 1366×768. The cause is
      the `78vh` cap on `.equipment-slots`/`.inventory-bag` — a dashboard-modal
      number applied to a HUD mount that has ~494px. Real fix is
      `.equipment-slot` sizing or a markup change.
- [ ] `account_anchor.html` has no `is_authenticated` guard (the navbar dropdown
      it was lifted from did). Unreachable today — `/adventure` is
      `@login_required` — and live the moment `chrome="minimal"` reaches an
      ungated route, which the combat screen is expected to want.
- [ ] Four decorative icons in the character panel still carry Bootstrap's
      `text-danger`/`text-warning` rather than tokens.

### Hygiene

- [ ] Flashed messages are dropped under `chrome="minimal"` — nothing flashes
      into `/adventure` today, so a message queued elsewhere surfaces on an
      unrelated later page instead of being lost visibly.
- [ ] `<main class="chrome-minimal">` has no CSS anywhere — dead hook or
      missing rule.
- [ ] `sql/README.md`'s Files section omits eight `.sql` files that do exist.
- [ ] `dashboard_helpers.render_dashboard` imports inside a per-character loop
      (`:82,88`) — same shape as the one fixed in `build_party_payload`.
- [ ] Dev-database throwaway accounts from Playwright verification runs; 11
      removed, more will accumulate. Worth a cleanup helper rather than manual
      FK-walking each time.
- [ ] **No JS test tooling** — no jest, no vitest, no `package.json`. A large
      share of the UI is vanilla JS and nothing automated covers it;
      `e2e/test_smoke.py` is the only browser-level net. This is how the dungeon
      silently lost potion consumption during the paper-doll port.

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
- [x] ~~Three gear-slot vocabularies~~ — `auto_equip_for` wrote `armor` (a name
      in no vocabulary, so nothing could unequip it), `_slot_for_item` wrote the
      legacy `boots`/`gloves`/`ring1`/`ring2`, and procedural loot wrote the
      canonical eight, all into the same `gear` dict. Now single-sourced from
      `archetypes.SLOTS`, with a data migration. Plan:
      [plans/2026-07-28-gear-slot-unification.md](plans/2026-07-28-gear-slot-unification.md).
- [x] ~~Looted gear cannot be equipped during a run~~ — the dungeon's only equip
      path posted `{slug, slot}` with no `uid` branch, so procedural instances
      404'd on the legacy path. The promoted panel sends `uid`.
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
- [x] ~~Dedupe `equipment.js` vs `equipment-enhanced.js`~~ — superseded and
      finished: all three files (including `equipment-shared.js`, which existed
      only to stop the two drifting) are deleted in favour of one
      `equipment-panel.js`. See the character-panel entry above.
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
