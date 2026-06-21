# Combat skill buttons — design

## Problem

`combat.html`'s `#combat-action-panel` is one static button set
(Attack/Defend/Firebolt/Ice Shard/Lightning/Potion/Flee) shared by every
party member. Firebolt/Ice Shard/Lightning are a separate, universal
"caster magic" system (any character with INT≥12 or a caster class can use
them, gated only by mana — `combat_service.py`'s `cast` endpoint and
`SPELLS` dict around line 1562). Independently, the talent-tree active
skill system (`Skill`/`CharacterSkill` models, `POST
/api/combat/<id>/cast_skill`, `combat_service.player_cast_skill`) is fully
implemented server-side — cooldowns, effect application, logging — but has
no combat UI button at all. A character who unlocks a skill via the skill
tree currently has no way to use it in a fight.

## Goal

Show each active party member's unlocked active skills as additional
buttons in the existing action panel, alongside (not replacing) the 3
universal spells — casters with no unlocked skills yet keep their
baseline magic; characters who've invested talent points get extra
options.

## Approach

**Data fetch:** when `render()` sets up the action panel for a newly
active character (`activeCharId` changes), `combat.js` fetches `GET
/api/characters/<activeCharId>/skills` (existing endpoint, already
returns `skill_id`, `skill_name`, `skill_type`, `effect_json`, `cooldown`
is on the `Skill` row not in this payload — see Gap below), filters to
`skill_type === 'active'`, and caches the result in a
`Map<charId, skills[]>` so repeated renders (e.g. on every `combat_update`
socket event) don't refetch every tick. Cache is per combat-session
lifetime (module-level `Map`, cleared on page load).

**Gap found during review:** `get_character_skills` (skill_api.py:101)
returns `effect_json` but not `cooldown` (that's a column on `Skill`, not
serialized here). Need to add `"cooldown": skill.cooldown` to that
endpoint's response — a one-line additive change, doesn't affect existing
consumers (skill-tree.js doesn't currently read a `cooldown` field, grepped
clean).

**Rendering:** a new function `renderSkillButtons(activeCharId, skills)`
builds one `<button class="btn-combat btn-combat-spell" data-action="cast_skill_<id>" data-skill-id="<id>" data-cooldown="<seconds>" data-last-used="<iso-or-empty>">` per active skill (icon from `skill.icon` if present, else a default), appended into the action panel's button-grid after the existing Lightning/Potion row and before Flee. Re-rendered (replacing prior skill buttons, identified by a `data-skill-btn` marker) each time the active character or its skill cache entry changes.

**Gating (mirrors existing mana-cost pattern at combat.js:348-355):**
- `canAct` (not active turn) → disabled, same as all other buttons.
- Client-side cooldown: if `last_used` present and `(Date.now() -
  Date.parse(last_used))/1000 < cooldown`, disable with a title showing
  remaining seconds. This is a UX nicety only — `player_cast_skill`
  already enforces the real cooldown server-side and returns
  `{"error": "on_cooldown", "remaining_seconds": N}` if the client guess is
  stale (e.g. another tab, or the page sat idle past a render).

**Click handling:** extend `doAction`'s action dispatch — for any action
matching `cast_skill_<id>`, POST to `/api/combat/<id>/cast_skill` with
`{version, actor_id, skill_id}` instead of the existing spell/attack
endpoints. Reuses the same particle-effect hook (`window.combatEffects`)
already wired for `cast_*` actions, generalized to match the `cast_skill_`
prefix too (damage → monster particles, heal → self particles, inferred
from the skill's `effect_json` shape already available client-side).

**Error feedback:** `doAction` currently swallows non-`state` responses
silently (`if (j.state) render(j.state)`, else nothing). Out of scope to
overhaul this for the whole file, but since skill casts have a
server-side cooldown race the client guess can miss, log
`{error}` responses to the existing combat log via `appendLog` with a
client-only synthetic line (e.g. "Skill is on cooldown") rather than
leaving the click looking like a no-op. Scoped narrowly to the
`cast_skill_*` path only.

## Testing

No JS test infra exists for combat.js (confirmed — `combat.js`'s other
client-only behaviors, e.g. the version-monotonicity guard and per-char
potion gating, are similarly untested and rely on live-browser
verification, per `docs/superpowers/TODO.md`'s prior entries). This
follows the same pattern: no automated test for the rendering/gating
logic itself.

Backend changes are testable:
- `get_character_skills` now including `cooldown` in the response: TDD'd
  with a small addition to whatever existing skill_api test file covers
  that endpoint.
- No other backend changes — `cast_skill` and `player_cast_skill` are
  unmodified, already covered by existing tests if any (grep `cast_skill`
  in tests/).

Manual verification: start a combat encounter with a character that has
at least one unlocked active skill (use the skill tree to unlock one if
none exist on the dev DB), confirm the button appears, casts successfully,
respects cooldown, and disappears/reappears correctly when initiative
passes to a different party member.

## Out of scope

- Redesigning the 3 universal spells or the skill-tree unlock flow.
- A toast/notification system for combat errors generally (only the
  narrow on-cooldown case for skill buttons gets a log line).
- Passive/toggle skill display (this only covers `skill_type === 'active'`).
