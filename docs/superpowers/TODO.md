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
- [x] ~~Party Stash button is a `coming soon` alert.~~ Deleted, button and
      handler. A shared party pool is the wrong model for this game: bags are
      per-character, and **per-character encumbrance** (with its DEX penalty
      and hard cap) only means something if every item sits in somebody's
      bag — a communal container is a hole straight through it. Wiring it to
      the existing Hoard would have been worse: the Hoard is the *safe*
      balance that survives wipes, so banking mid-run would have nullified
      both the wipe risk and the early-extraction penalty. The hoard stays a
      town feature; `Extract` already banks the haul.
      Owner's model, recorded here because the code does not yet match it:
      each character carries their own bag; **items can be exchanged between
      characters outside combat**; in combat a character may only use their
      own inventory; a character who dies and is not resurrected can be
      looted, and whatever is left on them is lost.
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
- [x] ~~**`websockets/game.py:223` cannot open a treasure.**~~ Deleted rather
      than repaired. The handler called `roll_loot(row.slug, rolls=1)` — a
      `str` where the signature wants a `Dict`, plus a keyword the function
      does not accept — so it raised `TypeError` on every emit, and no shipped
      client ever emitted it (`adventure.js` carried a note explaining why it
      kept using REST). Repairing the call was not enough to be worth it: the
      handler also skipped the adjacency check and the hidden-chest perception
      roll, ignored the per-entity `data.loot_table` override, and deleted the
      chest while granting nothing. All of that already works, once, in
      `claim_treasure_entity`, which the REST path uses. The TypeError fired
      before `db.session.delete`, so nothing was ever destroyed by it.
- [x] ~~**`unequip_item` destroys a malformed gear value.**~~ It was worse than
      filed: the branch named here is unreachable (nothing writes a uid-less
      dict into `gear`, and `_serialize_gear_slot` renders no unequip button
      for one), but two *click-reachable* siblings were destroying ordinary
      items. Equipping a catalogue item over a looted one sent the instance
      through `add_item(inv, <dict>, 1)` → `{"slug": {...}, "qty": 1}`, which
      `load_inventory` drops; and the uid path appended a displaced legacy
      slug string into a list of dicts, which `load_inventory`'s canonical
      branch skips. Both are one click and the item is gone. Now one guard —
      `add_gear_value` in `app/inventory/utils.py` — on all four paths, and
      the uid path reads/writes through `load_inventory`/`dump_inventory`
      instead of raw JSON, which removes the mixed-list hazard that made the
      shapes diverge in the first place (and let it reuse `find_instance` /
      `remove_instance`, which already existed unused).
      `tests/test_gear_swap_preserves_items.py` pins all four; each was
      confirmed to fail with the guard backed out.
- [x] ~~**`consume` has no HP clamp.**~~ Already fixed by the potion-resolver
      chunk — `consume_item` clamps both HP and MP against
      `compute_hp_mana_max` and writes `mana`/`current_mana` together. The
      *shrine* was the live residue and is fixed here: it read a `max_mana`
      key only level-up ever writes, so it fell back to *current* mana and
      restored `min(cur, cur + cur×pct)` — exactly nothing — and wrote only
      the legacy `mana` key, so combat's `_derive_stats` discarded even that.
      Now mirrors camp: computed cap, `current_mana`-first read, both keys
      written, and a "resting can only help" floor.
- [x] ~~**Server refusals are machine codes.**~~ Thirteen returns across
      `equip_item`/`unequip_item`/`consume_item` now carry a player-facing
      `message`; four new constants, four reused. `error` codes are unchanged
      — they are API surface — so only `message` was added. One reclassified:
      the `remove_one` miss after ownership was already verified against the
      same in-memory `inv` is a lost race, not a refusal, and now answers
      `item_removal_failed`/500 like `consume_item`'s equivalent rather than
      telling the player they are not carrying something they are.
- [x] ~~**Resize-then-zoom snaps the camera off-centre.**~~ One `setView()`
      setter in `dungeon-canvas.js` writes live and target together, with the
      four immediate writers (mouse drag, touch drag, wheel zoom, the
      non-smooth `centerOnPlayer` that `resizeCanvas` calls) routed through
      it. The eased writers are deliberately left alone — target-only is what
      easing means. The resize site passes `targetZoom` rather than the live
      zoom, so a resize mid-button-zoom no longer freezes it at the
      intermediate value. Pinned by
      `e2e/test_smoke.py::test_resize_then_zoom_keeps_the_camera_put`,
      confirmed failing with the setter backed out.
- [x] ~~**`adventure.js`'s `.character-card` selector is dead**~~ — and so was
      the whole feature behind it. `last_roll` appears in **zero** Python
      files: the server has never sent it, so `updateLastRollUI` never ran and
      the "fallback above the log" that the selector bug supposedly forced
      every roll into had never fired either. Deleted the function, both
      guarded call sites, the `.last-roll-line` div, its CSS rule, and the
      three comments describing the row as shared. The encumbrance marker now
      owns that row outright; its height was always reserved by
      `.party-status-line`'s own `min-height`, so the rail budget is
      unchanged (`test_hud_panels_do_not_cover_the_party_or_each_other` still
      passes). Making the readout *work* is a feature build — server support
      plus an overflow treatment plus a re-measure — not a selector fix.
- [x] ~~**The floating log collides with the zoom controls below a 705px
      viewport height.**~~ The ceiling gained a second, viewport-relative
      bound via `min()`, plus a `--hud-controls-reserve: 276px` token naming
      the controls' bottom edge (172px top + three 32px buttons + two
      `--space-1` gaps) so the log can clear it without restating the number.
      Nothing moves at the 768px floor — the existing constant still wins
      there. Pinned by `test_floating_log_clears_the_zoom_controls` at 768
      (control) and 640 (fails without the bound). Residual: below ~436px of
      viewport the log's `min-height: 120px` wins and the collision returns;
      that is far under any supported size.

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
      **It was eight, not seven.** A final review found
      `glass-theme.css:246-282` — six per-class `!important` gradients, live
      on `/combat` because `combat.html:127` loads that file in
      `{% block head %}`, i.e. after `theme.css`. `!important` beat the
      tokens regardless of order or specificity, so `/combat` rendered six
      classes from one palette and six from another (a Rogue was a yellow
      gradient there, slate violet on the dashboard). It survived two sweeps
      because `DESIGN_SYSTEM.md:401` declares `glass-theme.css` the "admin
      and account" dialect with an explicit "do not use `.glass-*` on a
      player-facing screen" — so a sweep that trusted the doc never opened
      it. Deleted, and the doc now records the `combat.html` violation as a
      known wart. A **ninth** source exists on disk —
      `tactical-theme.css:298-333`, six more hardcoded hexes — but that file
      is loaded by no template and is already marked for deletion in the
      orphan table; `tests/test_class_colour_tokens.py` exempts it only for
      as long as it stays unreachable.
- [ ] **Judgement call for the owner: `fighter` `#d1666d` and `sorcerer`
      `#d16691` may be too close.** Identical saturation and lightness,
      separated only by 20.2° of hue. Both clear the stated criterion (the
      test requires <12° hue *and* <18 lightness to count as a collision, so
      this pair passes on hue distance alone), and both clear the contrast
      floor. But on a badge the size of the party rail's they are the pair a
      player is most likely to conflate, and the criterion was written to
      catch same-hue collisions rather than same-lightness ones. Left
      unchanged deliberately — changing a hue is the owner's call, not a
      reviewer's. If it does change, note that the contrast figures in
      `equipment.css` and `tokens.css` are palette-dependent and must be
      re-derived.
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
- [ ] `.character-card` is dead everywhere, in three media. No template emits
      it (the rail and roster both emit `.operative-card`), yet
      `scripts/screenshot_adventure.py:99`, `screenshot_help.py:55` and
      `screenshot_storyboard.py:95,254` all locate on it — so those scripts
      have been measuring zero cards — and `glass-theme.css:181-215,596` still
      styles it. Turned up by the 2026-07-29 live-defect triage while deleting
      the dead last-roll readout, which was the fourth user of the selector.
- [ ] Three copies of `_perception_mod_from_stats`
      (`dungeon/api_helpers/perception.py:56` — the one `room_events` imports,
      `dungeon/api_helpers/treasure.py:29`, and `routes/dungeon_api.py:1421`).
      The `dungeon_api` copy is reachable only from `_roll_perception_for_user`
      (`:1443`), which has **no callers at all** — both are orphans and can go;
      the treasure copy should import from `perception.py` instead.
- [ ] The gear-slot migration's `_unbaggable`
      (`migrations/versions/c9405725c1f4_unify_gear_slots.py:39`) has the same
      uid-less-dict hole the app side just closed with `add_gear_value`. The
      migration is already applied, so it was deliberately left alone; if it is
      ever hardened, mirror that helper's clause rather than diverging again.
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

## Party inventory model

The intended model (owner, 2026-07-29) is per-character bags with exchange
between characters outside combat. Two pieces of it do not exist yet.

- [ ] **No character-to-character item exchange.** Nothing hands an item from
      one party member to another: `trading_api.py` is merchant buy/sell/repair
      only, and there is no give/take endpoint anywhere in `app/routes/`. So
      the potions land on whoever looted them and stay there for the whole
      delve. Needs a give endpoint plus an encumbrance re-check on the
      receiving side (the giver can only get lighter) and the same
      `_reject_if_in_combat` lock `equip` uses — in combat a character may only
      use their own inventory. The paper-doll panel is the natural surface,
      since it already renders one character's bag and knows the party.
- [ ] **Looting a corpse has no same-run guard** — already tracked as a Spec 2
      follow-up: `POST /api/dungeon/loot-body` checks only that both characters
      belong to the user and the donor `is_dead`, not that they are in the same
      run. "Anything left on them is lost" is not enforced either; the body
      keeps its remaining items indefinitely rather than the run consuming them.

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
- [x] ~~Shrine (`app/dungeon/room_events.py`, `_resolve_shrine`) still writes
      `stats["mana"]` instead of `current_mana`~~ — fixed, and it turned out
      to be restoring nothing at all: the cap came from `stats["max_mana"]`,
      a key only `level_up_character` ever writes, so for almost every
      character it fell back to *current* mana and the restore collapsed to
      `min(cur, cur + cur×pct) == cur`. The existing test hid this by seeding
      `max_mana` into stats by hand. Now uses `compute_hp_mana_max` like camp,
      reads `current_mana` first, writes both keys, and floors at "resting can
      only help". Two tests in `test_room_events_resolution.py`, one of them
      specifically for a character with no stored `max_mana`.

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
