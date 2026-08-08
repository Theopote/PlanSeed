"""StairCore 放置 — seed 驱动区位，跨层对齐；禁止静默缩小。"""

from __future__ import annotations

import random
from typing import Literal

from packages.schema.core import CorePlacement, CorePlacementResult, StairCoreSpec
from packages.schema.layout import PlacementRect
from packages.schema.site import CardinalEdge
from solver.geometry.snap import snap_value

DEFAULT_STAIR_CORE = StairCoreSpec()

Orientation = Literal["ns", "ew"]


class CorePlacementFailure(Exception):
    """楼梯核以规定尺寸无法放入 footprint（不得缩小 hard requirement）。"""

    def __init__(self, message: str, *, spec: StairCoreSpec, floor_width: float, floor_depth: float):
        super().__init__(message)
        self.spec = spec
        self.floor_width = floor_width
        self.floor_depth = floor_depth


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


def default_orientation_for(placement: CorePlacement) -> Orientation:
    """WEST/EAST/CENTER → ns；NORTH/SOUTH → ew。"""
    if placement in (CorePlacement.WEST, CorePlacement.EAST, CorePlacement.CENTER):
        return "ns"
    return "ew"


def footprint_for_orientation(spec: StairCoreSpec, orientation: Orientation) -> tuple[float, float]:
    """返回 (width, depth) 在 footprint 坐标系中的尺寸（不缩小）。"""
    if orientation == "ns":
        return spec.width, spec.depth
    return spec.depth, spec.width


def core_fits(
    *,
    floor_width: float,
    floor_depth: float,
    spec: StairCoreSpec,
    orientation: Orientation,
) -> bool:
    fw, fd = footprint_for_orientation(spec, orientation)
    return fw <= floor_width + 1e-9 and fd <= floor_depth + 1e-9


def place_stair_core(
    *,
    floor_width: float,
    floor_depth: float,
    spec: StairCoreSpec,
    placement: CorePlacement,
    snap_module: float = 0.3,
    orientation: Orientation | None = None,
) -> CorePlacementResult:
    """
    在 footprint 内放置楼梯核 AABB。

    尺寸必须等于 spec（允许 orientation 交换长短边）；放不下则抛 CorePlacementFailure。
    禁止缩放缩小。
    """
    w, d = floor_width, floor_depth
    orient = orientation or default_orientation_for(placement)
    fw, fd = footprint_for_orientation(spec, orient)

    if fw > w + 1e-9 or fd > d + 1e-9:
        raise CorePlacementFailure(
            f"楼梯核 {fw:.2f}×{fd:.2f}（orientation={orient}）无法放入 "
            f"{w:.2f}×{d:.2f} footprint；禁止缩小 hard requirement",
            spec=spec,
            floor_width=w,
            floor_depth=d,
        )

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
    x = max(0.0, min(x, w - fw))
    y = max(0.0, min(y, d - fd))

    # snap 后仍须完整落入；若 snap 推出界外则失败（不缩小）
    if x + fw > w + 1e-6 or y + fd > d + 1e-6 or x < -1e-9 or y < -1e-9:
        raise CorePlacementFailure(
            f"楼梯核 snap 后越界：({x:.2f},{y:.2f}) {fw:.2f}×{fd:.2f} in {w:.2f}×{d:.2f}",
            spec=spec,
            floor_width=w,
            floor_depth=d,
        )

    rect = PlacementRect(x=x, y=y, width=fw, depth=fd)
    return CorePlacementResult(
        placement=placement,
        rect=rect,
        orientation=orient,
        width=fw,
        depth=fd,
    )


def _placement_try_order(
    primary: CorePlacement,
    rng: random.Random,
) -> list[CorePlacement]:
    rest = [p for p in CorePlacement if p != primary]
    rng.shuffle(rest)
    return [primary, *rest]


def place_stair_core_resolving(
    *,
    floor_width: float,
    floor_depth: float,
    spec: StairCoreSpec,
    primary_placement: CorePlacement,
    snap_module: float = 0.3,
    rng: random.Random | None = None,
) -> CorePlacementResult:
    """
    尝试放置规定尺寸的楼梯核：

    1. primary placement + 默认 orientation
    2. 同 placement + 交替 orientation
    3. 其他 placement × orientations

    全部失败 → CorePlacementFailure（candidate 应判 invalid）。
    """
    rng = rng or random.Random(0)
    attempts: list[tuple[CorePlacement, Orientation]] = []
    for placement in _placement_try_order(primary_placement, rng):
        primary_orient = default_orientation_for(placement)
        alt_orient: Orientation = "ew" if primary_orient == "ns" else "ns"
        attempts.append((placement, primary_orient))
        attempts.append((placement, alt_orient))

    last_err: CorePlacementFailure | None = None
    for placement, orient in attempts:
        if not core_fits(
            floor_width=floor_width,
            floor_depth=floor_depth,
            spec=spec,
            orientation=orient,
        ):
            continue
        try:
            return place_stair_core(
                floor_width=floor_width,
                floor_depth=floor_depth,
                spec=spec,
                placement=placement,
                snap_module=snap_module,
                orientation=orient,
            )
        except CorePlacementFailure as err:
            last_err = err
            continue

    raise CorePlacementFailure(
        f"所有区位/朝向均无法以 {spec.width}×{spec.depth} 放入 "
        f"{floor_width}×{floor_depth} footprint",
        spec=spec,
        floor_width=floor_width,
        floor_depth=floor_depth,
    ) from last_err
