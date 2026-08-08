"""矩形挖洞 → 剩余正交矩形分解。"""

from __future__ import annotations

from solver.geometry.rect import Rect


def subtract_rect(outer: Rect, hole: Rect) -> list[Rect]:
    """
    从 outer 中挖去 hole，返回互不重叠的剩余轴对齐矩形（最多 4 块）。

    hole 与 outer 不相交时返回 [outer]；hole 覆盖 outer 时返回 []。
    """
    # 裁剪 hole 到 outer
    x0 = max(outer.left, hole.left)
    y0 = max(outer.top, hole.top)
    x1 = min(outer.right, hole.right)
    y1 = min(outer.bottom, hole.bottom)

    if x1 <= x0 + 1e-9 or y1 <= y0 + 1e-9:
        return [outer]

    parts: list[Rect] = []
    if y0 > outer.top + 1e-9:
        parts.append(Rect(x=outer.x, y=outer.y, width=outer.width, depth=y0 - outer.top))
    if y1 < outer.bottom - 1e-9:
        parts.append(Rect(x=outer.x, y=y1, width=outer.width, depth=outer.bottom - y1))
    if x0 > outer.left + 1e-9:
        parts.append(Rect(x=outer.x, y=y0, width=x0 - outer.left, depth=y1 - y0))
    if x1 < outer.right - 1e-9:
        parts.append(Rect(x=x1, y=y0, width=outer.right - x1, depth=y1 - y0))

    return [p for p in parts if p.width > 1e-9 and p.depth > 1e-9]
