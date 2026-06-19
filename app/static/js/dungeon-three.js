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

    // -- Public API (stubs in this task; filled in by later tasks) --
    loadMap(data) {
        this.grid = data.grid;
        this.width = data.width;
        this.height = data.height;
        this.seed = data.seed;
        this._renderFrame();
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
    }

    zoomOut() {
        this.targetZoom = Math.max(MIN_ZOOM, this.targetZoom - ZOOM_STEP);
    }

    resetZoom() {
        this.targetZoom = 1.0;
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
