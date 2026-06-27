# Economy & Progression

Reference for the looter-extract economy and character progression systems
(Path A: Specs 1–5). Design/spec docs live in `docs/superpowers/specs/`.

## Mental model

- A **run** takes a party of up to 4 characters into a seeded dungeon.
- Loot and coin found in a run are **at-risk** until you **extract**.
- On extraction, each surviving character's haul pools into the per-user **Hoard**
  (persistent). On a **party wipe**, the run's haul is lost; the Hoard is safe.
- Characters can **permadie**; the Hoard endures, so progression is never wiped — you
  outfit new characters from it.
- Per-character progression (XP → levels → stat/talent points → skills) is the
  at-risk personal stake.

## Currency (Spec 1)

- Stored internally as **copper** (smallest unit). Display is 3-tier
  (`Xg Ys Zc`, 100 copper = 1 silver, 100 silver = 1 gold) via
  `app/economy/currency.py::format_copper`.
- **Party gold** (`Character.gold`, summed across the active party) is **at-risk** coin
  carried into dungeons — lost on a party wipe, banked into the Hoard on extraction.
- **Hoard copper** (`Hoard.copper`) is the **safe** balance that survives wipes.
- Town vendors draw from both: **party gold is spent first**, then Hoard copper tops up
  any shortfall. The combined available balance is exposed as `total_available` on
  `GET /api/hoard`; the Hoard-only safe balance is still `copper`.

## The Hoard (Spec 2)

- `Hoard` model (`app/models/hoard.py`), one row per user: `items_json` (gear instances
  + stacks, canonical inventory format) and `copper`.
- Service: `app/economy/hoard_service.py` — `deposit_items`, `deposit_copper`,
  `withdraw_to_character`, `pool_run_haul`.
- API (`app/routes/hoard_api.py`):
  - `GET /api/hoard` — items + copper + `copper_display` + `party_gold` +
    `party_gold_display` + `total_available` + `total_available_display`.
  - `POST /api/hoard/withdraw` `{character_id, slug|uid}` — move an item to a character.
  - `POST /api/dungeon/loot-body` `{downed_id, survivor_id}` — loot a downed ally's bag.
- Extraction (`app/services/extraction_service.py`) pools each extracting character's
  bag + run-purse into the Hoard; combat wires death/permadeath
  (`combat_service.sync_member_death_states` / `resolve_party_defeat_if_any`).

## Trading (Specs 1–2)

- `app/routes/trading_api.py`. Town vendor purchases debit **party gold first** (drained
  across party members in session order), then Hoard copper for any remainder. Sell
  proceeds always go to the Hoard. All endpoints are `@login_required` + owner-checked.
  - `GET /api/merchants/<slug>`, `POST /api/trade/buy`, `POST /api/trade/sell`
    (sell by catalog `item_slug` or gear `uid`). `POST /api/trade/repair` `{uid}`.
  - Buy/repair responses include `new_balance` (combined party+hoard), `new_balance_display`,
    `hoard_balance`, `hoard_balance_display`.
- `_debit_combined(cost, party_chars, hoard)` in `trading_api.py` is the shared debit
  helper used by both buy and repair.
- Vendors are seeded by `python run.py seed-merchants` (idempotent).

## Floor loot (Spec 3)

- `DungeonLoot` rows hold either a catalog `item_id` **or** a procedural gear
  `instance_json`. Placement (`app/loot/generator.py::generate_loot_for_seed`) rolls a
  config-driven chance per node; claim via `POST /api/dungeon/loot/claim/<id>`.

## Durability & repair (Spec 4a)

- Procedural gear carries `durability`/`max_durability`. Survivors' equipped gear wears
  on a win. A **broken** item (durability 0) gives *reduced* affix bonuses (not removed).
- `app/services/durability.py`: `degrade_gear`, `repair_cost`, `apply_repair`.
- `POST /api/trade/repair` `{uid}` — repair to full, paid from Hoard copper.

## Progression: XP, levels, points (Spec 5a)

- `app/models/xp.py::xp_for_level` (canonical D&D-5e curve).
- `app/services/progression.py::grant_xp` — adds XP, applies level-ups, awards
  `talent_points` (→ `CharacterTalentPoints`) and `stat_points` (→ `Character.stat_points`).
- XP is awarded on **monster defeat** (combat) and **extraction**.
- `POST /api/characters/<id>/level-up` `{stat_allocations}` spends earned `stat_points`
  (rejects over-spend / negatives).

## Skills (Spec 5b)

- Models: `app/models/skill.py` (`SkillTree`, `Skill`, `CharacterSkill`,
  `CharacterTalentPoints`). Seed starter trees/skills: `python run.py seed-skills`.
- `app/routes/skill_api.py` (all owner-checked; `grant_talent_points` is admin-only):
  unlock (`POST /api/characters/<id>/skills`), use, reset.
- **Passive** skills fold into derived combat + dashboard stats
  (`app/services/skill_effects.py::passive_bonuses`).
- **Active** skills are combat actions: `POST /api/combat/<id>/cast_skill {skill_id}`
  (`combat_service.player_cast_skill`), applying `effect_json` damage/heal.

## Tunable config (GameConfig keys)

All read with safe fallbacks; set via the admin config UI or
`python run.py config-set <key> '<json>'`.

| Key | Fields (defaults) |
|---|---|
| `trading` | `buy_modifier` 1.0, `sell_modifier` 0.5 |
| `floor_loot` | `procedural_gear_chance` 0.25, `rarity_weights` {common 60, uncommon 25, rare 10, epic 4, legendary 1} |
| `durability` | `enabled` true, `max_durability` 100, `loss_per_fight` 2, `repair_cost_per_point` 1, `broken_bonus_multiplier` 0.5 |
| `progression` | `xp_difficulty_mod` 1.0, `talent_points_per_level` 1, `stat_points_per_level` 2, `extraction_xp` 50 |
| `encumbrance` | `base_capacity`, `per_str`, `warn_pct`, `hard_cap_pct`, `dex_penalty` |

## Deploy / data seeding checklist

After `createdb` + `alembic upgrade head` (or `./manage.sh db upgrade`):

```bash
./manage.sh db seed        # items + merchants + skills (idempotent), OR individually:
python run.py reseed-items
python run.py seed-merchants
python run.py seed-skills
```
