"""RegenerationScope → LayoutLocks 解析。"""

from __future__ import annotations

from packages.schema.layout import LayoutCandidate, PlacementSource
from packages.schema.locks import LayoutLocks, LockedRoomRect, LockedStairCore
from packages.schema.program import DesignProgram
from packages.schema.regeneration import RegenerationScope
from solver.topology.graph import build_graph_from_program, neighbors


def derive_affected_neighbors(
    program: DesignProgram,
    mutable_room_ids: list[str],
) -> list[str]:
    """从 RoomGraph 推导 mutable 房间的一阶邻接（不含 mutable 自身）。"""
    graph = build_graph_from_program(program)
    mutable = set(mutable_room_ids)
    found: set[str] = set()
    for rid in mutable_room_ids:
        for n in neighbors(graph, rid):
            if n not in mutable:
                found.add(n)
    return sorted(found)


def enrich_regeneration_scope(
    scope: RegenerationScope,
    program: DesignProgram,
) -> RegenerationScope:
    """填充 affected_neighbors（若调用方未提供）。"""
    if scope.affected_neighbors:
        return scope
    return scope.model_copy(
        update={
            "affected_neighbors": derive_affected_neighbors(
                program, scope.mutable_rooms
            )
        }
    )


def resolve_locked_room_ids(
    scope: RegenerationScope,
    program: DesignProgram,
) -> set[str]:
    """根据 scope 计算应钉死的 program 房间 id。"""
    program_ids = {r.id for r in program.rooms}
    mutable = scope.mutable_room_ids
    unknown_mutable = mutable - program_ids
    if unknown_mutable:
        raise ValueError(f"mutable_rooms 不在 program 中：{sorted(unknown_mutable)}")

    if scope.locked_rooms:
        locked = scope.locked_room_ids - mutable
        unknown_locked = locked - program_ids
        if unknown_locked:
            raise ValueError(f"locked_rooms 不在 program 中：{sorted(unknown_locked)}")
    else:
        locked = program_ids - mutable

    return locked


def _placement_lock_from_candidate(
    candidate: LayoutCandidate,
    room_id: str,
) -> LockedRoomRect:
    for fl in candidate.floors:
        for p in fl.placements:
            if p.room_id == room_id and p.source == PlacementSource.PROGRAM:
                r = p.rect
                return LockedRoomRect(
                    room_id=p.room_id,
                    floor_id=p.floor_id,
                    x=r.x,
                    y=r.y,
                    width=r.width,
                    depth=r.depth,
                )
    raise ValueError(f"base candidate 无 program 房间放置：{room_id!r}")


def _stair_lock_from_candidate(
    candidate: LayoutCandidate,
) -> LockedStairCore | None:
    for fl in candidate.floors:
        for p in fl.placements:
            if p.room_id.startswith("stair-"):
                r = p.rect
                return LockedStairCore(
                    x=r.x,
                    y=r.y,
                    width=r.width,
                    depth=r.depth,
                    core_placement=fl.core_placement,
                )
    return None


def locks_from_regeneration_scope(
    scope: RegenerationScope,
    program: DesignProgram,
    base_candidate: LayoutCandidate,
) -> LayoutLocks:
    """
    将 RegenerationScope + 基线候选转为 LayoutLocks。

    锁定房间几何取自 base_candidate；楼梯核（若有）默认一并锁定。
    """
    enriched = enrich_regeneration_scope(scope, program)
    locked_ids = resolve_locked_room_ids(enriched, program)
    room_locks = [
        _placement_lock_from_candidate(base_candidate, rid)
        for rid in sorted(locked_ids)
    ]
    return LayoutLocks(
        rooms=room_locks,
        stair=_stair_lock_from_candidate(base_candidate),
    )


def locks_from_placement_rects(
    scope: RegenerationScope,
    program: DesignProgram,
    placements: list[LockedRoomRect],
) -> LayoutLocks:
    """API 路径：由前端提交的 placement 摘要构建 locks。"""
    enriched = enrich_regeneration_scope(scope, program)
    locked_ids = resolve_locked_room_ids(enriched, program)
    by_id = {p.room_id: p for p in placements}
    missing = locked_ids - set(by_id)
    if missing:
        raise ValueError(f"base_placements 缺少锁定房间：{sorted(missing)}")
    room_locks = [by_id[rid] for rid in sorted(locked_ids)]
    stair = None
    for p in placements:
        if p.room_id.startswith("stair-"):
            stair = LockedStairCore(
                x=p.x,
                y=p.y,
                width=p.width,
                depth=p.depth,
            )
            break
    return LayoutLocks(rooms=room_locks, stair=stair)
