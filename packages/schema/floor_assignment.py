"""楼层归属结果模型 — FloorAssignmentSolver 输出。"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from packages.schema.room import FloorSpec, RoomSpec


class FloorAssignmentSource(StrEnum):
    """归属来源 — 可追踪、可解释。"""

    EXPLICIT_CONSTRAINT = "explicit_constraint"  # FloorConstraint
    EXPLICIT_ROOM_IDS = "explicit_room_ids"  # FloorSpec.room_ids
    EXPLICIT_FLOOR_ID = "explicit_floor_id"  # RoomSpec.floor_id
    FLOOR_PREFERENCE = "floor_preference"  # RoomSpec.floor_preference
    RESIDENTIAL_RULE = "residential_rule"  # 住宅默认规则
    FALLBACK = "fallback"  # 兜底，永不丢弃


class RoomFloorDecision(BaseModel):
    room_id: str
    floor_id: str
    source: FloorAssignmentSource
    source_key: str | None = None
    rule_id: str | None = None
    reason: str = ""


class FloorAssignment(BaseModel):
    """完整楼层归属方案。"""

    decisions: list[RoomFloorDecision] = Field(default_factory=list)

    def decision_for(self, room_id: str) -> RoomFloorDecision | None:
        return next((d for d in self.decisions if d.room_id == room_id), None)

    def floor_id_for(self, room_id: str) -> str | None:
        d = self.decision_for(room_id)
        return d.floor_id if d else None

    def room_ids_by_floor(self) -> dict[str, list[str]]:
        mapping: dict[str, list[str]] = {}
        for d in self.decisions:
            mapping.setdefault(d.floor_id, []).append(d.room_id)
        return mapping

    def apply(self, rooms: list[RoomSpec], floors: list[FloorSpec]) -> None:
        """写回 RoomSpec.floor_id 与 FloorSpec.room_ids。"""
        by_id = {d.room_id: d.floor_id for d in self.decisions}
        for room in rooms:
            floor_id = by_id.get(room.id)
            if floor_id is None:
                raise ValueError(f"FloorAssignment 缺少房间 {room.id}")
            room.floor_id = floor_id
        for fl in floors:
            fl.room_ids = [r.id for r in rooms if by_id.get(r.id) == fl.id]
