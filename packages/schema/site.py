"""场地与边界模型 — 严格区分 site / buildable / footprint。"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class CardinalEdge(StrEnum):
    NORTH = "north"
    SOUTH = "south"
    EAST = "east"
    WEST = "west"


class CardinalOrientation(StrEnum):
    NORTH = "north"
    SOUTH = "south"
    EAST = "east"
    WEST = "west"


class SetbackSpec(BaseModel):
    """退线距离（米），从对应边界向内收缩。"""

    north: float = Field(default=0.0, ge=0)
    south: float = Field(default=0.0, ge=0)
    east: float = Field(default=0.0, ge=0)
    west: float = Field(default=0.0, ge=0)


class Rect2D(BaseModel):
    """轴对齐矩形，单位米。"""

    x: float = Field(ge=0)
    y: float = Field(ge=0)
    width: float = Field(gt=0)
    depth: float = Field(gt=0)

    @property
    def x1(self) -> float:
        return self.x + self.width

    @property
    def y1(self) -> float:
        return self.y + self.depth


class Point2D(BaseModel):
    """二维点（米）。Phase 8.4 不规则场地用。"""

    x: float
    y: float


class Polygon2D(BaseModel):
    """
    简单多边形（可含洞）。

    约定：外环逆时针或顺时针均可；洞为内环。
    Alpha 仅保证**正交边**（轴对齐）完整支持；斜边可表示但不保证分解质量。
    """

    exterior: list[Point2D] = Field(min_length=3)
    holes: list[list[Point2D]] = Field(default_factory=list)


class SiteSpec(BaseModel):
    """
    矩形地块规格。

    三者语义不可混用：
    - site boundary：法定/实际用地外轮廓
    - buildable envelope：退线后的可建范围
    - building footprint：建筑占地区域（solver 输出，输入阶段可为空）
    """

    width: float = Field(ge=6, le=60, description="用地宽度（米，东-西）")
    depth: float = Field(ge=6, le=60, description="用地深度（米，北-南）")
    north_angle: float = Field(
        default=0.0,
        ge=0,
        lt=360,
        description=(
            "正北相对 model north 外向（−Y）的顺时针角（度）。"
            "0=model north 朝世界正北；90=model north 朝世界正东。"
            "见 SiteCoordinateSystem.edge_azimuth"
        ),
    )
    entrance_edge: CardinalEdge = Field(
        default=CardinalEdge.SOUTH,
        description="主入口所在边",
    )
    road_edges: list[CardinalEdge] = Field(
        default_factory=list,
        description="临路边（可为空，表示内街/无临路）",
    )
    setbacks: SetbackSpec = Field(default_factory=SetbackSpec)
    setback_source: Literal["unspecified", "user"] = Field(
        default="unspecified",
        description="unspecified = 未提供规划退界，0 不代表法规结论",
    )
    site_boundary: Rect2D | None = Field(
        default=None,
        description="显式用地边界；为空时由 width×depth 推导",
    )
    buildable_envelope: Rect2D | None = Field(
        default=None,
        description="可建 envelope；为空时由 site + setbacks 推导",
    )
    building_footprint: Rect2D | None = Field(
        default=None,
        description="建筑占地（solver 输出回填，输入可为空）",
    )
    # Phase 8.4 — 不规则场地（opt-in；默认仍用矩形 width×depth）
    site_polygon: Polygon2D | None = Field(
        default=None,
        description="不规则用地多边形；为空则沿用矩形 site_boundary",
    )
    buildable_polygon: Polygon2D | None = Field(
        default=None,
        description="不规则可建多边形；可由 site_polygon + 退线推导（solver.geometry.irregular）",
    )

    stair_width: float = Field(
        default=1.8,
        ge=1.0,
        le=3.0,
        description="楼梯核短边（净宽）；不再表示整层交通条带宽度",
    )
    stair_depth: float = Field(
        default=4.2,
        ge=2.4,
        le=8.0,
        description="楼梯核长边（梯段+平台）",
    )
    grid_module: float = Field(default=0.3, ge=0.1, le=1.0, description="坐标 snap 模数（米）")
    structural_module: float = Field(default=3.3, ge=2.4, le=4.5, description="结构网格模数（米）")

    @model_validator(mode="after")
    def derive_rectangles(self) -> SiteSpec:
        if self.site_boundary is None:
            self.site_boundary = Rect2D(x=0, y=0, width=self.width, depth=self.depth)
        if self.buildable_envelope is None:
            sb = self.setbacks
            inner_w = self.width - sb.west - sb.east
            inner_d = self.depth - sb.north - sb.south
            if inner_w <= 0 or inner_d <= 0:
                raise ValueError(
                    "退线后无可建范围："
                    f"site {self.width:g}×{self.depth:g}，"
                    f"setbacks N{sb.north:g}/S{sb.south:g}/E{sb.east:g}/W{sb.west:g}"
                )
            self.buildable_envelope = Rect2D(
                x=sb.west,
                y=sb.north,
                width=inner_w,
                depth=inner_d,
            )
        return self
