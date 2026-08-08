"""对外主入口 — Entrance ≠ Stair。"""

from __future__ import annotations

from pydantic import BaseModel, Field

from packages.schema.site import CardinalEdge


class ExteriorEntrySpec(BaseModel):
    """输入侧入口需求（Phase 1.6）。"""

    id: str = Field(default="exterior-entry")
    preferred_edge: CardinalEdge | None = Field(
        default=None,
        description="偏好边；空则用 SiteSpec.entrance_edge → road_edges → 默认南",
    )
    width: float = Field(default=1.2, gt=0, description="入口洞口沿墙宽度（米）")
    required: bool = True


class ExteriorEntryPlacement(BaseModel):
    """
    Solver 输出：buildable 外缘上的入口点/线段。

    AccessGraph 以此为交通起点：ExteriorEntry → Foyer / Living / Hall → …
    """

    id: str = Field(default="exterior-entry", description="AccessGraph 节点 id")
    edge: CardinalEdge = Field(description="实际所在边")
    floor_id: str = Field(default="F1", description="通常为地面层")
    x: float
    y: float
    width: float = Field(default=1.2, gt=0)
    on_road_edge: bool = Field(
        default=False,
        description="是否落在 road_edges 上",
    )
    connected_room_ids: list[str] = Field(
        default_factory=list,
        description="与入口贴边直接相连的房间（厅/门厅优先，非楼梯）",
    )


# 兼容旧名
ExteriorEntry = ExteriorEntryPlacement
