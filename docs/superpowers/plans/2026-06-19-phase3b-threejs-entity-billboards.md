# Phase 3b — Three.js Entity/Player Billboards & Movement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add player and entity (monster/NPC) billboard sprites to the
Three.js dungeon renderer (`dungeon-three.js`), plus camera-follow movement,
bringing it to feature parity with the 2D renderer on everything except
fog-of-war opacity and the minimap.

**Architecture:** `THREE.Sprite` billboards (always face the camera by
default) textured from the existing SVG icon files via `Image` + raw
`THREE.Texture`. A small texture cache avoids redundant loads. Entities are
rebuilt from scratch on every `setEntities` call (simplest correct approach
given small entity counts). The player sprite persists across calls and the
camera re-targets to the player's position on every move.

**Tech Stack:** Same as Phase 3a — Three.js `0.169.0` via CDN ES-module
import, no new dependencies, no JS test runner (verification is manual/visual
via Playwright).

## Global Constraints

- Single file touched: `app/static/js/dungeon-three.js`. No template, other-JS,
  or backend changes.
- Sprite world position: `(x, 0.6, y)` for both player and entities.
- Sprite scale: `0.8 × 0.8` world units (fixed, no per-entity variation).
- Entity visibility cutoff: Euclidean distance from current `playerPos` must
  be `<= OUTER_VIS_RADIUS` (`26`, matching `dungeon-canvas.js`'s default) or
  the entity is skipped entirely — no opacity gradient, binary cutoff only.
- Player icon path: `/static/iconography/axe-sword.svg` (fixed, not derived
  from any entity-style `icon` field).
- Entity default icon fallback (when `entity.icon` is absent):
  `/static/iconography/goblin-scout-t1.svg` (matches `dungeon-canvas.js`).
- `centerOnPlayer()` must become a real, idempotent call (no-op only if
  `this.playerPos` is `null`).
- No smoothing/easing on camera movement — every move snaps instantly via one
  `_positionCamera` call.
- A failed icon image load must `console.warn` and leave that sprite visually
  blank — never throw.

---

### Task 1: Texture cache + sprite factory helpers

**Files:**
- Modify: `app/static/js/dungeon-three.js`

**Interfaces:**
- Consumes: `THREE` (already imported), `this._renderFrame()` (existing,
  Phase 3a).
- Produces: `this._textureCache` (a `Map<string, THREE.Texture>`, initialized
  in the constructor), `_getOrLoadTexture(path: string): THREE.Texture`,
  `_makeSprite(iconPath: string): THREE.Sprite` — both used by Task 2/3.

- [ ] **Step 1: Add the texture cache field to the constructor**

In `app/static/js/dungeon-three.js`, find the constructor's field
initialization block (currently ending with `this.wallMesh = null;` right
before the `this._initScene();` call). Add immediately after `this.wallMesh =
null;`:

```javascript
        this._textureCache = new Map();
        this.playerSprite = null;
        this.entitySprites = [];
```

- [ ] **Step 2: Add `_getOrLoadTexture` and `_makeSprite` methods**

Add these two new methods anywhere after `_renderFrame()` and before the
`// -- Public API` comment:

```javascript
    _getOrLoadTexture(path) {
        if (this._textureCache.has(path)) {
            return this._textureCache.get(path);
        }
        const texture = new THREE.Texture();
        const img = new Image();
        img.onload = () => {
            texture.image = img;
            texture.needsUpdate = true;
            this._renderFrame();
        };
        img.onerror = () => {
            console.warn('Failed to load icon texture:', path);
        };
        img.src = path;
        this._textureCache.set(path, texture);
        return texture;
    }

    _makeSprite(iconPath) {
        const material = new THREE.SpriteMaterial({
            map: this._getOrLoadTexture(iconPath),
            transparent: true,
        });
        const sprite = new THREE.Sprite(material);
        sprite.scale.set(0.8, 0.8, 1);
        return sprite;
    }
```

- [ ] **Step 3: Verify the file still parses with no syntax errors**

Run: `node --check app/static/js/dungeon-three.js`
Expected: no output, exit code 0 (this is a syntax-only check; ES-module
import resolution isn't validated by `--check`, which is fine — it's not the
concern here, only correctness of the edit).

- [ ] **Step 4: Commit**

```bash
git add app/static/js/dungeon-three.js
git commit -m "feat(dungeon-three): add texture cache and sprite factory helpers"
```

---

### Task 2: Player billboard + camera-follow movement

**Files:**
- Modify: `app/static/js/dungeon-three.js`

**Interfaces:**
- Consumes: `_makeSprite(iconPath)` (Task 1), `_positionCamera(target)`
  (existing, Phase 3a), `this.playerSprite` (initialized to `null` in Task 1).
- Produces: `updatePlayerPosition(x, y)` (replaces the Phase 3a stub),
  `centerOnPlayer()` (replaces the Phase 3a no-op stub) — both depended on by
  Task 3's manual verification and by `adventure.js`'s existing call sites
  (unchanged, no signature change).

- [ ] **Step 1: Replace `updatePlayerPosition`**

Find the existing method (Phase 3a stub):
```javascript
    updatePlayerPosition(x, y) {
        this.playerPos = { x, y };
    }
```
Replace with:
```javascript
    updatePlayerPosition(x, y) {
        this.playerPos = { x, y };
        if (!this.playerSprite) {
            this.playerSprite = this._makeSprite('/static/iconography/axe-sword.svg');
            this.scene.add(this.playerSprite);
        }
        this.playerSprite.position.set(x, 0.6, y);
        this.centerOnPlayer();
    }
```

- [ ] **Step 2: Replace `centerOnPlayer`**

Find the existing method (Phase 3a no-op stub):
```javascript
    centerOnPlayer() {
        // No-op in this milestone (no player rendering/camera-follow yet).
    }
```
Replace with:
```javascript
    centerOnPlayer() {
        if (!this.playerPos) return;
        this._positionCamera(new THREE.Vector3(this.playerPos.x, 0, this.playerPos.y));
        this._renderFrame();
    }
```

- [ ] **Step 3: Verify the file still parses with no syntax errors**

Run: `node --check app/static/js/dungeon-three.js`
Expected: no output, exit code 0.

- [ ] **Step 4: Commit**

```bash
git add app/static/js/dungeon-three.js
git commit -m "feat(dungeon-three): add player billboard sprite and camera-follow movement"
```

---

### Task 3: Entity billboards with vision-radius cutoff

**Files:**
- Modify: `app/static/js/dungeon-three.js`

**Interfaces:**
- Consumes: `_makeSprite(iconPath)` (Task 1), `this.entitySprites` (Task 1),
  `this.playerPos` (set by Task 2's `updatePlayerPosition`).
- Produces: `setEntities(entities)` (replaces the Phase 3a stub) — each entity
  is `{x: number, y: number, icon?: string}`. No later task depends on this
  beyond manual verification (Task 4).

- [ ] **Step 1: Add the `OUTER_VIS_RADIUS` constant**

Find the existing constants block near the top of the file (after
`CAMERA_AZIMUTH_DEG`). Add:

```javascript
const OUTER_VIS_RADIUS = 26; // matches dungeon-canvas.js's default fogConfig.fullRadius
const ENTITY_DEFAULT_ICON = '/static/iconography/goblin-scout-t1.svg';
```

- [ ] **Step 2: Replace `setEntities`**

Find the existing method (Phase 3a stub):
```javascript
    setEntities(entities) {
        this.entities = entities;
    }
```
Replace with:
```javascript
    setEntities(entities) {
        this.entities = entities;

        this.entitySprites.forEach((sprite) => this.scene.remove(sprite));
        this.entitySprites = [];

        if (!this.playerPos) {
            this._renderFrame();
            return;
        }

        entities.forEach((entity) => {
            const dist = Math.hypot(entity.x - this.playerPos.x, entity.y - this.playerPos.y);
            if (dist > OUTER_VIS_RADIUS) {
                return;
            }
            const sprite = this._makeSprite(entity.icon || ENTITY_DEFAULT_ICON);
            sprite.position.set(entity.x, 0.6, entity.y);
            this.entitySprites.push(sprite);
            this.scene.add(sprite);
        });

        this._renderFrame();
    }
```

- [ ] **Step 3: Verify the file still parses with no syntax errors**

Run: `node --check app/static/js/dungeon-three.js`
Expected: no output, exit code 0.

- [ ] **Step 4: Commit**

```bash
git add app/static/js/dungeon-three.js
git commit -m "feat(dungeon-three): add entity billboard sprites with vision-radius cutoff"
```

---

### Task 4: Live browser verification and TODO update

**Files:**
- Modify: `docs/superpowers/TODO.md`
- Test: manual, via real browser (Playwright), as used for Phases 1-3a.

**Interfaces:**
- Consumes: all of Tasks 1-3 (the complete, wired-up `DungeonCanvasThree`
  class).
- Produces: nothing new — closing verification + documentation task.

- [ ] **Step 1: Run the full backend test suite to confirm no regressions**

```bash
export DATABASE_URL=postgresql://adventure:changeme@localhost:5433/adventure_test
export TEST_DATABASE_URL=$DATABASE_URL
.venv/bin/python -c "from app import create_app, db; app=create_app()
with app.app_context():
    db.drop_all(); db.create_all()"
.venv/bin/python -m pytest tests/ -q --deselect tests/test_combat_persistence.py --deselect tests/test_gear_party_payload.py::test_payload_reflects_gear_hp
```
Expected: all tests pass (the second deselect is the confirmed pre-existing
failure from prior phases, unrelated to this frontend-only work — this phase
makes zero backend changes).

- [ ] **Step 2: Launch the dev server and verify in a real browser**

Use a Playwright install available on the host (as used for Phases 1-3a's
verification: register a throwaway account via curl, capture the session
cookie, inject into a Playwright browser context, navigate, screenshot — all
within one continuous Playwright page session per the known stale-cookie
gotcha from Phase 3a). Navigate to `/adventure?renderer=three` and confirm:
- The player's billboard renders at the correct grid tile (visually matches
  the player's position shown in the 2D renderer for the same account/dungeon).
- Triggering a move (via the existing movement controls) snaps the camera to
  follow the player to the new tile — take screenshots before and after one
  move and confirm the player sprite stays centered in both.
- If the test dungeon has any monster/NPC entities present, they render as
  billboards at their correct tiles.
- No console errors on load or after a move.
- Loading `/adventure` (no query param) still shows the unaffected default 2D
  renderer.

Clean up the throwaway test account afterward, deleting in FK order:
`DungeonEntity` (by `instance_id`) → `Character` (by `user_id`) →
`DungeonInstance` (by `user_id`) → `User`.

- [ ] **Step 3: Update `docs/superpowers/TODO.md`**

Find the Phase 3a entry via `grep -n "UI Redesign Phase 3a" docs/superpowers/TODO.md`.
Add a new entry immediately after it:

```markdown
### UI Redesign Phase 3b — Three.js entity/player billboards + movement ✅
Added `THREE.Sprite` billboards for the player (fixed `axe-sword.svg` icon)
and entities (per-entity `icon` field, falling back to `goblin-scout-t1.svg`),
textured via `Image` + raw `THREE.Texture` with a small per-path cache.
Entities beyond `OUTER_VIS_RADIUS` (26, matching `dungeon-canvas.js`'s
default) from the player are skipped — a binary cutoff, not the opacity
gradient (that's Phase 3c's fog-of-war work). `updatePlayerPosition` now
moves/creates the player sprite and re-centers the camera on every call
(camera-follow movement, snap-only, no easing). `centerOnPlayer()` is a real
call now, no longer a no-op stub. Design:
`specs/2026-06-19-phase3b-threejs-entity-billboards-design.md`.
Next: Phase 3c (client-side fog-of-war opacity dimming).
```

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/TODO.md
git commit -m "docs(todo): mark UI redesign Phase 3b (entity/player billboards) done"
```
