"""楼层平面覆盖率 — 可建面积须被 placements 完全铺满（含楼梯）。"""

from __future__ import annotations

from packages.schema.layout import PlacementRect, RoomPlacement, Violation
from packages.schema.program import DesignProgram
from solver.evaluation.weights import DEFAULT_WEIGHTS
from solver.geometry.rect import (
    Rect,
    from_placement,
    intersection,
    intersects,
    shared_edge_length,
    touches,
)

COVERAGE_TOLERANCE = 1e-6
LAYOUT_ABSORB_TOLERANCE = 0.5


def is_fixed_void_placement(room_id: str) -> bool:
    """预扣除竖向空洞（楼梯 / 天井）— 不可被 grow/fill 侵入或作为 donor。"""
    return room_id.startswith("stair-") or room_id.startswith("void-")


def _rect_aspect_ratio(rect: Rect) -> float:
    short = min(rect.width, rect.depth)
    long = max(rect.width, rect.depth)
    return long / max(short, 0.01)


def _fill_aspect_cap_exempt(room_id: str) -> bool:
    """gap 吸收时长宽比豁免（楼梯 / 天井 / 系统交通）。"""
    if is_fixed_void_placement(room_id):
        return True
    return room_id.startswith("circ-")


def _merged_respects_aspect_cap(room_id: str, merged: Rect) -> bool:
    if _fill_aspect_cap_exempt(room_id):
        return True
    return _rect_aspect_ratio(merged) <= DEFAULT_WEIGHTS.aspect_ratio_threshold + 1e-6


def _cede_shrinks_donor_short_side(direction: str, donor: Rect) -> bool:
    """匀面积是否沿 donor 短边收缩（宽扁房削深 / 高窄房削宽会拉高长宽比）。"""
    if direction in ("north", "south"):
        return donor.width >= donor.depth
    return donor.depth >= donor.width


def _donor_cede_respects_aspect_cap(
    room_id: str,
    merged: Rect,
    prior_aspect_ratio: float,
    *,
    cede_direction: str,
    donor_before: Rect,
) -> bool:
    """grow 匀面积 donor：已超标时优先「不恶化」；短边匀出时放行 grow。"""
    if _fill_aspect_cap_exempt(room_id):
        return True
    thr = DEFAULT_WEIGHTS.aspect_ratio_threshold + 1e-6
    new_ratio = _rect_aspect_ratio(merged)
    if prior_aspect_ratio <= thr:
        return new_ratio <= thr
    if new_ratio <= prior_aspect_ratio + 1e-6:
        return True
    return _cede_shrinks_donor_short_side(cede_direction, donor_before)


def largest_aspect_ok_placement_rect(
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    threshold: float | None = None,
) -> PlacementRect:
    """在边界内取面积尽量大且满足长宽比的矩形（贴原点对齐）。"""
    thr = (
        threshold
        if threshold is not None
        else DEFAULT_WEIGHTS.aspect_ratio_threshold
    )
    w = max(0.0, x1 - x0)
    h = max(0.0, y1 - y0)
    if w <= 1e-9 or h <= 1e-9:
        return PlacementRect(x=x0, y=y0, width=max(w, 0.01), depth=max(h, 0.01))
    if _rect_aspect_ratio(Rect(x=0, y=0, width=w, depth=h)) <= thr + 1e-6:
        return PlacementRect(x=x0, y=y0, width=w, depth=h)
    if w >= h:
        return PlacementRect(x=x0, y=y0, width=h * thr, depth=h)
    return PlacementRect(x=x0, y=y0, width=w, depth=w * thr)


def clamp_program_room_aspect_ratios(
    footprint: Rect,
    placements: list[RoomPlacement],
    floor_id: str,
    *,
    threshold: float | None = None,
    min_area_by_room_id: dict[str, float] | None = None,
    tolerance: float = COVERAGE_TOLERANCE,
) -> list[RoomPlacement]:
    """裁切超细长 program 房间，余量交回 fill（不裁到低于 min_area）。"""
    from packages.schema.layout import PlacementSource

    thr = (
        threshold
        if threshold is not None
        else DEFAULT_WEIGHTS.aspect_ratio_threshold
    )
    updated = [p.model_copy(deep=True) for p in placements]
    changed = False
    for i, p in enumerate(updated):
        if p.source != PlacementSource.PROGRAM:
            continue
        if is_fixed_void_placement(p.room_id):
            continue
        r = p.rect
        if _rect_aspect_ratio(from_placement(r)) <= thr + 1e-6:
            continue
        clamped = largest_aspect_ok_placement_rect(
            r.x, r.y, r.right, r.bottom, thr
        )
        lo = (
            min_area_by_room_id.get(p.room_id)
            if min_area_by_room_id is not None
            else None
        )
        if lo is not None and clamped.area + tolerance < lo:
            continue
        updated[i] = p.model_copy(update={"rect": clamped})
        changed = True
    if not changed:
        return updated
    return fill_floor_coverage_gaps(
        footprint,
        updated,
        min_area_by_room_id=min_area_by_room_id,
        tolerance=tolerance,
    )


def _overlap_clip_priority(p: RoomPlacement) -> int:
    """数值越小越不应被裁切（楼梯 / 天井 > 走廊 > 其他 generated > program）。"""
    from packages.schema.layout import PlacementSource

    if is_fixed_void_placement(p.room_id):
        return 0
    if p.room_id.startswith("circ-"):
        return 1
    if p.source == PlacementSource.GENERATED:
        return 2
    return 3


def resolve_placement_overlaps(
    placements: list[RoomPlacement],
    *,
    tolerance: float = COVERAGE_TOLERANCE,
) -> list[RoomPlacement]:
    """消除轴对齐矩形重叠；固定区优先保留，退让方取最大残余片段。"""
    updated = [p.model_copy(deep=True) for p in placements]
    max_iter = len(updated) ** 2 + 4
    for _ in range(max_iter):
        best_pair: tuple[int, int] | None = None
        best_area = tolerance
        for i in range(len(updated)):
            for j in range(i + 1, len(updated)):
                inter = intersection(
                    from_placement(updated[i].rect),
                    from_placement(updated[j].rect),
                )
                if inter is not None and inter.area > best_area:
                    best_area = inter.area
                    best_pair = (i, j)
        if best_pair is None:
            break
        i, j = best_pair
        a, b = updated[i], updated[j]
        pa, pb = _overlap_clip_priority(a), _overlap_clip_priority(b)
        if pa > pb:
            clip_idx, keep_idx = i, j
        elif pb > pa:
            clip_idx, keep_idx = j, i
        elif a.rect.area >= b.rect.area:
            clip_idx, keep_idx = i, j
        else:
            clip_idx, keep_idx = j, i
        clip_p = updated[clip_idx]
        keep_p = updated[keep_idx]
        clipped = clip_placement_away_from_obstacles(
            clip_p.rect,
            [from_placement(keep_p.rect)],
            tolerance=tolerance,
        )
        if clipped is None:
            updated.pop(clip_idx)
        else:
            updated[clip_idx] = clip_p.model_copy(update={"rect": clipped})
    return updated


def placement_overlap_violations(
    *,
    floor_id: str,
    placements: list[RoomPlacement],
    tolerance: float = COVERAGE_TOLERANCE,
) -> list[Violation]:
    """检测同层房间面积重叠（含 program 侵入 stair/void）。"""
    violations: list[Violation] = []
    rects = [from_placement(p.rect) for p in placements]
    for i, a in enumerate(placements):
        for j in range(i + 1, len(placements)):
            inter = intersection(rects[i], rects[j])
            if inter is None or inter.area <= tolerance:
                continue
            violations.append(
                Violation(
                    constraint_id="geometry.placement_overlap",
                    room_ids=sorted({a.room_id, placements[j].room_id}),
                    message=(
                        f"楼层 {floor_id} 房间重叠：{a.room_id}↔{placements[j].room_id} "
                        f"（{inter.area:.4f} m²）"
                    ),
                    measured_value=inter.area,
                    hard=True,
                    source="system",
                )
            )
    return violations


def clip_placement_away_from_obstacles(
    rect: PlacementRect,
    obstacles: list[Rect],
    *,
    tolerance: float = COVERAGE_TOLERANCE,
) -> PlacementRect | None:
    """从 placement 中裁掉与固定障碍重叠部分，取最大残余片段。"""
    from solver.geometry.free_rects import subtract_rects

    cur = from_placement(rect)
    for obs in obstacles:
        if not intersects(cur, obs):
            continue
        parts = subtract_rects([cur], [obs])
        parts = [p for p in parts if p.area > tolerance]
        if not parts:
            return None
        cur = max(parts, key=lambda p: p.area)
    return PlacementRect(x=cur.x, y=cur.y, width=cur.width, depth=cur.depth)


def floor_placed_area(placements: list[RoomPlacement]) -> float:
    return sum(p.rect.area for p in placements)


def floor_coverage_gap(footprint_area: float, placements: list[RoomPlacement]) -> float:
    return footprint_area - floor_placed_area(placements)


def pack_target_area(pack_rects: list[Rect]) -> float:
    return sum(r.area for r in pack_rects)


def pack_coverage_gap(pack_rects: list[Rect], placed_rects: list[Rect]) -> float:
    return pack_target_area(pack_rects) - sum(r.area for r in placed_rects)


def assert_floor_fully_covered(
    footprint_area: float,
    placements: list[RoomPlacement],
    *,
    floor_id: str = "",
    tolerance: float = COVERAGE_TOLERANCE,
) -> None:
    gap = floor_coverage_gap(footprint_area, placements)
    if gap > tolerance:
        label = f" on floor {floor_id}" if floor_id else ""
        raise AssertionError(
            f"layout coverage gap{label}: {gap:.6f} m² "
            f"(footprint={footprint_area:.6f}, placed={floor_placed_area(placements):.6f})"
        )
    if gap < -tolerance:
        label = f" on floor {floor_id}" if floor_id else ""
        raise AssertionError(
            f"layout coverage overlap{label}: {-gap:.6f} m² over footprint"
        )
    rects = [from_placement(p.rect) for p in placements]
    for i, a in enumerate(rects):
        for j in range(i + 1, len(rects)):
            if intersects(a, rects[j]):
                label = f" on floor {floor_id}" if floor_id else ""
                raise AssertionError(
                    f"layout overlap{label}: {placements[i].room_id} vs {placements[j].room_id}"
                )


def merge_adjacent_rects(a: Rect, b: Rect) -> Rect | None:
    """两邻接/相交矩形的并；仅当并仍为轴对齐矩形时返回。"""
    if not (touches(a, b) or a.left < b.right and a.right > b.left and a.top < b.bottom and a.bottom > b.top):
        return None
    x0 = min(a.x, b.x)
    y0 = min(a.y, b.y)
    x1 = max(a.right, b.right)
    y1 = max(a.bottom, b.bottom)
    union = Rect(x=x0, y=y0, width=x1 - x0, depth=y1 - y0)
    inter = intersection(a, b)
    inter_area = inter.area if inter is not None else 0.0
    if abs(union.area - (a.area + b.area - inter_area)) > 1e-4:
        return None
    return union


def layout_coverage_violations(
    program: DesignProgram,
    *,
    floor_id: str,
    placements: list[RoomPlacement],
    tolerance: float = COVERAGE_TOLERANCE,
) -> list[Violation]:
    footprint = program.buildable.width * program.buildable.depth
    gap = floor_coverage_gap(footprint, placements)
    if gap <= tolerance:
        return []
    return [
        Violation(
            constraint_id="geometry.layout_coverage",
            room_ids=[],
            message=(
                f"楼层 {floor_id} 存在未分配空白：{gap:.4f} m² "
                f"（可建 {footprint:.4f} m²，已放置 {floor_placed_area(placements):.4f} m²）"
            ),
            hard=True,
            source="system",
        )
    ]


def absorb_sliver_into(placed: Rect, sliver: Rect, *, tolerance: float = 1e-6) -> Rect | None:
    """把与 placed 对齐的细条 sliver 并入 placed（仅扩大 placed，不处理 L 形余量）。"""
    # sliver 在 placed 下方
    if abs(sliver.top - placed.bottom) <= tolerance:
        x0 = max(placed.left, sliver.left)
        x1 = min(placed.right, sliver.right)
        if x1 - x0 <= tolerance:
            return None
        if x0 > placed.left + tolerance or x1 < placed.right - tolerance:
            return None
        return Rect(
            x=placed.x,
            y=placed.y,
            width=placed.width,
            depth=sliver.bottom - placed.y,
        )
    # sliver 在 placed 上方
    if abs(sliver.bottom - placed.top) <= tolerance:
        x0 = max(placed.left, sliver.left)
        x1 = min(placed.right, sliver.right)
        if x1 - x0 <= tolerance:
            return None
        if x0 > placed.left + tolerance or x1 < placed.right - tolerance:
            return None
        return Rect(
            x=placed.x,
            y=sliver.y,
            width=placed.width,
            depth=placed.bottom - sliver.y,
        )
    # sliver 在 placed 右侧
    if abs(sliver.left - placed.right) <= tolerance:
        y0 = max(placed.top, sliver.top)
        y1 = min(placed.bottom, sliver.bottom)
        if y1 - y0 <= tolerance:
            return None
        if y0 > placed.top + tolerance or y1 < placed.bottom - tolerance:
            return None
        return Rect(
            x=placed.x,
            y=placed.y,
            width=sliver.right - placed.x,
            depth=placed.depth,
        )
    # sliver 在 placed 左侧
    if abs(sliver.right - placed.left) <= tolerance:
        y0 = max(placed.top, sliver.top)
        y1 = min(placed.bottom, sliver.bottom)
        if y1 - y0 <= tolerance:
            return None
        if y0 > placed.top + tolerance or y1 < placed.bottom - tolerance:
            return None
        return Rect(
            x=sliver.x,
            y=placed.y,
            width=placed.right - sliver.x,
            depth=placed.depth,
        )
    return merge_adjacent_rects(placed, sliver)


def try_absorb_sliver_without_overlap(
    placed: Rect,
    sliver: Rect,
    others: list[Rect],
    *,
    tolerance: float = COVERAGE_TOLERANCE,
) -> Rect | None:
    merged = absorb_sliver_into(placed, sliver, tolerance=tolerance)
    if merged is None:
        return None
    for other in others:
        inter = intersection(merged, other)
        if inter is not None and inter.area > tolerance:
            return None
    return merged


def try_absorb_sliver_within_area_cap(
    placed: Rect,
    sliver: Rect,
    others: list[Rect],
    max_area: float,
    *,
    tolerance: float = COVERAGE_TOLERANCE,
) -> Rect | None:
    """在不超过 max_area 的前提下，尽量将 sliver 并入 placed。"""
    spare = max_area - placed.area
    if spare <= tolerance:
        return None

    full = try_absorb_sliver_without_overlap(
        placed, sliver, others, tolerance=tolerance
    )
    if full is not None and full.area <= max_area + tolerance:
        return full

    def _valid(merged: Rect) -> Rect | None:
        if merged.area > max_area + tolerance:
            return None
        for other in others:
            inter = intersection(merged, other)
            if inter is not None and inter.area > tolerance:
                return None
        return merged

    overlap_top = max(placed.top, sliver.top)
    overlap_bottom = min(placed.bottom, sliver.bottom)
    overlap_height = overlap_bottom - overlap_top

    # sliver 在 placed 右侧
    if abs(sliver.left - placed.right) <= tolerance and overlap_height > tolerance:
        max_w = spare / placed.depth if placed.depth > tolerance else 0.0
        width = min(sliver.width, max_w, sliver.right - placed.right)
        if width > tolerance:
            merged = Rect(
                x=placed.x,
                y=placed.y,
                width=placed.width + width,
                depth=placed.depth,
            )
            return _valid(merged)

    # sliver 在 placed 左侧
    if abs(sliver.right - placed.left) <= tolerance and overlap_height > tolerance:
        max_w = spare / placed.depth if placed.depth > tolerance else 0.0
        width = min(sliver.width, max_w, placed.left - sliver.left)
        if width > tolerance:
            merged = Rect(
                x=placed.x - width,
                y=placed.y,
                width=placed.width + width,
                depth=placed.depth,
            )
            return _valid(merged)

    overlap_left = max(placed.left, sliver.left)
    overlap_right = min(placed.right, sliver.right)
    overlap_width = overlap_right - overlap_left

    # sliver 在 placed 下方
    if abs(sliver.top - placed.bottom) <= tolerance and overlap_width > tolerance:
        max_d = spare / placed.width if placed.width > tolerance else 0.0
        depth = min(sliver.depth, max_d, sliver.bottom - placed.bottom)
        if depth > tolerance:
            merged = Rect(
                x=placed.x,
                y=placed.y,
                width=placed.width,
                depth=placed.depth + depth,
            )
            return _valid(merged)

    # sliver 在 placed 上方
    if abs(sliver.bottom - placed.top) <= tolerance and overlap_width > tolerance:
        max_d = spare / placed.width if placed.width > tolerance else 0.0
        depth = min(sliver.depth, max_d, placed.top - sliver.top)
        if depth > tolerance:
            merged = Rect(
                x=placed.x,
                y=placed.y - depth,
                width=placed.width,
                depth=placed.depth + depth,
            )
            return _valid(merged)

    return None


def shrink_placement_to_max_area(
    placement: RoomPlacement,
    max_area: float,
    neighbor_rects: list[Rect],
    *,
    tolerance: float = COVERAGE_TOLERANCE,
) -> RoomPlacement:
    if placement.room_id.startswith("stair-") or placement.rect.area <= max_area + tolerance:
        return placement
    cur = from_placement(placement.rect)
    capped = _best_capped_rect(cur.x, cur.y, cur.right, cur.bottom, max_area, neighbor_rects)
    return placement.model_copy(
        update={
            "rect": PlacementRect(
                x=capped.x,
                y=capped.y,
                width=capped.width,
                depth=capped.depth,
            )
        }
    )


def _best_capped_rect(
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    max_area: float,
    neighbor_rects: list[Rect],
) -> Rect:
    from solver.geometry.free_rects import subtract_rects

    full = Rect(x=x0, y=y0, width=x1 - x0, depth=y1 - y0)
    best: Rect | None = None
    best_score = -1.0
    w = max(0.0, x1 - x0)
    h = max(0.0, y1 - y0)
    candidates: list[PlacementRect] = []
    if w * h <= max_area + COVERAGE_TOLERANCE:
        return full
    if w > 0:
        depth = min(h, max_area / w)
        if depth > 0:
            candidates.append(PlacementRect(x=x0, y=y0, width=w, depth=depth))
            candidates.append(PlacementRect(x=x0, y=y1 - depth, width=w, depth=depth))
    if h > 0:
        width = min(w, max_area / h)
        if width > 0:
            candidates.append(PlacementRect(x=x0, y=y0, width=width, depth=h))
            candidates.append(PlacementRect(x=x1 - width, y=y0, width=width, depth=h))
    for cand in candidates or [PlacementRect(x=x0, y=y0, width=w, depth=h)]:
        capped = Rect(x=cand.x, y=cand.y, width=cand.width, depth=cand.depth)
        if capped.area > max_area + COVERAGE_TOLERANCE:
            continue
        leftovers = subtract_rects([full], [capped])
        score = sum(
            shared_edge_length(piece, neighbor)
            for piece in leftovers
            for neighbor in neighbor_rects
        )
        if score > best_score:
            best_score = score
            best = capped
    return best or Rect(x=x0, y=y0, width=w, depth=min(h, max_area / max(w, 1e-9)))


def rebalance_placements_to_area_bounds(
    footprint: Rect,
    placements: list[RoomPlacement],
    max_area_by_room_id: dict[str, float],
    *,
    tolerance: float = COVERAGE_TOLERANCE,
) -> list[RoomPlacement]:
    """满铺后按上限裁切超大房间，并立即将碎片转给同层尚有容量的邻接房间。"""
    from solver.geometry.free_rects import subtract_rects

    absorb_tol = max(tolerance, LAYOUT_ABSORB_TOLERANCE)
    updated = [p.model_copy(deep=True) for p in placements]
    order = sorted(
        range(len(updated)),
        key=lambda i: updated[i].rect.area
        - max_area_by_room_id.get(updated[i].room_id, float("inf")),
        reverse=True,
    )
    for i in order:
        p = updated[i]
        cap = max_area_by_room_id.get(p.room_id)
        if (
            cap is None
            or p.room_id.startswith("stair-")
            or p.rect.area <= cap + tolerance
        ):
            continue
        cur = from_placement(p.rect)
        neighbors = [
            from_placement(other.rect)
            for j, other in enumerate(updated)
            if j != i
        ]
        capped = _best_capped_rect(
            cur.x, cur.y, cur.right, cur.bottom, cap, neighbors
        )
        leftovers = subtract_rects([cur], [capped])
        updated[i] = p.model_copy(
            update={
                "rect": PlacementRect(
                    x=capped.x,
                    y=capped.y,
                    width=capped.width,
                    depth=capped.depth,
                )
            }
        )
        for piece in leftovers:
            if piece.area <= tolerance:
                continue
            best_j: int | None = None
            best_rect: Rect | None = None
            best_edge = 0.0
            for j, other in enumerate(updated):
                if i == j or other.room_id.startswith("stair-"):
                    continue
                other_cap = max_area_by_room_id.get(other.room_id)
                if other_cap is None:
                    continue
                other_cur = from_placement(other.rect)
                others = [
                    from_placement(o.rect)
                    for k, o in enumerate(updated)
                    if k not in (i, j)
                ]
                merged = try_absorb_sliver_within_area_cap(
                    other_cur,
                    piece,
                    others,
                    other_cap,
                    tolerance=absorb_tol,
                )
                if merged is None:
                    continue
                edge = shared_edge_length(other_cur, piece)
                if edge > best_edge:
                    best_j = j
                    best_rect = merged
                    best_edge = edge
            if best_j is None or best_rect is None:
                continue
            other = updated[best_j]
            updated[best_j] = other.model_copy(
                update={
                    "rect": PlacementRect(
                        x=best_rect.x,
                        y=best_rect.y,
                        width=best_rect.width,
                        depth=best_rect.depth,
                    )
                }
            )
    return fill_floor_coverage_gaps(
        footprint,
        updated,
        tolerance=absorb_tol,
        max_area_by_room_id=max_area_by_room_id,
    )


def finalize_area_bounds(
    footprint: Rect,
    placements: list[RoomPlacement],
    max_area_by_room_id: dict[str, float],
    *,
    tolerance: float = COVERAGE_TOLERANCE,
) -> list[RoomPlacement]:
    """满铺后裁切超上限房间，再在剩余容量内二次填缝。"""
    return rebalance_placements_to_area_bounds(
        footprint,
        placements,
        max_area_by_room_id,
        tolerance=tolerance,
    )


def clip_placement_to_max_area(
    placement: RoomPlacement,
    max_area: float,
    *,
    tolerance: float = COVERAGE_TOLERANCE,
) -> RoomPlacement:
    if placement.rect.area <= max_area + tolerance:
        return placement
    rect = placement.rect
    if rect.width > 0:
        depth = min(rect.depth, max_area / rect.width)
        if depth * rect.width <= max_area + tolerance:
            return placement.model_copy(
                update={"rect": rect.model_copy(update={"depth": depth})}
            )
    if rect.depth > 0:
        width = min(rect.width, max_area / rect.depth)
        return placement.model_copy(
            update={"rect": rect.model_copy(update={"width": width})}
        )
    return placement


def enforce_area_bounds_with_refill(
    footprint: Rect,
    placements: list[RoomPlacement],
    max_area_by_room_id: dict[str, float],
    *,
    tolerance: float = COVERAGE_TOLERANCE,
) -> list[RoomPlacement]:
    """先满铺，再裁切超上限房间，最后在剩余容量内二次填缝。"""
    filled = fill_floor_coverage_gaps(footprint, placements, tolerance=tolerance)
    clipped = [
        clip_placement_to_max_area(
            p,
            max_area_by_room_id[p.room_id],
            tolerance=tolerance,
        )
        if p.room_id in max_area_by_room_id and not p.room_id.startswith("stair-")
        else p
        for p in filled
    ]
    return fill_floor_coverage_gaps(
        footprint,
        clipped,
        tolerance=tolerance,
        max_area_by_room_id=max_area_by_room_id,
    )


def clip_small_area_overruns(
    placements: list[RoomPlacement],
    max_area_by_room_id: dict[str, float],
    *,
    tolerance: float = 1.0,
) -> list[RoomPlacement]:
    """裁切轻微超出上限的浮点误差（不用于大幅缩房）。"""
    clipped: list[RoomPlacement] = []
    for p in placements:
        cap = max_area_by_room_id.get(p.room_id)
        if (
            cap is None
            or p.room_id.startswith("stair-")
            or p.rect.area <= cap + COVERAGE_TOLERANCE
        ):
            clipped.append(p)
            continue
        overrun = p.rect.area - cap
        if overrun > tolerance:
            clipped.append(p)
            continue
        clipped.append(clip_placement_to_max_area(p, cap))
    return clipped


def _donor_relation(
    receiver: Rect, donor: Rect, *, tolerance: float = 1e-6
) -> tuple[str, float] | None:
    """donor 相对 receiver 的邻接方向，及共享边长度。"""
    x_overlap = min(receiver.right, donor.right) - max(receiver.left, donor.left)
    y_overlap = min(receiver.bottom, donor.bottom) - max(receiver.top, donor.top)
    if abs(donor.bottom - receiver.top) <= tolerance and x_overlap > tolerance:
        return ("north", x_overlap)
    if abs(donor.top - receiver.bottom) <= tolerance and x_overlap > tolerance:
        return ("south", x_overlap)
    if abs(donor.right - receiver.left) <= tolerance and y_overlap > tolerance:
        return ("west", y_overlap)
    if abs(donor.left - receiver.right) <= tolerance and y_overlap > tolerance:
        return ("east", y_overlap)
    return None


def _cede_along_shared_edge(
    receiver: RoomPlacement,
    donor: RoomPlacement,
    direction: str,
    delta: float,
) -> tuple[RoomPlacement, RoomPlacement]:
    ru, du = receiver.rect, donor.rect
    if direction == "north":
        new_r = ru.model_copy(update={"y": ru.y - delta, "depth": ru.depth + delta})
        new_d = du.model_copy(update={"depth": du.depth - delta})
    elif direction == "south":
        new_r = ru.model_copy(update={"depth": ru.depth + delta})
        new_d = du.model_copy(update={"y": du.y + delta, "depth": du.depth - delta})
    elif direction == "west":
        new_r = ru.model_copy(update={"x": ru.x - delta, "width": ru.width + delta})
        new_d = du.model_copy(update={"width": du.width - delta})
    else:
        new_r = ru.model_copy(update={"width": ru.width + delta})
        new_d = du.model_copy(update={"x": du.x + delta, "width": du.width - delta})
    return (
        receiver.model_copy(update={"rect": new_r}),
        donor.model_copy(update={"rect": new_d}),
    )


def grow_rooms_to_min_area(
    footprint: Rect,
    placements: list[RoomPlacement],
    min_area_by_room_id: dict[str, float],
    max_area_by_room_id: dict[str, float],
    *,
    tolerance: float = COVERAGE_TOLERANCE,
) -> list[RoomPlacement]:
    """从已超下限的邻接房间（或走廊）匀面积给低于 min_area 的 program 房间。"""
    min_dim = 0.05
    updated = [p.model_copy(deep=True) for p in placements]
    for _ in range(max(4, len(updated) * 4)):
        progress = False
        for i, recv in enumerate(updated):
            if is_fixed_void_placement(recv.room_id) or recv.room_id.startswith("circ-"):
                continue
            lo = min_area_by_room_id.get(recv.room_id)
            if lo is None:
                continue
            deficit = lo - recv.rect.area
            if deficit <= tolerance:
                continue
            hi = max_area_by_room_id.get(recv.room_id, float("inf"))
            headroom = hi - recv.rect.area
            if headroom <= tolerance:
                continue
            recv_rect = from_placement(recv.rect)
            best: tuple[float, int, str, float, float] | None = None
            for j, donor in enumerate(updated):
                if i == j or is_fixed_void_placement(donor.room_id):
                    continue
                donor_min = min_area_by_room_id.get(donor.room_id, 0.0)
                spare = donor.rect.area - donor_min
                if spare <= tolerance:
                    continue
                donor_r = from_placement(donor.rect)
                donor_prior_ar = _rect_aspect_ratio(donor_r)
                rel = _donor_relation(recv_rect, donor_r, tolerance=tolerance)
                if rel is None:
                    continue
                direction, overlap = rel
                donor_edge = (
                    donor_r.width if direction in ("north", "south") else donor_r.depth
                )
                if overlap <= tolerance or donor_edge <= tolerance:
                    continue
                # 扩出的条带必须落在 donor 范围内，否则会切进楼梯或其他房间
                if direction in ("north", "south"):
                    if (
                        recv_rect.left < donor_r.left - tolerance
                        or recv_rect.right > donor_r.right + tolerance
                    ):
                        continue
                elif (
                    recv_rect.top < donor_r.top - tolerance
                    or recv_rect.bottom > donor_r.bottom + tolerance
                ):
                    continue
                size_limit = (
                    donor_r.depth - min_dim
                    if direction in ("north", "south")
                    else donor_r.width - min_dim
                )
                delta = min(
                    spare / donor_edge,
                    size_limit,
                    deficit / overlap,
                    headroom / overlap,
                )
                if delta <= tolerance:
                    continue
                if best is None or spare > best[0]:
                    best = (spare, j, direction, delta, donor_prior_ar)
            if best is None:
                continue
            _, j, direction, delta, donor_prior_ar = best
            donor_before = from_placement(updated[j].rect)
            new_recv, new_donor = _cede_along_shared_edge(
                updated[i], updated[j], direction, delta
            )
            if min(new_recv.rect.width, new_recv.rect.depth) <= tolerance:
                continue
            if min(new_donor.rect.width, new_donor.rect.depth) <= tolerance:
                continue
            if not _merged_respects_aspect_cap(
                new_recv.room_id, from_placement(new_recv.rect)
            ):
                continue
            if not _donor_cede_respects_aspect_cap(
                new_donor.room_id,
                from_placement(new_donor.rect),
                donor_prior_ar,
                cede_direction=direction,
                donor_before=donor_before,
            ):
                continue
            new_recv_r = from_placement(new_recv.rect)
            new_donor_r = from_placement(new_donor.rect)
            overlaps = False
            for k, other in enumerate(updated):
                if k in (i, j):
                    continue
                other_r = from_placement(other.rect)
                if intersects(new_recv_r, other_r) or intersects(new_donor_r, other_r):
                    overlaps = True
                    break
            if overlaps:
                continue
            updated[i] = new_recv
            updated[j] = new_donor
            progress = True
            break
        if not progress:
            break
        updated = [
            p
            for p in updated
            if not (p.room_id.startswith("circ-") and p.rect.area <= tolerance)
        ]
        updated = fill_floor_coverage_gaps(
            footprint,
            updated,
            tolerance=tolerance,
            max_area_by_room_id=max_area_by_room_id,
            min_area_by_room_id=min_area_by_room_id,
        )
    return updated


def fill_floor_coverage_gaps(
    footprint: Rect,
    placements: list[RoomPlacement],
    *,
    tolerance: float = COVERAGE_TOLERANCE,
    max_iterations: int | None = None,
    max_area_by_room_id: dict[str, float] | None = None,
    min_area_by_room_id: dict[str, float] | None = None,
    extra_gaps: list[Rect] | None = None,
) -> list[RoomPlacement]:
    """把 footprint 内未被 placements 覆盖的碎片并入邻接房间（含楼梯）。"""
    from solver.geometry.free_rects import subtract_rects

    if max_iterations is None:
        max_iterations = len(placements) * 8 + 8

    updated = [p.model_copy(deep=True) for p in placements]
    pending_extra = list(extra_gaps) if extra_gaps else []
    for _ in range(max_iterations):
        gaps = subtract_rects(
            [footprint],
            [from_placement(p.rect) for p in updated],
        )
        if pending_extra:
            gaps.extend(pending_extra)
            pending_extra.clear()
        gaps = [g for g in gaps if g.area > tolerance]
        if not gaps:
            return updated

        gaps.sort(key=lambda g: g.area, reverse=True)
        fixed_indices = [
            i for i, p in enumerate(updated) if is_fixed_void_placement(p.room_id)
        ]
        program_indices = [
            i for i in range(len(updated)) if i not in fixed_indices
        ]

        def remaining_capacity(i: int) -> float:
            if max_area_by_room_id is None:
                return float("inf")
            cap = max_area_by_room_id.get(updated[i].room_id)
            if cap is None:
                return float("inf")
            return max(0.0, cap - updated[i].rect.area)

        def min_deficit(i: int) -> float:
            if min_area_by_room_id is None:
                return 0.0
            lo = min_area_by_room_id.get(updated[i].room_id)
            if lo is None:
                return 0.0
            return max(0.0, lo - updated[i].rect.area)

        def try_absorb_into(
            indices: list[int], gap: Rect
        ) -> tuple[int, Rect] | None:
            best_idx: int | None = None
            best_rect: Rect | None = None
            best_edge = 0.0
            ordered = sorted(
                indices,
                key=lambda idx: (min_deficit(idx), remaining_capacity(idx)),
                reverse=True,
            )
            for i in ordered:
                p = updated[i]
                if remaining_capacity(i) <= tolerance:
                    continue
                cur = from_placement(p.rect)
                others = [
                    from_placement(other.rect)
                    for j, other in enumerate(updated)
                    if j != i
                ]
                cap = (
                    max_area_by_room_id.get(p.room_id)
                    if max_area_by_room_id is not None
                    else None
                )
                if cap is not None:
                    merged = try_absorb_sliver_within_area_cap(
                        cur,
                        gap,
                        others,
                        cap,
                        tolerance=max(tolerance, LAYOUT_ABSORB_TOLERANCE),
                    )
                else:
                    merged = try_absorb_sliver_without_overlap(
                        cur, gap, others, tolerance=tolerance
                    )
                if merged is None:
                    if cap is not None and cap - cur.area > tolerance:
                        merged_rect = merge_adjacent_rects(cur, gap)
                        if (
                            merged_rect is not None
                            and merged_rect.area <= cap + tolerance
                        ):
                            overlap = False
                            for other in others:
                                inter = intersection(merged_rect, other)
                                if inter is not None and inter.area > tolerance:
                                    overlap = True
                                    break
                            if not overlap:
                                merged = merged_rect
                if merged is None:
                    continue
                if not _merged_respects_aspect_cap(p.room_id, merged):
                    continue
                edge = shared_edge_length(cur, gap)
                if edge > best_edge:
                    best_idx = i
                    best_rect = merged
                    best_edge = edge
            if best_idx is None or best_rect is None:
                return None
            return best_idx, best_rect

        # 楼梯核尺寸固定；低于 min_area 的房间优先吸收碎片
        undersized = [i for i in program_indices if min_deficit(i) > tolerance]
        progress = False
        for gap in gaps:
            found = try_absorb_into(undersized, gap) if undersized else None
            if found is None:
                found = try_absorb_into(program_indices, gap)
            if found is None:
                continue
            best_idx, best_rect = found
            p = updated[best_idx]
            updated[best_idx] = p.model_copy(
                update={
                    "rect": p.rect.model_copy(
                        update={
                            "x": best_rect.x,
                            "y": best_rect.y,
                            "width": best_rect.width,
                            "depth": best_rect.depth,
                        }
                    )
                }
            )
            progress = True
            break

        if not progress:
            return updated
    return updated


def _is_circulation_network_member(
    placement: RoomPlacement,
    entry_room_ids: frozenset[str],
) -> bool:
    """现有循环空间：走廊 / 楼梯 / 入口锚点房间。"""
    if placement.room_id.startswith("stair-"):
        return True
    if (placement.category or "").lower() == "circulation":
        return True
    return placement.room_id in entry_room_ids


def _has_direct_circulation_neighbor(
    private: RoomPlacement,
    placements: list[RoomPlacement],
    entry_room_ids: frozenset[str],
    *,
    min_length: float = 0.05,
) -> bool:
    from solver.topology.doors import shared_boundary_between

    for other in placements:
        if other.room_id == private.room_id:
            continue
        if not _is_circulation_network_member(other, entry_room_ids):
            continue
        if shared_boundary_between(private, other, min_length=min_length) is not None:
            return True
    return False


def _is_meaningful_circulation_placement(
    placement: RoomPlacement,
    *,
    min_corridor_width: float,
) -> bool:
    """排除切分边角料级走廊碎片，避免误判为已有走廊邻接。"""
    if placement.room_id.startswith("stair-"):
        return True
    if (placement.category or "").lower() != "circulation":
        return False
    short = min(placement.rect.width, placement.rect.depth)
    return short + 1e-9 >= min_corridor_width * 1.5


def _has_meaningful_circulation_neighbor(
    private: RoomPlacement,
    placements: list[RoomPlacement],
    entry_room_ids: frozenset[str],
    *,
    min_corridor_width: float,
) -> bool:
    """
    与足够宽的走廊条共边才算有走廊邻接。

    仅贴楼梯/入口不算——楼梯核邻接仍可能被迫穿其他卧室到达。
    """
    from solver.topology.doors import shared_boundary_between

    min_len = min_corridor_width * 1.5
    for other in placements:
        if other.room_id == private.room_id:
            continue
        if not other.room_id.startswith("circ-"):
            continue
        if not _is_meaningful_circulation_placement(
            other, min_corridor_width=min_corridor_width
        ):
            continue
        if shared_boundary_between(private, other, min_length=min_len) is not None:
            return True
    return False


def _non_private_geometric_neighbors(
    private: RoomPlacement,
    placements: list[RoomPlacement],
    *,
    min_length: float = 0.05,
) -> list[RoomPlacement]:
    from solver.topology.doors import shared_boundary_between

    neighbors: list[RoomPlacement] = []
    for other in placements:
        if other.room_id == private.room_id:
            continue
        if (other.category or "").lower() == "private":
            continue
        if shared_boundary_between(private, other, min_length=min_length) is not None:
            neighbors.append(other)
    return neighbors


def _corridor_touches_circulation_network(
    corridor: RoomPlacement,
    placements: list[RoomPlacement],
    entry_room_ids: frozenset[str],
    *,
    min_length: float = 0.05,
) -> bool:
    from solver.topology.doors import shared_boundary_between

    for other in placements:
        if not _is_circulation_network_member(other, entry_room_ids):
            continue
        if shared_boundary_between(corridor, other, min_length=min_length) is not None:
            return True
    return False


def _corridor_links_private_to_circulation(
    private: RoomPlacement,
    corridor: RoomPlacement,
    placements: list[RoomPlacement],
    entry_room_ids: frozenset[str],
    *,
    min_length: float = 0.05,
) -> bool:
    """新走廊条直接贴循环空间，或 private 经共墙图（含新走廊）可达循环空间。"""
    from collections import deque
    from solver.topology.doors import shared_boundary_between

    if _corridor_touches_circulation_network(
        corridor, placements, entry_room_ids, min_length=min_length
    ):
        return True

    nodes = list(placements) + [corridor]
    by_id = {p.room_id: p for p in nodes}
    start = private.room_id
    seen: set[str] = {start}
    q: deque[str] = deque([start])
    while q:
        cur = q.popleft()
        p = by_id[cur]
        if (
            cur != start
            and cur != corridor.room_id
            and _is_circulation_network_member(p, entry_room_ids)
        ):
            return True
        for other in nodes:
            if other.room_id in seen:
                continue
            if shared_boundary_between(p, other, min_length=min_length) is None:
                continue
            seen.add(other.room_id)
            q.append(other.room_id)
    return False


def _try_corridor_strip_from_neighbor(
    private: RoomPlacement,
    neighbor: RoomPlacement,
    boundary: object,
    *,
    corridor_width: float,
    min_area_by_room_id: dict[str, float],
    tolerance: float = COVERAGE_TOLERANCE,
) -> tuple[RoomPlacement, RoomPlacement] | None:
    """从 neighbor 沿与 private 的共边切出走廊条；失败返回 None。"""
    from packages.schema.layout import PlacementSource
    from solver.topology.doors import SharedBoundary

    assert isinstance(boundary, SharedBoundary)
    rn_rect = from_placement(neighbor.rect)
    rn = neighbor.rect
    thr = DEFAULT_WEIGHTS.aspect_ratio_threshold + 1e-6

    if boundary.axis == "y":
        y0, y1 = rn_rect.top, rn_rect.bottom
        span = y1 - y0
        if span + 1e-9 < corridor_width * 1.5:
            return None
        if abs(rn_rect.left - boundary.x0) <= 1e-6:
            if rn.width < corridor_width + tolerance:
                return None
            corr = PlacementRect(x=rn.x, y=y0, width=corridor_width, depth=span)
            new_r = PlacementRect(
                x=rn.x + corridor_width,
                y=rn.y,
                width=rn.width - corridor_width,
                depth=rn.depth,
            )
        elif abs(rn_rect.right - boundary.x0) <= 1e-6:
            if rn.width < corridor_width + tolerance:
                return None
            corr = PlacementRect(
                x=rn.x + rn.width - corridor_width,
                y=y0,
                width=corridor_width,
                depth=span,
            )
            new_r = PlacementRect(
                x=rn.x,
                y=rn.y,
                width=rn.width - corridor_width,
                depth=rn.depth,
            )
        else:
            return None
    else:
        x0, x1 = rn_rect.left, rn_rect.right
        span = x1 - x0
        if span + 1e-9 < corridor_width * 1.5:
            return None
        if abs(rn_rect.top - boundary.y0) <= 1e-6:
            if rn.depth < corridor_width + tolerance:
                return None
            corr = PlacementRect(x=x0, y=rn.y, width=span, depth=corridor_width)
            new_r = PlacementRect(
                x=rn.x,
                y=rn.y + corridor_width,
                width=rn.width,
                depth=rn.depth - corridor_width,
            )
        elif abs(rn_rect.bottom - boundary.y0) <= 1e-6:
            if rn.depth < corridor_width + tolerance:
                return None
            corr = PlacementRect(
                x=x0,
                y=rn.y + rn.depth - corridor_width,
                width=span,
                depth=corridor_width,
            )
            new_r = PlacementRect(
                x=rn.x,
                y=rn.y,
                width=rn.width,
                depth=rn.depth - corridor_width,
            )
        else:
            return None

    if _rect_aspect_ratio(from_placement(new_r)) > thr:
        return None
    lo = min_area_by_room_id.get(neighbor.room_id)
    if lo is not None and new_r.area + tolerance < lo:
        return None

    corridor = RoomPlacement(
        room_id="circ-pending",
        floor_id=neighbor.floor_id,
        rect=corr,
        source=PlacementSource.GENERATED,
        name="走廊",
        category="circulation",
    )
    shrunk = neighbor.model_copy(update={"rect": new_r})
    return shrunk, corridor


def _floor_repair_maintains_constraints(
    footprint: Rect,
    placements: list[RoomPlacement],
    trial_placements: list[RoomPlacement],
    floor_id: str,
    min_area_by_room_id: dict[str, float],
    *,
    tolerance: float = COVERAGE_TOLERANCE,
) -> bool:
    """修补后：无重叠、楼层覆盖率不恶化（donor 面积/长宽比在 _try 中已校验）。"""
    _ = min_area_by_room_id
    if placement_overlap_violations(
        floor_id=floor_id, placements=trial_placements, tolerance=tolerance
    ):
        return False
    footprint_area = footprint.width * footprint.depth
    gap_before = floor_coverage_gap(footprint_area, placements)
    gap_after = floor_coverage_gap(footprint_area, trial_placements)
    if abs(gap_after - gap_before) > tolerance:
        return False
    return True


def _floor_placements_geom_changed(
    before: list[RoomPlacement],
    after: list[RoomPlacement],
) -> bool:
    if len(before) != len(after):
        return True
    by_before = {p.room_id: p.rect for p in before}
    for p in after:
        prev = by_before.get(p.room_id)
        if prev is None or prev != p.rect:
            return True
    return False


def improve_private_room_corridor_access(
    footprint: Rect,
    placements: list[RoomPlacement],
    floor_id: str,
    *,
    min_corridor_width: float = 0.9,
    min_area_by_room_id: dict[str, float] | None = None,
    entry_room_ids: frozenset[str] | None = None,
    tolerance: float = COVERAGE_TOLERANCE,
) -> list[RoomPlacement]:
    """
    对无走廊邻接的 private 房间，尝试从非 private 邻居借边生成走廊条（尽力而为，单轮）。

    见 ADR-011 / docs/proposals/corridor-access-repair.md。
    """
    _ = footprint  # 与管线其它步骤签名一致，本步不扩 footprint
    from solver.topology.doors import shared_boundary_between

    min_areas = min_area_by_room_id or {}
    entry_ids = entry_room_ids or frozenset()
    updated = [p.model_copy(deep=True) for p in placements]
    by_id = {p.room_id: p for p in updated}

    needs_repair = [
        p.room_id
        for p in updated
        if (p.category or "").lower() == "private"
        and not _has_meaningful_circulation_neighbor(
            p, updated, entry_ids, min_corridor_width=min_corridor_width
        )
    ]

    circ_seq = sum(1 for p in updated if p.room_id.startswith(f"circ-{floor_id}-"))

    for priv_id in needs_repair:
        priv = by_id[priv_id]
        neighbors = _non_private_geometric_neighbors(priv, updated)
        repaired = False
        for neighbor in neighbors:
            boundary = shared_boundary_between(
                priv,
                neighbor,
                min_length=min_corridor_width * 1.5,
            )
            if boundary is None:
                continue
            trial = _try_corridor_strip_from_neighbor(
                priv,
                neighbor,
                boundary,
                corridor_width=min_corridor_width,
                min_area_by_room_id=min_areas,
                tolerance=tolerance,
            )
            if trial is None:
                continue
            shrunk_neighbor, corridor = trial
            if not _corridor_links_private_to_circulation(
                priv, corridor, updated, entry_ids
            ):
                continue
            if shared_boundary_between(priv, corridor, min_length=0.05) is None:
                continue

            trial_placements: list[RoomPlacement] = []
            for idx, p in enumerate(updated):
                if p.room_id == neighbor.room_id:
                    trial_placements.append(shrunk_neighbor)
                else:
                    trial_placements.append(p)
            trial_placements.append(corridor)
            if not _floor_repair_maintains_constraints(
                footprint,
                updated,
                trial_placements,
                floor_id,
                min_areas,
                tolerance=tolerance,
            ):
                continue

            for idx, p in enumerate(updated):
                if p.room_id == neighbor.room_id:
                    updated[idx] = shrunk_neighbor
                    break
            corridor = corridor.model_copy(
                update={"room_id": f"circ-{floor_id}-{circ_seq}"}
            )
            circ_seq += 1
            updated.append(corridor)
            by_id[shrunk_neighbor.room_id] = shrunk_neighbor
            by_id[corridor.room_id] = corridor
            repaired = True
            break
        if repaired:
            break

    return updated


def apply_corridor_access_repair_if_safe(
    program: DesignProgram,
    candidate: "LayoutCandidate",
    footprint: Rect,
    *,
    min_area_by_room_id: dict[str, float] | None = None,
    entry_room_ids: frozenset[str] | None = None,
) -> "LayoutCandidate":
    """
    在完整候选上尝试走廊邻接修补；仅当修补后仍通过 checker 时才采纳。

    避免在 per-floor 管线中盲目借边，把原本 valid 的候选打成 invalid。
    """
    from solver.constraints.checker_impl import DefaultConstraintChecker

    checker = DefaultConstraintChecker()
    if not checker.check(program, candidate.model_copy(deep=True)).valid:
        return candidate

    min_areas = min_area_by_room_id or {
        r.id: r.resolved_min_area() for r in program.rooms
    }
    entry_ids = entry_room_ids or frozenset()
    result = candidate

    for floor_idx, floor in enumerate(candidate.floors):
        improved = improve_private_room_corridor_access(
            footprint,
            list(floor.placements),
            floor.floor_id,
            min_area_by_room_id=min_areas,
            entry_room_ids=entry_ids,
        )
        if not _floor_placements_geom_changed(floor.placements, improved):
            continue
        improved = resolve_placement_overlaps(improved)
        new_floors = [fl.model_copy(deep=True) for fl in result.floors]
        new_floors[floor_idx] = floor.model_copy(update={"placements": improved})
        trial = result.model_copy(deep=True, update={"floors": new_floors})
        if checker.check(program, trial).valid:
            result = trial

    return result


def assign_residual_gaps_as_circulation(
    footprint: Rect,
    placements: list[RoomPlacement],
    floor_id: str,
    *,
    tolerance: float = COVERAGE_TOLERANCE,
) -> list[RoomPlacement]:
    """
    将 program 房间无法吸收的剩余碎片标为 generated circulation。

    典型场景：楼梯核邻接区无法在不重叠的前提下扩入 program 房间。
  """
    from packages.schema.layout import PlacementSource
    from solver.geometry.free_rects import subtract_rects

    updated = [p.model_copy(deep=True) for p in placements]
    gaps = subtract_rects(
        [footprint],
        [from_placement(p.rect) for p in updated],
    )
    gaps = [g for g in gaps if g.area > tolerance]
    if not gaps:
        return updated

    residual_count = sum(
        1 for p in updated if p.room_id.startswith(f"circ-{floor_id}-")
    )
    for i, gap in enumerate(gaps):
        updated.append(
            RoomPlacement(
                room_id=f"circ-{floor_id}-{residual_count + i}",
                floor_id=floor_id,
                rect=PlacementRect(
                    x=gap.x,
                    y=gap.y,
                    width=gap.width,
                    depth=gap.depth,
                ),
                source=PlacementSource.GENERATED,
                name="走廊",
                category="circulation",
            )
        )
    return updated


def expand_rect_to_cover_pack_gaps(
    pack_rects: list[Rect],
    placed: list[Rect],
    *,
    tolerance: float = COVERAGE_TOLERANCE,
    max_iterations: int | None = None,
) -> list[Rect]:
    """把已放置矩形沿邻接方向扩张，直至铺满 pack_rects 或无法继续。"""
    if not pack_rects:
        return placed
    if max_iterations is None:
        max_iterations = len(pack_rects) * max(len(placed), 1) + 4

    rects = list(placed)
    for _ in range(max_iterations):
        gap = pack_coverage_gap(pack_rects, rects)
        if gap <= tolerance:
            return rects
        best_idx: int | None = None
        best_merged: Rect | None = None
        best_edge = 0.0
        for pr in pack_rects:
            covered = sum(
                (intersection(pr, r).area if intersection(pr, r) is not None else 0.0)
                for r in rects
            )
            if pr.area - covered <= tolerance:
                continue
            for i, cur in enumerate(rects):
                edge = shared_edge_length(cur, pr)
                if edge <= best_edge:
                    continue
                merged = merge_adjacent_rects(cur, pr)
                if merged is None:
                    continue
                best_idx = i
                best_merged = merged
                best_edge = edge
        if best_idx is None or best_merged is None:
            return rects
        rects[best_idx] = best_merged
    return rects
