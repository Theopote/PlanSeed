"""竖向核心 / 楼梯核 — 非整层交通条带。"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field

from packages.schema.layout import PlacementRect


class CorePlacement(StrEnum):
    """楼梯核在建筑 footprint 内的区位。"""

    NORTH = "north"
    SOUTH = "south"
    EAST = "east"
    WEST = "west"
    CENTER = "center"


class StairCoreSpec(BaseModel):
    """
    楼梯竖向核心规格。

    默认 1.8 × 4.2 m，接近实际单跑/双跑楼梯占位，
    而非 stair_width × 整栋进深的算法条带。
    """

    width: float = Field(default=1.8, ge=1.0, le=4.0, description="核心短边（净宽方向）")
    depth: float = Field(default=4.2, ge=2.4, le=8.0, description="核心长边（梯段+休息平台）")
    preferred_placement: CorePlacement | None = Field(
        default=None,
        description="用户/约束指定区位；为空则由 seed 选择",
    )


class CorePlacementResult(BaseModel):
    """某一候选方案的楼梯核几何。"""

    placement: CorePlacement
    rect: PlacementRect
    orientation: Literal["ns", "ew"] = Field(
        description="ns=长边沿南北；ew=长边沿东西",
    )
    width: float
    depth: float
