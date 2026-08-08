"""空间关系图 — Program → RoomGraph → TopologyPlan → AccessGraph → Geometry。"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class RoomEdgeKind(StrEnum):
    ADJACENT = "adjacent"
    CONNECTED = "connected"
    NEAR = "near"
    FAR = "far"
    AVOID = "avoid"


class RoomEdge(BaseModel):
    source_id: str
    target_id: str
    kind: RoomEdgeKind
    weight: float = Field(default=1.0, ge=0)


class RoomGraph(BaseModel):
    room_ids: list[str] = Field(default_factory=list)
    edges: list[RoomEdge] = Field(default_factory=list)

    def add_edge(self, edge: RoomEdge) -> None:
        if edge.source_id not in self.room_ids:
            self.room_ids.append(edge.source_id)
        if edge.target_id not in self.room_ids:
            self.room_ids.append(edge.target_id)
        self.edges.append(edge)


class AdjacencyCluster(BaseModel):
    """同层内希望共域的连通分量（adjacent / connected / near）。"""

    floor_id: str
    room_ids: list[str] = Field(default_factory=list)


class RoomPair(BaseModel):
    """无序房间对（存储时 source_id < target_id 规范化可选）。"""

    room_a_id: str
    room_b_id: str
    weight: float = Field(default=1.0, ge=0)


class TopologyPlan(BaseModel):
    """
    由 RoomGraph 派生的生成前拓扑计划。

    MVP：影响区内打包顺序与 avoid 分半；不重划功能区边界。
    """

    clusters: list[AdjacencyCluster] = Field(default_factory=list)
    prefer_adjacent: list[RoomPair] = Field(
        default_factory=list,
        description="邻接偏好（adjacent），按 weight 降序",
    )
    avoid_pairs: list[RoomPair] = Field(
        default_factory=list,
        description="应分离的房间对（far / avoid）",
    )
    pack_order_hint: dict[str, list[str]] = Field(
        default_factory=dict,
        description="每层建议打包顺序（确定性；不依赖 seed）",
    )


class SpaceConnectionType(StrEnum):
    """
    通行连接类型 — 不同于 AdjacencyConstraint（几何邻接）。

    Kitchen—Dining 可只要邻接不必有门；Hall—Bedroom 必须可通行。
    """

    OPEN = "open"  # 开敞连通（无门扇）
    DOOR = "door"  # 门洞
    PASSAGE = "passage"  # 过道 / 开口
    STAIR = "stair"  # 跨层楼梯连接
    EXTERIOR_ENTRY = "exterior_entry"  # 对外入口


class SpaceConnection(BaseModel):
    """
    两空间之间的通行关系（交通语义）。

    AccessGraph 由 SpaceConnection 构成；Door placement（2.2）只消费
    type∈{DOOR, PASSAGE, …} 且已确认 shared boundary 的边。
    """

    id: str
    a: str = Field(description="节点 id（房间 / entry / stair-core …）")
    b: str = Field(description="节点 id")
    type: SpaceConnectionType
    required: bool = True
    weight: float = Field(default=1.0, ge=0)
    description: str = ""


class AccessGraph(BaseModel):
    """
    可达图 — Phase 2.1 核心。

    节点：房间 + 特殊节点（entry、stair 等）。
    边：SpaceConnection（通行要求，不是几何邻接）。
    """

    node_ids: list[str] = Field(default_factory=list)
    connections: list[SpaceConnection] = Field(default_factory=list)

    def add_connection(self, conn: SpaceConnection) -> None:
        if conn.a not in self.node_ids:
            self.node_ids.append(conn.a)
        if conn.b not in self.node_ids:
            self.node_ids.append(conn.b)
        self.connections.append(conn)

    def required_connections(self) -> list[SpaceConnection]:
        return [c for c in self.connections if c.required]
