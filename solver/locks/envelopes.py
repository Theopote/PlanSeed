"""Zone Lock 过程护栏：成员不得被后处理推出 envelope。"""

from __future__ import annotations

from packages.schema.layout import RoomPlacement
from packages.schema.locks import LayoutLocks
from solver.geometry.rect import Rect, from_placement


_TOL = 1e-4


def build_zone_member_envelopes(locks: LayoutLocks) -> dict[str, Rect]:
    """
    room_id → 必须留在其内的 zone envelope。

    已 Room-Lock 的房间不进入（几何完全钉死，由 protected_room_ids 处理）。
    """
    out: dict[str, Rect] = {}
    room_locked = locks.locked_room_ids
    for lz in locks.zones:
        env = Rect(x=lz.x, y=lz.y, width=lz.width, depth=lz.depth)
        for rid in lz.room_ids:
            if rid in room_locked:
                continue
            out[rid] = env
    return out


def placement_in_envelope(p: RoomPlacement, envelope: Rect, *, tol: float = _TOL) -> bool:
    r = from_placement(p.rect)
    return (
        r.x >= envelope.x - tol
        and r.y >= envelope.y - tol
        and r.x + r.width <= envelope.x + envelope.width + tol
        and r.y + r.depth <= envelope.y + envelope.depth + tol
    )


def placements_respect_zone_envelopes(
    placements: list[RoomPlacement],
    envelopes: dict[str, Rect],
) -> bool:
    for p in placements:
        env = envelopes.get(p.room_id)
        if env is None:
            continue
        if not placement_in_envelope(p, env):
            return False
    return True
