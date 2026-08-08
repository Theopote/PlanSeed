"""StairCore 放置 — seed 驱动区位，跨层对齐。"""

from __future__ import annotations

import random

from packages.schema.core import CorePlacement, CorePlacementResult, StairCoreSpec
from packages.schema.layout import PlacementRect
from packages.schema.site import CardinalEdge
from solver.geometry.snap import snap_value


DEFAULT_STAIR_CORE = StairCoreSpec()


def resolve_stair_core_spec(
    *,
    stair_width: float | None = None,
    stair_depth: float | None = None,
    preferred: CorePlacement | None = None,
) -> StairCoreSpec:
    """site.stair_width 可覆盖核心短边；长边默认 4.2。"""
    return StairCoreSpec(
        width=stair_width if stair_width is not None else DEFAULT_STAIR_CORE.width,
        depth=stair_depth if stair_depth is not None else DEFAULT_STAIR_CORE.depth,
        preferred_placement=preferred,
    )


def choose_core_placement(
    rng: random.Random,
    *,
    preferred: CorePlacement | None = None,
    entrance_edge: CardinalEdge | None = None,
) -> CorePlacement:
    """seed 选择区位；有 preferred 则固定；否则略偏向入口边。"""
    if preferred is not None:
        return preferred

    options = list(CorePlacement)
    # 入口边对应区位加权：多拷贝一次
    if entrance_edge is not None:
        edge_map = {
            CardinalEdge.NORTH: CorePlacement.NORTH,
            CardinalEdge.SOUTH: CorePlacement.SOUTH,
            CardinalEdge.EAST: CorePlacement.EAST,
            CardinalEdge.WEST: CorePlacement.WEST,
        }
        bias = edge_map.get(entrance_edge)
        if bias is not None:
            options.append(bias)
    return rng.choice(options)


def place_stair_core(
    *,
    floor_width: float,
    floor_depth: float,
    spec: StairCoreSpec,
    placement: CorePlacement,
    snap_module: float = 0.3,
) -> CorePlacementResult:
    """
    在 footprint 内放置楼梯核 AABB。

    WEST/EAST：短边贴边，长边沿南北 (orientation=ns)
    NORTH/SOUTH：短边贴边，长边沿东西 (orientation=ew)
    CENTER：默认 ns，居中
    """
    w, d = floor_width, floor_depth
    cw, cd = spec.width, spec.depth

    if placement in (CorePlacement.WEST, CorePlacement.EAST, CorePlacement.CENTER):
        # footprint: width=cw (E-W), depth=cd (N-S)
        fw, fd = cw, cd
        orientation: str = "ns"
    else:
        # NORTH/SOUTH: elongate along E-W
        fw, fd = cd, cw
        orientation = "ew"

    if fw > w + 1e-6 or fd > d + 1e-6:
        # 缩放到可放入
        scale = min(w / fw, d / fd, 1.0)
        fw, fd = fw * scale, fd * scale

    if placement == CorePlacement.WEST:
        x, y = 0.0, (d - fd) / 2
    elif placement == CorePlacement.EAST:
        x, y = w - fw, (d - fd) / 2
    elif placement == CorePlacement.NORTH:
        x, y = (w - fw) / 2, 0.0
    elif placement == CorePlacement.SOUTH:
        x, y = (w - fw) / 2, d - fd
    else:  # CENTER
        x, y = (w - fw) / 2, (d - fd) / 2

    x = snap_value(x, snap_module)
    y = snap_value(y, snap_module)
    # 保证仍在界内
    x = max(0.0, min(x, w - fw))
    y = max(0.0, min(y, d - fd))

    rect = PlacementRect(x=x, y=y, width=fw, depth=fd)
    return CorePlacementResult(
        placement=placement,
        rect=rect,
        orientation=orientation,  # type: ignore[arg-type]
        width=fw,
        depth=fd,
    )
