"""Circulation 子系统。"""

from solver.circulation.stair_core import (
    CorePlacementFailure,
    choose_core_placement,
    place_stair_core,
    place_stair_core_resolving,
    resolve_stair_core_spec,
)
from solver.circulation.stair_identity import (
    is_stair_core_placement,
    is_stair_core_room_id,
    stair_core_placements,
)

__all__ = [
    "CorePlacementFailure",
    "choose_core_placement",
    "is_stair_core_placement",
    "is_stair_core_room_id",
    "place_stair_core",
    "place_stair_core_resolving",
    "resolve_stair_core_spec",
    "stair_core_placements",
]
