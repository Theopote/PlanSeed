"""建筑分区模型 — day / night / service / circulation。"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from packages.schema.layout import PlacementRect


class ArchitecturalZone(StrEnum):
    """住宅功能分区（ZonePlanner 使用）。"""

    DAY = "day"  # 公共起居 ≈ ZoneKind.PUBLIC
    NIGHT = "night"  # 私密/主卫 suite ≈ ZoneKind.PRIVATE
    SERVICE = "service"  # 厨卫（非 suite）、车库、储藏
    CIRCULATION = "circulation"


class ZoneKind(StrEnum):
    """文档用语：PUBLIC / PRIVATE / SERVICE / CIRCULATION。"""

    PUBLIC = "public"
    PRIVATE = "private"
    SERVICE = "service"
    CIRCULATION = "circulation"


def architectural_from_zone_kind(kind: ZoneKind) -> ArchitecturalZone:
    return {
        ZoneKind.PUBLIC: ArchitecturalZone.DAY,
        ZoneKind.PRIVATE: ArchitecturalZone.NIGHT,
        ZoneKind.SERVICE: ArchitecturalZone.SERVICE,
        ZoneKind.CIRCULATION: ArchitecturalZone.CIRCULATION,
    }[kind]


class ZoneRoomGroup(BaseModel):
    zone: ArchitecturalZone
    room_ids: list[str] = Field(default_factory=list)
    target_area: float = 0.0


class ZoneGeometry(BaseModel):
    """某一楼层上某分区的几何容器。"""

    zone: ArchitecturalZone
    floor_id: str
    rect: PlacementRect
    room_ids: list[str] = Field(default_factory=list)


class FloorZonePlan(BaseModel):
    floor_id: str
    zones: list[ZoneGeometry] = Field(default_factory=list)
