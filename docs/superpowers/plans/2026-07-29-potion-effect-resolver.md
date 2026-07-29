# Potion Effect Resolver Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One resolver deciding what a potion does, shared by combat and exploration, so a potion behaves identically in both — and so a potion the engine cannot yet express is refused rather than silently destroyed.

**Architecture:** A new pure module, `app/services/item_effects.py`, parses a slug into a typed effect descriptor. `combat_service.player_use_item` and `inventory_api.consume_item` both consume it instead of their current hardcoded slug lists and substring matching. Ownership is verified before any effect is applied, closing an infinite-potion exploit. The combat UI's two fixed buttons become a list of the actor's usable potions, driven by an `item_counts` map that finally counts more than two slugs.

**Tech Stack:** Flask, SQLAlchemy, pytest, vanilla JS (no build step), Playwright for e2e.

**Spec:** [specs/2026-07-28-combat-item-usage-design.md](../specs/2026-07-28-combat-item-usage-design.md) — read its two 2026-07-29 correction sections first; they overturn the original framing.

## Global Constraints

- **The resolver is the only place a slug becomes an effect.** No new substring matching, no second slug table. Adding a family later must be a table entry plus a handler, nothing else.
- **A potion is never consumed unless an effect was applied.** Refuse and keep. This replaces today's behaviour, where 127 of 154 potions are removed from the bag for zero effect.
- **Ownership is verified before the effect is applied**, in both paths. Today the combat path applies first and decrements afterwards inside a swallowing `try/except`, so an empty bag still heals.
- **In combat and out of combat must agree.** Same resolver, same numbers, same clamping. Today `potion-healing` heals 25 in a fight and 5 outside it, unclamped.
- **Restores clamp to the maximum** — `max_hp` / `mana_max` in combat, the character's computed caps out of combat.
- **Player-facing copy uses D&D register** — party, roster, provisions, delve, hoard, spoils. Refusals are sentences a player can read, not machine codes.
- **No new combat mechanics.** The expiring stat-modifier effect kind, `remove_effect`, dynamic initiative, typed damage reaching players and stamina are all explicitly out of scope; see the spec.

## The effect table

Two families resolve to an effect. Everything else resolves to `None` and is refused.

| slug | effect |
|---|---|
| `potion_heal_lN` (N = 1…20) | restore `10 + 5 × (N − 1)` HP → 10 at l1, 105 at l20 |
| `potion_mana_lN` (N = 1…20) | restore `4 + 2 × (N − 1)` MP → 4 at l1, 42 at l20 |
| `potion-healing` (legacy) | restore 25 HP |
| `potion-mana` (legacy) | restore 5 MP |
| `potion-regen` (legacy) | `regen_buff`, 5 ticks, `hp_mult` 3.0, `mp_mult` 3.0 |
| everything else | `None` — refused, not consumed |

The legacy hyphenated slugs keep their **current combat** values so nothing regresses in a fight; out of combat they rise to match, which is the point of unifying. `potion_regen_lN` deliberately resolves to `None` for now — the regen buff's duration and multipliers are duplicated literally in four places (`inventory_api.py:650`, `combat_service.py:1618`, `dungeon_api.py:1776`, `dungeon/room_events.py:171`) and tiering it invites a fifth. Tiered regen is a follow-up once those are folded together.

**These numbers are a first pass.** They are the only balance decision in this plan; record them in the TODO's playtest-verdict section (Task 5) rather than treating them as settled.

## How to run the tests

```bash
export TEST_DATABASE_URL=postgresql://adventure:changeme@localhost:5433/adventure_test
.venv/bin/python -m pytest tests/ -q
```

Foreground, generous timeout. Baseline `820 passed, 3 skipped, 1 xpassed`. `tests/test_camp_regen_buff.py` and `tests/test_camp_supplies_and_cooldown.py` have a known flake together — re-run alone if one fails.

E2E needs a running server (`.venv/bin/python run.py`):

```bash
E2E=1 ADVENTURE_BASE_URL=http://localhost:5000 .venv/bin/python -m pytest e2e -q
```

**Python routes do not hot-reload** — a stale server has produced false-positive checks repeatedly in this project. Confirm the server runs your code, kill it when done, never commit `adventure.pid`. **Do not use `git stash`** — there is an unrelated pre-existing stash belonging to the repo owner.

## File Structure

| File | Change | Responsible for |
|---|---|---|
| `app/services/item_effects.py` | **create** | Slug → effect descriptor. Pure, no DB, no Flask. |
| `app/services/combat_service.py` | modify | `player_use_item`: resolver, ownership-first, refuse-without-consuming; `item_counts` build |
| `app/routes/inventory_api.py` | modify | `consume_item`: same resolver, clamped, stops destroying |
| `app/routes/combat_api.py` | modify | `item_counts` backfill for old sessions |
| `app/templates/combat.html` | modify | Two fixed buttons become a panel |
| `app/static/js/combat.js` | modify | Render the actor's usable potions from `item_counts` |
| `tests/test_item_effect_resolver.py` | **create** | The resolver against all 154 real catalogue slugs |
| `tests/test_potion_use_parity.py` | **create** | Same potion, same effect, in and out of combat |
| `tests/test_combat_actions.py` | modify | The exploit: using without owning |

---

### Task 1: The resolver

A pure module with no Flask and no DB, so it can be tested against every slug in the catalogue without a fixture.

**Files:**
- Create: `app/services/item_effects.py`
- Test: `tests/test_item_effect_resolver.py`

**Interfaces:**
- Consumes: nothing.
- Produces:

  ```python
  resolve_potion_effect(slug: str) -> dict | None
  ```

  Returns `None` when the slug names no implemented effect. Otherwise a dict with a `kind` key and kind-specific fields:

  ```python
  {"kind": "restore_hp", "amount": 35}
  {"kind": "restore_mp", "amount": 12}
  {"kind": "status", "name": "regen_buff", "ticks": 5, "data": {"hp_mult": 3.0, "mp_mult": 3.0}}
  ```

  Also produces `REFUSAL_NO_EFFECT: str` — the player-facing sentence used by both call sites when the resolver returns `None`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_item_effect_resolver.py`:

```python
"""One place decides what a potion does.

Before this, three code paths each guessed. combat_service.player_use_item
matched three hyphenated slugs exactly; inventory_api.consume_item matched
unanchored substrings ("healing", which the catalogue spells "heal"), so 127 of
154 potions were removed from the bag for zero effect; and the two disagreed on
magnitude by 5x for the one slug they shared.

Spec: docs/superpowers/specs/2026-07-28-combat-item-usage-design.md
"""

import pytest

from app.services.item_effects import REFUSAL_NO_EFFECT, resolve_potion_effect


@pytest.mark.parametrize(
    "slug,expected",
    [
        ("potion_heal_l1", {"kind": "restore_hp", "amount": 10}),
        ("potion_heal_l2", {"kind": "restore_hp", "amount": 15}),
        ("potion_heal_l20", {"kind": "restore_hp", "amount": 105}),
        ("potion_mana_l1", {"kind": "restore_mp", "amount": 4}),
        ("potion_mana_l20", {"kind": "restore_mp", "amount": 42}),
        ("potion-healing", {"kind": "restore_hp", "amount": 25}),
        ("potion-mana", {"kind": "restore_mp", "amount": 5}),
    ],
)
def test_implemented_families_resolve(slug, expected):
    assert resolve_potion_effect(slug) == expected


def test_legacy_regen_resolves_to_a_status_effect():
    effect = resolve_potion_effect("potion-regen")

    assert effect["kind"] == "status"
    assert effect["name"] == "regen_buff"
    assert effect["ticks"] == 5
    assert effect["data"] == {"hp_mult": 3.0, "mp_mult": 3.0}


@pytest.mark.parametrize(
    "slug",
    [
        "potion_buff_attack_l3",
        "potion_buff_defense_l1",
        "potion_buff_speed_l20",
        "potion_resist_fire_l2",
        "potion_resist_cold_l1",
        "potion_resist_lightning_l5",
        "potion_resist_poison_l4",
        "potion_antidote_l1",
        "potion_stamina_l3",
        "potion_perception_l5",
        "potion_group_battle_l2",
        "potion_invis_l1",
        "potion_luck_l4",
        "potion_regen_l2",
    ],
)
def test_unimplemented_families_resolve_to_nothing(slug):
    """Refused, not silently destroyed. Each of these needs a mechanic that
    does not exist yet -- see the spec's family table."""
    assert resolve_potion_effect(slug) is None


@pytest.mark.parametrize(
    "slug",
    ["", None, "not-a-potion", "potion_heal", "potion_heal_l", "potion_heal_lx", "sword_of_heal_l3", "POTION_HEAL_L3"],
)
def test_malformed_input_resolves_to_nothing_without_raising(slug):
    assert resolve_potion_effect(slug) is None


def test_tier_is_read_from_the_suffix_not_a_substring():
    """`potion_heal_l11` is tier 11, not tier 1 -- an anchored parse, not a scan."""
    assert resolve_potion_effect("potion_heal_l11")["amount"] == 60


def test_a_refusal_sentence_exists_and_reads_as_prose():
    assert REFUSAL_NO_EFFECT
    assert REFUSAL_NO_EFFECT[0].isupper()
    assert REFUSAL_NO_EFFECT.endswith(".")
    assert "_" not in REFUSAL_NO_EFFECT, "a refusal is prose, not a machine code"
```

Then the catalogue test — the one that stops the resolver drifting from the data:

```python
def test_every_catalogue_potion_either_resolves_or_is_refused(test_app):
    """No potion may raise, and the implemented count must be deliberate.

    This is the guard against the original bug: a slug the resolver does not
    recognise must produce None, never an exception and never a wrong effect.
    """
    from app.models.models import Item

    with test_app.app_context():
        slugs = [i.slug for i in Item.query.filter_by(type="potion").all()]

    assert len(slugs) >= 150, "catalogue shrank unexpectedly; check the seed"

    resolved = {s: resolve_potion_effect(s) for s in slugs}
    implemented = {s: e for s, e in resolved.items() if e is not None}

    # 20 heal + 20 mana + 3 legacy hyphenated
    assert len(implemented) == 43, sorted(implemented)
    assert all(e["kind"] in ("restore_hp", "restore_mp", "status") for e in implemented.values())
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
export TEST_DATABASE_URL=postgresql://adventure:changeme@localhost:5433/adventure_test
.venv/bin/python -m pytest tests/test_item_effect_resolver.py -q
```
Expected: collection error — the module does not exist.

- [ ] **Step 3: Write the resolver**

Create `app/services/item_effects.py`. It must be importable without a Flask app context — no `db`, no models, no `current_app`.

Design notes to honour:

- **Parse the tier by anchoring on the end of the slug**, e.g. `re.fullmatch(r"potion_(?P<family>.+)_l(?P<tier>\d+)", slug)`. A family may itself contain underscores (`buff_attack`, `resist_fire`, `group_battle`), so splitting on `_` and taking a fixed index will not work.
- **Families live in one table**, mapping a family name to a handler that takes the tier and returns the descriptor. Unknown family → `None`. That table is the extension point: adding `buff_attack` later is one entry.
- **Legacy hyphenated slugs get their own small map**, since they carry no tier.
- Guard `None`, non-string, empty, and case: the catalogue is lower-case and matching is exact — do not lower-case the input, because a slug that differs in case is not a slug in this catalogue.
- Return **fresh dicts** each call; callers mutate what they get.
- `REFUSAL_NO_EFFECT` is a module constant, e.g. `"That draught has no effect you can call upon yet."` — D&D register, a full sentence, no underscores.

Document at the top *why* the module exists: three paths guessing, 127 potions destroyed, and a 5x disagreement on the one shared slug.

- [ ] **Step 4: Run the tests to verify they pass**

```bash
.venv/bin/python -m pytest tests/test_item_effect_resolver.py -q
```
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add app/services/item_effects.py tests/test_item_effect_resolver.py
git commit -m "feat(items): one resolver for what a potion does

Three paths each guessed what a slug meant: combat matched three hyphenated
slugs exactly, out-of-combat matched unanchored substrings, and the catalogue
spells it 'heal' where the substring said 'healing' -- so 127 of 154 potions
were consumed for zero effect. This is the single place that decides, tested
against every slug in the catalogue.

heal and mana scale with the _lN tier. Every other family resolves to None and
will be refused rather than destroyed; each needs a combat mechanic that does
not exist yet (see the spec's family table)."
```

---

### Task 2: The combat path

Replace the hardcoded slug block, and fix the exploit while the function is open.

**Files:**
- Modify: `app/services/combat_service.py:1568-1689` (`player_use_item`)
- Test: `tests/test_combat_actions.py` (extend)

**Interfaces:**
- Consumes: `resolve_potion_effect`, `REFUSAL_NO_EFFECT` from Task 1.
- Produces: `player_use_item` returns `{"error": "no_effect", "message": REFUSAL_NO_EFFECT}` for an unimplemented potion and `{"error": "not_carried", "message": ...}` when the actor does not hold it — **in both cases without consuming the item and without ending the turn.**

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_combat_actions.py`:

```python
def test_using_a_potion_you_do_not_have_is_refused(client, ...):
    """The exploit: the effect used to be applied on a slug match, with the
    inventory decrement running afterwards inside a swallowing try/except -- so
    an empty bag healed 25 and burned a turn, repeatably."""
```

Assert: HP unchanged, the turn did **not** advance (`active_index` and `combat_turn` are the same before and after), and the response carries an error.

```python
def test_an_unimplemented_potion_is_refused_and_kept(client, ...):
    """127 of 154 potions had no effect. They must not vanish for nothing."""
```

Give the character `potion_buff_speed_l3`, use it, and assert: the item is still in `items`, HP/mana unchanged, the turn did not advance, and the response's `message` is prose rather than a code.

```python
def test_a_tiered_heal_potion_scales_with_its_suffix(client, ...):
    """potion_heal_l4 restores more than potion_heal_l1."""
```

Match the fixture style already in `tests/test_potions_per_character.py` — it sets up a combat session and posts to `/api/dungeon/combat/<id>/action`, which is the path the existing item tests use.

- [ ] **Step 2: Run to verify they fail**

```bash
.venv/bin/python -m pytest tests/test_combat_actions.py -q
```
Expected: the three new tests FAIL — today an unowned `potion-healing` heals, an unimplemented potion returns `cannot_use`, and `potion_heal_l4` returns `cannot_use`.

- [ ] **Step 3: Reorder so ownership comes first**

In `player_use_item`, restructure to:

1. Resolve the effect from the slug. `None` → return `{"error": "no_effect", "message": REFUSAL_NO_EFFECT}` **before** touching anything.
2. Load the character row and confirm the item is present in `items` **before** applying. Absent → `{"error": "not_carried", "message": "<prose>"}`.
3. Apply the descriptor to the party-snapshot member by `kind`:
   - `restore_hp` → `m["hp"] = min(m.get("max_hp", ...), m.get("hp", 0) + amount)`
   - `restore_mp` → the same against `mana_max`
   - `status` → `replace_effect(m.get("effects", []) or [], name, ticks, **data)`
4. Only then decrement inventory, and **stop swallowing the failure** — if the decrement fails after the effect was applied, that is a real error worth surfacing, not a debug log.
5. Then the existing `phase = "end"` / `_progress_phase` / `_check_end` sequence.

The existing inventory walk handles both bare-string and `{"slug", "qty"}` entries; keep that. Extract the "does this character hold this slug" check so ownership and decrement cannot disagree.

- [ ] **Step 4: Make `item_counts` count every resolvable potion**

`_base_player_snapshot` (`combat_service.py:244-254`) hardcodes two slugs via `_potion_counts_by_character`. It should instead count every slug in the character's inventory for which `resolve_potion_effect` returns non-`None`, so the UI in Task 4 can list them.

Three other sites write the same map and must agree — `_check_end` (`:808-817`), the decrement in `player_use_item` (`:1667-1677`, currently limited to two slugs so `potion-regen` never decrements), and the backfill in `combat_api.py:59-72`. Give them one shared helper rather than four copies of the rule.

- [ ] **Step 5: Run the tests**

```bash
.venv/bin/python -m pytest tests/test_combat_actions.py tests/test_potions_per_character.py tests/test_regen_potion_combat.py tests/test_unconscious_actions.py -q
```
Expected: all PASS, including the existing tests — the legacy slugs keep their current combat values deliberately.

Then the full suite:
```bash
.venv/bin/python -m pytest tests/ -q
```

- [ ] **Step 6: Commit**

```bash
git add app/services/combat_service.py app/routes/combat_api.py tests/test_combat_actions.py
git commit -m "fix(combat): resolve potions properly, and stop the infinite heal

player_use_item applied the effect on a slug string match and decremented the
bag afterwards, inside a try/except that logged at debug and swallowed
everything -- so POSTing use_item with an empty bag healed 25 and burned a turn,
repeatably. The only gate was client-side. Ownership is now checked before the
effect is applied.

The three hardcoded slugs become the shared resolver, so tiered heal and mana
potions work in a fight for the first time. A potion with no implemented effect
is refused with a readable message and kept, rather than consumed for nothing.
item_counts now counts every potion the resolver recognises."
```

---

### Task 3: The out-of-combat path

The same resolver, so the potion does the same thing on both sides of a fight.

**Files:**
- Modify: `app/routes/inventory_api.py:595-653` (`consume_item`)
- Test: `tests/test_potion_use_parity.py`

**Interfaces:**
- Consumes: Task 1's resolver; Task 2's ownership pattern.
- Produces: `POST /api/characters/<id>/consume` returns `{"error": "no_effect", "message": ...}` for an unimplemented potion, leaving the item in the bag.

- [ ] **Step 1: Write the failing test**

Create `tests/test_potion_use_parity.py`. The point is the property, not the numbers:

```python
"""A potion does the same thing in a fight and out of one.

potion-healing used to heal 25 in combat and 5 outside it, unclamped -- while a
comment in combat_service claimed the two had been aligned deliberately. And
potion_heal_lN was destroyed for zero effect out of combat, because the matcher
looked for the substring "healing" and the catalogue spells it "heal".
"""
```

Cover:
- `potion_heal_l4` out of combat restores the resolver's amount, and the same amount in combat.
- An out-of-combat restore **clamps** at the character's max rather than exceeding it.
- `potion_buff_speed_l3` is refused out of combat and **stays in the bag** — the regression test for the 127 destroyed potions.
- `potion-healing` restores 25 out of combat now, matching combat.

- [ ] **Step 2: Run to verify it fails**

Expected: the tiered potion is consumed with no heal, and the legacy potion heals 5.

- [ ] **Step 3: Rewrite the effect block**

Replace `inventory_api.py:613-628`'s substring cascade with the resolver. Then:

- Confirm the item is in the bag **before** applying, as in Task 2.
- Clamp restores to the character's computed maxima. `character_stats.compute_hp_mana_max(ch)` is the canonical source — use it rather than a literal.
- Keep the `type == "potion"` gate at `:610` for now; scrolls and rations are separately dead (not equippable, not consumable) and are their own chunk.
- Keep the existing `CharacterStatusEffect` write for the `status` kind (`:644-653`), but drive its name, duration and data from the descriptor instead of literals.

- [ ] **Step 4: Run the tests**

```bash
.venv/bin/python -m pytest tests/test_potion_use_parity.py tests/test_bag_potion_consumption.py tests/test_regen_potion_out_of_combat.py -q
.venv/bin/python -m pytest tests/ -q
```
Expected: all PASS. Note `tests/test_bag_potion_consumption.py` asserts current out-of-combat behaviour — if it pins the old `+5` heal for `potion-healing`, updating it is correct and the commit message should say so.

- [ ] **Step 5: Commit**

```bash
git add app/routes/inventory_api.py tests/test_potion_use_parity.py tests/test_bag_potion_consumption.py
git commit -m "fix(inventory): one potion, one effect, in or out of a fight

consume_item matched unanchored substrings -- 'healing' against a catalogue that
spells it 'heal' -- so all twenty potion_heal_lN were removed from the bag for
zero HP, along with every other unmatched family: 127 of 154 potions destroyed
for nothing. It also healed 5 where combat healed 25, unclamped, while a comment
claimed the two were aligned.

Both paths now share the resolver, clamp to the character's real maxima, and
refuse rather than destroy."
```

---

### Task 4: The combat item panel

Two fixed buttons become the actor's usable potions.

**Files:**
- Modify: `app/templates/combat.html:23-32`
- Modify: `app/static/js/combat.js:296`, `:417-470`, `:572-581`
- Test: `e2e/test_smoke.py` (extend)

**Interfaces:**
- Consumes: the widened `item_counts` from Task 2 — `{slug: {char_id: count}}`.
- Produces: a panel listing the active character's resolvable potions with counts.

- [ ] **Step 1: Replace the two buttons**

In `combat.html`, replace the heal/mana `.btn-group-combat` with a single container the client fills. Keep it inside `#combat-action-panel`, which `combat.js:407-411` reparents under the active character's card each render — so the panel must survive being moved.

- [ ] **Step 2: Render from `item_counts`**

In `combat.js`, replace the two hardcoded button branches (`:417-470`) with a render over `item_counts` for the active character:

- One entry per slug the actor holds, with its count visible — **not** only in a `title`, which is where the count lives today.
- Zero-count entries are omitted rather than shown disabled; the map only contains what the resolver recognises, so an entry existing means it is usable.
- Group by effect kind so a bag of twenty potions is not a wall. The name is available on the item; a `restore_hp` group and a `restore_mp` group is enough at this scale.
- Keyboard-reachable: real `<button>` elements, consistent with the existing action buttons.
- Preserve the existing behaviours in that block: the mana entry stays hidden for `MANALESS_CLASSES` (`:420-423`), and listeners are re-bound by clone-and-replace each render (`:467-469`).

`doAction` (`:572-581`) already posts `{slug}` to `/use_item`; it needs the slug from the clicked entry rather than a literal.

**Surface refusals.** Today a failed item use is silent: the client only re-renders when `j.state` exists (`:617`), inside a bare `catch {}`. The new `no_effect` and `not_carried` responses carry a `message` — show it, or the refuse-don't-consume decision is invisible to the player.

- [ ] **Step 3: Extend the e2e smoke**

Add a case that opens a combat session, asserts the potion panel lists an entry with a count, clicks it, and asserts a `/use_item` request carrying that slug — mirroring the `page.expect_request` pattern already used for the `uid` equip assertion. Seed via the existing helper in `e2e/test_smoke.py` rather than inventing a second seeding path.

- [ ] **Step 4: Verify**

```bash
.venv/bin/python -m pytest tests/ -q
```
Then with a server running your code:
```bash
E2E=1 ADVENTURE_BASE_URL=http://localhost:5000 .venv/bin/python -m pytest e2e -q
```

Then play it: enter a fight holding several potion tiers, confirm the panel lists them with counts, drink one and watch HP move and the count drop, and try an unimplemented potion from the bag to confirm the refusal is legible and the item survives.

- [ ] **Step 5: Commit**

```bash
git add app/templates/combat.html app/static/js/combat.js e2e/test_smoke.py
git commit -m "feat(combat): list the potions you actually carry

The two fixed buttons only ever knew potion-healing and potion-mana, so looted
potions were invisible in a fight and potion-regen -- implemented server-side --
had no button at all. The panel now lists what the actor carries, with counts
visible rather than hidden in a tooltip, and surfaces refusals that were
previously silent."
```

---

### Task 5: Record what is still missing

The content gap is now visible to players; make it visible in the backlog too.

**Files:**
- Modify: `docs/superpowers/TODO.md`

- [ ] **Step 1: Close the item-usage entry and open what it revealed**

Mark the playtest item done, noting that 43 of 154 potions resolve and why the rest do not. Then add, under **Gameplay — waiting on playtest verdicts**:

```markdown
- [ ] Potion tier curve: heal is `10 + 5×(N−1)` (10→105), mana is `4 + 2×(N−1)`
      (4→42). First pass, never playtested — the only balance numbers in the
      resolver.
```

And under **Engineering**, the mechanics each blocked family needs — an expiring stat-modifier effect kind (unblocks `buff_attack`, `buff_defense`, `resist_fire` at once), a `remove_effect` primitive plus a `CharacterStatusEffect` delete for `antidote`, dynamic initiative for `buff_speed`, typed damage reaching players for the other three resists, and the fact that `stamina` and `perception` have no combat mechanic at all. Note `stun` has a handler nothing can trigger, and that the regen buff's duration and multipliers are duplicated in four places.

- [ ] **Step 2: Commit**

```bash
git add docs/superpowers/TODO.md
git commit -m "docs(todo): potion resolver landed; record the mechanics still missing"
```

---

## Self-Review

**Spec coverage** — against the two 2026-07-29 correction sections:

| Spec requirement | Task |
|---|---|
| One resolver, shared by both paths | 1, 2, 3 |
| `heal` / `mana` scale with the `_lN` tier | 1 |
| Unimplemented family refuses and keeps the item | 1 (descriptor), 2 (combat), 3 (exploration) |
| Ownership verified before the effect is applied | 2, 3 |
| Restores clamp to maxima in both paths | 2, 3 |
| Refusals are prose, not machine codes | 1 (constant), 4 (surfaced) |
| `item_counts` carries more than two slugs | 2 |
| UI lists the actor's usable potions with counts | 4 |
| No new combat mechanics | all — the blocked families are recorded in 5, not built |

**Type consistency:** `resolve_potion_effect(slug) -> dict | None` is defined in Task 1's Interfaces and called in Tasks 2 and 3. The three `kind` values (`restore_hp`, `restore_mp`, `status`) are produced in Task 1 and dispatched on in Task 2 Step 3 and Task 3 Step 3. `REFUSAL_NO_EFFECT` is defined in Task 1 and consumed in Tasks 2, 3 and 4.

**Known risks:**

1. **Task 2 restructures a 120-line function that four callers reach** — the REST route, `dungeon_api`'s action dispatcher, and the socket handler. Only the `dungeon_api` path has test coverage today. The new tests should go through the same path the existing ones use, and the REST route's own lack of coverage is worth noting rather than fixing here.
2. **`item_counts` is written at four sites and read at one.** Task 2 Step 4 consolidates the rule, but a missed site means the UI and the server disagree about what the player is carrying — and the count is what the panel renders from.
3. **The balance numbers are invented.** They are the plan's only unforced judgement, and Task 5 records them as unverified rather than pretending otherwise.
