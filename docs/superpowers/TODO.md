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
- [x] ~~**Item usage in combat** — the service knew 3 hardcoded slugs and the
      UI offered 2 buttons, against 154 potions in the catalogue~~ — one
      resolver, `resolve_potion_effect` in `app/services/item_effects.py`,
      now backs both the combat and out-of-combat paths. 43 of 154 potions
      resolve (20 `heal`, 20 `mana`, 3 legacy hyphenated slugs); every other
      family refuses with a readable message and keeps the item rather than
      consuming it. Two live bugs came out of the exploration pass and are
      fixed with it: an infinite-potion exploit (ownership was checked
      *after* the effect applied, inside a swallowing `try/except`), and
      out-of-combat consumption silently destroying 127/154 potions for zero
      effect (it matched the substring `"healing"` against a catalogue that
      spells it `heal`). The combat screen's two fixed buttons are now a
      panel listing the potions the character actually carries, grouped by
      effect, with counts on the button. Spec:
      [specs/2026-07-28-combat-item-usage-design.md](specs/2026-07-28-combat-item-usage-design.md),
      whose two 2026-07-29 correction sections record what the exploration
      pass found and what was deliberately left out. The other 111 potions
      are recorded below, under Engineering, one missing mechanic per family.
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

- [x] ~~**Every combat loot drop is granted twice.**~~ `loot_service.roll_loot`
      returns the same drops under two keys — `items` (a quantity map) and
      `items_list` (a flat mirror, "for legacy compatibility",
      `loot_service.py:182`) — and `_check_end` iterated **both**, in two
      independent `if`s, so one drop landed at `qty: 2` and two at `qty: 4`
      (confirmed empirically). Now an `elif` chain, so exactly one
      representation is consumed. The outer guard also required `items`, which
      meant `items_list` could never actually serve as the fallback it exists
      to be — it was reachable only as a duplicate; the guard now accepts
      either key. Three tests pin the count against `roll_loot`'s real dual
      shape, including that a genuine `qty: 2` stays 2.
- [ ] **`websockets/game.py:223` cannot open a treasure.** It calls
      `roll_loot(row.slug or "treasure", rolls=1)` — a `str` where the
      signature wants a `Dict`, plus a `rolls=` keyword the function does not
      accept. The `TypeError` fires first, so that socket path raises on every
      treasure open. Found while fixing the doubled grant; the REST treasure
      path (`dungeon/api_helpers/treasure.py:129`) calls it correctly.
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

### One vocabulary, many times over

- [x] ~~**Class colours have four sources.**~~ It was seven —
      `tokens.css`'s `--class-*` hues (now the single source, with
      `-bg`/`-fg`/`-border` derived per class); `theme.css:337-417`'s twelve
      hardcoded badge rules, loaded on every page and the one that actually
      paints a badge, rewritten to read the tokens (nothing changed visibly
      until this did); `base.css`'s six-class `--class-*-bg/-fg/-border`
      block, deleted; `classes.css`, deleted — an orphan loaded by no
      template, 15 of 18 values disagreeing with `base.css`;
      `class-badges.css`, deleted — a second orphan, and the only file
      already reading the tokens correctly; `config_api.CLASS_COLORS` +
      `/api/config/class_colors` + `adventure.js`'s injector, deleted — it
      `!important`-overrode the token system on `/adventure` only and hid
      from grep because it built the property names by interpolation; and
      `dashboard.css`'s unscoped `.badge` rule, scoped with
      `:where(:not(.class-badge))` — found only by opening a browser, it
      tied `.fighter-badge`'s specificity and loaded later, silently
      stripping the class tint. Visible symptom: a Fighter's badge was
      `#7a3314` on the dashboard and `#301d0b` in the dungeon. The palette
      itself was replaced too — `bard` and `paladin` were the same hue,
      three golds sat within 6°, and `fighter`/`warlock`/`rogue` were below
      the 4.5:1 contrast floor — with twelve hues solved numerically; worst
      case is now 5.40:1 against both realm grounds, enforced by
      `tests/test_class_colour_tokens.py`. A live bug came out in the
      process: `adventure.html:118` emitted `class-badge-{{ class_lower }}`
      (one token) where every selector wants two, so the party-rail class
      badge rendered unstyled from `7dfcf1e` until this fixed it.
- [ ] **Class icons have the same six-vs-twelve gap, in a different
      medium.** `adventure.html:99-115` is a six-branch `if/elif` on
      `class_lower` (fighter, mage, rogue, druid, cleric, ranger) with a
      letter-avatar fallback, so the other six classes (barbarian, bard,
      monk, paladin, sorcerer, warlock) render an initial instead of an
      icon.
- [ ] The party-rail class badge's fill is only 1.00-1.24:1 against the
      card — `-bg` mixes 22% of the hue into `--realm-bg` rather than into
      the card's `--surface-overlay`. Not a defect: the legibility floor is
      met by the text (7.01:1) and the border (2.11-4.16:1), not the fill —
      but it means the fill is decorative there and nothing should rely on
      it.
- [ ] The rail badge and the dashboard roster badge now agree on colour and
      disagree on shape: the rail one carries `.badge`, so `app.css:585`
      rounds it to `0.375rem` against `--radius: 0`. Part of the
      already-tracked badge-to-chip conversion in `DESIGN_SYSTEM.md`'s
      migration plan (phase 7 — "chips": square, hairline outline, no
      radius).
- [ ] `tactical-theme.css:193` (`.panel-header .badge`, no `:not()`
      exclusion) would flatten class badges the same way the
      `dashboard.css` rule above did — but the file is referenced by no
      template, route or script (a third orphan; `DESIGN_SYSTEM.md`'s
      appendix already marks it "Superseded — delete"). Unverified in a
      browser since nothing loads it.
- [ ] `dashboard.css:210`'s `.badge-open` is dead code — grep finds only its
      own declaration.
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
- [ ] Potion tier curve: heal is `10 + 5×(N−1)` (10→105 across `l1`-`l20`),
      mana is `4 + 2×(N−1)` (4→42) — `app/services/item_effects.py`'s
      `_heal`/`_mana`. First pass, never playtested, and the only balance
      decision in the whole potion-resolver chunk.
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
- [ ] Shrine (`app/dungeon/room_events.py:163-166`, `_resolve_shrine`) still
      writes `stats["mana"]` instead of `current_mana` (pre-existing camp
      convention). Camp (`dungeon_api.py:1744-1745`) and `consume_item`
      (`inventory_api.py:656-657`) both write both keys now — camp already
      did, and the potion-resolver chunk fixed `consume_item` — so the
      shrine is the one live remaining instance. Combat's `_derive_stats`
      prefers `current_mana`, so a mana restore from a shrine can be
      silently discarded the moment the party enters its next fight.

Potion families the resolver refuses (111 of 154 potions) have no combat
mechanic to attach to yet. `app/services/item_effects.py`'s
`_FAMILY_HANDLERS` table is the extension point once one exists — one table
entry plus a handler:

- [ ] `buff_attack`, `buff_defense`, `resist_fire` (45 potions) need one
      shared piece: an effect kind that modifies a derived stat and expires.
      The combat snapshot is mutable so a modifier sticks, but nothing can
      un-apply it — there is no expiry hook and no recompute pass. Note
      `defense` is *evasion* only, so a defence potion makes you harder to
      hit, not tougher. Highest leverage of the blocked families — unblocks
      three at once.
- [ ] `antidote` (5 potions) needs a `remove_effect` primitive.
      `status_effects.py` can add and replace an effect but never remove
      one; expiry is the only route today. It must also delete the
      `CharacterStatusEffect` row, or the poison returns via `_derive_stats`.
- [ ] `buff_speed` (20 potions) needs dynamic or re-rolled initiative.
      `speed` is read once, by `_calc_initiative` during `start_session`,
      and never again.
- [ ] `resist_cold`, `resist_lightning`, `resist_poison` (15 potions) need
      typed damage that actually reaches players. No cold or lightning
      damage ever reaches a player today — monster attacks hardcode
      `["physical"]` and the one firebolt hardcodes `["fire"]`; the
      `damage_types` column exists and no damage path reads it. Poison
      bypasses `apply_resistances` entirely. Also the element string is
      `"ice"`, not `cold`. Player `resistances` is hardcoded `{}` at
      `combat_service.py:209`, so `combat_utils.apply_resistances` is live
      code that always no-ops.
- [ ] `stamina`, `perception` (10 potions) have no combat mechanic at all —
      zero references to stamina anywhere in `app/`; perception exists only
      in exploration and reads `Character.stats` rather than the combat
      snapshot.
- [ ] `group_battle`, `invis`, `luck` (12 potions) were never in the
      original item-usage spec's table and have no mechanic at all.
- [ ] `stun` has a handler nothing can trigger — `status_effects.py:102`
      defines it, but `add_effect` is never called anywhere in `app/`.
- [ ] The regen buff's duration and multipliers are duplicated
      literal-for-literal in four places: `inventory_api.py`,
      `combat_service.py`, `dungeon_api.py`, `dungeon/room_events.py`. This
      is why `item_effects.py` deliberately leaves `potion_regen_lN`
      unhandled (resolves to `None`) — tiering it would create a fifth copy.
      Folding those four together is the prerequisite for a tiered regen
      potion.
- [ ] `tests/test_bag_potion_consumption.py` asserts only `hp > 0` and
      `hp > previous`, so it would pass against a heal of 5, 25 or 500 —
      it never pins the actual amount. A pre-existing coverage gap, now
      backstopped by the potion resolver's parity test, but worth
      tightening since this is the file whose name reads as the one
      guarding it.
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

Known flaky tests, not regressions if seen in isolation:
- `tests/test_camp_regen_buff.py` and `tests/test_camp_supplies_and_cooldown.py`
  fail intermittently when run together — re-run the failure alone to confirm.
- `tests/test_quest_hooks.py::test_kill_increments_daily_quest` self-skips
  (`pytest.skip("No kill_count quest generated this run")`) roughly a third of
  runs: `quest_generator.get_or_generate_daily` draws 3 templates via
  `random.choices(_DAILY_TEMPLATES, weights=[3,2,3,2], k=3)` against unseeded
  global `random` state, so the odds of drawing zero `kill_count` templates
  are `0.7³ ≈ 34%`. Bisected and reproduced in isolation across fresh
  interpreters — not an artifact of suite ordering.
