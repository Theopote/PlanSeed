"""坐标 snap — 默认 0.3m 模数。"""

from __future__ import annotations

from solver.geometry.rect import Rect


def snap_value(value: float, module: float = 0.3) -> float:
    if module <= 0:
        raise ValueError("module must be positive")
    return round(value / module) * module


def snap_rect(rect: Rect, module: float = 0.3) -> Rect:
    x = snap_value(rect.x, module)
    y = snap_value(rect.y, module)
    right = snap_value(rect.right, module)
    bottom = snap_value(rect.bottom, module)
    width = max(module, right - x)
    depth = max(module, bottom - y)
    return Rect(x=x, y=y, width=width, depth=depth)
