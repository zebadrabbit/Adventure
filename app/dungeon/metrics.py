from typing import Dict

def init_metrics() -> Dict[str, int | float | bool]:
    return {
        'doors_created': 0,
        'doors_downgraded': 0,
        'doors_inferred': 0,
        'repairs_performed': 0,
        'chains_collapsed': 0,
        'orphan_fixes': 0,
        'rooms_dropped': 0,
        'door_clusters_reduced': 0,
        'tunnels_pruned': 0,
        'corner_nubs_pruned': 0,
        'runtime_ms': 0.0,
    }
