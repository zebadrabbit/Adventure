# Ponytail Audit Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove dead files, unify duplicate logging systems, inline three micro-modules with single callers, and drop two unused pip dependencies.

**Architecture:** Pure deletion + move-and-inline. No new abstractions. Each task is independently mergeable. Tasks 1–5 are independent and can be done in any order; Task 3 (logging) is slightly more involved but still standalone.

**Tech Stack:** Python/Flask, structlog (already installed), pytest

## Global Constraints

- Never add new abstractions — deletion over addition
- All existing tests must pass after each task: `cd /home/winter/work/Adventure && source .venv/bin/activate && pytest -x -q`
- Use structlog's positional-event style: `logger.error("event_name", key=val)` not `logger.error(event="event_name", key=val)`
- Do not touch `requirements-dev.txt`

---

### Task 1: Delete three dead files

**Files:**
- Delete: `app/logging_config.py` (zero callers, never imported)
- Delete: `app/static/chat-widget.js` (deprecation stub; template uses `js/chat-widget.js` directly)
- Delete: `app/routes/debug_api.py` (defines `bp_debug` but it is never imported or registered in `app/__init__.py`)

**Interfaces:**
- Consumes: nothing
- Produces: nothing (pure deletion)

- [ ] **Step 1: Verify zero callers**

```bash
grep -rn "logging_config\|chat-widget\.js\|debug_api\|bp_debug" \
  /home/winter/work/Adventure/app /home/winter/work/Adventure/tests \
  --include="*.py" --include="*.html" --include="*.js" \
  | grep -v __pycache__ \
  | grep -v "app/logging_config.py" \
  | grep -v "app/static/chat-widget.js" \
  | grep -v "app/routes/debug_api.py"
```

Expected: no output (confirm nothing references them).

- [ ] **Step 2: Delete the files**

```bash
rm /home/winter/work/Adventure/app/logging_config.py
rm /home/winter/work/Adventure/app/static/chat-widget.js
rm /home/winter/work/Adventure/app/routes/debug_api.py
```

- [ ] **Step 3: Run tests**

```bash
cd /home/winter/work/Adventure && source .venv/bin/activate && pytest -x -q
```

Expected: all pass.

- [ ] **Step 4: Commit**

```bash
git add -u
git commit -m "delete: remove dead logging_config, chat-widget stub, unregistered debug_api"
```

---

### Task 2: Unify logging — migrate logging_utils callers to structlog, delete logging_utils.py

Three files import from `app.logging_utils`. Each needs its import replaced with `structlog` and its call style updated from `logger.error(event="foo", key=val)` to `logger.error("foo", key=val)`.

**Files:**
- Modify: `app/dungeon/movement_handler.py`
- Modify: `app/dungeon/api_helpers/perception.py`
- Modify: `app/websockets/game.py`
- Delete: `app/logging_utils.py`

**Interfaces:**
- Consumes: `structlog` (already in requirements.txt)
- Produces: nothing new

- [ ] **Step 1: Update movement_handler.py**

Replace lines 20–23 in `app/dungeon/movement_handler.py`:

```python
# Before
from app.logging_utils import get_logger
...
logger = get_logger(__name__)

# After
import structlog
...
logger = structlog.get_logger(__name__)
```

Then update every call site in that file from keyword-event style to positional:

```python
# Before
logger.error(event="movement_commit_failed", user_id=current_user.id, error=str(e))
# After
logger.error("movement_commit_failed", user_id=current_user.id, error=str(e))
```

Apply the same pattern to every `logger.*` call in the file (search for `logger.` and fix any that use `event=`).

- [ ] **Step 2: Update perception.py**

In `app/dungeon/api_helpers/perception.py`, find the lazy import block (around line 124):

```python
# Before
from app.logging_utils import get_logger
...
logger = get_logger(__name__)

# After
import structlog
...
logger = structlog.get_logger(__name__)
```

Update any `logger.*` calls with `event=` keyword to positional style.

- [ ] **Step 3: Update game.py**

`app/websockets/game.py` has two import blocks — one at module level (line 34) using `log as _log` and one lazy inside a function (line 173) using `get_logger`.

**Module-level block (line 34):** Replace:
```python
# Before
try:
    from app.logging_utils import log as _log
except Exception:
    class _NoLog:
        ...
    _log = _NoLog()

# After
import structlog
_log = structlog.get_logger(__name__)
```

Remove the `_NoLog` fallback class entirely — structlog is always available (it's in requirements.txt and installed in .venv).

**Lazy block (line 173):** Replace:
```python
# Before
from app.logging_utils import get_logger
...
logger = get_logger(__name__)

# After
import structlog
logger = structlog.get_logger(__name__)
```

Update call sites: `_log.info(event="join_game", ...)` → `_log.info("join_game", ...)`, etc.

- [ ] **Step 4: Delete logging_utils.py**

```bash
rm /home/winter/work/Adventure/app/logging_utils.py
```

- [ ] **Step 5: Run tests**

```bash
cd /home/winter/work/Adventure && source .venv/bin/activate && pytest -x -q
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add -u
git commit -m "refactor: unify logging — migrate logging_utils callers to structlog, delete logging_utils"
```

---

### Task 3: Inline compose_name and delete loot/naming.py

`compose_name` is a 9-line function with exactly one caller: `app/loot/generator.py:308`. Inline it and delete the module.

**Files:**
- Modify: `app/loot/generator.py`
- Delete: `app/loot/naming.py`

**Interfaces:**
- Consumes: nothing new
- Produces: nothing new

- [ ] **Step 1: Inline compose_name into generator.py**

In `app/loot/generator.py`, find (around line 205):
```python
from app.loot.naming import compose_name  # noqa: E402
```
Delete this import.

Find the call site (around line 308):
```python
name = compose_name(prefix_name, arch["base_name"], suffix_name)
```

Replace with the inlined logic:
```python
_name_parts = []
if prefix_name:
    _name_parts.append(prefix_name)
_name_parts.append(arch["base_name"])
name = " ".join(_name_parts)
if suffix_name:
    name = f"{name} {suffix_name}"
```

- [ ] **Step 2: Delete naming.py**

```bash
rm /home/winter/work/Adventure/app/loot/naming.py
```

- [ ] **Step 3: Run tests**

```bash
cd /home/winter/work/Adventure && source .venv/bin/activate && pytest -x -q -k "loot or gear or naming or generator"
```

Expected: all pass.

- [ ] **Step 4: Commit**

```bash
git add -u
git commit -m "refactor: inline compose_name into generator, delete loot/naming.py"
```

---

### Task 4: Move gear_bonuses and add_gear_to_character into loot_service, delete loot/equip.py and loot/inventory.py

`gear_bonuses` (in `loot/equip.py`) has 3 callers, all using lazy inline imports. `add_gear_to_character` (in `loot/inventory.py`) has 2 callers, also lazy imports. Both belong in `loot_service.py`.

**Files:**
- Modify: `app/services/loot_service.py` (add both functions)
- Modify: `app/services/character_stats.py` (update import)
- Modify: `app/routes/dashboard_helpers.py` (update import)
- Modify: `app/services/combat_service.py` (update both imports)
- Modify: `app/dungeon/api_helpers/treasure.py` (update import)
- Delete: `app/loot/equip.py`
- Delete: `app/loot/inventory.py`

**Interfaces:**
- Consumes: `app.services.durability.durability_config` (already used in equip.py)
- Produces: `gear_bonuses(gear: dict | None) -> dict` and `add_gear_to_character(character, instances: list[dict]) -> None` now live in `app.services.loot_service`

- [ ] **Step 1: Add gear_bonuses to loot_service.py**

At the bottom of `app/services/loot_service.py`, append the full `gear_bonuses` function exactly as it exists in `app/loot/equip.py` (copy verbatim):

```python
def gear_bonuses(gear: dict | None) -> dict:
    """Sum affix values across all equipped instances -> {stat: total}.

    A "broken" instance (durability == 0) contributes a reduced share of its
    affixes (``broken_bonus_multiplier`` from durability config) — reduced, not
    removed. Instances without durability tracking count at full value.
    """
    totals: dict[str, float] = {}
    if not isinstance(gear, dict):
        return totals

    try:
        from app.services.durability import durability_config

        broken_mult = float(durability_config().get("broken_bonus_multiplier", 0.5))
    except Exception:
        broken_mult = 0.5

    for inst in gear.values():
        if not isinstance(inst, dict):
            continue
        affixes = inst.get("affixes")
        if not isinstance(affixes, list):
            continue
        mult = broken_mult if inst.get("durability") == 0 else 1.0
        for a in affixes:
            if not isinstance(a, dict):
                continue
            stat = a.get("stat")
            val = a.get("val")
            if not stat or not isinstance(val, (int, float)):
                continue
            totals[stat] = totals.get(stat, 0) + val * mult
    return {k: (int(v) if float(v).is_integer() else v) for k, v in totals.items()}
```

- [ ] **Step 2: Add add_gear_to_character to loot_service.py**

Also append to `app/services/loot_service.py`:

```python
def add_gear_to_character(character, instances: list[dict]) -> None:
    """Append gear instances to character.items (JSON list), preserving existing."""
    import json
    try:
        items = json.loads(character.items) if character.items else []
        if not isinstance(items, list):
            items = []
    except Exception:
        items = []
    for inst in instances or []:
        if isinstance(inst, dict) and inst.get("uid"):
            items.append(inst)
    character.items = json.dumps(items)
```

- [ ] **Step 3: Update callers — character_stats.py**

In `app/services/character_stats.py`, find:
```python
from app.loot.equip import gear_bonuses
```
Replace with:
```python
from app.services.loot_service import gear_bonuses
```

- [ ] **Step 4: Update callers — dashboard_helpers.py**

In `app/routes/dashboard_helpers.py`, find:
```python
from app.loot.equip import gear_bonuses
```
Replace with:
```python
from app.services.loot_service import gear_bonuses
```

- [ ] **Step 5: Update callers — combat_service.py**

In `app/services/combat_service.py`, find (two separate lazy imports):
```python
from app.loot.equip import gear_bonuses
```
Replace with:
```python
from app.services.loot_service import gear_bonuses
```

And:
```python
from app.loot.inventory import add_gear_to_character
```
Replace with:
```python
from app.services.loot_service import add_gear_to_character
```

- [ ] **Step 6: Update callers — treasure.py**

In `app/dungeon/api_helpers/treasure.py`, find:
```python
from app.loot.inventory import add_gear_to_character
```
Replace with:
```python
from app.services.loot_service import add_gear_to_character
```

- [ ] **Step 7: Delete the now-empty modules**

```bash
rm /home/winter/work/Adventure/app/loot/equip.py
rm /home/winter/work/Adventure/app/loot/inventory.py
```

- [ ] **Step 8: Run tests**

```bash
cd /home/winter/work/Adventure && source .venv/bin/activate && pytest -x -q
```

Expected: all pass.

- [ ] **Step 9: Commit**

```bash
git add -u
git commit -m "refactor: consolidate gear_bonuses and add_gear_to_character into loot_service, delete loot/equip.py and loot/inventory.py"
```

---

### Task 5: Remove redis everywhere (dependency, compose service, env vars)

`redis==5.0.1` has zero import sites in application code, and `REDIS_URL` is set in `.env.example` / `docker-compose.yml` but never read by any Python code. The redis compose service is orphaned.

**Do NOT remove `psycopg2-binary`** — `docker-compose.yml` runs Postgres (`DATABASE_URL=postgresql://...`); the driver is required for that deployment.

**Files:**
- Modify: `requirements.txt` (remove `redis==5.0.1` line only)
- Modify: `docker-compose.yml` (remove the `redis` service block, the `REDIS_URL` env line, and any `depends_on: redis` entries)
- Modify: `.env.example` (remove the `REDIS_URL` line and any comment block that only describes it)

**Interfaces:**
- Consumes: nothing
- Produces: nothing new

- [ ] **Step 1: Verify no imports or env reads**

```bash
grep -rn "import redis\|from redis\|REDIS_URL" /home/winter/work/Adventure/app /home/winter/work/Adventure/run.py --include="*.py" | grep -v __pycache__
```

Expected: no output.

- [ ] **Step 2: Remove the lines/blocks listed under Files**

- [ ] **Step 3: Validate compose file still parses**

```bash
docker compose -f /home/winter/work/Adventure/docker-compose.yml config -q || docker-compose -f /home/winter/work/Adventure/docker-compose.yml config -q
```

(If docker is unavailable in the environment, a YAML parse check via python is acceptable: `python -c "import yaml,sys; yaml.safe_load(open('docker-compose.yml'))"`.)

- [ ] **Step 4: Run tests**

```bash
cd /home/winter/work/Adventure && source .venv/bin/activate && pytest -x -q
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add -u
git commit -m "chore: remove unused redis dependency, compose service, and REDIS_URL env"
```

---

### Task 6: Delete unreferenced static JS and the empty app/utils package

Three JS files are referenced by no template and no other script: `app/static/js/dashboard-autofill.js` (89 lines), `app/static/js/fog_admin_modal.js` (137), `app/static/js/party.js` (80). `app/utils/` contains only `__pycache__`.

**Files:**
- Delete: `app/static/js/dashboard-autofill.js`
- Delete: `app/static/js/fog_admin_modal.js`
- Delete: `app/static/js/party.js`
- Delete: `app/utils/` (directory)

- [ ] **Step 1: Verify zero references**

```bash
grep -rn "dashboard-autofill\|fog_admin_modal\|js/party\.js\|from app.utils\|from app import utils\|app\.utils" \
  /home/winter/work/Adventure/app /home/winter/work/Adventure/tests \
  --include="*.py" --include="*.html" --include="*.js" | grep -v __pycache__
```

Expected: no output (matches inside the files being deleted are fine).

- [ ] **Step 2: Delete the files and directory, run tests (`pytest -x -q`), commit**

```bash
git commit -m "delete: remove unreferenced JS (dashboard-autofill, fog_admin_modal, party) and empty app/utils package"
```

---

### Task 7: Delete the experimental Three.js renderer

`app/static/js/dungeon-three.js` (467 lines) is an experimental alternate renderer, toggle-gated behind `?renderer=three`, loading three.js from a jsdelivr CDN. `dungeon-canvas.js` is the shipped renderer. Delete the experiment.

**Files:**
- Delete: `app/static/js/dungeon-three.js`
- Modify: `app/templates/adventure.html` — remove the `<script type="module" src=...dungeon-three.js>` tag, its explanatory comment block, the `<canvas id="dungeon-minimap-three">` element, and the `#dungeon-minimap-three` CSS rule
- Modify: any JS that branches on `renderer=three` or references `dungeon-minimap-three` (check `adventure.js`, `dungeon-canvas.js`) — remove the dead branch

- [ ] **Step 1: Find all references**

```bash
grep -rn "dungeon-three\|minimap-three\|renderer=three\|renderer === 'three'\|renderer==='three'" \
  /home/winter/work/Adventure/app --include="*.js" --include="*.html" --include="*.py" | grep -v __pycache__
```

- [ ] **Step 2: Remove them all, delete the file**

- [ ] **Step 3: Run tests (`pytest -x -q`) and commit**

```bash
git commit -m "delete: remove experimental Three.js renderer (dungeon-three.js) and its toggle plumbing"
```

---

### Task 8: Production guard for default SECRET_KEY + single-worker notes

`app/__init__.py:45` defaults `SECRET_KEY` to `"dev-secret-change-me"` with no production guard. Add a hard fail on startup when running in production with the default key. Also mark the two in-memory single-process assumptions with `ponytail:` comments.

**Files:**
- Modify: `app/__init__.py` — after the `secret_key = os.getenv(...)` line, add:

```python
if secret_key == "dev-secret-change-me" and os.getenv("FLASK_ENV", "").lower() == "production":
    raise RuntimeError("SECRET_KEY must be set in production (see .env.example)")
```

(Adjust the env check to match however this app already distinguishes prod — inspect `app/__init__.py` for an existing `FLASK_ENV`/`ENV`/`DEBUG` convention and use that instead if one exists.)

- Modify: `app/services/rate_limiter.py` — add one comment near the module docstring: `# ponytail: in-memory, single-process only; move to a shared store if gunicorn workers > 1`

**Test:** one small test asserting the RuntimeError fires with the default key + production env (monkeypatch env vars, reimport or call the guard). Keep it minimal — if the guard is extracted as a tiny function, test that function directly.

- [ ] **Step 1: Inspect existing prod/dev detection convention in `app/__init__.py` and `run.py`**
- [ ] **Step 2: Add the guard + comment, add the minimal test**
- [ ] **Step 3: Run tests (`pytest -x -q`) and commit**

```bash
git commit -m "feat(security): refuse to start in production with default SECRET_KEY"
```

---

### Task 9: Consolidate the two admin panels — fold admin.py into admin_new.py

Both `app/routes/admin.py` (562 lines, `bp_admin`) and `app/routes/admin_new.py` (809 lines, `bp_admin_new`) are registered. Templates (`admin_base.html`, `admin_users.html`, `admin_game_rules.html`, `base.html`) still call `url_for('admin.*')` endpoints. End state: ONE admin blueprint, `admin.py` deleted.

**Approach (implementer verifies before acting):**
1. Enumerate every route in `admin.py` and every route in `admin_new.py`. Identify overlaps (same functionality in both) and `admin.py`-only endpoints.
2. For each `admin.py`-only endpoint, check whether anything references it (`url_for('admin.<name>')` in templates/python, fetch URLs in JS). Unreferenced → drop. Referenced → move the handler into `admin_new.py` (keep URL paths stable for JS fetch calls; update `url_for` endpoint names in templates from `admin.*` to `admin_new.*`).
3. For overlapping endpoints, keep the `admin_new.py` version; repoint any template/JS references.
4. Remove `bp_admin` import/registration from `app/__init__.py`; delete `app/routes/admin.py`.
5. If admin templates exist that are only rendered by dropped endpoints, delete those templates too.

**Constraints:**
- No URL path changes for endpoints called from JS via hardcoded paths (JS does not use url_for).
- All existing admin tests must pass; update tests that import from `app.routes.admin` to the new location rather than deleting them.

- [ ] **Step 1: Route inventory + reference map (report it in the task report before changing code)**
- [ ] **Step 2: Move/merge referenced handlers, repoint templates**
- [ ] **Step 3: Deregister and delete admin.py, delete orphaned templates**
- [ ] **Step 4: Run full tests (`pytest -x -q`) and commit**

```bash
git commit -m "refactor(admin): consolidate admin panels into single blueprint, delete legacy admin.py"
```

---

### Task 10: Single migration path — alembic only

Four schema-migration mechanisms coexist:
1. Alembic (`migrations/`, 18 revisions) — actively used, keep.
2. `app/migrations/apply_migrations` (131 lines, versioned guarded DDL via `schema_version` table).
3. `_run_lightweight_migrations` in `app/__init__.py` (guarded DDL at import time).
4. `server._run_migrations` in `app/server.py` (guarded ALTER TABLE for user columns etc.).

End state: alembic is the only migration system. Startup still self-migrates (dev convenience) by invoking alembic programmatically.

**Approach:**
1. Write ONE new alembic revision (`legacy_baseline_guards`) that performs, idempotently (inspect columns first, same guards as today), every DDL change currently made by mechanisms 2–4. Content must be a faithful port — enumerate every guarded ALTER/CREATE in those three places and carry each one over.
2. Replace the calls to mechanisms 2–4 in `app/__init__.py` / `app/server.py` with a single programmatic `flask_migrate.upgrade()` (or `alembic.command.upgrade(config, "head")`) invocation at the same startup point, guarded so a failure logs rather than crashes dev startup only if that matches current behavior (current mechanisms swallow errors — preserve that startup resilience with one try/except around the upgrade call, logging the exception).
3. Handle pre-alembic databases: if the DB has tables but no `alembic_version` table, `flask_migrate.stamp()` to the revision preceding the new one before upgrading (document this in the revision docstring). Fresh DBs: `create_all` already runs first; stamping to head after create_all is the existing implicit behavior — make it explicit.
4. Delete `app/migrations/` entirely, `_run_lightweight_migrations` from `app/__init__.py`, and `server._run_migrations` (and its call sites).
5. The `schema_version` table becomes vestigial — leave the table in existing DBs (no destructive drop) but remove all code touching it.
6. `sql/*_migration.sql` files: check whether anything executes them at runtime (grep showed `sql/` referenced from `app/server.py`, `run.py`, `app/routes/admin_new.py`, `app/seed_items.py`, `app/models/models.py`, `docker-compose.yml`). SEED files stay. Files that only duplicate schema DDL now covered by alembic get deleted; if a runtime code path executes a `*_migration.sql`, port that DDL into the new alembic revision and remove the execution path.

**Constraints:**
- A test database created fresh (delete `test.db`, run the suite) must come up with an identical schema to before.
- An existing dev database must upgrade cleanly: verify by copying the current dev DB (if present) and running startup against the copy.
- Full test suite passes.

- [ ] **Step 1: Enumerate every guarded DDL statement across mechanisms 2–4 and any runtime-executed `*_migration.sql` (list them in the task report)**
- [ ] **Step 2: Write the alembic revision + startup upgrade call**
- [ ] **Step 3: Delete mechanisms 2–4 and dead SQL files**
- [ ] **Step 4: Fresh-DB + existing-DB verification, full tests, commit**

```bash
git commit -m "refactor(db): consolidate four migration mechanisms into alembic-only path"
```
