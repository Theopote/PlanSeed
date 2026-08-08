"""会话级布局锁 — Phase 4.1；不进 RequirementSpec / RoomSpec。

Lock = 不可变几何契约（immutable geometry contract），不是 generator hint。

优先级：Room Lock > Zone Lock（FunctionalZoneGroup）> Free

- Room Lock：房间矩形绝对固定（含后处理 / ConnectionResolver）
- Zone Lock：同层同 kind 的全部 zone 组件 envelope 固定；区内未 Room-Lock 的房间可重排，但不得越界
- Stair Lock：楼梯核跨层几何固定
- Free：完全自由

同 floor_id + zone kind 的多条 LockedZoneRect = 锁定整个 FunctionalZoneGroup（多组件），
而非「只锁其中一块」。
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from packages.schema.zoning import ArchitecturalZone


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


class LockedZoneRect(BaseModel):
    """
    钉死的功能分区组件矩形。

    同 floor_id + zone 的多条共同构成 FunctionalZoneGroup 锁。
    zone_id 对应 ZonePlacement.id（如 F1-day-0）；可空以兼容旧客户端。
    """

    zone: ArchitecturalZone = Field(description="day | night | service（非 circulation）")
    floor_id: str
    x: float = Field(ge=0)
    y: float = Field(ge=0)
    width: float = Field(gt=0)
    depth: float = Field(gt=0)
    room_ids: list[str] = Field(
        default_factory=list,
        description="锁定时归属该组件的房间；空则按 classify 回填",
    )
    zone_id: str | None = Field(
        default=None,
        description="分区组件 id（ZonePlacement.id）；空则按 floor+kind+几何匹配",
    )

    @field_validator("zone", mode="before")
    @classmethod
    def _coerce_zone(cls, v: object) -> object:
        if isinstance(v, str):
            return v.lower().strip()
        return v


class LayoutLocks(BaseModel):
    """Generate 时尊重的锁；空 = 全自由生成。"""

    rooms: list[LockedRoomRect] = Field(default_factory=list)
    stair: LockedStairCore | None = None
    zones: list[LockedZoneRect] = Field(default_factory=list)

    @property
    def locked_room_ids(self) -> set[str]:
        return {r.room_id for r in self.rooms}

    def rooms_on_floor(self, floor_id: str) -> list[LockedRoomRect]:
        return [r for r in self.rooms if r.floor_id == floor_id]

    def zones_on_floor(self, floor_id: str) -> list[LockedZoneRect]:
        return [z for z in self.zones if z.floor_id == floor_id]

    def locked_zone_kinds_on_floor(self, floor_id: str) -> set[str]:
        return {z.zone.value if hasattr(z.zone, "value") else str(z.zone) for z in self.zones if z.floor_id == floor_id}
