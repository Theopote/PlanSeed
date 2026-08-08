"""
ConnectionResolver — topology → 局部几何（Phase 2.1.1 / 2.1.2）。

原则：
- **禁止**整层重跑 Guillotine / 为门全局重优化
- 同层 required 开口边：
  1) 投影重叠且缝隙 ≤ max_nudge → 闭合分界
  2) 已共边但偏短 → 沿墙向加长
  3) 仍失败 → 小 AABB 内跨区局部重切（强制对端先共边）
- 不动楼梯核；重切区撞核或过大则放弃
"""

from __future__ import annotations

from packages.schema.layout import LayoutCandidate, PlacementRect, RoomPlacement
from packages.schema.program import DesignProgram
from solver.geometry.rect import Rect, contains, from_placement, intersects, shared_edge_length
from solver.geometry.snap import snap_value
from solver.topology.access import MIN_ACCESS_WALL
from solver.topology.doors import (
    find_placements,
    required_opening_connections,
    shared_boundary_between,
)

DEFAULT_MAX_NUDGE = 1.5


def _is_stair(p: RoomPlacement) -> bool:
    return p.room_id.startswith("stair-") or (
        (p.category or "") == "circulation" and "楼梯" in (p.name or "")
    )


def _overlap_1d(a0: float, a1: float, b0: float, b1: float) -> float:
    return min(a1, b1) - max(a0, b0)


def _floor_bounds(candidate: LayoutCandidate, floor_id: str, program: DesignProgram) -> Rect:
    return Rect(
        x=0.0,
        y=0.0,
        width=program.buildable.width,
        depth=program.buildable.depth,
    )


def _obstacles(
    candidate: LayoutCandidate, floor_id: str, *keep: RoomPlacement
) -> list[Rect]:
    keep_ids = {p.room_id for p in keep}
    return [
        from_placement(p.rect)
        for fl in candidate.floors
        if fl.floor_id == floor_id
        for p in fl.placements
        if p.room_id not in keep_ids
    ]


def _valid_pair(
    ra: Rect,
    rb: Rect,
    *,
    bounds: Rect,
    obstacles: list[Rect],
    min_span: float,
) -> bool:
    if ra.width + 1e-9 < min_span or ra.depth + 1e-9 < min_span:
        return False
    if rb.width + 1e-9 < min_span or rb.depth + 1e-9 < min_span:
        return False
    if not contains(bounds, ra) or not contains(bounds, rb):
        return False
    if intersects(ra, rb):
        return False
    for obs in obstacles:
        if intersects(ra, obs) or intersects(rb, obs):
            return False
    return True


def _set_rect(p: RoomPlacement, r: Rect) -> None:
    p.rect = PlacementRect(x=r.x, y=r.y, width=r.width, depth=r.depth)


def _try_close_axis_gap(
    pa: RoomPlacement,
    pb: RoomPlacement,
    *,
    bounds: Rect,
    obstacles: list[Rect],
    module: float,
    min_wall: float,
    max_nudge: float,
) -> bool:
    """投影重叠足够时，闭合 X 或 Y 向缝隙。"""
    ra, rb = from_placement(pa.rect), from_placement(pb.rect)
    min_span = module * 2
    y_ov = _overlap_1d(ra.top, ra.bottom, rb.top, rb.bottom)
    x_ov = _overlap_1d(ra.left, ra.right, rb.left, rb.right)

    # —— 左右缝（需足够 Y 重叠）——
    if y_ov + 1e-9 >= min_wall:
        if ra.right <= rb.left + 1e-9:
            gap = rb.left - ra.right
            left, right = pa, pb
            r_left, r_right = ra, rb
        elif rb.right <= ra.left + 1e-9:
            gap = ra.left - rb.right
            left, right = pb, pa
            r_left, r_right = rb, ra
        else:
            gap = -1.0
            left = right = pa
            r_left = r_right = ra
        if 0 < gap <= max_nudge + 1e-9:
            mid = snap_value((r_left.right + r_right.left) / 2.0, module)
            mid = max(r_left.x + min_span, min(r_right.right - min_span, mid))
            new_l = Rect(
                x=r_left.x, y=r_left.y, width=mid - r_left.x, depth=r_left.depth
            )
            new_r = Rect(
                x=mid, y=r_right.y, width=r_right.right - mid, depth=r_right.depth
            )
            if _valid_pair(
                new_l, new_r, bounds=bounds, obstacles=obstacles, min_span=min_span
            ):
                _set_rect(left, new_l)
                _set_rect(right, new_r)
                return True

    # —— 上下缝（需足够 X 重叠）——
    if x_ov + 1e-9 >= min_wall:
        if ra.bottom <= rb.top + 1e-9:
            gap = rb.top - ra.bottom
            top_p, bot_p = pa, pb
            r_top, r_bot = ra, rb
        elif rb.bottom <= ra.top + 1e-9:
            gap = ra.top - rb.bottom
            top_p, bot_p = pb, pa
            r_top, r_bot = rb, ra
        else:
            gap = -1.0
            top_p = bot_p = pa
            r_top = r_bot = ra
        if 0 < gap <= max_nudge + 1e-9:
            mid = snap_value((r_top.bottom + r_bot.top) / 2.0, module)
            mid = max(r_top.y + min_span, min(r_bot.bottom - min_span, mid))
            new_t = Rect(
                x=r_top.x, y=r_top.y, width=r_top.width, depth=mid - r_top.y
            )
            new_b = Rect(
                x=r_bot.x, y=mid, width=r_bot.width, depth=r_bot.bottom - mid
            )
            if _valid_pair(
                new_t, new_b, bounds=bounds, obstacles=obstacles, min_span=min_span
            ):
                _set_rect(top_p, new_t)
                _set_rect(bot_p, new_b)
                return True
    return False


def _try_lengthen_shared_edge(
    pa: RoomPlacement,
    pb: RoomPlacement,
    *,
    bounds: Rect,
    obstacles: list[Rect],
    module: float,
    min_wall: float,
    max_nudge: float,
) -> bool:
    """已有短共边时，沿墙向延伸一侧以凑够 min_wall。"""
    ra, rb = from_placement(pa.rect), from_placement(pb.rect)
    shared = shared_edge_length(ra, rb)
    if shared <= 1e-9 or shared + 1e-9 >= min_wall:
        return False
    need = min_wall - shared
    if need > max_nudge + 1e-9:
        return False
    min_span = module * 2
    grow = max(need, snap_value(need, module))
    tol = 1e-6

    trials: list[tuple[Rect, Rect]] = []

    # 竖向贴边 → 改 Y 范围
    vertical_touch = abs(ra.right - rb.left) <= tol or abs(ra.left - rb.right) <= tol
    if vertical_touch and _overlap_1d(ra.top, ra.bottom, rb.top, rb.bottom) > tol:
        # 向下延伸 a
        trials.append(
            (Rect(x=ra.x, y=ra.y, width=ra.width, depth=ra.depth + grow), rb)
        )
        # 向上延伸 a
        ny = max(bounds.top, ra.y - grow)
        trials.append(
            (Rect(x=ra.x, y=ny, width=ra.width, depth=ra.bottom - ny), rb)
        )
        # 向下 / 向上延伸 b
        trials.append(
            (ra, Rect(x=rb.x, y=rb.y, width=rb.width, depth=rb.depth + grow))
        )
        ny = max(bounds.top, rb.y - grow)
        trials.append(
            (ra, Rect(x=rb.x, y=ny, width=rb.width, depth=rb.bottom - ny))
        )

    # 水平贴边 → 改 X 范围
    horizontal_touch = abs(ra.bottom - rb.top) <= tol or abs(ra.top - rb.bottom) <= tol
    if horizontal_touch and _overlap_1d(ra.left, ra.right, rb.left, rb.right) > tol:
        trials.append(
            (Rect(x=ra.x, y=ra.y, width=ra.width + grow, depth=ra.depth), rb)
        )
        nx = max(bounds.left, ra.x - grow)
        trials.append(
            (Rect(x=nx, y=ra.y, width=ra.right - nx, depth=ra.depth), rb)
        )
        trials.append(
            (ra, Rect(x=rb.x, y=rb.y, width=rb.width + grow, depth=rb.depth))
        )
        nx = max(bounds.left, rb.x - grow)
        trials.append(
            (ra, Rect(x=nx, y=rb.y, width=rb.right - nx, depth=rb.depth))
        )

    for na, nb in trials:
        if not _valid_pair(
            na, nb, bounds=bounds, obstacles=obstacles, min_span=min_span
        ):
            continue
        if shared_edge_length(na, nb) + 1e-9 >= min_wall:
            _set_rect(pa, na)
            _set_rect(pb, nb)
            return True
    return False


def repair_connection_pair(
    pa: RoomPlacement,
    pb: RoomPlacement,
    *,
    bounds: Rect,
    obstacles: list[Rect],
    module: float,
    min_wall: float = MIN_ACCESS_WALL,
    max_nudge: float = DEFAULT_MAX_NUDGE,
) -> bool:
    """尝试局部修补一对放置；成功返回 True。"""
    if _is_stair(pa) or _is_stair(pb):
        return False
    if shared_boundary_between(pa, pb, min_length=min_wall) is not None:
        return False
    if _try_close_axis_gap(
        pa,
        pb,
        bounds=bounds,
        obstacles=obstacles,
        module=module,
        min_wall=min_wall,
        max_nudge=max_nudge,
    ):
        return True
    return _try_lengthen_shared_edge(
        pa,
        pb,
        bounds=bounds,
        obstacles=obstacles,
        module=module,
        min_wall=min_wall,
        max_nudge=max_nudge,
    )


def resolve_required_connections(
    program: DesignProgram,
    candidate: LayoutCandidate,
    *,
    module: float | None = None,
    min_wall: float = MIN_ACCESS_WALL,
    max_nudge: float = DEFAULT_MAX_NUDGE,
    allow_reslice: bool = True,
) -> int:
    """
    对 required 开口连接做局部共边修补，必要时跨区局部重切。

    返回成功修补次数（含 reslice）。远距过大 / 撞楼梯核的必连不处理。
    """
    from solver.topology.reslice import try_reslice_required_pair

    snap = module if module is not None else program.solver_config.snap_module
    repaired = 0
    resliced = 0
    for conn in required_opening_connections(program):
        pas = find_placements(candidate, conn.a)
        pbs = find_placements(candidate, conn.b)
        if not pas or not pbs:
            continue
        done = False
        for pa in pas:
            for pb in pbs:
                if pa.floor_id != pb.floor_id:
                    continue
                if shared_boundary_between(pa, pb, min_length=min_wall) is not None:
                    done = True
                    break
                bounds = _floor_bounds(candidate, pa.floor_id, program)
                obs = _obstacles(candidate, pa.floor_id, pa, pb)
                if repair_connection_pair(
                    pa,
                    pb,
                    bounds=bounds,
                    obstacles=obs,
                    module=snap,
                    min_wall=min_wall,
                    max_nudge=max_nudge,
                ):
                    repaired += 1
                    done = True
                    break
                if allow_reslice and try_reslice_required_pair(
                    program,
                    candidate,
                    pa,
                    pb,
                    module=snap,
                    min_wall=min_wall,
                    floor_bounds=bounds,
                ):
                    resliced += 1
                    repaired += 1
                    done = True
                    break
            if done:
                break
    if repaired:
        candidate.metrics["connection_repairs"] = float(
            candidate.metrics.get("connection_repairs", 0)
        ) + repaired
    if resliced:
        candidate.metrics["connection_reslices"] = float(
            candidate.metrics.get("connection_reslices", 0)
        ) + resliced
    return repaired
