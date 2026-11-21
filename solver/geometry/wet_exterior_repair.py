"""黑卫软修复：与贴外墙的相邻房间交换矩形（不改拓扑切分）。"""

from __future__ import annotations

from packages.schema.layout import PlacementSource, RoomPlacement
from packages.schema.program import DesignProgram
from packages.schema.room import RoomSpec
from solver.geometry.exterior import has_exterior_wall
from solver.geometry.rect import from_placement, shared_edge_length
from solver.semantics.roles import (
    is_foyer,
    is_guest_bath,
    is_laundry,
    is_master_bath,
    is_storage,
    is_study,
)


def _is_bath_for_exterior(room: RoomSpec) -> bool:
    return is_guest_bath(room) or is_master_bath(room)


def _is_auxiliary_donor(room: RoomSpec) -> bool:
    """仅储藏/洗衣/书房可出让外墙，避免与客厅卧室对调打崩 valid。"""
    return is_storage(room) or is_laundry(room) or is_study(room)


def _donor_rank(room: RoomSpec) -> int:
    if is_storage(room):
        return 0
    if is_laundry(room):
        return 1
    if is_study(room):
        return 2
    return 9


def _area_compatible(a: float, b: float) -> bool:
    if a <= 1e-9 or b <= 1e-9:
        return False
    ratio = a / b
    return 0.55 <= ratio <= 1.8


def swap_black_baths_to_exterior(
    placements: list[RoomPlacement],
    *,
    program: DesignProgram,
    rooms_by_id: dict[str, RoomSpec],
    min_shared_edge: float = 0.6,
) -> list[RoomPlacement]:
    """
    对无外墙的客卫/主卫，与同层贴外墙且共边的储藏/洗衣/书房交换矩形。

    不碰门厅、楼梯、客厅卧室与厨房，避免入口/动线硬失败。
    """
    by_id = {p.room_id: p for p in placements}
    changed = False

    bath_ids = [
        rid
        for rid, room in rooms_by_id.items()
        if _is_bath_for_exterior(room) and rid in by_id
    ]
    for bath_id in bath_ids:
        bath_p = by_id[bath_id]
        bath_rect = from_placement(bath_p.rect)
        if has_exterior_wall(bath_rect, program):
            continue

        donors: list[tuple[int, float, str]] = []
        for other_id, other_p in by_id.items():
            if other_id == bath_id:
                continue
            if other_p.floor_id != bath_p.floor_id:
                continue
            if (
                other_p.source == PlacementSource.GENERATED
                or other_p.category == "circulation"
            ):
                continue
            other_room = rooms_by_id.get(other_id)
            if other_room is None or not _is_auxiliary_donor(other_room):
                continue
            if is_foyer(other_room) or _is_bath_for_exterior(other_room):
                continue
            other_rect = from_placement(other_p.rect)
            if not has_exterior_wall(other_rect, program):
                continue
            shared = shared_edge_length(bath_rect, other_rect)
            if shared < min_shared_edge:
                continue
            if not _area_compatible(bath_rect.area, other_rect.area):
                continue
            donors.append((_donor_rank(other_room), -shared, other_id))

        if not donors:
            continue
        donors.sort()
        donor_id = donors[0][2]
        donor_p = by_id[donor_id]
        bath_p.rect, donor_p.rect = donor_p.rect, bath_p.rect
        changed = True

    if not changed:
        return placements
    return list(placements)
