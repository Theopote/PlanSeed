"""房间语义：tags / role；Solver 不解析自然语言。"""

from solver.semantics.roles import (
    has_any_tag,
    is_dining,
    is_elderly_bedroom,
    is_garage,
    is_guest_bath,
    is_kitchen,
    is_laundry,
    is_master_bath,
    is_master_bedroom,
    is_storage,
    is_study,
    room_tags,
)

__all__ = [
    "has_any_tag",
    "is_dining",
    "is_elderly_bedroom",
    "is_garage",
    "is_guest_bath",
    "is_kitchen",
    "is_laundry",
    "is_master_bath",
    "is_master_bedroom",
    "is_storage",
    "is_study",
    "room_tags",
]
