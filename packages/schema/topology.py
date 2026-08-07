"""空间关系图 — Program → RoomGraph → Zoning → Geometry。"""

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
