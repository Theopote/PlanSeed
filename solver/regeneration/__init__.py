"""局部重生成 — RegenerationScope 解析。"""

from solver.regeneration.scope import (
    derive_affected_neighbors,
    enrich_regeneration_scope,
    locks_from_placement_rects,
    locks_from_regeneration_scope,
    resolve_locked_room_ids,
)

__all__ = [
    "derive_affected_neighbors",
    "enrich_regeneration_scope",
    "locks_from_placement_rects",
    "locks_from_regeneration_scope",
    "resolve_locked_room_ids",
]
