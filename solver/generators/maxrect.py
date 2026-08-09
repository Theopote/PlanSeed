"""MaxRect packing strategy — Phase 8.0-B LayoutGenerator。

复用 Guillotine 的 StairCore / Zone / Topology 流水线，仅替换叶子 `_layout_rooms`。
"""

from __future__ import annotations

import random

from packages.schema.layout import PlacementRect

from solver.generators.guillotine import GuillotineGenerator, _LayoutRoom
from solver.geometry.maxrects import place_in_free_rects, update_free_rects
from solver.geometry.rect import Rect
from solver.geometry.snap import snap_value
from solver.topology.plan import (
    bipartition_slicing_units,
    group_into_slicing_units,
    split_avoid_groups,
)

MAXRECT_GENERATOR_VERSION = "maxrect-v1"


class MaxRectGenerator(GuillotineGenerator):
    """Generator #2 — Maximal Rectangles leaf packing。"""

    strategy_id = "maxrect"
    generator_version = MAXRECT_GENERATOR_VERSION

    def _layout_rooms(
        self,
        rooms: list[_LayoutRoom],
        x0: float,
        y0: float,
        x1: float,
        y1: float,
        module: float,
        rng: random.Random,
        *,
        avoid_pairs=None,
        cluster_members: list[set[str]] | None = None,
    ) -> None:
        if not rooms:
            return
        if len(rooms) == 1:
            rooms[0].rect = PlacementRect(
                x=x0,
                y=y0,
                width=max(module, x1 - x0),
                depth=max(module, y1 - y0),
            )
            return

        unit_ids = group_into_slicing_units(
            [r.spec.id for r in rooms], cluster_members
        )
        # 与 Guillotine 相同：整坨 cluster 无法切开时退回无 cluster 约束
        if (
            cluster_members
            and len(unit_ids) == 1
            and len(unit_ids[0]) == len(rooms)
            and len(rooms) > 1
        ):
            self._layout_rooms(
                rooms,
                x0,
                y0,
                x1,
                y1,
                module,
                rng,
                avoid_pairs=avoid_pairs,
                cluster_members=None,
            )
            return

        # avoid 对：先做一次面积比切分，再各自 MaxRect（保留隐私分离意图）
        avoid_split = None
        if avoid_pairs:
            avoid_split = split_avoid_groups(rooms, avoid_pairs)
        if avoid_split is not None:
            group1, group2 = avoid_split
            self._bipartition_then_pack(
                group1,
                group2,
                x0,
                y0,
                x1,
                y1,
                module,
                rng,
                cluster_members=cluster_members,
            )
            return

        if cluster_members and len(unit_ids) >= 2:
            id_to = {r.spec.id: r for r in rooms}
            units = [[id_to[rid] for rid in u if rid in id_to] for u in unit_ids]
            units = [u for u in units if u]
            parted = bipartition_slicing_units(
                units, weight_of=lambda lr: lr.weight
            )
            if parted is not None:
                group1, group2 = parted
                self._bipartition_then_pack(
                    group1,
                    group2,
                    x0,
                    y0,
                    x1,
                    y1,
                    module,
                    rng,
                    cluster_members=cluster_members,
                )
                return

        self._pack_maxrect_fill(rooms, x0, y0, x1, y1, module, rng)

    def _bipartition_then_pack(
        self,
        group1: list[_LayoutRoom],
        group2: list[_LayoutRoom],
        x0: float,
        y0: float,
        x1: float,
        y1: float,
        module: float,
        rng: random.Random,
        *,
        cluster_members: list[set[str]] | None,
    ) -> None:
        area1 = sum(r.weight for r in group1) or 1.0
        area2 = sum(r.weight for r in group2) or 1.0
        width = x1 - x0
        height = y1 - y0
        frac = area1 / (area1 + area2)
        if abs(width - height) < 1e-6:
            split_horizontal = rng.random() < 0.5
        else:
            # 与 Guillotine 相反偏好：短边方向优先切，制造分布差异
            split_horizontal = width < height
        min_span = module * 2
        if split_horizontal:
            cut_x = snap_value(x0 + width * frac, module)
            cut_x = max(x0 + min_span, min(x1 - min_span, cut_x))
            self._layout_rooms(
                group1, x0, y0, cut_x, y1, module, rng, cluster_members=cluster_members
            )
            self._layout_rooms(
                group2, cut_x, y0, x1, y1, module, rng, cluster_members=cluster_members
            )
        else:
            cut_y = snap_value(y0 + height * frac, module)
            cut_y = max(y0 + min_span, min(y1 - min_span, cut_y))
            self._layout_rooms(
                group1, x0, y0, x1, cut_y, module, rng, cluster_members=cluster_members
            )
            self._layout_rooms(
                group2, x0, cut_y, x1, y1, module, rng, cluster_members=cluster_members
            )

    def _pack_maxrect_fill(
        self,
        rooms: list[_LayoutRoom],
        x0: float,
        y0: float,
        x1: float,
        y1: float,
        module: float,
        rng: random.Random,
    ) -> None:
        free: list[Rect] = [
            Rect(x=x0, y=y0, width=max(module, x1 - x0), depth=max(module, y1 - y0))
        ]
        for idx, lr in enumerate(rooms):
            is_last = idx == len(rooms) - 1
            rem_weight = sum(r.weight for r in rooms[idx:]) or 1.0
            rem_area = sum(f.area for f in free) or 1.0
            target = rem_area if is_last else rem_area * (lr.weight / rem_weight)
            min_w = lr.spec.min_width if lr.spec.min_width is not None else module * 2
            placed = place_in_free_rects(
                free,
                target,
                min_width=min_w,
                module=module,
                rng=rng,
                fill=is_last,
            )
            if placed is None:
                # 极端：铺满当前最大自由矩形
                if not free:
                    lr.rect = PlacementRect(
                        x=x0,
                        y=y0,
                        width=max(module, x1 - x0),
                        depth=max(module, y1 - y0),
                    )
                    continue
                biggest = max(free, key=lambda r: r.area)
                placed = Rect(
                    x=biggest.x,
                    y=biggest.y,
                    width=biggest.width,
                    depth=biggest.depth,
                )
            lr.rect = PlacementRect(
                x=placed.x,
                y=placed.y,
                width=max(module, placed.width),
                depth=max(module, placed.depth),
            )
            free = update_free_rects(free, placed)

        # 残余自由矩形：并入与之共享边最长的已放置房间（保持矩形）
        self._absorb_free_rects(rooms, free)

    def _absorb_free_rects(
        self,
        rooms: list[_LayoutRoom],
        free: list[Rect],
    ) -> None:
        if not free:
            return
        for fr in list(free):
            best_i = -1
            best_len = 0.0
            best_merged: PlacementRect | None = None
            for i, lr in enumerate(rooms):
                if lr.rect is None:
                    continue
                merged = _try_rect_merge(lr.rect, fr)
                if merged is None:
                    continue
                shared = _shared_edge_len(lr.rect, fr)
                if shared > best_len + 1e-9:
                    best_len = shared
                    best_i = i
                    best_merged = merged
            if best_i >= 0 and best_merged is not None:
                rooms[best_i].rect = best_merged


def _shared_edge_len(a: PlacementRect, b: Rect, *, tol: float = 1e-6) -> float:
    length = 0.0
    for x_edge in (a.x, a.x + a.width):
        if abs(x_edge - b.left) <= tol or abs(x_edge - b.right) <= tol:
            overlap = min(a.y + a.depth, b.bottom) - max(a.y, b.top)
            if overlap > tol:
                length = max(length, overlap)
    for y_edge in (a.y, a.y + a.depth):
        if abs(y_edge - b.top) <= tol or abs(y_edge - b.bottom) <= tol:
            overlap = min(a.x + a.width, b.right) - max(a.x, b.left)
            if overlap > tol:
                length = max(length, overlap)
    return length


def _try_rect_merge(room: PlacementRect, free: Rect) -> PlacementRect | None:
    """若 room∪free 仍为轴对齐矩形则返回合并结果。"""
    x0 = min(room.x, free.x)
    y0 = min(room.y, free.y)
    x1 = max(room.x + room.width, free.right)
    y1 = max(room.y + room.depth, free.bottom)
    w = x1 - x0
    d = y1 - y0
    # 面积相等 ⇒ 无洞无重叠浪费（允许贴边重叠 0）
    union_area = w * d
    sum_area = room.width * room.depth + free.area
    # 若仅贴边不重叠：union == sum；若重叠一点则 union < sum
    overlap_x = max(
        0.0,
        min(room.x + room.width, free.right) - max(room.x, free.x),
    )
    overlap_y = max(
        0.0,
        min(room.y + room.depth, free.bottom) - max(room.y, free.y),
    )
    inter = overlap_x * overlap_y
    if abs(union_area - (sum_area - inter)) > 1e-4:
        return None
    # 必须是「并起来仍是矩形」：用覆盖检查
    # room 与 free 的 AABB 面积 == union，且两者都在 AABB 内（恒真）且无 L 形
    # L 形判定：union 面积 > room+free-inter
    if union_area > sum_area - inter + 1e-4:
        return None
    # 额外：两边在某一轴完全对齐延伸
    aligned = (
        abs(room.x - free.x) <= 1e-6
        and abs(room.width - free.width) <= 1e-6
    ) or (
        abs(room.y - free.y) <= 1e-6
        and abs(room.depth - free.depth) <= 1e-6
    )
    if not aligned and inter <= 1e-9:
        # 仅角点接触不可合
        if _shared_edge_len(room, free) <= 1e-6:
            return None
        # 边接触但宽高都不对齐 → L 形
        return None
    if not aligned and inter > 1e-9:
        return None
    return PlacementRect(x=x0, y=y0, width=w, depth=d)

