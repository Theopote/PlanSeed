"""对外主入口 — 与 StairCore 严格分离。"""

from __future__ import annotations

from pydantic import BaseModel, Field

from packages.schema.site import CardinalEdge


class ExteriorEntry(BaseModel):
    """
    建筑对外主入口（Entrance ≠ Stair）。

    位于 buildable 外轮廓上，由 SiteSpec.entrance_edge（及 road_edges 偏好）决定边。
    AccessGraph 以此为交通起点：ExteriorEntry → Foyer / Living / Hall → …
    """

    id: str = Field(default="exterior-entry", description="AccessGraph 节点 id")
    edge: CardinalEdge = Field(description="所在世界/场地主入口边")
    floor_id: str = Field(default="F1", description="通常为地面层")
    # 开口中心（模型坐标，贴 buildable 外缘）
    x: float
    y: float
    width: float = Field(default=1.2, gt=0, description="入口洞口沿墙宽度（米）")
    on_road_edge: bool = Field(
        default=False,
        description="entrance_edge 是否同时属于 road_edges",
    )
    connected_room_ids: list[str] = Field(
        default_factory=list,
        description="与入口贴边直接相连的房间（厅/门厅优先，非楼梯）",
    )
