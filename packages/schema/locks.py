"""会话级布局锁 — Phase 4.1；不进 RequirementSpec / RoomSpec。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class LockedRoomRect(BaseModel):
    """钉死的房间矩形（来自当前候选 Placement）。"""

    room_id: str
    floor_id: str
    x: float = Field(ge=0)
    y: float = Field(ge=0)
    width: float = Field(gt=0)
    depth: float = Field(gt=0)


class LockedStairCore(BaseModel):
    """钉死的楼梯核（跨层对齐；几何以 rect 为准）。"""

    x: float = Field(ge=0)
    y: float = Field(ge=0)
    width: float = Field(gt=0)
    depth: float = Field(gt=0)
    core_placement: str | None = Field(
        default=None,
        description="north|south|east|west|center；可空，仅元数据",
    )


class LayoutLocks(BaseModel):
    """Generate 时尊重的锁；空 = 全自由生成。"""

    rooms: list[LockedRoomRect] = Field(default_factory=list)
    stair: LockedStairCore | None = None

    @property
    def locked_room_ids(self) -> set[str]:
        return {r.room_id for r in self.rooms}

    def rooms_on_floor(self, floor_id: str) -> list[LockedRoomRect]:
        return [r for r in self.rooms if r.floor_id == floor_id]
