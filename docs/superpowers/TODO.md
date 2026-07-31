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
- [x] ~~**Author monsters for levels 21-50**~~ — **not needed. The cap is 20.**
      The original aim was "Diablo with rifts"; the owner's correction was
      "within a sane levelling system", and depth after the cap is the dungeon
      tier ladder's job rather than more level numbers. Measured before
      deciding: **81% of all XP in the game** (1.5M of 1.855M) sat in levels
      21-50, which were 30 identical 50,000-XP steps fought against clamped
      level-20 monsters, because the catalogue stops at 20. A survey of every
      level-gated system found **nothing** that becomes reachable above 20
      except dungeon tiers 4-7 — and those were already unreachable, since
      `dashboard.py` clamps the tier to 1-3 and the only code that reads a
      tier's level band is never called. So the cap cost nothing and deleted
      the largest content task on this list.
- [x] ~~**Ambient spawns do not scale with level**~~ — moot at the cap. The
      clamp in `scaled_instance` only bit above level 20, which no longer
      exists. Left as-is deliberately rather than "fixed": with a 1-20 game the
      band a monster is authored for *is* its level range.
- [ ] **The levelling curve is re-derived, and it is tuning, not truth.**
      `app/models/xp.py` now rises monotonically in *kills* — 22 at level 1,
      179 at 19->20, ~1,557 for a whole run by a four-party. The old 5e-derived
      curve was **inverted**: hardest at 6->7 (~571 kills), easiest at 16->17
      (~92), because monster `xp_base` grows ~27x from level 5 to 20 while 5e's
      requirement grows ~10x. `tests/test_xp_curve_shape.py` pins the *shape*
      against the real catalogue, not the numbers — re-derive the numbers when
      monster XP changes and let that test judge the result. Playtest verdict
      wanted on whether ~1,557 kills is the right length.
- [ ] **`armor` is a dead stat above about level 5.** Evasion is `armor + 10`,
      against an accuracy of `attack + d20` where attack reaches ~46 by level
      20 — so every attack auto-hits and armor changes nothing. Either give it
      a real role (damage reduction?) or stop pretending it has one.
- [ ] **`traits` has no mechanical consumer.** All 108 rows carry them and
      nothing reads them for mechanics — `immune_fire` and `vulnerable_cold`
      are decoration. Related: `resistances` and `damage_types` are NULL on
      every row, so `apply_resistances` is a no-op for every monster.
- [ ] **Level-gated content is thin now that the ladder is short.** Skills top
      out at `required_level` 5 across all 34 seeded rows, item generation is
      hard-capped at level 20, and the `level_reached` achievements never fire
      (`check_achievements` is never called with that key). A 20-level game
      wants things arriving *through* those 20 levels.
## Rewards that scale with effort

The 2026-07-30 survey measured the reward layer against 40,000 simulated drops.
The procedural naming system was fine; everything that should make one drop
better than another was not.

- [x] ~~**Rarity was decorative.**~~ It changed the affix *count* and the price,
      never the magnitude — a common `Longsword of the Bear` at level 20 rolled
      `{str: 9, con: 4}`, byte-identical to a mythic one. Rarity now carries a
      `power` multiplier that scales every rolled value. Mean stat points at
      level 20 went common 14.0 -> 29.0 and mythic 59.9 -> 166.7, and epic vs
      legendary (44.0 vs 48.9, effectively the same item) is now 86.7 vs 118.1.
- [x] ~~**Three affix stats were read by nothing.**~~ `crit`, `lifesteal` and
      `resist` were rolled, named and shown in tooltips while 11.4% of every
      affix point went nowhere — and on rings and amulets it was 100% of the
      prefix weight, making `of Warding` and `of Precision` entirely inert. All
      three are wired now. Note `apply_resistances` takes *multipliers*, not
      flat points, so gear resist converts at one point = one percent, floored
      at 60% so a stacked set cannot reach immunity.
- [x] ~~**7.4% of drops had no stats at all**~~, and the two most common items
      in the game were a bare `Ring` and a bare `Amulet` — jewelry had no base
      stat block and slot choice is uniform over eight slots. Jewelry gets an
      innate `max_hp`, and every rarity now rolls at least one affix.
- [x] ~~**Common items could never carry a prefix**~~ — the suffix always ate
      the first affix slot, so 60% of drops were a bare base or `Base of the X`.
      Prefix rolls first now: 27.2% -> 100% of drops have an adjective.
- [x] ~~**Duplicate affixes read as a bug**~~ — extras roll from the same small
      prefix pool, so a weapon could show `+20 damage, +5 damage, +11 damage`.
      Merged into one entry, and a prefix that repeats its suffix's word
      (`Warding ... of Warding`) is dropped from the name.

Still open, in the order I would take them:

- [x] ~~**The catalogue does not scale with depth.**~~ All 215 rows now carry a
      real level and rarity, via the loader's 8-column header form (which
      existed and had never been exercised). Derived, not hand-authored: 151
      potions from their `_l<N>` slug tier, misc rows by price rank *within
      their type*, and the 13 zero-priced keys and quest items deliberately left
      at level 0 — the generator treats 0 as always-eligible, which is what a
      gate key should be. Rarity bands off the level. The result went from
      225/229 common at level 0-2 to common 61 / uncommon 49 / rare 50 / epic 43
      / legendary 26, spread across every band. `tests/test_catalogue_spread.py`
      reads the seed files (not the DB — `db_isolation` rebuilds leave a minimal
      catalogue mid-suite) and fails against the old flat data.
- [x] ~~**`loot_quality_bonus` is computed and never read.**~~ `roll_loot` reads
      the `loot_multiplier` now. It gives each gear instance a chance at one
      rarity step up — a 1.30 multiplier is a 30% chance of one step, never more
      than one — rather than rolling extra drops: the tier bonus is a *quality*
      bonus, and more drops would inflate encumbrance and vendor income too.
      Also deleted `app/server.py::_infer_levels_and_rarity`, which guessed
      level and rarity from name keywords on every boot as a stated stopgap
      "until explicit metadata lives in the SQL files". It does now, and the
      heuristic actively fought it: its skip condition only spared rows that
      were *both* non-zero level and non-common, so every legitimately common
      low-level item was rewritten each time the server started.
- [x] ~~**111 of 154 potions refuse to be drunk**~~ — **125 of 151 tiered
      potions resolve now (83%, was 26%)**. One primitive did most of it: a
      persisted `CharacterStatusEffect` row whose `data` carries
      `{scope, mods, resist_points}`, folded into the party snapshot at a single
      point (`combat_service.apply_effect_modifiers`) that runs on hydration, on
      drinking, and at turn start. **No migration** — `name` is already wide
      enough and `data` is already JSON-in-Text.
      The owner's rule (*combat buffs fall off when the fight ends, regardless
      of the clock*) is implemented by omission rather than a clearing pass: the
      end-of-combat write-back already deletes every persisted row, so a
      combat-scoped effect is simply never re-added. Expiry otherwise rides the
      existing game clock, as decided.
      Unblocked: `buff_attack`/`buff_defense`/`buff_speed` (60), the four
      `resist_*` families (20), and `antidote` (5), whose mechanic already
      existed — `poison` is a real status.
      Two traps avoided: `resist_cold` keys on **`ice`**, the element the spell
      config and damage pipeline actually emit (`apply_resistances` silently
      drops unknown keys, so `cold` would have been a five-potion no-op that
      looked implemented); and resist is stored as **points**, summed across
      gear and every effect and converted to a multiplier exactly once, because
      multiplying two multipliers (0.8 × 0.75 = 0.60) slips past the 0.4 floor
      each source respects individually.
      Also fixed on the way: `PERSISTED_EFFECT_NAMES` was two function-local
      copies **1,287 lines apart**, so a new effect added to one and not the
      other would silently fail to hydrate or fail to persist. Now one constant.

- [ ] **26 potions still have no mechanic** — `stamina` and `perception` (5
      each), and `invis`, `regen`, `luck`, `group_battle` (4 each). Each needs a
      design decision rather than an implementation:
      - `stamina` — nothing in `app/` references stamina at all. Either a third
        resource or re-theme onto something that exists.
      - `perception` — exists in exploration only, and reads `Character.stats`
        rather than the combat snapshot. Closest to buildable: a world-scoped
        buff on the perception stat the trap/hidden-cache rolls already use.
      - `luck` — the seed file's own header says `(affects loot RNG -
        conceptual)`. That parenthesis is the author admitting there is no
        mechanic. Would need a hook in `roll_loot`.
      - `regen` — still blocked on the same thing it always was, and the note
        claiming otherwise was wrong: the regen-buff literals
        (`{"hp_mult": 2.0, "mp_mult": 2.0}`) are still copied verbatim in
        `dungeon_api.py:1707` and `room_events.py:187`, with a third variant
        (3.0/3.0) in `item_effects`' legacy map. Only `PERSISTED_EFFECT_NAMES`
        was consolidated. Tiering regen would add a fourth copy; fold them onto
        one constant first.
      - `invis` — "partial"/"near-perfect" in the descriptions implies a
        miss-chance percentage, not a boolean.
      - `group_battle` — the only family that targets anyone but the drinker.
        Needs party-wide application, which no potion path has.
- [ ] **The potion naming ladder disagrees with itself.** The dense families
      (heal/mana/buff_*) use a 20-step ladder where *Superior* is tier 6 and
      *Greater* is tier 5. Six sparse families call tier 10 *Superior*, and the
      four late families (invis/regen/luck/group_battle) call tier 15 *Greater*
      and leave tier 10 unnamed. So the same adjective means three different
      tiers depending on which potion you are holding, and `luck` is the only
      family with no *Ultimate* at tier 20. Pure data; nothing reads the names.
- [ ] **`attack_speed` is defined on all 12 weapon archetypes and read by
      nothing**, so a Dagger is strictly worse than a Greataxe with nothing to
      compensate. Either make it matter or drop it from the data.
- [ ] `Flaming`, `Frozen` and `Shocking` are byte-identical rolls — same stat,
      same min/max/scale/weight. Pure reskins. They are the obvious hook for
      elemental damage now that typed damage and resistances actually resolve.

- [ ] **Unique / set items** (owner, 2026-07-30 — explicitly a *later* item, not
      now). Named uniques across rarity tiers, with set bonuses, so there is
      something to chase and collect rather than just a better roll of the same
      procedural gear. Depends on the catalogue having real levels and rarities
      first — a "set" means nothing while every item is level 0 common. The
      procedural generator (`app/loot/generator.py`) already produces named
      instances with a uid, so a unique is closer to a hand-authored instance
      with a fixed affix list than to a new system.
- [ ] Item catalogue rarity spread: 225/229 common, almost all level 0-2, so
      loot tiers can only be separated by price.
- [ ] Maze too spiralling: tune `dead_end_keep` / `extra_connection_chance` /
      `straight_max`.
- [ ] Map readability: wall/floor contrast, props, coordinate + floor readout.
- [ ] Adventure UX: ~~log window too restrictive for looting~~ (floating,
      collapsible, resizable now), ~~static character panels~~ (live HP/MP,
      encumbrance, clickable to the paper doll) — **D&D lingo throughout is
      still open**, and "Party Stash" is the design system's own worked example
      of what not to say (`DESIGN_SYSTEM.md` rule 8).
- [ ] **Combat overhaul** — phase 1 (multi-enemy) is **built**:
      [plans/2026-07-30-combat-multi-enemy.md](plans/2026-07-30-combat-multi-enemy.md).
      `monsters_json` is the source of truth, initiative spans every combatant,
      corpses are tombstoned and skipped, monsters act as themselves with
      per-monster cooldowns, loot/XP/kills fold across the pack, actions carry a
      `target_id`, and the screen lists the enemies with a target picker.
      Two live bugs fell out of the survey and are fixed: `_check_end` had no
      re-entry guard, so a second `end_turn` after a win re-rolled and re-granted
      the whole loot table; and the "all bosses defeated" unlock, once hoisted
      out of the per-corpse loop, would have fired on every kill because
      `0 >= 0`.
      **It is switched off in play.** `SpawnConfig.combat_pack_max` ships at 1,
      so you still fight one monster at a time. At 3 the full-run test wipes the
      party: monsters are costed for a solo appearance, nothing exists above
      level 20, and the catalogue is 225/229 common. Turning it on is one line
      and belongs with the tuning verdicts below — it is the single highest-value
      thing a playtest could settle now.
      Phases 2 (the grid) and 3 (the zoom) are unstarted; spec:
      [specs/2026-07-28-tactical-combat-design.md](specs/2026-07-28-tactical-combat-design.md).
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
- [x] ~~`tactical-theme.css:193` (`.panel-header .badge`) would flatten class
      badges~~ — the whole file is **deleted** (688 lines). Unreachability was
      re-verified four ways first: no `css/tactical-theme.css` in any template,
      no `@import` of it from any reachable stylesheet, no route/JS/script
      reference, and no bundler or asset manifest in the repo.
      `tests/test_class_colour_tokens.py` lost its exemption machinery with it —
      an empty exemption set plus a reachability check with nothing to check is
      a guard that passes on nothing. Both surviving tests now apply to every
      stylesheet on disk, reachable or not, which is strictly stronger.
- [ ] `dashboard.css:210`'s `.badge-open` is dead code — grep finds only its
      own declaration.
- [ ] `party-management.css`'s `.rarity-*` block was `!important` and defeated
      the rarity tokens on both screens — fixed, but the same `!important`
      pattern is worth sweeping for elsewhere.
- [ ] `--info` is a literal alias of `--accent` (`tokens.css`), so anything
      reading it shares a hue with `-primary`. Still an open judgement call, but
      lower stakes now: `.tactical-btn-info`, its only button consumer, was
      deleted with the Party Stash button. Remaining readers are `auth.css`,
      `equipment.css` and the character panel's gear-bonus summary.
- [x] ~~Hover glows are inconsistent~~ — `--glow-success` added at the same
      14px/30% formula as `--glow-accent`/`--glow-danger`, and the two hovers
      that hand-rolled their own (including `-danger`'s raw `rgba()`) now read
      tokens. No `--glow-info` was added: its only consumer was the deleted
      `.tactical-btn-info`, and a token with no reader is one more thing to keep
      true. Note this is a real pixel change — both hovers are now brighter and
      slightly wider than before.

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
- [x] ~~`account_anchor.html` has no `is_authenticated` guard~~ — wrapped in
      the same guard shape `base.html` uses on the navbar dropdown it was lifted
      from. Still unreachable today, but the combat screen is expected to want
      `chrome="minimal"` on a route that may not be gated.
- [x] ~~Four decorative icons in the character panel still carry Bootstrap's
      `text-danger`/`text-warning`~~ — six of them, in fact, all in
      `equipment-panel.js`. Bootstrap's hues are a second palette: they do not
      shift between the warm and cold grounds like everything around them. The
      three stat-label icons are decorative (the label beside them already says
      STR/CON/DEX) and now inherit `--ink-muted`; the HP and XP icons and the
      gear-bonus summary keep a colour, taken from tokens.

### Hygiene

- [ ] Flashed messages are dropped under `chrome="minimal"` — nothing flashes
      into `/adventure` today, so a message queued elsewhere surfaces on an
      unrelated later page instead of being lost visibly.
- [ ] `<main class="chrome-minimal">` has no CSS anywhere — dead hook or
      missing rule.
- [x] ~~`.character-card` is dead everywhere, in three media.~~ All cleared:
      four Playwright locators repointed to `.operative-card`, and the rules in
      `glass-theme.css` and `dashboard.css` deleted. One correction to the
      original note — the class was not imaginary: `git log -S` shows
      `dashboard.html` carried `class="card character-card h-100"` until
      `7dfcf1e` renamed it, and the scripts were never updated. Their
      `count() == 0` guard meant the breakage was silent rather than loud.
- [x] ~~Three copies of `_perception_mod_from_stats`~~ — down to one, in
      `dungeon/api_helpers/perception.py`. `treasure.py` now imports it (the two
      bodies were byte-identical, checked with a real diff, so the collapse is
      behaviour-preserving). `dungeon_api.py`'s copy went along with
      `_roll_perception_for_user`, which had no callers — and with
      `_get_party_for_current_user`, which that dead function was the last
      caller of. A comment marks the spot warning against resurrecting the
      latter: it matches the party by **name** and falls back to returning every
      character the user owns, so using it as a guard passes everyone. The run's
      party is `session["last_party_ids"]`.
- [ ] The gear-slot migration's `_unbaggable`
      (`migrations/versions/c9405725c1f4_unify_gear_slots.py:39`) has the same
      uid-less-dict hole the app side just closed with `add_gear_value`. The
      migration is already applied, so it was deliberately left alone; if it is
      ever hardened, mirror that helper's clause rather than diverging again.
- [x] ~~`sql/README.md`'s Files section omits eight `.sql` files~~ — all eight
      added, each described from the file's actual contents. Also recorded the
      dialect split the Loading section silently straddles: the four
      `*_migration.sql` files are Postgres (`SERIAL`, `ON CONFLICT`) while the
      `*_seed.sql` files use SQLite `AUTOINCREMENT`, so the instruction to pipe
      them all into `sqlite3` cannot be right for both.
- [x] ~~`dashboard_helpers` imports inside a per-character loop~~ — hoisted out
      of the loop in `serialize_character_list` (the TODO named
      `render_dashboard`, which calls it), matching `build_party_payload`'s
      approach: function scope, not module scope, since these stay deferred to
      avoid a cycle. One import deliberately stays inside the loop's `try` and
      now says so, so a later pass does not hoist away its degrade-to-empty
      behaviour.
- [ ] Dev-database throwaway accounts from Playwright verification runs; 11
      removed, more will accumulate. Worth a cleanup helper rather than manual
      FK-walking each time.
- [ ] **No JS test tooling** — no jest, no vitest, no `package.json`. A large
      share of the UI is vanilla JS and nothing automated covers it;
      `e2e/test_smoke.py` is the only browser-level net. This is how the dungeon
      silently lost potion consumption during the paper-doll port.

## Party inventory model

The intended model (owner, 2026-07-29): each character carries their own bag;
items can be exchanged between characters **outside** combat; in combat a
character may only use their own inventory; a character who dies and is not
resurrected can be looted, and whatever is left on them is lost.

- [ ] **A second, contradictory shared-container system is still live.**
      `app/routes/party_api.py:115-247` serves `/api/party/<id>/inventory`,
      `/inventory/contribute`, `/inventory/take` and `/inventory/use` against a
      `PartySharedInventory` model (`app/models/party.py:100`), plus
      `/gold/contribute` and `/gold/withdraw` for a shared purse. The dashboard
      renders a whole **"Shared Inventory"** tab for it with a "Party Treasury"
      readout (`dashboard.html:589,614-621`), and `party-management.js:483`
      calls `take`. This is precisely the model the Party Stash button was
      deleted for contradicting, and it is reachable today. Deciding its fate
      is an owner call, not a cleanup: it is an API, a model, a table and a UI
      tab. Note the two "Contribute" buttons have no handler, so the tab is
      already half-dead.

- [x] ~~**No character-to-character item exchange.**~~ Built:
      `POST /api/characters/<cid>/give` with `{to_character_id, uid|slug}`,
      and on the client a bag cell dragged onto a party frame. Guards, in
      order: id coercion (the target id comes from the body, so an unparseable
      one 500s rather than refuses); ownership on both sides; **same-character
      before any inventory is read** — `_char_owned` ends in
      `db.session.get`, so a self-give returns the same mapped object twice
      and reading two lists off it duplicates the item; item present; not in
      combat; neither side downed; same-run; receiver's encumbrance. The
      combat check is one call to `_active_combat_for`, not
      `_reject_if_in_combat` — the latter returns `None` for any slot outside
      `COMBAT_LOCKED_SLOTS`, so it fails *open* for a slotless operation.
      Encumbrance is weighed on a prospective bag rather than via
      `can_add_item`, which looks weight up by catalogue slug and so cannot
      see a procedural instance's own `weight`.
      Client note: bag cells were `draggable="false"` for anything drinkable,
      which made a potion — the likeliest thing anyone hands over — the one
      thing that could not be picked up. All filled cells are draggable now
      and `onSlotDrop` refuses a potion instead, so equipment slots stay
      protected. 13 server tests + 1 browser test; every guard confirmed by
      backing it out.
- [ ] **Whole stacks cannot be split.** A give moves exactly one unit of a
      stack (or one whole instance). Handing over five potions is five drags.
      The drop gesture cannot express a quantity; a shift-drag or a small
      prompt would need designing. `hoard.js` has the same limitation.
- [ ] **The give is dungeon-HUD only.** The dashboard mounts the same panel as
      a `modal-xl` with a backdrop, so the roster cards behind it cannot
      receive a drop. Acceptable today because the hoard tab is already the
      town-side transfer surface, but it means the gesture is not learnable
      from the dashboard.
- [ ] **The give has no keyboard route.** Bag cells were deliberately made
      `role="button" tabindex="0"` with a keydown activator, and page hotkeys
      are suppressed to protect that. A drag-only affordance regresses against
      that standard. The loot-claim dropdown (`adventure.js` +
      `#loot-dropdown-item-template`) is the existing pattern to copy.

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

      **Design decided by the owner, 2026-07-30:**
      - **Expiry rides the existing game clock.** There is already a
        `GameClock` and an `advance_for(action)` cost table driving tick decay,
        so a buff's remaining duration is ticks against that, not a second
        timebase. `status_effects.py` + `apply_tick_decay` are the existing
        machinery to extend rather than parallel.
      - **Combat buffs fall off when combat ends, regardless of the clock.**
        A buff bought for a fight must not survive the fight just because few
        ticks passed. So an effect needs to know whether it is combat-scoped,
        and combat teardown has to clear those — the clock alone is not the
        whole rule.
      - **Durations need a balance pass.** Whatever numbers the first
        implementation picks are a guess until playtested; they belong with the
        other tuning verdicts below rather than being treated as settled.
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
