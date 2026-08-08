"""楼层归属 — 兼容入口，正式实现见 floor_assignment.py。"""

from solver.program.floor_assignment import (
    DuplicateRoomAssignmentError,
    FloorAssignmentSolver,
    UnassignedRoomError,
    assert_all_rooms_placed,
    auto_assign_floor,
    ensure_floor_assignment,
)

__all__ = [
    "DuplicateRoomAssignmentError",
    "FloorAssignmentSolver",
    "UnassignedRoomError",
    "assert_all_rooms_placed",
    "auto_assign_floor",
    "ensure_floor_assignment",
]
