# Run/Extraction Surface Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the two remaining gaps in the dungeon run/extraction UI: a player can loot a
downed ally's bag from the extraction modal, and extraction success shows what was actually
secured to the Hoard instead of a bare alert.

**Architecture:** Two small backend changes (`pool_run_haul` and `extract_party` return the
totals they already compute but currently discard) followed by two frontend changes to the
existing extraction modal in `adventure.html` (no new files, no new endpoints — the
loot-body endpoint already exists from Spec 2).

**Tech Stack:** Python/Flask/SQLAlchemy (backend), vanilla JS + Bootstrap modal (frontend),
pytest (backend tests).

## Global Constraints

- Floor-loot pickup and the extraction screen's core flow are already complete and must not
  be modified except where this plan explicitly says so (the success-confirmation panel).
- `app/templates/adventure.html`'s extraction modal already uses bare `alert()` for its other
  error paths (status-load failure, "must select at least one character") — match that
  existing style for new error paths in this plan; do not introduce a new toast/notification
  system.
- Money must render via `format_copper`-produced `*_display` strings, never a hand-rolled
  number — applies to the new `secured.copper_display` field end to end.
- Out of scope: loot-body's documented same-run guard gap, and `combat_service`'s dungeon
  instance resolution heuristic — neither is touched by this plan.
- Spec reference: `docs/superpowers/specs/2026-06-17-run-extraction-surface-design.md`.

---

## File Structure

- **Modify `app/economy/hoard_service.py`** — `pool_run_haul` starts returning what it moved.
- **Modify `app/services/extraction_service.py`** — `extract_party` aggregates those returns
  into the result dict under a new `secured` key.
- **Modify `tests/test_hoard.py`** and **`tests/test_extraction_economy.py`** — extend
  existing tests for the new return values (no new test files; these are small additions to
  files that already test these exact functions).
- **Modify `app/templates/adventure.html`** — extraction modal gets a success-confirmation
  panel and a per-dead-character "Loot Body" dropdown.

---

### Task 1: `pool_run_haul` returns what it moved

**Files:**
- Modify: `app/economy/hoard_service.py:70-76`
- Test: `tests/test_hoard.py`

**Interfaces:**
- Produces: `pool_run_haul(hoard: Hoard, character: Character) -> dict` returning
  `{"copper": int, "items": int}` — `copper` is the amount moved (the character's prior
  `gold` value), `items` is `len(bag)` (the number of bag entries moved, where each entry is
  either a stack `{slug, qty}` or a single gear instance — entries, not individual stacked
  units). Consumed by Task 2.

- [ ] **Step 1: Write the failing test**

In `tests/test_hoard.py`, extend the existing `test_pool_run_haul_moves_bag_and_purse_then_zeroes`
test (it already exercises this exact function) to also assert on the return value:

```python
def test_pool_run_haul_moves_bag_and_purse_then_zeroes():
    user = create_user(_uname("hoarder_f"))
    char = create_character(user, name="Runner", items=[{"slug": "potion_heal_l1", "qty": 1}])
    char.gold = 500  # run-purse (copper)
    hoard = Hoard.get_or_create(user.id)
    moved = hoard_service.pool_run_haul(hoard, char)
    assert moved == {"copper": 500, "items": 1}
    assert hoard.copper == 500
    assert any(i.get("slug") == "potion_heal_l1" for i in json.loads(hoard.items_json))
    assert char.gold == 0
    assert json.loads(char.items) == []
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd /home/winter/work/Adventure && .venv/bin/python -m pytest tests/test_hoard.py::test_pool_run_haul_moves_bag_and_purse_then_zeroes -v`
Expected: FAIL — `assert None == {"copper": 500, "items": 1}` (current `pool_run_haul`
returns `None`).

- [ ] **Step 3: Implement the return value**

In `app/economy/hoard_service.py`, replace:

```python
def pool_run_haul(hoard: Hoard, character: Character) -> None:
    """Move a character's entire bag + run-purse into the hoard, then zero them."""
    bag = _load(character.items)
    deposit_items(hoard, bag)
    deposit_copper(hoard, character.gold or 0)
    character.items = "[]"
    character.gold = 0
```

with:

```python
def pool_run_haul(hoard: Hoard, character: Character) -> dict:
    """Move a character's entire bag + run-purse into the hoard, then zero them.

    Returns {"copper": int, "items": int} — what was moved, for caller-side reporting.
    """
    bag = _load(character.items)
    copper = character.gold or 0
    deposit_items(hoard, bag)
    deposit_copper(hoard, copper)
    character.items = "[]"
    character.gold = 0
    return {"copper": copper, "items": len(bag)}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd /home/winter/work/Adventure && .venv/bin/python -m pytest tests/test_hoard.py::test_pool_run_haul_moves_bag_and_purse_then_zeroes -v`
Expected: PASS

- [ ] **Step 5: Run the full hoard test file to check for regressions**

Run: `cd /home/winter/work/Adventure && .venv/bin/python -m pytest tests/test_hoard.py -v`
Expected: all tests PASS (this function has other callers in the same file's test suite —
none of them assert on the return value today, so none should break).

- [ ] **Step 6: Commit**

```bash
git add app/economy/hoard_service.py tests/test_hoard.py
git commit -m "feat(extraction): pool_run_haul reports copper/items moved"
```

---

### Task 2: `extract_party` aggregates secured totals into the result

**Files:**
- Modify: `app/services/extraction_service.py:8-15` (imports), `:88-120` (the
  `pool_run_haul` call site and the `result` dict construction)
- Test: `tests/test_extraction_economy.py`

**Interfaces:**
- Consumes: `hoard_service.pool_run_haul(hoard, char) -> {"copper": int, "items": int}`
  (Task 1).
- Produces: `extract_party(...)`'s `result` dict gains a `"secured"` key:
  `{"copper": int, "copper_display": str, "items": int}` — `copper`/`items` are the sum
  across all extracting characters in this call; `copper_display` is
  `format_copper(copper)`. Consumed by Task 3 (frontend reads `result.secured`).

- [ ] **Step 1: Write the failing test**

In `tests/test_extraction_economy.py`, extend the existing
`test_extract_pools_bag_and_purse_into_hoard` test to assert on the new `secured` key, and
add a second test covering aggregation across two characters:

```python
def test_extract_pools_bag_and_purse_into_hoard():
    user = create_user("extr_a_" + uuid.uuid4().hex[:8])
    inst = _instance_for(user)
    char = create_character(user, name="A", items=[{"slug": "potion_heal_l1", "qty": 2}])
    char.gold = 300
    char.locked_dungeon_id = inst.id
    db.session.commit()

    ok, msg, result = extraction_service.extract_party(inst, [char.id], user.id)
    assert ok, msg
    assert result["secured"] == {"copper": 300, "copper_display": "3s", "items": 1}
    hoard = Hoard.query.filter_by(user_id=user.id).first()
    assert hoard.copper == 300
    assert any(i.get("slug") == "potion_heal_l1" for i in json.loads(hoard.items_json))
    db.session.refresh(char)
    assert char.gold == 0
    assert json.loads(char.items) == []


def test_extract_secured_totals_aggregate_across_party():
    user = create_user("extr_secured_" + uuid.uuid4().hex[:8])
    inst = _instance_for(user)
    char_a = create_character(user, name="A", items=[{"slug": "potion_heal_l1", "qty": 1}])
    char_a.gold = 200
    char_a.locked_dungeon_id = inst.id
    char_b = create_character(user, name="B", items=[{"slug": "potion_heal_l1", "qty": 1}, {"slug": "torch", "qty": 1}])
    char_b.gold = 50
    char_b.locked_dungeon_id = inst.id
    db.session.commit()

    ok, msg, result = extraction_service.extract_party(inst, [char_a.id, char_b.id], user.id)
    assert ok, msg
    assert result["secured"] == {"copper": 250, "copper_display": "2s 50c", "items": 3}
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd /home/winter/work/Adventure && .venv/bin/python -m pytest tests/test_extraction_economy.py::test_extract_pools_bag_and_purse_into_hoard tests/test_extraction_economy.py::test_extract_secured_totals_aggregate_across_party -v`
Expected: FAIL — `KeyError: 'secured'` (the `result` dict doesn't have that key yet).

- [ ] **Step 3: Add the `format_copper` import**

In `app/services/extraction_service.py`, replace:

```python
from app import db
from app.economy import hoard_service
from app.models.dungeon_instance import DungeonInstance
from app.models.hoard import Hoard
from app.models.models import Character
```

with:

```python
from app import db
from app.economy import hoard_service
from app.economy.currency import format_copper
from app.models.dungeon_instance import DungeonInstance
from app.models.hoard import Hoard
from app.models.models import Character
```

- [ ] **Step 4: Aggregate the secured totals**

Replace:

```python
        # Pool this character's run haul (bag + run-purse) into the hoard
        hoard_service.pool_run_haul(hoard, char)

    # Mark left behind characters as permadeath
    for char in left_behind_chars:
        char.permadeath = True
        char.locked_in_dungeon = False
        char.locked_dungeon_id = None

    db.session.commit()

    result = {
        "extracted": [c.name for c in extracting_chars],
        "left_behind": [c.name for c in left_behind_chars],
        "penalties": penalties,
        "early_extraction": early_extraction,
    }
```

with:

```python
        # Pool this character's run haul (bag + run-purse) into the hoard
        moved = hoard_service.pool_run_haul(hoard, char)
        secured_copper += moved["copper"]
        secured_items += moved["items"]

    # Mark left behind characters as permadeath
    for char in left_behind_chars:
        char.permadeath = True
        char.locked_in_dungeon = False
        char.locked_dungeon_id = None

    db.session.commit()

    result = {
        "extracted": [c.name for c in extracting_chars],
        "left_behind": [c.name for c in left_behind_chars],
        "penalties": penalties,
        "early_extraction": early_extraction,
        "secured": {
            "copper": secured_copper,
            "copper_display": format_copper(secured_copper),
            "items": secured_items,
        },
    }
```

This requires initializing the two accumulators before the loop that contains the
`pool_run_haul` call. Replace:

```python
    hoard = Hoard.get_or_create(user_id)

    # Apply penalties to extracting characters
    for char in extracting_chars:
```

with:

```python
    hoard = Hoard.get_or_create(user_id)
    secured_copper = 0
    secured_items = 0

    # Apply penalties to extracting characters
    for char in extracting_chars:
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd /home/winter/work/Adventure && .venv/bin/python -m pytest tests/test_extraction_economy.py::test_extract_pools_bag_and_purse_into_hoard tests/test_extraction_economy.py::test_extract_secured_totals_aggregate_across_party -v`
Expected: PASS

- [ ] **Step 6: Run the full extraction test files to check for regressions**

Run: `cd /home/winter/work/Adventure && .venv/bin/python -m pytest tests/test_extraction_economy.py tests/test_extraction.py -v`
Expected: all tests PASS.

- [ ] **Step 7: Commit**

```bash
git add app/services/extraction_service.py tests/test_extraction_economy.py
git commit -m "feat(extraction): aggregate secured copper/items into extract_party result"
```

---

### Task 3: Secured-to-hoard confirmation panel

**Files:**
- Modify: `app/templates/adventure.html:502-524` (the extraction success/failure handler)

**Interfaces:**
- Consumes: `POST /api/dungeon/extraction/extract`'s JSON response, now including
  `result.secured = {copper, copper_display, items}` (Task 2). Falls back gracefully if
  `result.secured` is absent (e.g. mid-deploy version skew).

- [ ] **Step 1: Replace the success/failure handler**

In `app/templates/adventure.html`, replace:

```javascript
          try {
            const resp = await fetch('/api/dungeon/extraction/extract', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ character_ids: selectedChars })
            });

            const data = await resp.json();

            if (data.success) {
              extractionModal.hide();
              alert(data.message);
              // Reload page to reflect changes
              window.location.reload();
            } else {
              alert(data.error || 'Extraction failed');
            }
          } catch (err) {
            console.error('Extraction failed:', err);
            alert('Extraction failed');
          }
```

with:

```javascript
          try {
            const resp = await fetch('/api/dungeon/extraction/extract', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ character_ids: selectedChars })
            });

            const data = await resp.json();

            if (data.success) {
              const secured = data.result && data.result.secured;
              const summary = secured
                ? `Secured ${secured.copper_display} and ${secured.items} item(s) to the Hoard.`
                : '';
              const statusDiv = document.getElementById('extraction-status');
              statusDiv.classList.remove('d-none');
              document.getElementById('extraction-characters').classList.add('d-none');
              statusDiv.innerHTML = `
                <div class="alert alert-success">
                  <strong>${data.message}</strong>
                  ${summary ? `<div class="mt-1">${summary}</div>` : ''}
                </div>`;
              document.getElementById('btn-confirm-extraction').classList.add('d-none');
              setTimeout(() => { window.location.href = '/dashboard'; }, 1800);
            } else {
              alert(data.error || 'Extraction failed');
            }
          } catch (err) {
            console.error('Extraction failed:', err);
            alert('Extraction failed');
          }
```

- [ ] **Step 2: Syntax-check the inline script**

This is an inline `<script>` block inside a Jinja template, so there's no standalone `.js`
file to run `node --check` against. Instead, confirm the template still parses:

Run: `cd /home/winter/work/Adventure && .venv/bin/python -c "
from app import create_app
app = create_app()
with app.app_context():
    app.jinja_env.get_template('adventure.html')
    print('TEMPLATE_OK')
"`
Expected: `TEMPLATE_OK` printed, no `TemplateSyntaxError`.

- [ ] **Step 3: Manual verification**

Use the `run`/`verify` skills with a live browser: start a dungeon run, accumulate some bag
items and run-purse copper on at least one character, open the extraction modal, and
extract. Confirm:
- The modal shows a green success panel with the extraction message and a
  "Secured Xg Ys Zc and N item(s) to the Hoard." line (exact wording depends on
  `copper_display`'s tiers — e.g. `"3s"` for 300 copper, no zero tiers shown).
- After ~1.8s the page redirects to `/dashboard` (not a hard reload of the dungeon page).
- Extracting with zero bag items and zero run-purse copper shows
  "Secured 0c and 0 item(s) to the Hoard." rather than blank/undefined text (verify
  `format_copper(0)` returns `"0c"`, confirmed in `app/economy/currency.py`'s docstring).

If live-browser verification isn't possible in your environment, perform Step 2 rigorously,
read the inserted markup carefully, note in your report that live-browser verification was
not performed, and rely on the controller to do the live check afterward.

- [ ] **Step 4: Commit**

```bash
git add app/templates/adventure.html
git commit -m "feat(extraction-ui): show secured-to-hoard confirmation instead of a bare alert"
```

---

### Task 4: Loot Body action in the extraction modal

**Files:**
- Modify: `app/templates/adventure.html:458-475` (the character-selection-list builder)

**Interfaces:**
- Consumes: the existing `POST /api/dungeon/loot-body` endpoint (`app/routes/hoard_api.py`,
  Spec 2 — unchanged), body `{downed_id: int, survivor_id: int}`, response
  `{success: true}` or `{error: "..."}`. Also consumes `data.characters` (the array already
  fetched from `GET /api/dungeon/extraction/status` by the surrounding code — each entry has
  `id`, `name`, `level`, `is_dead`, `permadeath`).

- [ ] **Step 1: Add the Loot Body dropdown to each dead character's row**

In `app/templates/adventure.html`, replace the character-list-building loop:

```javascript
              data.characters.forEach(char => {
                const div = document.createElement('div');
                div.className = 'form-check';
                div.innerHTML = `
              <input class="form-check-input extraction-char-check" type="checkbox"
                     value="${char.id}" id="extract-char-${char.id}" checked>
              <label class="form-check-label" for="extract-char-${char.id}">
                ${char.name} (Level ${char.level})
                ${char.is_dead ? '<span class="badge bg-danger ms-1">DEAD</span>' : ''}
                ${char.permadeath ? '<span class="badge bg-dark ms-1">PERMADEATH</span>' : ''}
              </label>
            `;
                charList.appendChild(div);
              });
```

with:

```javascript
              const livingChars = data.characters.filter(c => !c.is_dead);

              data.characters.forEach(char => {
                const div = document.createElement('div');
                div.className = 'form-check d-flex align-items-center justify-content-between';

                const labelHtml = `
              <div>
                <input class="form-check-input extraction-char-check" type="checkbox"
                       value="${char.id}" id="extract-char-${char.id}" checked>
                <label class="form-check-label" for="extract-char-${char.id}">
                  ${char.name} (Level ${char.level})
                  ${char.is_dead ? '<span class="badge bg-danger ms-1">DEAD</span>' : ''}
                  ${char.permadeath ? '<span class="badge bg-dark ms-1">PERMADEATH</span>' : ''}
                </label>
              </div>`;

                let lootBodyHtml = '';
                if (char.is_dead && livingChars.length > 0) {
                  lootBodyHtml = `
              <div class="dropdown">
                <button class="btn btn-sm btn-outline-warning dropdown-toggle" type="button"
                        data-bs-toggle="dropdown" id="loot-body-btn-${char.id}">
                  Loot Body
                </button>
                <ul class="dropdown-menu">
                  ${livingChars.map(lc => `<li><a class="dropdown-item loot-body-target"
                      href="#" data-downed-id="${char.id}" data-survivor-id="${lc.id}">${lc.name}</a></li>`).join('')}
                </ul>
              </div>`;
                }

                div.innerHTML = labelHtml + lootBodyHtml;
                charList.appendChild(div);
              });

              charList.querySelectorAll('.loot-body-target').forEach(link => {
                link.addEventListener('click', async (ev) => {
                  ev.preventDefault();
                  const downedId = parseInt(link.getAttribute('data-downed-id'), 10);
                  const survivorId = parseInt(link.getAttribute('data-survivor-id'), 10);
                  const btn = document.getElementById(`loot-body-btn-${downedId}`);
                  try {
                    const r = await fetch('/api/dungeon/loot-body', {
                      method: 'POST',
                      headers: { 'Content-Type': 'application/json' },
                      body: JSON.stringify({ downed_id: downedId, survivor_id: survivorId })
                    });
                    const res = await r.json();
                    if (r.ok && res.success) {
                      btn.outerHTML = '<span class="badge bg-secondary">Looted</span>';
                      document.dispatchEvent(new CustomEvent('mud-characters-state-invalidated', { detail: { character_id: survivorId } }));
                    } else {
                      alert(res.error || 'Loot failed');
                    }
                  } catch (err) {
                    console.error('Loot body failed:', err);
                    alert('Loot failed (network error)');
                  }
                });
              });
```

- [ ] **Step 2: Template syntax check**

Run: `cd /home/winter/work/Adventure && .venv/bin/python -c "
from app import create_app
app = create_app()
with app.app_context():
    app.jinja_env.get_template('adventure.html')
    print('TEMPLATE_OK')
"`
Expected: `TEMPLATE_OK` printed, no `TemplateSyntaxError`.

- [ ] **Step 3: Manual verification**

Use the `run`/`verify` skills with a live browser: get a party into a dungeon run with one
downed character (carrying at least one bag item) and at least one living character, then
open the extraction modal. Confirm:
- The downed character's row shows a "Loot Body" dropdown listing the living character(s) by
  name.
- A character with no living party members shows no "Loot Body" control (not a disabled one).
- A character that is not dead shows no "Loot Body" control.
- Clicking a target name transfers the bag (verify via the Equipment modal afterward showing
  the item on the survivor) and the button is replaced with a "Looted" badge.
- A second click attempt is impossible (button replaced, not just disabled) — confirms no
  double-loot path through this UI.

If live-browser verification isn't possible in your environment, perform Step 2 rigorously,
read the inserted markup/logic carefully against the brief, note in your report that
live-browser verification was not performed, and rely on the controller to do the live check
afterward.

- [ ] **Step 4: Commit**

```bash
git add app/templates/adventure.html
git commit -m "feat(extraction-ui): add loot-body action for downed party members"
```

---

## Plan Self-Review Notes

- **Spec coverage:** Backend totals (Goal 1 → Tasks 1-2) ✅, secured-to-hoard confirmation
  (Goal 2 → Task 3) ✅, Loot Body action (Goal 3 → Task 4) ✅. Non-goals (same-run guard,
  combat instance resolution, floor-loot/extraction-core untouched) correctly excluded.
- **Type/name consistency check:** `pool_run_haul`'s return shape `{"copper": int, "items":
  int}` (Task 1) is consumed identically in Task 2's `moved["copper"]`/`moved["items"]`.
  `result["secured"]` shape `{"copper", "copper_display", "items"}` (Task 2) is consumed
  identically in Task 3's `secured.copper_display`/`secured.items`. Task 4 is independent of
  Tasks 1-3 (uses the pre-existing `data.characters` and the pre-existing `/api/dungeon/
  loot-body` endpoint) — no shared state with the other tasks beyond both editing the same
  template file in different functions, so task order between 3 and 4 doesn't matter, but
  they're sequenced 3-then-4 to keep each diff small and reviewable.
- **No placeholders:** every step has complete, runnable code, exact test code with concrete
  assertions, and exact commands with expected output.
