"""局部重生成 — RegenerationScope 解析。"""

from solver.regeneration.scope import (
    assert_preserve_topology,
    derive_affected_neighbors,
    enrich_regeneration_scope,
    filter_candidates_preserving_topology,
    locks_from_placement_rects,
    locks_from_regeneration_scope,
    resolve_locked_room_ids,
)

__all__ = [
    "assert_preserve_topology",
    "derive_affected_neighbors",
    "enrich_regeneration_scope",
    "filter_candidates_preserving_topology",
    "locks_from_placement_rects",
    "locks_from_regeneration_scope",
    "resolve_locked_room_ids",
]
