"""楼层平面覆盖率 — 可建面积须被 placements 完全铺满（含楼梯）。"""

from __future__ import annotations

from packages.schema.layout import RoomPlacement, Violation
from packages.schema.program import DesignProgram
from solver.geometry.rect import Rect, from_placement, intersection, intersects, shared_edge_length, touches

COVERAGE_TOLERANCE = 1e-6


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


def fill_floor_coverage_gaps(
    footprint: Rect,
    placements: list[RoomPlacement],
    *,
    tolerance: float = COVERAGE_TOLERANCE,
    max_iterations: int | None = None,
) -> list[RoomPlacement]:
    """把 footprint 内未被 placements 覆盖的碎片并入邻接房间（含楼梯）。"""
    from solver.geometry.free_rects import subtract_rects

    if max_iterations is None:
        max_iterations = len(placements) * 8 + 8

    updated = [p.model_copy(deep=True) for p in placements]
    for _ in range(max_iterations):
        gaps = subtract_rects(
            [footprint],
            [from_placement(p.rect) for p in updated],
        )
        gaps = [g for g in gaps if g.area > tolerance]
        if not gaps:
            return updated

        gap = gaps[0]
        stair_indices = [
            i for i, p in enumerate(updated) if p.room_id.startswith("stair-")
        ]
        candidate_indices = stair_indices + [
            i for i in range(len(updated)) if i not in stair_indices
        ]
        best_idx: int | None = None
        best_rect: Rect | None = None
        best_edge = 0.0
        for i in candidate_indices:
            p = updated[i]
            cur = from_placement(p.rect)
            others = [
                from_placement(other.rect)
                for j, other in enumerate(updated)
                if j != i
            ]
            merged = try_absorb_sliver_without_overlap(
                cur, gap, others, tolerance=tolerance
            )
            if merged is None:
                continue
            edge = shared_edge_length(cur, gap)
            if edge > best_edge:
                best_idx = i
                best_rect = merged
                best_edge = edge
        if best_idx is None or best_rect is None:
            return updated
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
