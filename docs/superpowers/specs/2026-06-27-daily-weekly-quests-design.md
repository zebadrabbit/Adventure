# Daily & Weekly Quest System — Design Spec
**Date:** 2026-06-27
**Status:** Approved

---

## Overview

A lightweight background progression layer that gives players 3 daily quests and 1
weekly quest each reset. Quests are kill- and run-based with randomized parameters,
reward XP/potions/gear, and reset on a fixed server-timezone schedule. They complement
normal adventuring — progress accumulates automatically from dungeon runs without
requiring separate quest-specific sessions.

---

## Reset Schedule

- **Daily:** midnight server-local time every day
- **Weekly:** Monday 00:00 server-local time

Progress and generation are per-user (not per-character) — the whole party's actions
count toward a single pool. This avoids the problem of a 4-character party needing to
complete objectives 4× over.

---

## Quest Types

### Daily (3 generated per reset)

Drawn randomly from kill/run templates. Examples of template families:

| Family | Example title | Objective |
|--------|--------------|-----------|
| `kill_count` | "Thin the Ranks" | Defeat N enemies in dungeon runs |
| `kill_elite` | "Veteran's Trial" | Defeat N elite/boss enemies |
| `run_complete` | "Back in One Piece" | Complete N dungeon runs (extract alive) |
| `run_extract` | "Clean Sweep" | Extract successfully N times without a wipe |

Parameters (N) are rolled per reset, scaled loosely to party average level:
- Kill count: 10–30
- Elite kills: 2–6
- Runs completed: 2–4
- Successful extracts: 1–3

Rewards per daily (scaled to difficulty):
- XP: 200–500
- 1–2 potions (healing or mana) deposited directly to hoard
- 15% chance of one level-appropriate common/uncommon gear piece to hoard

### Weekly (1 generated per reset)

**For now:** "Complete 10 daily quests this week."

Progress counter increments each time any daily is claimed. Reward:
- XP: 1500
- 3–5 potions to hoard
- 1 guaranteed uncommon+ gear piece (level-appropriate)
- Bonus hoard copper: ~500c

Weekly tracks completions across the full Mon–Sun window regardless of which day
the dailies were from.

---

## Data Model

### New table: `user_quest_pool`

Stores the generated quest set for a given user and reset period.

```
user_quest_pool
  id              PK
  user_id         FK → user
  period_type     "daily" | "weekly"
  period_key      string — "2026-06-27" (daily) | "2026-W26" (weekly)
  quests_json     JSON array of generated quest objects (see below)
  created_at      timestamp
  UNIQUE(user_id, period_type, period_key)
```

### Generated quest object (stored in `quests_json`)

```json
{
  "id": "uuid4",
  "template": "kill_count",
  "title": "Thin the Ranks",
  "description": "Defeat 18 enemies in the dungeon.",
  "objective": {"type": "kill_count", "target": 18, "current": 0},
  "rewards": {"xp": 350, "potions": [{"slug": "potion-healing", "qty": 2}], "gear_roll": true},
  "status": "active",
  "claimed_at": null
}
```

No new migration for `QuestTemplate` — daily/weekly quests bypass the hand-authored
template table entirely and are generated + stored as self-contained JSON. The existing
`QuestTemplate` table is reserved for future narrative quests.

### `user_quest_pool` migration

Single `alembic` migration. No changes to existing quest models.

---

## Generation

`app/services/quest_generator.py` — new file.

```python
def get_or_generate_daily(user_id) -> list[dict]:
    """Return today's daily quests for user, generating if not yet created."""

def get_or_generate_weekly(user_id) -> dict:
    """Return this week's weekly quest for user, generating if not yet created."""

def _generate_dailies(avg_level: int) -> list[dict]:
    """Roll 3 daily quests from weighted template families."""

def _generate_weekly() -> dict:
    """Generate the weekly (always: complete 10 dailies)."""

def _period_key_daily() -> str:  # "2026-06-27"
def _period_key_weekly() -> str:  # "2026-W26"
```

Generation is **lazy** — triggered on first `GET /api/quests/daily` of the reset period.
No background scheduler needed for generation. Rewards are also granted lazily on claim.

Average level: mean of the user's owned characters' levels (fallback to 1).

---

## Progress Tracking

Progress is updated by hooking into existing dungeon events. Two integration points:

### Kill tracking
`combat_service.py` already resolves monster deaths. After each monster kill, fire:
```python
quest_service.record_kill(user_id, monster_type, is_elite)
```
This increments `objective.current` on matching active daily quests in the pool JSON,
then saves. No separate `QuestProgress` rows — the pool JSON is the single source of
truth.

### Run tracking
`extraction_service.py` already handles successful extraction. After extract:
```python
quest_service.record_run_complete(user_id, extracted=True)
```
Similarly increments matching objectives.

Both calls are fire-and-forget (catch all exceptions, log, never block combat/extraction).

---

## Reward Delivery

Rewards are granted when the player **claims** a completed quest via the UI. Not
auto-granted on completion, to keep the player in the loop and avoid silent hoard
mutations.

`POST /api/quests/daily/claim` `{quest_id: str}`
- Validates: quest status == "active", objective.current >= objective.target,
  period still valid (no claiming yesterday's quests).
- Grants: XP to all party characters (split evenly), potions + gear to hoard.
- Sets `status: "claimed"`, `claimed_at: now`.
- If weekly counter reaches 10: auto-marks weekly claimable.

`POST /api/quests/weekly/claim`
- Same pattern; grants weekly rewards to hoard + XP to party.

Gear rolls: use existing `app/loot/generator.py` procedural gear generation, passing
avg party level as the tier seed.

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/quests/daily` | Get today's 3 dailies (generates if needed) |
| `GET` | `/api/quests/weekly` | Get this week's weekly (generates if needed) |
| `POST` | `/api/quests/daily/claim` | Claim a completed daily `{quest_id}` |
| `POST` | `/api/quests/weekly/claim` | Claim the completed weekly |

All endpoints are `@login_required`. No character_id needed — user-scoped.

---

## Quest Tab UI

The existing Quests tab (added in the previous session) currently shows active/completed/
available sub-tabs wired to the old per-character quest system. This spec adds:

- **Daily** sub-tab: shows today's 3 quests with progress bars and a CLAIM button when
  complete.
- **Weekly** sub-tab: shows the weekly with a daily-completions counter (e.g. `7/10`)
  and CLAIM button.
- The existing Active/Completed/Available tabs remain for future hand-authored quests.

Progress bars and claim buttons refresh after each dungeon run (poll on tab open, or
listen for a `quest-progress-updated` custom event fired by the combat/extraction
handlers).

---

## Seeding

`python run.py seed-daily-quests` (or included in `./manage.sh db seed`) — a no-op
idempotent command that verifies the `user_quest_pool` table exists. No static rows to
seed; everything is generated lazily.

---

## Out of Scope (Future)

- Heroic / mythic difficulty modifiers as weekly quest types
- Portal / special dungeon objectives
- Hand-authored narrative quest chains
- Per-character quest progress (existing `QuestProgress` model)
- Streak bonuses for consecutive daily completions
- Push notifications for reset
