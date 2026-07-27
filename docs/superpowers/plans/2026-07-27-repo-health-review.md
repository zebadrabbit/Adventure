# Repo health review — gaps, debt, improvements (2026-07-27)

Independent audit of the whole repo (code, CI, deps, tests, docs). The backend is in
good shape: 570 green tests, alembic-only migrations, structlog unified, a disciplined
running TODO. Findings below are what's *left* — ordered by priority, with a checklist
at the end.

---

## P0 — Security hardening (highest value, small diffs)

### 1. No CSRF protection anywhere
The app uses Flask-Login session-cookie auth with dozens of state-changing
`POST /api/...` endpoints (trade, repair, withdraw-from-hoard, combat actions, seed,
account settings). There is zero CSRF defense: no Flask-WTF `CSRFProtect`, no
custom-header check, and no `SESSION_COOKIE_SAMESITE` set in `app/__init__.py`.
Any third-party page a logged-in player visits can forge these requests.

**Fix (cheap, layered):** set `SESSION_COOKIE_SAMESITE="Lax"`,
`SESSION_COOKIE_HTTPONLY=True`, and `SESSION_COOKIE_SECURE=True` (prod only) in config;
then require a custom header (e.g. `X-Requested-With`) on `/api/` POSTs in the existing
`_apply_rate_limit`-style `before_request` hook — the JS already funnels through shared
fetch helpers, so it's a small client change.

### 2. Socket.IO CORS defaults to `*`
`app/__init__.py:116`: `cors_allowed_origins=os.getenv("CORS_ALLOWED_ORIGINS", "*")`.
Combined with cookie auth this permits cross-site WebSocket hijacking. Default should
be same-origin (empty/unset), with the env var as the opt-out for dev.

### 3. Dependency patch-level CVEs + no audit automation
Pins are old at patch level: `Werkzeug==3.0.4` (known fixes landed in 3.0.6),
`gunicorn==21.2.0` (request-smuggling fix landed in 22.0), `Flask-SocketIO==5.3.7`,
`alembic==1.13.2`, etc. There's no `pip-audit` step in CI and no Dependabot config.

**Fix:** one bump-and-test pass now; add `pip-audit` to CI and a
`.github/dependabot.yml` so this stops rotting silently.

### 4. Minor: unauthenticated `/api/client/log`
Accepts arbitrary JSON from anyone and writes it to server logs (`client_log_api.py`).
Rate-limited per-IP, but still a log-spam/injection vector. Gate behind
`@login_required` (the JS only calls it from authenticated pages anyway) or drop it.

---

## P1 — Correctness & config debt

### 5. 140 silent `except Exception: pass` blocks across 29 files
`combat_service.py` has 37, `websockets/lobby.py` 26, `dungeon_api.py` 17.
The repo's own TODO documents a real bug this caused (empty `MonsterCatalog` failing
invisibly for weeks). CI has a check (`scripts/fix_exception_handling.py --check`) but
it runs with `|| true` — purely advisory.

**Fix (ratchet, not big-bang):** convert `pass` → `log.debug/warning(...)` module by
module starting with the top three files, record the current count, and make the CI
check enforce "no new ones" (same ratchet pattern already used for inline-style checks).

### 6. README/code contradiction on SQLite
README: "PostgreSQL 13+ (required — SQLite is not supported)". But `app/__init__.py`
silently falls back to `sqlite:///instance/mud.db` when `DATABASE_URL` is unset,
`run.py --help` advertises the SQLite default, there's a SQLite PRAGMA listener, and
the Docker CI smoke test runs with `DATABASE_URL=sqlite:///test.db`. A missing env var
in prod means a silent empty SQLite DB instead of an error.

**Fix:** pick one truth. If Postgres-only is policy, fail fast on missing/sqlite
`DATABASE_URL` (allow an explicit override for the Docker smoke test) and delete the
PRAGMA block; update run.py help text.

### 7. Dev settings applied unconditionally
`TEMPLATES_AUTO_RELOAD=True` and `SEND_FILE_MAX_AGE_DEFAULT=0` are set for every
environment — the latter disables static caching in prod even though the `asset_url`
mtime cache-buster exists precisely so caching can be long-lived. `engineio_logger`
defaults ON. Gate all three on `FLASK_ENV != "production"`.

### 8. `create_app()` is not a factory (known, big — schedule deliberately)
Importing `app` runs `load_dotenv()`, connects to the DB, runs migrations, and seeds —
module-level side effects that already caused the historic "pytest wiped the dev DB"
incident and forced the elaborate conftest SAVEPOINT machinery. A real
application-factory refactor is the single biggest structural improvement available,
but it touches every blueprint/test. Recommend: park it as its own spec'd project,
don't fold it into a cleanup pass.

---

## P2 — Testing & CI

### 9. CI runs the full suite 2–3 times
`ci.yml`: the test step runs pytest with coverage; the "Enforce minimum coverage" step
re-runs the entire suite just to grep the TOTAL line with awk; the "Coverage (optional)"
step can run it a third time. **Fix:** one run with
`--cov=app --cov-fail-under=80` — deletes both extra steps and roughly halves CI time.

### 10. Zero JS test infrastructure for ~350 KB of frontend code
40 JS files (adventure.js 54 KB, dungeon-canvas.js 38 KB, combat.js 36 KB…), no
package.json, no test runner. The TODO repeatedly notes "no JS test infra" and one-off
Playwright repro scripts keep being written and discarded. Playwright is already in
`requirements-dev.txt`. **Fix:** a small committed Playwright smoke suite (login →
dashboard → enter dungeon → move → combat round → extract) run as a separate CI job,
plus keeping the one-off repro scripts under `tests/e2e/` instead of throwing them away.

### 11. Test-order flakiness (pytest-randomly) keeps resurfacing
The same ~6 tests (camp regen, poison persistence, dashboard theme) flake under random
ordering — repeatedly diagnosed as cross-test DB state, repeatedly "not a regression".
Worth one focused pass to actually fix the shared-state root cause instead of
re-litigating it every branch.

---

## P3 — Structural debt (refactors)

### 12. God files
- `app/routes/dungeon_api.py` — 1,865 lines (an `api_helpers/` package already exists;
  finish the extraction).
- `app/services/combat_service.py` — 1,676 lines (actions vs session lifecycle vs
  monster turn vs rewards are separable; `combat_utils.py`/`combat_constants.py`
  already started).
- `app/routes/admin_new.py` — 1,000 lines.
- `adventure.js` / `combat.js` — same disease client-side.
Split opportunistically — each file that gets touched for a feature gets its extraction
first.

### 13. Known duplication (flagged in the TODO, still open)
- `equipment.js` vs `equipment-enhanced.js` — near-identical encumbrance/gear-bonus
  helpers; the TODO says "hoist into a shared module if either changes again". Verify
  whether plain `equipment.js` is even still loaded; delete it if dead.
- `compute_hp_mana_max` exists as the canonical helper, but
  `combat_service._derive_stats` and `dashboard_helpers.build_party_payload` still
  carry their own duplicated HP/mana-cap math (deliberately deferred earlier).
- `glass-theme.css` dead purple body-class rules (confirmed dead pending one
  admin_themes.html check).

---

## P4 — Docs & process hygiene

### 14. TODO.md is 896 lines, ~90 % completed items
It's the de-facto changelog of the superpowers era. Move the `[x]` history into an
`ARCHIVE.md` (or rely on git history) and keep TODO.md as only the open list —
right now the open items are buried in the last 40 lines.

### 15. Stale one-off docs in docs/
`CORRIDOR_GAP_FIX.md`, `DASHBOARD_FIX.md`, `PROJECT_HEALTH_REPORT.md` (2025-12),
`exception_report.md`, `STRUCTLOG_PROGRESS.md`, `rebase_helper.md` — point-in-time
artifacts, none linked from the README doc table. Archive or delete; stale docs get
read as current.

### 16. Auto-bump workflow never minor-bumps scoped commits
`auto-bump.yml` matches `feat:*` but every real commit is `feat(scope): ...`, which
falls through to `patch` — that's why the version history is a wall of patch bumps.
Fix the case patterns (`feat*` / `fix*`), and consider whether every push to main
really needs a bump commit (half of recent history is `chore: auto bump`).

---

## P5 — Open gameplay items (carried from TODO.md, unchanged)

Waiting on playtest verdicts, not engineering-blocked:
- `EVENT_TUNING` numbers (shrine/trap/ambush counts, damage, DCs, respawn trickle)
- Mana costs 4/8/12 vs potion +5 (potion likely wants a buff)
- Spawn density / aggro radius play-feel
- Combat-screen visual redesign (deferred to a live session)
- Shrine/camp writes `stats["mana"]` not `current_mana` (post-combat restore may not
  be visible; small cleanup)
- Multi-worker Socket.IO (sticky sessions + message queue) — only if `--workers > 1`
  ever becomes real

---

## Proposed execution order

| Phase | Scope | Size |
|---|---|---|
| 1 | P0 security: cookie flags + SameSite, custom-header CSRF gate, Socket.IO CORS default, dep bump + pip-audit + dependabot, gate `/api/client/log` | S–M, 1 branch |
| 2 | P1 quick config wins: SQLite fail-fast + README truth, prod-gate dev settings, engineio logger default | S, 1 branch |
| 3 | P2 CI: single-run coverage, exception-check ratchet made enforcing | S, 1 branch |
| 4 | P1 exception-swallowing ratchet: combat_service → lobby → dungeon_api | M, 1 branch per file |
| 5 | P2 Playwright smoke suite (committed, in CI) | M |
| 6 | P4 hygiene: prune TODO.md, archive stale docs, fix auto-bump patterns | S |
| 7 | P3 refactors: equipment.js dedupe/delete, hp/mana-cap dedupe, opportunistic god-file splits | M, ongoing |
| 8 | P1 app-factory refactor — own spec, own project | L |
| 9 | P5 gameplay tuning — playtest-driven | — |

## Checklist (executed on the `repo-health` branch, 2026-07-27)

- [x] Session cookie flags: `SAMESITE=Lax`, `HTTPONLY`, `SECURE` (prod, env-overridable)
- [x] CSRF gate: `X-Requested-With` required on mutating `/api/` requests; global fetch wrapper in `static/js/api-guard.js`
- [x] Socket.IO `cors_allowed_origins` default → same-origin, env override for dev
- [x] Bump deps (Werkzeug 3.0.6, gunicorn 23.0, alembic 1.14.1, psycopg2 2.9.10) — suite green
- [x] Add `pip-audit` to CI + `.github/dependabot.yml`
- [x] Gate unauthenticated `/api/client/log` behind login
- [x] `DATABASE_URL` fail-fast (no silent SQLite fallback); README/run.py/Docker reconciled; SQLite PRAGMA block dropped
- [x] Prod-gate `TEMPLATES_AUTO_RELOAD`, `SEND_FILE_MAX_AGE_DEFAULT`; `engineio_logger` default off
- [x] CI: single pytest run with `--cov-fail-under=80`; duplicate coverage steps deleted
- [x] Exception-handling check enforcing (`--max-count` ratchet, currently 62)
- [x] De-silence `except Exception: pass` in `combat_service.py` (38 sites)
- [x] De-silence `except Exception: pass` in `websockets/lobby.py` (27 sites)
- [x] De-silence `except Exception: pass` in `dungeon_api.py` (17 sites)
- [x] Committed Playwright smoke suite (`e2e/`) + `e2e-smoke` CI job — 5 tests green vs a live server
- [~] pytest-randomly flakes: not reproduced — 4+ consecutive full-suite greens today; re-open only if seen again
- [x] `docs/superpowers/TODO.md` pruned to open items; history → `TODO_ARCHIVE.md`
- [x] Stale docs → `docs/archive/` (kept `rebase_helper.md`; it documents a live script)
- [x] `auto-bump.yml` scoped-commit matching fixed
- [x] `equipment.js`/`equipment-enhanced.js` shared logic → `equipment-shared.js` (both files are live; kept)
- [x] Dashboard HP/mana-cap math folded onto `compute_hp_mana_max` (combat's copy stays inline, documented — CON→STR legacy fallback differs)
- [x] `glass-theme.css` purple rules: already removed in an earlier cleanup — verified, no action
- [x] App-factory refactor spec: `specs/2026-07-27-app-factory-refactor-design.md`
- [ ] Playtest-driven tuning pass (EVENT_TUNING, mana/potion economy, spawn density, aggro) — needs live play, tracked in TODO.md

Bonus fixes discovered along the way: pinned-black formatting drift in
`test_autofill_name_pools.py`; 16 assets missing trailing newlines; the
`optimize_svgs` pre-commit hook has a broken `files` regex and has never
run (logged in TODO.md, not fixed — enabling it rewrites every SVG).
