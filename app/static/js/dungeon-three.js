/**
 * Three.js-based dungeon map renderer (Phase 3a — static tile grid only).
 * Toggle-gated alternative to dungeon-canvas.js; see docs/superpowers/specs/
 * 2026-06-19-phase3a-threejs-dungeon-scene-design.md for full design.
 */
import * as THREE from 'https://cdn.jsdelivr.net/npm/three@0.169.0/build/three.module.js';

const ZOOM_STEP = 0.1;
const MIN_ZOOM = 0.5;
const MAX_ZOOM = 2.0;
const FRUSTUM_HALF_SIZE = 10; // world units at zoom = 1.0
const CAMERA_RADIUS = 12; // world units
const CAMERA_ELEVATION_DEG = 55;
const CAMERA_AZIMUTH_DEG = 45;

const TILE_COLORS = {
    room: 0x2d3340,
    tunnel: 0x242a36,
    door: 0x9a6b35,
    locked_door: 0x964a4a,
    teleporter: 0x6b46c1,
    wall: 0x39414f,
    secret_door: 0x39414f,
};

const FLOOR_TYPES = new Set(['room', 'tunnel', 'door', 'locked_door', 'teleporter']);
const WALL_TYPES = new Set(['wall', 'secret_door']);

class DungeonCanvasThree {
    constructor(canvasId, options = {}) {
        this.canvas = document.getElementById(canvasId);
        if (!this.canvas) {
            throw new Error(`Canvas element #${canvasId} not found`);
        }
        this.options = options;

        this.grid = null;
        this.width = 0;
        this.height = 0;
        this.seed = null;
        this.playerPos = null;
        this.seenTiles = new Set();
        this.entities = [];
        this.notices = [];

        this.zoom = 1.0;
        this.targetZoom = 1.0;

        this.floorMesh = null;
        this.wallMesh = null;

        this._textureCache = new Map();
        this.playerSprite = null;
        this.entitySprites = [];

        this._initScene();
    }

    _initScene() {
        this.scene = new THREE.Scene();
        this.renderer = new THREE.WebGLRenderer({ canvas: this.canvas, antialias: true });
        this.renderer.setSize(this.canvas.width, this.canvas.height, false);

        const aspect = this.canvas.width / this.canvas.height;
        this.camera = new THREE.OrthographicCamera(
            -FRUSTUM_HALF_SIZE * aspect,
            FRUSTUM_HALF_SIZE * aspect,
            FRUSTUM_HALF_SIZE,
            -FRUSTUM_HALF_SIZE,
            0.1,
            1000
        );
        this._positionCamera(new THREE.Vector3(0, 0, 0));
        this._renderFrame();
    }

    _positionCamera(target) {
        const elevRad = THREE.MathUtils.degToRad(CAMERA_ELEVATION_DEG);
        const azimRad = THREE.MathUtils.degToRad(CAMERA_AZIMUTH_DEG);
        const horizDist = CAMERA_RADIUS * Math.cos(elevRad);
        this.camera.position.set(
            target.x + horizDist * Math.cos(azimRad),
            CAMERA_RADIUS * Math.sin(elevRad),
            target.z + horizDist * Math.sin(azimRad)
        );
        this.camera.lookAt(target);
        this.camera.updateProjectionMatrix();
    }

    _renderFrame() {
        this.renderer.render(this.scene, this.camera);
    }

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

    // -- Public API (stubs in this task; filled in by later tasks) --
    loadMap(data) {
        this.grid = data.grid;
        this.width = data.width;
        this.height = data.height;
        this.seed = data.seed;

        for (let y = 0; y < this.height; y++) {
            for (let x = 0; x < this.width; x++) {
                if (this.grid[y][x] !== 'unknown') {
                    this.seenTiles.add(`${x},${y}`);
                }
            }
        }

        this._buildTileGrid();
        this._positionCamera(new THREE.Vector3(this.width / 2, 0, this.height / 2));
        this._renderFrame();
    }

    _buildTileGrid() {
        if (this.tileMeshes) {
            this.tileMeshes.forEach((mesh) => {
                this.scene.remove(mesh);
                mesh.dispose?.();
            });
        }
        this.tileMeshes = [];

        // Group cells by exact tile type (one InstancedMesh per type, plain
        // solid-color material — see commit message for why per-instance
        // vertexColors was abandoned: MeshBasicMaterial's vertexColors path
        // multiplies instanceColor against the geometry's own vertex color
        // attribute, which BoxGeometry/PlaneGeometry don't define, producing
        // solid black instead of the intended per-instance color).
        const cellsByType = new Map();
        for (let y = 0; y < this.height; y++) {
            for (let x = 0; x < this.width; x++) {
                const cellType = this.grid[y][x];
                if (!FLOOR_TYPES.has(cellType) && !WALL_TYPES.has(cellType)) {
                    // 'cave' and 'unknown' (and anything else unrecognized):
                    // intentionally skipped, no instance allocated.
                    continue;
                }
                if (!cellsByType.has(cellType)) {
                    cellsByType.set(cellType, []);
                }
                cellsByType.get(cellType).push({ x, y });
            }
        }

        for (const [cellType, cells] of cellsByType) {
            const isWall = WALL_TYPES.has(cellType);
            const geometry = isWall ? new THREE.BoxGeometry(1, 1, 1) : new THREE.PlaneGeometry(1, 1);
            const yOffset = isWall ? 0.5 : 0;
            const mesh = this._buildInstancedMesh(cells, geometry, TILE_COLORS[cellType], (m, cell) => {
                if (!isWall) {
                    m.makeRotationX(-Math.PI / 2);
                }
                m.setPosition(cell.x, yOffset, cell.y);
            });
            this.tileMeshes.push(mesh);
            this.scene.add(mesh);
        }

        // Back-compat aliases for any external code/tests inspecting these by
        // name (e.g. floor vs. wall tile counts) — point at the first mesh of
        // each category, or null if that category has no cells this map.
        this.floorMesh = this.tileMeshes.find((m) => !m.userData.isWall) || null;
        this.wallMesh = this.tileMeshes.find((m) => m.userData.isWall) || null;
    }

    _buildInstancedMesh(cells, geometry, colorHex, placeFn) {
        const material = new THREE.MeshBasicMaterial({ color: colorHex });
        const mesh = new THREE.InstancedMesh(geometry, material, Math.max(cells.length, 1));
        mesh.count = cells.length;
        mesh.userData.isWall = geometry.type === 'BoxGeometry';
        const m = new THREE.Matrix4();
        cells.forEach((cell, i) => {
            m.identity();
            placeFn(m, cell);
            mesh.setMatrixAt(i, m);
        });
        mesh.instanceMatrix.needsUpdate = true;
        return mesh;
    }

    updatePlayerPosition(x, y) {
        this.playerPos = { x, y };
    }

    setEntities(entities) {
        this.entities = entities;
    }

    setNotices(notices) {
        this.notices = notices;
    }

    addRevealedTiles(tiles) {
        // No-op in this milestone (Phase 3a renders a static grid only).
    }

    zoomIn() {
        this.targetZoom = Math.min(MAX_ZOOM, this.targetZoom + ZOOM_STEP);
        this._applyZoom();
    }

    zoomOut() {
        this.targetZoom = Math.max(MIN_ZOOM, this.targetZoom - ZOOM_STEP);
        this._applyZoom();
    }

    resetZoom() {
        this.targetZoom = 1.0;
        this._applyZoom();
    }

    _applyZoom() {
        this.zoom = this.targetZoom;
        this.camera.zoom = this.zoom;
        this.camera.updateProjectionMatrix();
        this._renderFrame();
    }

    getCoverage() {
        const total = this.width * this.height;
        const seen = this.seenTiles.size;
        const pct = total ? (seen / total) * 100 : 0;
        return { seen, total, pct: pct.toFixed(2) };
    }

    clearSeenTiles() {
        this.seenTiles.clear();
    }

    loadSeenTiles() {
        // No-op in this milestone — seenTiles is populated directly from
        // loadMap()'s grid data, not persisted/restored from localStorage.
    }

    saveSeenTiles() {
        // No-op in this milestone (see loadSeenTiles note above).
    }

    centerOnPlayer() {
        // No-op in this milestone (no player rendering/camera-follow yet).
    }
}

window.DungeonCanvasThree = DungeonCanvasThree;
