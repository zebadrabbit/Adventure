"""Pipeline orchestration for dungeon generation.

Provides the public Dungeon class used elsewhere in the codebase while
coordinating sub-module responsibilities. During refactor, this class wraps
legacy monolith behavior incrementally replaced by modular components.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Dict, Any, Tuple, List
import random

from .cells import DungeonCell
from .metrics import init_metrics
from .generator import Generator
from .pruning import run_all_pruning_passes, prune_corner_tunnel_nubs
from .doors import repair_and_validate_doors, collapse_linear_door_runs, enforce_door_invariants
from .doors import enforce_door_invariants, infer_missing_doors
from .connectivity import final_consolidation_pass, post_generation_safety
from .features import assign_features

# NOTE: Legacy flags are presumed to exist elsewhere (e.g., config module or environment).
# For transitional stability we gate optional phases with simple attribute checks if needed.

@dataclass
class Dungeon:
    seed: Optional[int] = None
    size: Tuple[int,int,int] = (75,75,1)
    allow_hidden_areas: bool = False
    allow_hidden_areas_strict: bool = False
    enable_metrics: bool = True

    def __post_init__(self):
        # Preserve legacy seed semantics: 0 is valid deterministic seed; None => random
        if self.seed is None:
            self.seed = random.randint(1, 1_000_000)
        # Environment override support (tests set env vars rather than passing params)
        import os
        env_map = {
            'DUNGEON_ALLOW_HIDDEN_AREAS': 'allow_hidden_areas',
            'DUNGEON_ALLOW_HIDDEN_AREAS_STRICT': 'allow_hidden_areas_strict',
            'DUNGEON_ENABLE_GENERATION_METRICS': 'enable_metrics',
        }
        for env_key, attr in env_map.items():
            if env_key in os.environ:
                val = os.environ.get(env_key, '').lower()
                setattr(self, attr, val not in {'0','false','no',''} )
        # Flask app config overrides (highest precedence) to mirror legacy behavior in tests
        try:
            from flask import current_app, has_app_context
            if has_app_context():
                cfg = current_app.config
                if 'DUNGEON_ALLOW_HIDDEN_AREAS' in cfg:
                    self.allow_hidden_areas = bool(cfg.get('DUNGEON_ALLOW_HIDDEN_AREAS'))
                if 'DUNGEON_ALLOW_HIDDEN_AREAS_STRICT' in cfg:
                    self.allow_hidden_areas_strict = bool(cfg.get('DUNGEON_ALLOW_HIDDEN_AREAS_STRICT'))
                if 'DUNGEON_ENABLE_GENERATION_METRICS' in cfg:
                    self.enable_metrics = bool(cfg.get('DUNGEON_ENABLE_GENERATION_METRICS'))
        except Exception:
            pass
        self.metrics: Dict[str, Any] = init_metrics() if self.enable_metrics else {}
        self.entrance_pos = None
        self._run_pipeline()

    # Added properties for legacy attribute access
    @property
    def width(self) -> int:
        return self.size[0]
    @property
    def height(self) -> int:
        return self.size[1]
    @property
    def depth(self) -> int:
        return self.size[2]

    def _run_pipeline(self):
        """Execute ordered generation phases with lightweight per-phase timing.

        Adds a new metrics entry `phase_ms` mapping phase name -> duration (ms) when
        metrics are enabled. This instrumentation is intentionally minimal (no nesting)
        to avoid perturbing overall performance while still surfacing hotspots for
        the performance regression guard.
        """
        if self.enable_metrics:
            import time
            start = time.perf_counter()
            phase_times = {}
            def _phase(label, fn, *a, **k):
                ps = time.perf_counter(); r = fn(*a, **k); pe = time.perf_counter()
                phase_times[label] = int((pe-ps)*1000)
                return r
        else:
            def _phase(label, fn, *a, **k):
                return fn(*a, **k)
        width,height,depth = self.size
        # Structural generation
        gen = Generator(self.size, self.seed)
        outputs = _phase('generate', gen.run)
        self.grid = outputs.grid
        self.rooms = outputs.rooms
        self.room_id_grid = outputs.room_id_grid
        # Feature assignment (entrance/boss etc.)
        _phase('assign_basic_features', self._assign_basic_features)
        # Debug metrics pre-safety (room count) like legacy
        if self.enable_metrics:
            self.metrics['debug_allow_hidden'] = self.allow_hidden_areas
            self.metrics['debug_allow_hidden_strict'] = self.allow_hidden_areas_strict
            self.metrics['debug_room_count_initial'] = sum(
                1 for x in range(width) for y in range(height) if self.grid[x][y][0].cell_type == 'room'
            )
        # First door validation (full carve probability)
        _phase('repair_validate_initial', repair_and_validate_doors, self, self.metrics, carve_probability=1.0, allow_wall_downgrade=True)
        # Initial collapse (avoid large door chains early); defer pruning until after consolidation to reduce passes
        _phase('collapse_door_runs', collapse_linear_door_runs, self, self.metrics)
        # Consolidation pass (connectivity, door guarantees, separation, repairs)
        _phase('consolidation', final_consolidation_pass, self)
        # Pruning sweep (door clusters, orphan tunnels, corner nubs) after consolidation
        _phase('pruning_passes', run_all_pruning_passes, self, self.metrics)
        # Post-generation safety (unreachable rooms normalization unless strict)
        _phase('post_generation_safety', post_generation_safety, self)
        # Final invariant enforcement sweep
        _phase('enforce_invariants', enforce_door_invariants, self, self.metrics)
        # Infer any missed doors after all collapses/invariants (cheap micro-pass)
        _phase('infer_doors', infer_missing_doors, self, self.metrics)
        # Final corner nub prune in case invariant sweep carved new single-cell stubs.
        # (Optimization) Only re-run invariants / inference if prune removed any cells.
        cnp = _phase('corner_nub_final', prune_corner_tunnel_nubs, self)
        if self.enable_metrics:
            self.metrics['corner_nubs_pruned'] += cnp
        if cnp:  # Conditional second sweep avoids redundant full-grid scans on fast path
            _phase('enforce_invariants_post_nubs', enforce_door_invariants, self, self.metrics)
            _phase('infer_doors_post_nubs', infer_missing_doors, self, self.metrics)
        if self.enable_metrics:
            self.metrics['debug_room_count_post_safety'] = sum(
                1 for x in range(width) for y in range(height) if self.grid[x][y][0].cell_type == 'room'
            )
        # Assign gameplay features (placeholder)
        _phase('assign_features', assign_features, self, self.metrics)

        if self.enable_metrics:
            import time
            end = time.perf_counter()
            self.metrics['runtime_ms'] = int((end - start) * 1000)
            self.metrics['phase_ms'] = phase_times
            # Feed rolling average tracker for admin_status if lobby helper present
            try:
                from app.websockets import lobby as lobby_ws
                if hasattr(lobby_ws, 'record_dungeon_runtime'):
                    lobby_ws.record_dungeon_runtime(self.metrics['runtime_ms'])
            except Exception:
                pass

    # Temporary feature assignment to ensure entrance placement for pruning metrics
    def _assign_basic_features(self):
        if not self.rooms:
            return
        # Entrance = first room center, Boss = last room center
        first = self.rooms[0]; last = self.rooms[-1]
        fx, fy = first.x + first.w//2, first.y + first.h//2
        lx, ly = last.x + last.w//2, last.y + last.h//2
        self.grid[fx][fy][0].features.append('entrance')
        self.entrance_pos = (fx, fy, 0)
        if (lx,ly)!=(fx,fy):
            self.grid[lx][ly][0].features.append('boss')
