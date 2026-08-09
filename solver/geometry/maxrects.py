"""Maximal Rectangles（MaxRect）自由矩形维护 — Phase 8.0-B。

确定性；与 Guillotine 递归二分切分不同：在自由矩形列表上放置后做 maximal 更新。
"""

from __future__ import annotations

import math
import random

from solver.geometry.free_rects import subtract_rects
from solver.geometry.rect import Rect, contains
from solver.geometry.snap import snap_value


def prune_free_list(free_rects: list[Rect], *, eps: float = 1e-9) -> list[Rect]:
    """去掉被其他自由矩形完全包含的项（MaxRects prune）。"""
    kept: list[Rect] = []
    for i, a in enumerate(free_rects):
        if a.width <= eps or a.depth <= eps:
            continue
        dominated = False
        for j, b in enumerate(free_rects):
            if i == j:
                continue
            if contains(b, a) and (
                b.width > a.width + eps
                or b.depth > a.depth + eps
                or b.area > a.area + eps
            ):
                dominated = True
                break
            # 完全相等：保留前者
            if (
                abs(a.x - b.x) <= eps
                and abs(a.y - b.y) <= eps
                and abs(a.width - b.width) <= eps
                and abs(a.depth - b.depth) <= eps
                and j < i
            ):
                dominated = True
                break
        if not dominated:
            kept.append(a)
    return kept


def update_free_rects(free_rects: list[Rect], used: Rect) -> list[Rect]:
    """放置 used 后更新自由矩形集。"""
    return prune_free_list(subtract_rects(free_rects, [used]))


def _bssf_score(free: Rect, width: float, depth: float) -> tuple[float, float] | None:
    """Best Short Side Fit：短边剩余越小越好。"""
    if width > free.width + 1e-9 or depth > free.depth + 1e-9:
        return None
    leftover_w = free.width - width
    leftover_d = free.depth - depth
    short = min(leftover_w, leftover_d)
    long = max(leftover_w, leftover_d)
    return (short, long)


def candidate_sizes(
    target_area: float,
    *,
    free: Rect,
    min_width: float,
    module: float,
) -> list[tuple[float, float]]:
    """在 free 内生成若干 (width, depth) 候选，面积贴近 target_area。"""
    target_area = max(target_area, module * module)
    aspects = (1.0, 1.25, 1.5, 1.75, 0.8, 0.67, 2.0, 0.5)
    out: list[tuple[float, float]] = []
    seen: set[tuple[float, float]] = set()

    def _add(w: float, d: float) -> None:
        w = snap_value(max(w, module), module)
        d = snap_value(max(d, module), module)
        w = min(w, free.width)
        d = min(d, free.depth)
        if w + 1e-9 < min_width and free.width + 1e-9 >= min_width:
            w = snap_value(min_width, module)
            w = min(w, free.width)
            d = snap_value(max(target_area / max(w, module), module), module)
            d = min(d, free.depth)
        if w < module - 1e-9 or d < module - 1e-9:
            return
        if w > free.width + 1e-9 or d > free.depth + 1e-9:
            return
        key = (round(w, 4), round(d, 4))
        if key not in seen:
            seen.add(key)
            out.append((w, d))

    for ar in aspects:
        w = math.sqrt(target_area * ar)
        d = target_area / max(w, 1e-9)
        _add(w, d)
        _add(d, w)

    # 贴边尝试：占满 free 一边
    if free.width >= min_width:
        w = free.width
        d = snap_value(target_area / max(w, module), module)
        _add(w, min(d, free.depth))
    if free.depth >= module:
        d = free.depth
        w = snap_value(target_area / max(d, module), module)
        _add(min(w, free.width), d)

    if not out:
        _add(min(free.width, max(min_width, module)), min(free.depth, module))
    return out


def place_in_free_rects(
    free_rects: list[Rect],
    target_area: float,
    *,
    min_width: float,
    module: float,
    rng: random.Random,
    fill: bool = False,
) -> Rect | None:
    """
    BSSF 选择自由矩形与尺寸；角点由 rng 在可行角中选取（同 seed 可复现）。

    fill=True 时直接占用整个最大自由矩形（末室收口）。
    """
    if not free_rects:
        return None
    if fill:
        largest = max(free_rects, key=lambda r: (r.area, r.width, r.depth, -r.x, -r.y))
        return Rect(x=largest.x, y=largest.y, width=largest.width, depth=largest.depth)

    best: tuple[tuple[float, float], int, Rect, float, float, int] | None = None
    # key: (score_short, score_long), free_idx, free, w, d, corner_idx

    for fi, free in enumerate(free_rects):
        for w, d in candidate_sizes(
            target_area, free=free, min_width=min_width, module=module
        ):
            orients = [(w, d)]
            if abs(w - d) > 1e-9:
                orients.append((d, w))
            for ww, dd in orients:
                if ww < min_width - 1e-9 and free.width >= min_width - 1e-9:
                    continue
                score = _bssf_score(free, ww, dd)
                if score is None:
                    continue
                cand = (score, fi, free, ww, dd, 0)
                if best is None or score < best[0] or (
                    score == best[0] and (fi, ww, dd) < (best[1], best[3], best[4])
                ):
                    best = cand

    if best is None:
        # 退路：塞进能放下 min 模块的最大自由矩形一角
        fitting = [f for f in free_rects if f.width >= module and f.depth >= module]
        if not fitting:
            return None
        free = max(fitting, key=lambda r: (r.area, -r.x, -r.y))
        w = min(free.width, max(min_width, module))
        d = min(free.depth, max(module, target_area / max(w, module)))
        w = snap_value(w, module)
        d = snap_value(d, module)
        w = min(w, free.width)
        d = min(d, free.depth)
        return Rect(x=free.x, y=free.y, width=max(module, w), depth=max(module, d))

    _score, _fi, free, w, d, _ = best
    corners = [
        (free.x, free.y),
        (free.x + free.width - w, free.y),
        (free.x, free.y + free.depth - d),
        (free.x + free.width - w, free.y + free.depth - d),
    ]
    cx, cy = corners[rng.randrange(0, 4)]
    return Rect(x=cx, y=cy, width=w, depth=d)
