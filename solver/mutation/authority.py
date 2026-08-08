"""Geometry Mutation Authority — 会话几何唯一校验入口。"""

from __future__ import annotations

from packages.schema.layout import PlacementRect
from packages.schema.locks import LayoutLocks
from packages.schema.mutation import (
    GeometryMutation,
    MutationKind,
    MutationPreviewResult,
    MutationReject,
)
from packages.schema.program import DesignProgram
from solver.geometry.rect import Rect, from_placement, intersects
from solver.geometry.snap import snap_value
from solver.locks.envelopes import build_zone_member_envelopes, rect_in_envelope


def preview_mutation(
    *,
    program: DesignProgram,
    placements: list,  # RoomPlacement-like: room_id, floor_id, rect
    locks: LayoutLocks,
    mutation: GeometryMutation,
    snap_module: float | None = None,
) -> MutationPreviewResult:
    """
    LockGuard + GeometryConstraintChecker（AccessImpact 本轮不做 hard reject）。

    MOVE：平移；Commit 侧通常 upsert Room/Stair Lock。
    """
    module = (
        snap_module
        if snap_module is not None
        else program.solver_config.snap_module
    )
    if mutation.kind == MutationKind.MOVE:
        return _preview_move(
            program=program,
            placements=placements,
            locks=locks,
            mutation=mutation,
            module=module,
        )
    if mutation.kind == MutationKind.RESIZE:
        return MutationPreviewResult(
            ok=False,
            reasons=[
                MutationReject(
                    code="mutation.resize_not_ready",
                    message="Resize 尚未开放（Phase 4.3 P1）",
                )
            ],
        )
    return MutationPreviewResult(
        ok=False,
        reasons=[
            MutationReject(
                code="mutation.unsupported",
                message=f"暂不支持 mutation kind={mutation.kind}",
            )
        ],
    )


def _preview_move(
    *,
    program: DesignProgram,
    placements: list,
    locks: LayoutLocks,
    mutation: GeometryMutation,
    module: float,
) -> MutationPreviewResult:
    reasons: list[MutationReject] = []
    rid = mutation.room_id
    if not rid or mutation.proposed is None:
        return MutationPreviewResult(
            ok=False,
            reasons=[
                MutationReject(
                    code="mutation.missing_target",
                    message="MOVE 需要 room_id 与 proposed rect",
                )
            ],
        )

    current = next((p for p in placements if p.room_id == rid), None)
    if current is None:
        return MutationPreviewResult(
            ok=False,
            reasons=[
                MutationReject(
                    code="mutation.unknown_room",
                    message=f"未知房间：{rid}",
                )
            ],
        )

    prop = mutation.proposed
    # snap 原点
    sx = snap_value(prop.x, module)
    sy = snap_value(prop.y, module)
    snapped = PlacementRect(
        x=sx, y=sy, width=prop.width, depth=prop.depth
    )

    buildable = Rect(
        x=0.0,
        y=0.0,
        width=program.buildable.width,
        depth=program.buildable.depth,
    )
    pr = from_placement(snapped)
    if not _contains_tol(buildable, pr):
        reasons.append(
            MutationReject(
                code="mutation.outside_buildable",
                message="目标位置超出可建范围",
            )
        )

    # Zone envelope（Room Lock 成员不在 envelopes 内）
    envelopes = build_zone_member_envelopes(locks)
    # 若房间仅在 zone 锁内（未单独 Room Lock），必须留在 envelope
    is_room_locked = rid in locks.locked_room_ids
    if not is_room_locked and not rid.startswith("stair-"):
        env = envelopes.get(rid)
        if env is not None and not rect_in_envelope(pr, env):
            reasons.append(
                MutationReject(
                    code="mutation.zone_envelope",
                    message="不可移出锁定分区 envelope",
                )
            )

    # 楼梯：若 stair lock 存在，MOVE stair 允许（Commit 更新 lock）；非 stair 不得与 stair lock 重叠
    if locks.stair is not None and not rid.startswith("stair-"):
        stair_r = Rect(
            x=locks.stair.x,
            y=locks.stair.y,
            width=locks.stair.width,
            depth=locks.stair.depth,
        )
        if intersects(pr, stair_r):
            reasons.append(
                MutationReject(
                    code="mutation.stair_overlap",
                    message="不可与锁定楼梯核重叠",
                )
            )

    # 与其它房间重叠（同层）
    for p in placements:
        if p.room_id == rid:
            continue
        if p.floor_id != mutation.floor_id and not rid.startswith("stair-"):
            continue
        # 楼梯 MOVE 同步各层：只查同 floor_id 的非 stair，或各层 stair 跳过互检
        if rid.startswith("stair-"):
            if p.room_id.startswith("stair-"):
                continue
            if p.floor_id != mutation.floor_id:
                continue
        elif p.floor_id != current.floor_id:
            continue
        if intersects(pr, from_placement(p.rect)):
            reasons.append(
                MutationReject(
                    code="mutation.overlap",
                    message=f"与房间 {p.room_id} 重叠",
                )
            )
            break

    # 与其它 Room Lock 重叠（同层）
    for lr in locks.rooms:
        if lr.room_id == rid:
            continue
        if lr.floor_id != mutation.floor_id:
            continue
        lr_r = Rect(x=lr.x, y=lr.y, width=lr.width, depth=lr.depth)
        if intersects(pr, lr_r):
            reasons.append(
                MutationReject(
                    code="mutation.lock_overlap",
                    message=f"与锁定房间 {lr.room_id} 重叠",
                )
            )
            break

    return MutationPreviewResult(
        ok=len(reasons) == 0,
        reasons=reasons,
        snapped=snapped if not reasons else snapped,
    )


def _contains_tol(outer: Rect, inner: Rect, tol: float = 1e-6) -> bool:
    return (
        inner.x >= outer.x - tol
        and inner.y >= outer.y - tol
        and inner.x + inner.width <= outer.x + outer.width + tol
        and inner.y + inner.depth <= outer.y + outer.depth + tol
    )
