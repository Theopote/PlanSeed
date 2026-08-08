"""Geometry Mutation Authority — 会话几何唯一校验入口。"""

from __future__ import annotations

from packages.schema.layout import PlacementRect, RoomPlacement
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
from solver.topology.constants import MIN_ACCESS_WALL
from solver.topology.doors import shared_boundary_between

# 绝对最小边长（米）；小于此硬拒。RoomSpec.min_width 另作 soft warning。
_HARD_MIN_EDGE = 0.9


def preview_mutation(
    *,
    program: DesignProgram,
    placements: list,  # RoomPlacement-like: room_id, floor_id, rect
    locks: LayoutLocks,
    mutation: GeometryMutation,
    snap_module: float | None = None,
) -> MutationPreviewResult:
    """
    LockGuard + GeometryConstraintChecker；AccessImpact 仅 soft warning。

    MOVE：平移原点 snap；RESIZE：四边 snap + 最小边硬拒 / min_width·area soft。
    Commit 侧通常 upsert Room/Stair Lock。
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
        return _preview_resize(
            program=program,
            placements=placements,
            locks=locks,
            mutation=mutation,
            module=module,
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
    rid, prop, current, early = _resolve_target(placements, mutation, "MOVE")
    if early is not None:
        return early
    assert rid is not None and prop is not None and current is not None

    snapped = PlacementRect(
        x=snap_value(prop.x, module),
        y=snap_value(prop.y, module),
        width=prop.width,
        depth=prop.depth,
    )
    reasons, conflicts = _geometry_check(
        program=program,
        placements=placements,
        locks=locks,
        room_id=rid,
        floor_id=mutation.floor_id,
        current_floor_id=current.floor_id,
        snapped=snapped,
    )
    warnings = _access_impact_warnings(
        current=current,
        snapped=snapped,
        placements=placements,
    )
    return MutationPreviewResult(
        ok=len(reasons) == 0,
        reasons=reasons,
        warnings=warnings,
        snapped=snapped,
        conflict_room_ids=conflicts,
    )


def _preview_resize(
    *,
    program: DesignProgram,
    placements: list,
    locks: LayoutLocks,
    mutation: GeometryMutation,
    module: float,
) -> MutationPreviewResult:
    rid, prop, current, early = _resolve_target(placements, mutation, "RESIZE")
    if early is not None:
        return early
    assert rid is not None and prop is not None and current is not None

    snapped = _snap_rect_edges(prop, module)
    reasons: list[MutationReject] = []
    warnings: list[MutationReject] = []
    conflicts: list[str] = []

    if snapped.width < _HARD_MIN_EDGE - 1e-9 or snapped.depth < _HARD_MIN_EDGE - 1e-9:
        reasons.append(
            MutationReject(
                code="mutation.min_edge",
                message=f"边长不可小于 {_HARD_MIN_EDGE:g} m",
            )
        )

    geo_reasons, conflicts = _geometry_check(
        program=program,
        placements=placements,
        locks=locks,
        room_id=rid,
        floor_id=mutation.floor_id,
        current_floor_id=current.floor_id,
        snapped=snapped,
    )
    reasons.extend(geo_reasons)

    if not rid.startswith("stair-"):
        room = program.room_by_id(rid)
        if room is not None:
            min_dim = min(snapped.width, snapped.depth)
            if room.min_width is not None and min_dim < room.min_width - 1e-9:
                warnings.append(
                    MutationReject(
                        code="mutation.soft_min_width",
                        message=(
                            f"净宽偏小：{min_dim:.2f} < "
                            f"建议 {room.min_width:.2f} m"
                        ),
                    )
                )
            min_area = room.resolved_min_area()
            area = snapped.width * snapped.depth
            if area < min_area - 1e-9:
                warnings.append(
                    MutationReject(
                        code="mutation.soft_min_area",
                        message=(
                            f"面积偏小：{area:.1f} < "
                            f"建议 {min_area:.1f} m²"
                        ),
                    )
                )

    warnings.extend(
        _access_impact_warnings(
            current=current,
            snapped=snapped,
            placements=placements,
        )
    )

    return MutationPreviewResult(
        ok=len(reasons) == 0,
        reasons=reasons,
        warnings=warnings,
        snapped=snapped,
        conflict_room_ids=conflicts,
    )


def _resolve_target(
    placements: list,
    mutation: GeometryMutation,
    label: str,
) -> tuple[str | None, PlacementRect | None, object | None, MutationPreviewResult | None]:
    rid = mutation.room_id
    if not rid or mutation.proposed is None:
        return (
            None,
            None,
            None,
            MutationPreviewResult(
                ok=False,
                reasons=[
                    MutationReject(
                        code="mutation.missing_target",
                        message=f"{label} 需要 room_id 与 proposed rect",
                    )
                ],
            ),
        )
    current = next((p for p in placements if p.room_id == rid), None)
    if current is None:
        return (
            None,
            None,
            None,
            MutationPreviewResult(
                ok=False,
                reasons=[
                    MutationReject(
                        code="mutation.unknown_room",
                        message=f"未知房间：{rid}",
                    )
                ],
            ),
        )
    return rid, mutation.proposed, current, None


def _snap_rect_edges(prop: PlacementRect, module: float) -> PlacementRect:
    x0 = snap_value(prop.x, module)
    y0 = snap_value(prop.y, module)
    x1 = snap_value(prop.x + prop.width, module)
    y1 = snap_value(prop.y + prop.depth, module)
    w = max(module, x1 - x0) if module > 0 else max(0.0, x1 - x0)
    d = max(module, y1 - y0) if module > 0 else max(0.0, y1 - y0)
    return PlacementRect(x=x0, y=y0, width=w, depth=d)


def _geometry_check(
    *,
    program: DesignProgram,
    placements: list,
    locks: LayoutLocks,
    room_id: str,
    floor_id: str,
    current_floor_id: str,
    snapped: PlacementRect,
) -> tuple[list[MutationReject], list[str]]:
    reasons: list[MutationReject] = []
    conflicts: list[str] = []
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

    envelopes = build_zone_member_envelopes(locks)
    is_room_locked = room_id in locks.locked_room_ids
    if not is_room_locked and not room_id.startswith("stair-"):
        env = envelopes.get(room_id)
        if env is not None and not rect_in_envelope(pr, env):
            reasons.append(
                MutationReject(
                    code="mutation.zone_envelope",
                    message="不可移出锁定分区 envelope",
                )
            )

    if locks.stair is not None and not room_id.startswith("stair-"):
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
            conflicts.append("__stair__")

    for p in placements:
        if p.room_id == room_id:
            continue
        if room_id.startswith("stair-"):
            if p.room_id.startswith("stair-"):
                continue
            if p.floor_id != floor_id:
                continue
        elif p.floor_id != current_floor_id:
            continue
        if intersects(pr, from_placement(p.rect)):
            reasons.append(
                MutationReject(
                    code="mutation.overlap",
                    message=f"与房间 {p.room_id} 重叠",
                )
            )
            conflicts.append(p.room_id)
            break

    for lr in locks.rooms:
        if lr.room_id == room_id:
            continue
        if lr.floor_id != floor_id:
            continue
        lr_r = Rect(x=lr.x, y=lr.y, width=lr.width, depth=lr.depth)
        if intersects(pr, lr_r):
            reasons.append(
                MutationReject(
                    code="mutation.lock_overlap",
                    message=f"与锁定房间 {lr.room_id} 重叠",
                )
            )
            if lr.room_id not in conflicts:
                conflicts.append(lr.room_id)
            break

    return reasons, conflicts


def _access_impact_warnings(
    *,
    current: object,
    snapped: PlacementRect,
    placements: list,
) -> list[MutationReject]:
    """推断：原与本房共边≥MIN_ACCESS_WALL 的邻居，变更后丢失共边 → soft。"""
    before = _as_room_placement(current)
    if before is None:
        return []
    after = before.model_copy(update={"rect": snapped})
    lost: list[str] = []
    for p in placements:
        if getattr(p, "room_id", None) == before.room_id:
            continue
        other = _as_room_placement(p)
        if other is None or other.floor_id != before.floor_id:
            continue
        if shared_boundary_between(before, other, min_length=MIN_ACCESS_WALL) is None:
            continue
        if shared_boundary_between(after, other, min_length=MIN_ACCESS_WALL) is None:
            lost.append(other.room_id)
    if not lost:
        return []
    names = "、".join(lost[:3])
    more = f" 等{len(lost)}处" if len(lost) > 3 else ""
    return [
        MutationReject(
            code="mutation.access_impact",
            message=f"可能打断与 {names}{more} 的通行共边",
        )
    ]


def _as_room_placement(obj: object) -> RoomPlacement | None:
    if isinstance(obj, RoomPlacement):
        return obj
    try:
        rid = obj.room_id  # type: ignore[attr-defined]
        fid = obj.floor_id  # type: ignore[attr-defined]
        rect = obj.rect  # type: ignore[attr-defined]
        if not isinstance(rect, PlacementRect):
            rect = PlacementRect(
                x=float(rect.x),
                y=float(rect.y),
                width=float(rect.width),
                depth=float(rect.depth),
            )
        return RoomPlacement(
            room_id=str(rid),
            floor_id=str(fid),
            rect=rect,
            name=str(rid),
            category="other",
        )
    except Exception:
        return None


def _contains_tol(outer: Rect, inner: Rect, tol: float = 1e-6) -> bool:
    return (
        inner.x >= outer.x - tol
        and inner.y >= outer.y - tol
        and inner.x + inner.width <= outer.x + outer.width + tol
        and inner.y + inner.depth <= outer.y + outer.depth + tol
    )
