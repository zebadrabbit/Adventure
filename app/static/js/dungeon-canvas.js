/**
 * Canvas-based dungeon map renderer
 * Replaces Leaflet for better performance and roguelike-appropriate rendering
 */

(function () {
    'use strict';

    const TILE_SIZE = 32; // pixels per tile
    const MIN_ZOOM = 0.5;
    const MAX_ZOOM = 2.0;
    const ZOOM_STEP = 0.1;

    // Fog-of-war configuration - these will be overridden by activeFogConfig from adventure.js
    // Default values in case fog config isn't loaded yet
    let INNER_VIS_RADIUS = 8;
    let OUTER_VIS_RADIUS = 26;
    let FOG_GRADIENT_STEPS = OUTER_VIS_RADIUS - INNER_VIS_RADIUS;
    let MEMORY_DIM_ALPHA = 0.35;
    let MIN_FOG_ALPHA = 0.18;
    let MAX_FOG_ALPHA = 0.92;
    let FOG_NOISE_AMPLITUDE = 0.08;

    // Expose function to update fog config from adventure.js
    window.updateCanvasFogConfig = function (cfg) {
        INNER_VIS_RADIUS = cfg.innerRadius;
        OUTER_VIS_RADIUS = cfg.fullRadius;
        FOG_GRADIENT_STEPS = OUTER_VIS_RADIUS - INNER_VIS_RADIUS;
        MEMORY_DIM_ALPHA = cfg.memoryOpacity;
        MIN_FOG_ALPHA = cfg.minOpacity;
        MAX_FOG_ALPHA = cfg.maxOpacity;
        FOG_NOISE_AMPLITUDE = cfg.noise;

        // Trigger re-render if canvas exists
        if (window.dungeonCanvas) {
            window.dungeonCanvas.render();
        }
    };

    // ---------------------------------------------------------------- tileset
    // Optional 16x16 spritesheet. When present every tile is drawn from it;
    // when absent paintTile() falls back to the procedural flagstone/bevel
    // rendering below, so a clone without the art still runs and still reads.
    //
    // The art is third-party and licence-restricted (see docs/ASSETS.md), so it
    // is gitignored -- absence is the normal case for anyone but the author.
    const TILE_SHEET_SRC = '/static/tiles/dungeon-set.png';
    const SHEET_TILE = 16; // source cell size in the sheet

    // Sheet coordinates as [col, row]. `base` is drawn first; `overlay` is drawn
    // on top of the base and may have transparency (stairs, props). Edit these
    // to re-pick tiles -- nothing else needs to change.
    const TILE_SPRITES = {
        room: { base: [5, 6] },
        tunnel: { base: [6, 6] },
        wall: { base: [13, 3] },
        secret_door: { base: [13, 3] },   // must be indistinguishable from wall
        door: { base: [11, 4] },
        locked_door: { base: [16, 0] },   // portcullis
        stairs_up: { base: [5, 6], overlay: [16, 3] },
        stairs_down: { base: [5, 6], overlay: [17, 4] },
        teleporter: { base: [5, 6] },     // the animated portal glow paints over this
    };

    const tileSheet = new Image();
    let tileSheetReady = false;
    tileSheet.onload = () => {
        tileSheetReady = true;
        if (window.dungeonCanvas) window.dungeonCanvas.render();
    };
    tileSheet.onerror = () => { tileSheetReady = false; };
    tileSheet.src = TILE_SHEET_SRC;

    // Tile color palette (dark mode optimized). `base` is the flat colour used
    // for the minimap and as a fallback; the richer per-tile art in paintTile()
    // layers floor texture, beveled walls and wooden doors on top.
    const TILE_COLORS = {
        room: '#2d3340',
        tunnel: '#242a36',
        wall: '#39414f',
        door: '#9a6b35',
        secret_door: '#39414f',
        locked_door: '#964a4a',
        cave: '#0a0b0f',
        teleporter: '#6B46C1',
        stairs_up: '#3f8f5f',
        stairs_down: '#8f7a3f',
        default: '#1a1d24'
    };

    // Extended style table for textured tile rendering.
    const TILE_STYLE = {
        cave: { kind: 'void', base: '#0a0b0f' },
        room: { kind: 'floor', base: '#2d3340', alt: '#333a48', edge: 'rgba(0,0,0,0.28)' },
        tunnel: { kind: 'floor', base: '#242a36', alt: '#282f3c', edge: 'rgba(0,0,0,0.32)' },
        wall: { kind: 'wall', base: '#39414f', hi: '#515b6e', lo: '#232932' },
        secret_door: { kind: 'wall', base: '#39414f', hi: '#515b6e', lo: '#232932' },
        door: { kind: 'door', floor: '#2d3340', wood: '#9a6b35', plank: '#6f4a22' },
        locked_door: { kind: 'door', floor: '#2d3340', wood: '#964a4a', plank: '#602a2a' },
        stairs_up: { kind: 'floor', base: '#2b4636', alt: '#3f8f5f', edge: 'rgba(0,0,0,0.32)' },
        stairs_down: { kind: 'floor', base: '#463e2b', alt: '#8f7a3f', edge: 'rgba(0,0,0,0.32)' },
        default: { kind: 'void', base: '#1a1d24' }
    };

    class DungeonCanvas {
        constructor(canvasId, options = {}) {
            this.canvas = document.getElementById(canvasId);
            if (!this.canvas) {
                throw new Error(`Canvas element #${canvasId} not found`);
            }

            this.ctx = this.canvas.getContext('2d');
            this.options = options;

            // Map state
            this.grid = null;
            this.width = 0;
            this.height = 0;
            this.playerPos = null;
            this.seenTiles = new Set();
            this.seed = null;

            // View state
            this.zoom = 1.0;
            this.offsetX = 0;
            this.offsetY = 0;
            this.isDragging = false;
            this.dragStartX = 0;
            this.dragStartY = 0;

            // Entity markers
            this.entities = [];
            this.notices = [];

            // Image cache for SVG icons
            this.imageCache = new Map();
            this.loadingImages = new Map();
            this.failedImages = new Set();

            // Animation state for smooth pan/zoom
            this.targetZoom = 1.0;
            this.targetOffsetX = 0;
            this.targetOffsetY = 0;
            this.animating = false;

            // Hover state for tooltips
            this.hoverTile = null;

            // Animation loop for teleporter effects
            this.animationFrameId = null;
            this.startContinuousAnimation();

            // Bind event handlers
            this.setupEventHandlers();
            this.resizeCanvas();
        }

        startContinuousAnimation() {
            // Continuous render loop for animated effects (teleporter pulse)
            const animate = () => {
                if (this.grid && this.hasTeleporters()) {
                    this.render();
                }
                this.animationFrameId = requestAnimationFrame(animate);
            };
            animate();
        }

        hasTeleporters() {
            // Check if grid contains any teleporter tiles
            if (!this.grid) return false;
            for (let y = 0; y < this.height; y++) {
                for (let x = 0; x < this.width; x++) {
                    if (this.grid[y][x] === 'teleporter') return true;
                }
            }
            return false;
        }

        setupEventHandlers() {
            // Mouse events for pan
            this.canvas.addEventListener('mousedown', this.onMouseDown.bind(this));
            this.canvas.addEventListener('mousemove', this.onMouseMove.bind(this));
            this.canvas.addEventListener('mouseup', this.onMouseUp.bind(this));
            this.canvas.addEventListener('mouseleave', this.onMouseUp.bind(this));

            // Hover for tooltips
            this.canvas.addEventListener('mousemove', this.onHover.bind(this), { passive: true });

            // Click for teleporter activation
            this.canvas.addEventListener('click', this.onClick.bind(this));

            // Mouse wheel for zoom
            this.canvas.addEventListener('wheel', this.onWheel.bind(this), { passive: false });

            // Touch events for mobile
            this.canvas.addEventListener('touchstart', this.onTouchStart.bind(this), { passive: false });
            this.canvas.addEventListener('touchmove', this.onTouchMove.bind(this), { passive: false });
            this.canvas.addEventListener('touchend', this.onTouchEnd.bind(this));

            // Resize handler
            window.addEventListener('resize', this.resizeCanvas.bind(this), { passive: true });
        }

        resizeCanvas() {
            // Clear last pass's explicit size before measuring. The inline
            // width/height set below beat the stylesheet's width/height:100%,
            // so re-reading the box without this returns the size we pinned it
            // to last time and the canvas can never follow the window down --
            // it stayed 1366x768 inside a 2560x1440 frame, and inside a 1100px
            // one it stuck out far enough to give the page a horizontal
            // scrollbar.
            this.canvas.style.width = '';
            this.canvas.style.height = '';

            const rect = this.canvas.getBoundingClientRect();
            const dpr = window.devicePixelRatio || 1;

            this.canvas.width = rect.width * dpr;
            this.canvas.height = rect.height * dpr;

            this.ctx.scale(dpr, dpr);
            this.canvas.style.width = rect.width + 'px';
            this.canvas.style.height = rect.height + 'px';

            // Re-centre, not just repaint. The canvas is the viewport now, so
            // both halves of centerOnPlayer's arithmetic have just changed:
            // the box it measures, and -- crossing the 1200px breakpoint --
            // the --hud-inset-* values it reads, which flip between 300/220
            // and 0/0. Without this the party drifts off centre, and in the
            // stacked layout can end up behind a panel. Not smoothed: a resize
            // is a discrete event, and easing toward a target that a drag on
            // the window edge keeps moving just looks like lag.
            this.centerOnPlayer(false);
            this.render();
        }

        onMouseDown(e) {
            this.isDragging = true;
            this.dragStartX = e.clientX - this.offsetX;
            this.dragStartY = e.clientY - this.offsetY;
            this.canvas.style.cursor = 'grabbing';
        }

        onMouseMove(e) {
            if (this.isDragging) {
                this.setView(e.clientX - this.dragStartX, e.clientY - this.dragStartY);
                this.render();
            }
        }

        onMouseUp() {
            this.isDragging = false;
            this.canvas.style.cursor = 'grab';
        }

        onClick(e) {
            // Don't activate if dragging
            if (this.isDragging) return;

            const rect = this.canvas.getBoundingClientRect();
            const mouseX = e.clientX - rect.left;
            const mouseY = e.clientY - rect.top;

            // Convert to world coordinates
            const worldX = (mouseX - this.offsetX) / this.zoom;
            const worldY = (mouseY - this.offsetY) / this.zoom;

            // Convert to tile coordinates (accounting for flipped Y)
            const tileX = Math.floor(worldX / TILE_SIZE);
            const tileY = this.height - 1 - Math.floor(worldY / TILE_SIZE);

            // Check if clicked tile is a teleporter
            if (tileX >= 0 && tileX < this.width && tileY >= 0 && tileY < this.height) {
                const cell = this.grid[tileY][tileX];
                if (cell === 'teleporter') {
                    this.activateTeleporter(tileX, tileY);
                }
            }
        }

        activateTeleporter(x, y) {
            // Check if player is on or adjacent to the teleporter
            if (!this.playerPos) return;

            const dist = Math.hypot(x - this.playerPos.x, y - this.playerPos.y);
            if (dist > 1.5) {
                console.log('[teleporter] Too far from teleporter');
                return;
            }

            console.log(`[teleporter] Activating teleporter at (${x}, ${y})`);

            // Move to teleporter first if not already on it
            if (this.playerPos.x !== x || this.playerPos.y !== y) {
                // Calculate direction to teleporter
                const dx = x - this.playerPos.x;
                const dy = y - this.playerPos.y;
                let dir = '';
                if (Math.abs(dx) > Math.abs(dy)) {
                    dir = dx > 0 ? 'e' : 'w';
                } else {
                    dir = dy > 0 ? 'n' : 's';
                }

                // Queue move to teleporter
                if (window.queueMove) {
                    window.queueMove(dir);
                }
            }
        }

        onHover(e) {
            if (this.isDragging) return;

            const rect = this.canvas.getBoundingClientRect();
            const mouseX = e.clientX - rect.left;
            const mouseY = e.clientY - rect.top;

            // Convert screen coords to world coords
            const worldX = (mouseX - this.offsetX) / this.zoom;
            const worldY = (mouseY - this.offsetY) / this.zoom;

            // Convert to tile coords
            const tileX = Math.floor(worldX / TILE_SIZE);
            const tileY = Math.floor(worldY / TILE_SIZE);

            // Flip Y coordinate back to game coords
            const gameTileY = this.height - 1 - tileY;

            if (tileX >= 0 && tileX < this.width && gameTileY >= 0 && gameTileY < this.height) {
                const cell = this.grid[gameTileY][tileX];
                if (cell && cell !== 'unknown') {
                    this.hoverTile = { x: tileX, y: gameTileY, cell };
                    this.render();
                    return;
                }
            }

            if (this.hoverTile) {
                this.hoverTile = null;
                this.render();
            }
        }

        onWheel(e) {
            e.preventDefault();
            const delta = e.deltaY > 0 ? -ZOOM_STEP : ZOOM_STEP;
            const newZoom = Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, this.zoom + delta));

            if (newZoom !== this.zoom) {
                const rect = this.canvas.getBoundingClientRect();
                const mouseX = e.clientX - rect.left;
                const mouseY = e.clientY - rect.top;

                // Zoom toward mouse position
                const zoomRatio = newZoom / this.zoom;
                this.setView(
                    mouseX - (mouseX - this.offsetX) * zoomRatio,
                    mouseY - (mouseY - this.offsetY) * zoomRatio,
                    newZoom
                );
                this.render();
            }
        }

        onTouchStart(e) {
            if (e.touches.length === 1) {
                e.preventDefault();
                const touch = e.touches[0];
                this.isDragging = true;
                this.dragStartX = touch.clientX - this.offsetX;
                this.dragStartY = touch.clientY - this.offsetY;
            }
        }

        onTouchMove(e) {
            if (e.touches.length === 1 && this.isDragging) {
                e.preventDefault();
                const touch = e.touches[0];
                this.setView(touch.clientX - this.dragStartX, touch.clientY - this.dragStartY);
                this.render();
            }
        }

        onTouchEnd() {
            this.isDragging = false;
        }

        loadMap(data) {
            this.grid = data.grid;
            this.width = data.width;
            this.height = data.height;
            this.seed = data.seed;

            if (data.player_pos && Array.isArray(data.player_pos) && data.player_pos.length >= 2) {
                this.playerPos = { x: data.player_pos[0], y: data.player_pos[1] };
                this.centerOnPlayer();
            }

            // Load persisted seen tiles
            this.loadSeenTiles();
            this.render();
        }

        /* How much of the viewport the HUD is standing on, in CSS pixels.
           Declared on .adv-hud so the numbers live with the layout that
           produces them; falls back to zero anywhere the HUD is absent.
           #dungeon-map is only ever rendered by adventure.html, so today that
           fallback is defensive rather than a live caller -- the stacked
           layout below 1200px zeroes the two properties on .adv-hud itself
           and comes through the branch above. */
        hudInsets() {
            const root = this.canvas.closest('.adv-hud');
            if (!root) return { left: 0, bottom: 0 };
            const cs = getComputedStyle(root);
            return {
                left: parseFloat(cs.getPropertyValue('--hud-inset-left')) || 0,
                bottom: parseFloat(cs.getPropertyValue('--hud-inset-bottom')) || 0,
            };
        }

        centerOnPlayer(smooth = true) {
            if (!this.playerPos) return;

            const rect = this.canvas.getBoundingClientRect();
            const centerX = (this.playerPos.x + 0.5) * TILE_SIZE * this.zoom;
            // Use flipped Y coordinate for centering
            const centerY = ((this.height - 1 - this.playerPos.y) + 0.5) * TILE_SIZE * this.zoom;

            const inset = this.hudInsets();
            // Centre the party in the space the player can actually see, not
            // in the geometric middle of the canvas — otherwise the party
            // rail and the log sit on top of them.
            const newOffsetX = (rect.width + inset.left) / 2 - centerX;
            const newOffsetY = (rect.height - inset.bottom) / 2 - centerY;

            if (smooth) {
                this.targetOffsetX = newOffsetX;
                this.targetOffsetY = newOffsetY;
                this.startAnimation();
            } else {
                // targetZoom, not the live zoom: a resize is not the player
                // touching the zoom, so a resize mid-button-zoom must not
                // freeze it at whatever intermediate value the ease reached.
                this.setView(newOffsetX, newOffsetY, this.targetZoom);
            }
        }

        startAnimation() {
            if (this.animating) return;
            this.animating = true;
            this.animate();
        }

        // Every immediate (un-eased) camera write must land on the target too.
        // animate()'s settle frame assigns offset/zoom := target, so a live
        // value the target does not know about is discarded the moment
        // anything eases: drag or resize, then zoom, and the camera yanks back
        // to where it was before. Drag stays instantaneous — render() reads
        // the live values only, so the target write is inert until an ease.
        setView(x, y, zoom = this.zoom) {
            this.offsetX = this.targetOffsetX = x;
            this.offsetY = this.targetOffsetY = y;
            this.zoom = this.targetZoom = zoom;
        }

        animate() {
            if (!this.animating) return;

            const easeSpeed = 0.2;
            let needsUpdate = false;

            // Animate offsets
            const dx = this.targetOffsetX - this.offsetX;
            const dy = this.targetOffsetY - this.offsetY;
            const dz = this.targetZoom - this.zoom;

            if (Math.abs(dx) > 0.5 || Math.abs(dy) > 0.5 || Math.abs(dz) > 0.01) {
                this.offsetX += dx * easeSpeed;
                this.offsetY += dy * easeSpeed;
                this.zoom += dz * easeSpeed;
                needsUpdate = true;
            } else {
                this.offsetX = this.targetOffsetX;
                this.offsetY = this.targetOffsetY;
                this.zoom = this.targetZoom;
                this.animating = false;
            }

            this.render();

            if (needsUpdate) {
                requestAnimationFrame(() => this.animate());
            }
        }

        updatePlayerPosition(x, y) {
            this.playerPos = { x, y };
            this.updateVisibility();
            this.centerOnPlayer();
            // Force immediate render to ensure visibility changes are shown
            requestAnimationFrame(() => this.render());
        }

        loadImage(src) {
            if (this.imageCache.has(src)) {
                return Promise.resolve(this.imageCache.get(src));
            }

            if (this.loadingImages.has(src)) {
                return this.loadingImages.get(src);
            }

            // Don't retry failed images
            if (this.failedImages.has(src)) {
                return Promise.reject(new Error(`Previously failed to load ${src}`));
            }

            const promise = new Promise((resolve, reject) => {
                const img = new Image();
                img.onload = () => {
                    this.imageCache.set(src, img);
                    this.loadingImages.delete(src);
                    resolve(img);
                    requestAnimationFrame(() => this.render());
                };
                img.onerror = () => {
                    this.loadingImages.delete(src);
                    this.failedImages.add(src);
                    reject(new Error(`Failed to load ${src}`));
                };
                img.src = src;
            });

            this.loadingImages.set(src, promise);
            return promise;
        }

        updateVisibility() {
            if (!this.playerPos) return;

            let seenChanged = false;
            const px = this.playerPos.x;
            const py = this.playerPos.y;

            for (let y = 0; y < this.height; y++) {
                for (let x = 0; x < this.width; x++) {
                    const dist = Math.hypot(x - px, y - py);
                    const key = `${x},${y}`;

                    // Mark tiles within fog radius as seen
                    if (dist <= OUTER_VIS_RADIUS && !this.seenTiles.has(key)) {
                        this.seenTiles.add(key);
                        seenChanged = true;
                    }
                }
            }

            if (seenChanged) {
                this.saveSeenTiles();
            }
        }

        loadSeenTiles() {
            if (!this.seed) return;
            try {
                const key = `dungeon_seen_${this.seed}`;
                const stored = localStorage.getItem(key);
                if (stored) {
                    this.seenTiles = new Set(JSON.parse(stored));
                }
            } catch (e) {
                console.warn('[dungeon-canvas] Failed to load seen tiles', e);
            }
        }

        saveSeenTiles() {
            if (!this.seed) return;
            try {
                const key = `dungeon_seen_${this.seed}`;
                localStorage.setItem(key, JSON.stringify([...this.seenTiles]));
            } catch (e) {
                console.warn('[dungeon-canvas] Failed to save seen tiles', e);
            }
        }

        clearSeenTiles() {
            this.seenTiles.clear();
            this.saveSeenTiles();
            this.render();
        }

        addRevealedTiles(tiles) {
            if (!Array.isArray(tiles) || tiles.length === 0) return;
            if (!this.grid) return;

            let updated = false;
            tiles.forEach(tile => {
                const x = tile.x;
                const y = tile.y;
                const cellType = tile.type || tile.cell_type;

                if (y >= 0 && y < this.height && x >= 0 && x < this.width) {
                    // Update grid with new tile data
                    this.grid[y][x] = { cell_type: cellType };
                    updated = true;
                }
            });

            if (updated) {
                // Re-render to show newly revealed tiles
                requestAnimationFrame(() => this.render());
            }
        }

        getTileColor(cell) {
            if (typeof cell === 'object' && cell !== null && cell.cell_type) {
                return TILE_COLORS[cell.cell_type] || TILE_COLORS.default;
            }
            return TILE_COLORS[cell] || TILE_COLORS.default;
        }

        getTileName(cell) {
            if (typeof cell === 'object' && cell !== null && cell.cell_type) {
                return cell.cell_type;
            }
            return cell;
        }

        // Draw one cell from the spritesheet. Returns false when the tile has no
        // mapping, so the caller can fall back to procedural painting.
        drawSpriteTile(name, px, py, S) {
            const spec = TILE_SPRITES[name];
            if (!spec) return false;
            const ctx = this.ctx;
            // Pixel art must not be smoothed when scaled 16 -> 32.
            const prevSmoothing = ctx.imageSmoothingEnabled;
            ctx.imageSmoothingEnabled = false;
            const blit = (cell) => {
                ctx.drawImage(
                    tileSheet,
                    cell[0] * SHEET_TILE, cell[1] * SHEET_TILE, SHEET_TILE, SHEET_TILE,
                    px, py, S, S
                );
            };
            blit(spec.base);
            if (spec.overlay) blit(spec.overlay);
            ctx.imageSmoothingEnabled = prevSmoothing;
            return true;
        }

        // Paint a single tile with light texture/depth so the map reads as a
        // stone dungeon rather than flat coloured squares: flagstone floors,
        // beveled wall blocks and planked wooden doors. Used when no tileset is
        // installed (see TILE_SHEET_SRC).
        paintTile(cell, tileX, tileY, px, py) {
            const ctx = this.ctx;
            const name = this.getTileName(cell);
            const S = TILE_SIZE;

            if (tileSheetReady && this.drawSpriteTile(name, px, py, S)) return;

            const s = TILE_STYLE[name] || TILE_STYLE.default;

            if (s.kind === 'floor') {
                ctx.fillStyle = ((tileX + tileY) & 1) ? s.alt : s.base;
                ctx.fillRect(px, py, S, S);
                // Subtle inset rim to suggest individual flagstones.
                ctx.strokeStyle = s.edge;
                ctx.lineWidth = 1;
                ctx.strokeRect(px + 0.5, py + 0.5, S - 1, S - 1);
            } else if (s.kind === 'wall') {
                ctx.fillStyle = s.base;
                ctx.fillRect(px, py, S, S);
                // Top/left highlight + bottom/right shadow => raised block.
                ctx.lineWidth = 1;
                ctx.strokeStyle = s.hi;
                ctx.beginPath();
                ctx.moveTo(px + 0.5, py + S - 1); ctx.lineTo(px + 0.5, py + 0.5); ctx.lineTo(px + S - 1, py + 0.5);
                ctx.stroke();
                ctx.strokeStyle = s.lo;
                ctx.beginPath();
                ctx.moveTo(px + S - 0.5, py + 0.5); ctx.lineTo(px + S - 0.5, py + S - 0.5); ctx.lineTo(px + 0.5, py + S - 0.5);
                ctx.stroke();
            } else if (s.kind === 'door') {
                ctx.fillStyle = s.floor;
                ctx.fillRect(px, py, S, S);
                const m = Math.max(2, Math.round(S * 0.18));
                ctx.fillStyle = s.wood;
                ctx.fillRect(px + m, py + m, S - 2 * m, S - 2 * m);
                ctx.strokeStyle = s.plank;
                ctx.lineWidth = 1;
                ctx.strokeRect(px + m + 0.5, py + m + 0.5, S - 2 * m - 1, S - 2 * m - 1);
                // Central plank seam.
                ctx.beginPath();
                ctx.moveTo(px + S / 2, py + m); ctx.lineTo(px + S / 2, py + S - m);
                ctx.stroke();
            } else {
                ctx.fillStyle = s.base;
                ctx.fillRect(px, py, S, S);
            }
        }

        render() {
            if (!this.grid) return;

            const rect = this.canvas.getBoundingClientRect();
            const dpr = window.devicePixelRatio || 1;

            // Clear canvas
            this.ctx.clearRect(0, 0, rect.width, rect.height);

            // Fill background
            this.ctx.fillStyle = '#000000';
            this.ctx.fillRect(0, 0, rect.width, rect.height);

            // Save context for transformations
            this.ctx.save();

            // Apply zoom and pan
            this.ctx.translate(this.offsetX, this.offsetY);
            this.ctx.scale(this.zoom, this.zoom);

            // Render tiles
            for (let y = 0; y < this.height; y++) {
                for (let x = 0; x < this.width; x++) {
                    const cell = this.grid[y][x];

                    // Skip unknown tiles
                    if (cell === 'unknown') continue;

                    const key = `${x},${y}`;
                    const wasSeen = this.seenTiles.has(key);

                    // Calculate distance to player
                    const dist = this.playerPos ? Math.hypot(x - this.playerPos.x, y - this.playerPos.y) : Infinity;

                    // Flip Y axis: game Y increases north, canvas Y increases south
                    const canvasY = (this.height - 1 - y) * TILE_SIZE;
                    // Textured tile (flagstone floor / beveled wall / wooden door)
                    this.paintTile(cell, x, y, x * TILE_SIZE, canvasY);

                    // Special rendering for teleporter
                    if (cell === 'teleporter' && dist <= OUTER_VIS_RADIUS) {
                        const centerX = x * TILE_SIZE + TILE_SIZE / 2;
                        const centerY = canvasY + TILE_SIZE / 2;
                        const time = Date.now() / 1000;

                        // Animated pulsing glow
                        const pulse = 0.5 + Math.sin(time * 3) * 0.3;
                        const gradient = this.ctx.createRadialGradient(
                            centerX, centerY, 2,
                            centerX, centerY, TILE_SIZE * 0.6
                        );
                        gradient.addColorStop(0, `rgba(147, 51, 234, ${pulse})`);
                        gradient.addColorStop(0.5, 'rgba(107, 70, 193, 0.4)');
                        gradient.addColorStop(1, 'rgba(107, 70, 193, 0)');

                        this.ctx.fillStyle = gradient;
                        this.ctx.fillRect(x * TILE_SIZE, canvasY, TILE_SIZE, TILE_SIZE);

                        // Portal ring
                        this.ctx.strokeStyle = `rgba(167, 139, 250, ${0.7 + pulse * 0.3})`;
                        this.ctx.lineWidth = 2;
                        this.ctx.beginPath();
                        this.ctx.arc(centerX, centerY, TILE_SIZE * 0.3, 0, Math.PI * 2);
                        this.ctx.stroke();

                        // Inner ring (rotated)
                        const rotation = time * 2;
                        this.ctx.strokeStyle = `rgba(196, 181, 253, ${0.5 + pulse * 0.2})`;
                        this.ctx.lineWidth = 1;
                        this.ctx.beginPath();
                        for (let i = 0; i < 6; i++) {
                            const angle = (i / 6) * Math.PI * 2 + rotation;
                            const r = TILE_SIZE * 0.2;
                            const px = centerX + Math.cos(angle) * r;
                            const py = centerY + Math.sin(angle) * r;
                            if (i === 0) {
                                this.ctx.moveTo(px, py);
                            } else {
                                this.ctx.lineTo(px, py);
                            }
                        }
                        this.ctx.closePath();
                        this.ctx.stroke();
                    }

                    // Apply fog-of-war
                    if (this.playerPos) {
                        if (dist <= INNER_VIS_RADIUS) {
                            // Fully visible - no fog
                        } else if (dist <= OUTER_VIS_RADIUS) {
                            // Gradient fog with noise
                            const fogProgress = (dist - INNER_VIS_RADIUS) / FOG_GRADIENT_STEPS;
                            // Add perlin-like noise based on tile position
                            const noise = (Math.sin(x * 0.5) * Math.cos(y * 0.5)) * FOG_NOISE_AMPLITUDE;
                            let alpha = MIN_FOG_ALPHA + (fogProgress * (MAX_FOG_ALPHA - MIN_FOG_ALPHA)) + noise;
                            alpha = Math.max(0, Math.min(1, alpha)); // Clamp to 0-1
                            this.ctx.fillStyle = `rgba(0, 0, 0, ${alpha})`;
                            this.ctx.fillRect(x * TILE_SIZE, canvasY, TILE_SIZE, TILE_SIZE);
                        } else if (wasSeen) {
                            // Memory fog (previously seen)
                            this.ctx.fillStyle = `rgba(0, 0, 0, ${MEMORY_DIM_ALPHA})`;
                            this.ctx.fillRect(x * TILE_SIZE, canvasY, TILE_SIZE, TILE_SIZE);
                        } else {
                            // Completely dark (unseen)
                            this.ctx.fillStyle = `rgba(0, 0, 0, ${MAX_FOG_ALPHA})`;
                            this.ctx.fillRect(x * TILE_SIZE, canvasY, TILE_SIZE, TILE_SIZE);
                        }
                    }

                }
            }

            // Render entities (monsters, NPCs)
            this.renderEntities();

            // Render notices (loot, events)
            this.renderNotices();

            // Render player marker
            if (this.playerPos) {
                this.renderPlayer();
            }

            // Restore context
            this.ctx.restore();

            // Render UI overlays
            this.renderMinimap();
            this.renderTooltip();

            if (this.options.showDebug) {
                this.renderDebugOverlay();
            }
        }

        renderPlayer() {
            const px = (this.playerPos.x + 0.5) * TILE_SIZE;
            // Flip Y axis for player position
            const py = ((this.height - 1 - this.playerPos.y) + 0.5) * TILE_SIZE;
            const size = TILE_SIZE * 0.8;

            // Load and draw player icon (axe-sword.svg)
            const playerIcon = '/static/iconography/axe-sword.svg';
            if (this.imageCache.has(playerIcon)) {
                const img = this.imageCache.get(playerIcon);
                this.ctx.drawImage(img, px - size / 2, py - size / 2, size, size);
            } else {
                // Fallback while loading
                this.ctx.fillStyle = '#FFD700';
                this.ctx.beginPath();
                this.ctx.arc(px, py, size / 2, 0, Math.PI * 2);
                this.ctx.fill();
                this.ctx.strokeStyle = '#FFFFFF';
                this.ctx.lineWidth = 2;
                this.ctx.stroke();

                // Load image for next render
                this.loadImage(playerIcon).catch(e => console.warn('Failed to load player icon:', e));
            }
        }

        renderEntities() {
            // Entity rendering (monsters, NPCs)
            this.entities.forEach(entity => {
                if (!this.playerPos) return;

                // Fog-of-war: the server broadcasts every entity's true position
                // regardless of what the player has actually uncovered (entities_update
                // has no visibility filtering of its own), so the client must apply the
                // same "skip unknown tiles" rule the map renderer already uses below —
                // otherwise elite/boss markers are visible before being revealed.
                const row = this.grid && this.grid[entity.y];
                const cell = row ? row[entity.x] : undefined;
                if (cell === undefined || cell === 'unknown') return;

                const dist = Math.hypot(entity.x - this.playerPos.x, entity.y - this.playerPos.y);
                if (dist > OUTER_VIS_RADIUS) return; // Don't render entities outside vision

                const ex = (entity.x + 0.5) * TILE_SIZE;
                // Flip Y axis for entity position
                const ey = ((this.height - 1 - entity.y) + 0.5) * TILE_SIZE;
                const size = TILE_SIZE * 0.7;

                // Load entity icon or use fallback (shrines get a dedicated icon; everything
                // else falls back to the generic monster icon unless the server supplies one).
                const iconSrc = entity.icon
                    || (entity.type === 'shrine' ? '/static/iconography/aura.svg' : null)
                    || '/static/iconography/goblin-scout-t1.svg';
                if (this.imageCache.has(iconSrc)) {
                    const img = this.imageCache.get(iconSrc);
                    this.ctx.drawImage(img, ex - size / 2, ey - size / 2, size, size);
                } else {
                    // Fallback circle while loading
                    this.ctx.fillStyle = entity.type === 'treasure' ? '#FFAA00' : '#FF4444';
                    this.ctx.beginPath();
                    this.ctx.arc(ex, ey, size / 2, 0, Math.PI * 2);
                    this.ctx.fill();
                    this.ctx.strokeStyle = '#000000';
                    this.ctx.lineWidth = 1.5;
                    this.ctx.stroke();

                    // Load image for next render
                    this.loadImage(iconSrc).catch(e => {
                        console.warn('Failed to load entity icon:', iconSrc, e);
                    });
                }
            });
        }

        renderNotices() {
            // Notice rendering (loot, events)
            this.notices.forEach(notice => {
                if (!this.playerPos) return;

                const dist = Math.hypot(notice.x - this.playerPos.x, notice.y - this.playerPos.y);
                if (dist > OUTER_VIS_RADIUS) return;

                const nx = (notice.x + 0.5) * TILE_SIZE;
                // Flip Y axis for notice position
                const ny = ((this.height - 1 - notice.y) + 0.5) * TILE_SIZE;
                const size = TILE_SIZE * 0.4;

                // Loot marker (yellow star placeholder)
                this.ctx.fillStyle = '#FFFF00';
                this.ctx.beginPath();
                for (let i = 0; i < 5; i++) {
                    const angle = (i * 4 * Math.PI) / 5 - Math.PI / 2;
                    const radius = i % 2 === 0 ? size / 2 : size / 4;
                    const x = nx + Math.cos(angle) * radius;
                    const y = ny + Math.sin(angle) * radius;
                    if (i === 0) this.ctx.moveTo(x, y);
                    else this.ctx.lineTo(x, y);
                }
                this.ctx.closePath();
                this.ctx.fill();
            });
        }

        renderDebugOverlay() {
            this.ctx.save();
            this.ctx.fillStyle = 'rgba(0, 0, 0, 0.7)';
            this.ctx.fillRect(10, 10, 200, 80);

            this.ctx.fillStyle = '#00FF00';
            this.ctx.font = '12px monospace';
            this.ctx.fillText(`Zoom: ${this.zoom.toFixed(2)}x`, 20, 30);
            this.ctx.fillText(`Offset: ${Math.round(this.offsetX)}, ${Math.round(this.offsetY)}`, 20, 50);
            if (this.playerPos) {
                this.ctx.fillText(`Player: (${this.playerPos.x}, ${this.playerPos.y})`, 20, 70);
            }
            this.ctx.restore();
        }

        renderMinimap() {
            if (!this.grid || !this.playerPos) return;

            const rect = this.canvas.getBoundingClientRect();
            const minimapSize = 120;
            const minimapX = rect.width - minimapSize - 10;
            // Below the account anchor, which owns the top-right corner:
            // 36px trigger + 8px gap. Keep in step with .adv-hud .map-controls
            // in adventure-hud.css, which sits below this in turn.
            const minimapY = 44;
            const tileScale = minimapSize / Math.max(this.width, this.height);

            this.ctx.save();

            // Minimap background
            this.ctx.fillStyle = 'rgba(0, 0, 0, 0.7)';
            this.ctx.fillRect(minimapX, minimapY, minimapSize, minimapSize);

            // Draw explored tiles
            for (let y = 0; y < this.height; y++) {
                for (let x = 0; x < this.width; x++) {
                    const key = `${x},${y}`;
                    if (this.seenTiles.has(key)) {
                        const cell = this.grid[y][x];
                        if (cell && cell !== 'unknown') {
                            // Flip Y for minimap rendering
                            const mx = minimapX + x * tileScale;
                            const my = minimapY + (this.height - 1 - y) * tileScale;

                            const color = this.getTileColor(cell);
                            this.ctx.fillStyle = color;
                            this.ctx.fillRect(mx, my, tileScale, tileScale);
                        }
                    }
                }
            }

            // Draw player position
            const px = minimapX + this.playerPos.x * tileScale;
            const py = minimapY + (this.height - 1 - this.playerPos.y) * tileScale;
            this.ctx.fillStyle = '#FFD700';
            this.ctx.beginPath();
            this.ctx.arc(px + tileScale / 2, py + tileScale / 2, 3, 0, Math.PI * 2);
            this.ctx.fill();

            // Minimap border
            this.ctx.strokeStyle = '#666';
            this.ctx.lineWidth = 2;
            this.ctx.strokeRect(minimapX, minimapY, minimapSize, minimapSize);

            this.ctx.restore();
        }

        renderTooltip() {
            if (!this.hoverTile) return;

            const { x, y, cell } = this.hoverTile;

            // Get cell type
            let cellType = 'unknown';
            if (typeof cell === 'object' && cell !== null && cell.cell_type) {
                cellType = cell.cell_type;
            } else if (typeof cell === 'string') {
                cellType = cell;
            }

            // Format tooltip text with helpful descriptions
            let text = `(${x + 1}, ${y + 1}): ${cellType}`;
            if (cellType === 'teleporter') {
                text = `Teleporter - Walk onto it to activate`;
            }

            // Measure text
            this.ctx.save();
            this.ctx.font = '14px sans-serif';
            const metrics = this.ctx.measureText(text);
            const padding = 8;
            const width = metrics.width + padding * 2;
            const height = 24;

            // Position tooltip near cursor (we'd need cursor position, so put it at tile location)
            const canvasY = (this.height - 1 - y) * TILE_SIZE;
            const screenX = (x * TILE_SIZE * this.zoom) + this.offsetX;
            const screenY = (canvasY * this.zoom) + this.offsetY - 30;

            // Draw tooltip background
            this.ctx.fillStyle = 'rgba(0, 0, 0, 0.8)';
            this.ctx.fillRect(screenX, screenY, width, height);

            // Draw tooltip border
            this.ctx.strokeStyle = '#888';
            this.ctx.lineWidth = 1;
            this.ctx.strokeRect(screenX, screenY, width, height);

            // Draw tooltip text
            this.ctx.fillStyle = '#FFF';
            this.ctx.fillText(text, screenX + padding, screenY + height - 8);

            this.ctx.restore();
        }

        setEntities(entities) {
            this.entities = entities;
            this.render();
        }

        setNotices(notices) {
            this.notices = notices;
            this.render();
        }

        // Zoom controls
        zoomIn() {
            this.targetZoom = Math.min(MAX_ZOOM, this.targetZoom + ZOOM_STEP);
            this.startAnimation();
        }

        zoomOut() {
            this.targetZoom = Math.max(MIN_ZOOM, this.targetZoom - ZOOM_STEP);
            this.startAnimation();
        }

        resetZoom() {
            this.targetZoom = 1.0;
            this.centerOnPlayer();
        }

        // Developer console helpers
        getCoverage() {
            const total = this.width * this.height;
            const seen = this.seenTiles.size;
            const pct = total ? (seen / total * 100) : 0;
            return { seen, total, pct: pct.toFixed(2) };
        }
    }

    // Export to global scope
    window.DungeonCanvas = DungeonCanvas;
})();
