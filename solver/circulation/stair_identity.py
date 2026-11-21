"""楼梯核身份 — 不得用普通 circulation / circ-* 推断楼梯。

跨层 STAIR、楼梯核尺寸校验、楼梯入口开口等，一律经本模块判定。
"""

from __future__ import annotations

from packages.schema.layout import RoomPlacement


def is_stair_core_room_id(room_id: str | None) -> bool:
    """稳定楼梯核 id：``stair-*``（或历史单名 ``stair``）。"""
    if not room_id:
        return False
    return room_id == "stair" or room_id.startswith("stair-")


def is_stair_core_placement(p: RoomPlacement) -> bool:
    """
    是否为楼梯核放置。

    仅认：
    - room_id 以 stair-/stair 开头；或
    - circulation 且 name 显式含「楼梯」

    **禁止**把 circ-* 走廊碎片或任意 circulation 当作楼梯核。
    """
    if is_stair_core_room_id(p.room_id):
        return True
    if (p.category or "").lower() != "circulation":
        return False
    return p.name is not None and "楼梯" in p.name


def stair_core_placements(placements: list[RoomPlacement]) -> list[RoomPlacement]:
    """过滤楼梯核；优先 stair-*，再显式命名，避免顺序敏感误选走廊。"""
    primary = [p for p in placements if is_stair_core_room_id(p.room_id)]
    if primary:
        return primary
    return [p for p in placements if is_stair_core_placement(p)]
