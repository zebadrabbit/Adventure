# Run/Extraction Surface: Loot-Body UI + Secured-to-Hoard Confirmation — Design

**Date:** 2026-06-17
**Status:** Design only — not yet planned/implemented.
**Part of:** Spec 4b (UI Surfacing), third sub-spec.

## Context

Re-auditing the dungeon view (`app/templates/adventure.html`, `app/static/js/adventure.js`)
against the original Spec 4 "run/extraction surface" backlog item found most of it already
built:
- **Floor-loot pickup** (`POST /api/dungeon/loot/claim/<id>`) is fully wired —
  `adventure.js`'s search-result UI already lets a player assign found loot to a party
  member via a dropdown (`adventure.js:680-755`).
- **Extraction screen** (`GET /api/dungeon/extraction/status`,
  `POST /api/dungeon/extraction/extract`) is fully wired — `adventure.html:390-526` has a
  working modal listing party characters with DEAD/PERMADEATH badges, early-extraction
  penalty warnings, and a confirm action.

Two real gaps remain, both small and centered on the same extraction modal:
1. **Loot-body has no UI at all.** The backend (`POST /api/dungeon/loot-body`, Spec 2) lets
   a living character take a downed ally's bag, but nothing in the frontend calls it — a
   downed character's items are simply abandoned unless the player happens to know the raw
   API exists.
2. **No "secured to hoard" confirmation.** Extraction success just does
   `alert(data.message)` (a plain string like `"Extracted 2 character(s)"`) — it doesn't
   tell the player what was actually secured (copper, item count), even though the backend
   (`extraction_service.extract_party` → `hoard_service.pool_run_haul`) already computes
   exactly that per character; it's just discarded instead of returned.

This sub-spec closes both gaps. It includes one small, justified backend change (Gap 2
requires the extraction result to actually carry the secured totals — they're computed but
thrown away today) — everything else is frontend-only.

## Goals
1. `pool_run_haul` returns what it moved (copper amount, item count) instead of `None`;
   `extract_party` aggregates this across all extracting characters into the result dict.
2. The extraction modal, on success, replaces the current `alert(data.message)` with an
   in-modal confirmation panel showing the extracted/left-behind character names (already
   known to the JS) plus the newly-available secured totals (`"Secured 4g 12s to the Hoard,
   plus 7 items."`, using `copper_display`-style formatting), before reloading the page.
3. The extraction modal's character list gains a **"Loot Body"** action next to any `DEAD`
   character: clicking it offers a dropdown of the dungeon's living characters (same `chars`
   list the modal already has, filtered to `!is_dead`); picking one calls
   `POST /api/dungeon/loot-body {downed_id, survivor_id}`. On success, the DEAD character's
   badge gains a "Looted" indicator and the action is disabled (idempotent re-loot just moves
   an empty bag — harmless, but disabling avoids a confusing repeat click).

## Non-goals
- Fixing loot-body's documented same-run guard gap (tracked separately in project memory —
  out of scope here; this sub-spec only adds the missing UI for the existing endpoint).
- Floor-loot pickup and the extraction screen's core flow — both already complete, untouched
  except for the success-confirmation change in Goal 2.
- Any change to `combat_service`'s "most recent DungeonInstance" resolution (separate known
  issue, unrelated to this work).

## Backend change (Gap 2)

`app/economy/hoard_service.py::pool_run_haul`:

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

`app/services/extraction_service.py::extract_party` aggregates the per-character return
values across the loop that already calls `pool_run_haul`, and adds to `result`. This
requires adding `from app.economy.currency import format_copper` to this file's imports
(not currently imported there):

```python
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

This is the only backend change in this sub-spec — both functions already do the underlying
work; this just stops discarding the result.

## UI design

### Secured-to-hoard confirmation
Replace the extraction success handler's `alert(data.message); window.location.reload();`
(`adventure.html:511-515`) with an inline panel rendered into the existing
`#extraction-status` div before reloading:

```javascript
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
}
```

(Redirecting to `/dashboard` rather than reloading the dungeon page, since extraction ends
the run — this matches the existing Hearth-and-abandon flow's redirect at
`adventure.html` line ~243, which already does the same `setTimeout` → `/dashboard` pattern.)

### Loot Body action
In the character-selection-list builder (`adventure.html:462-475`), for each `char.is_dead`
entry, append a "Loot Body" dropdown button (Bootstrap dropdown, matching the existing
floor-loot claim dropdown pattern from `adventure.js`) populated with the *other* characters
in `data.characters` where `!is_dead`. Selecting one POSTs to `/api/dungeon/loot-body`:

```javascript
fetch('/api/dungeon/loot-body', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ downed_id: deadChar.id, survivor_id: survivor.id })
})
.then(r => r.json())
.then(res => {
  if (res.success) {
    // mark this row as looted: disable the button, add a "Looted" badge
  } else {
    alert(res.error || 'Loot failed');
  }
});
```

If `data.characters` contains no dead entries, or no living entries to loot into, the Loot
Body button doesn't render for that row (no dead chars → nothing to loot; no living chars →
nowhere to send it, matches the existing pattern of hiding inapplicable controls rather than
showing a disabled one with no explanation).

## Error handling
- Loot-body failure (character not found / not owned / not dead — see `hoard_api.py`):
  surface `res.error` via `alert()`, consistent with the rest of this modal's existing error
  style (it already uses bare `alert()` for extraction-status load failure and for "must
  select at least one character"). Introducing a toast system here would be a larger,
  unrelated change to this file's conventions — out of scope.
- Extraction success path: if `data.result.secured` is missing (e.g. hitting an older cached
  JS bundle against a newer backend, or vice versa, mid-deploy), the summary line is simply
  omitted (`summary` becomes `''`) rather than showing broken text — the core
  `data.message` line always renders regardless.

## Testing
Backend: a Python test for the `pool_run_haul` return value and `extract_party`'s aggregated
`secured` totals (this repo has full pytest coverage for `extraction_service`/`hoard_service`
already — these are small additions to existing test files, not new test infrastructure).

Frontend (no JS test runner in this repo) — manual verification via the `run`/`verify`
skills:
- Run a dungeon with at least one downed character and one living character, with the downed
  character holding at least one bag item.
- Open the extraction modal; confirm the downed character's row shows a "Loot Body" dropdown
  listing the living character(s).
- Loot the body; confirm the action disables/marks looted, and the living character's bag
  later shows the transferred item (verify via the existing Equipment modal).
- Extract the party; confirm the success panel shows the secured copper/item summary instead
  of a bare alert, then redirects to `/dashboard`.
- Extract with zero secured copper/items (e.g. an empty-handed run) and confirm the summary
  line is omitted gracefully (no "undefined" or "NaN" text).

## Affected files
- `app/economy/hoard_service.py` (`pool_run_haul` return value), `tests/` (extend existing
  hoard/extraction service tests for the new return shape).
- `app/services/extraction_service.py` (`extract_party` result aggregation), `tests/`
  (extend existing extraction tests for the new `secured` key).
- `app/templates/adventure.html` (extraction modal: success panel, Loot Body dropdown per
  dead character).
- No new files; no changes to `adventure.js`'s floor-loot pickup code (already complete).
