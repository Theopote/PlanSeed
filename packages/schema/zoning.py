"""建筑分区模型 — day / night / service / circulation。"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from packages.schema.layout import PlacementRect


class ArchitecturalZone(StrEnum):
    """住宅功能分区（ZonePlanner 使用）。"""

    DAY = "day"  # 公共起居：客厅、餐厅等
    NIGHT = "night"  # 私密：卧室、书房
    SERVICE = "service"  # 厨卫、车库、储藏
    CIRCULATION = "circulation"  # 楼梯核等（通常由系统生成）


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
