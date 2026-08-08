"""建筑分区模型 — Functional Zone 与 Technical Wet Stack 分离。"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from packages.schema.layout import PlacementRect


class ArchitecturalZone(StrEnum):
    """
    功能分区（Functional Zone）— 决定与谁相邻、落在哪块平面区。

    不再把所有 WET 等同于 SERVICE：厨房属 DAY，主卫属 NIGHT。
    """

    DAY = "day"  # 公共起居 / 厨餐 ≈ ZoneKind.PUBLIC
    NIGHT = "night"  # 私密卧室 / 主卫 suite ≈ ZoneKind.PRIVATE
    SERVICE = "service"  # 车库、洗衣、客卫等后勤支撑
    CIRCULATION = "circulation"


class ZoneKind(StrEnum):
    """文档用语：PUBLIC / PRIVATE / SERVICE / CIRCULATION。"""

    PUBLIC = "public"
    PRIVATE = "private"
    SERVICE = "service"
    CIRCULATION = "circulation"


class WetStackGroup(StrEnum):
    """
    技术叠置组（Technical Stack）— 给排水竖向对齐，独立于功能分区。

    厨房与主卫可同属 WS1，却分属 DAY / NIGHT。
    """

    WS1 = "WS1"
    WS2 = "WS2"


def architectural_from_zone_kind(kind: ZoneKind) -> ArchitecturalZone:
    return {
        ZoneKind.PUBLIC: ArchitecturalZone.DAY,
        ZoneKind.PRIVATE: ArchitecturalZone.NIGHT,
        ZoneKind.SERVICE: ArchitecturalZone.SERVICE,
        ZoneKind.CIRCULATION: ArchitecturalZone.CIRCULATION,
    }[kind]


class RoomZoning(BaseModel):
    """单房间的功能分区 + 可选湿区技术叠组。"""

    functional_zone: ArchitecturalZone
    wet_stack_group: WetStackGroup | None = None


class ZoneRoomGroup(BaseModel):
    zone: ArchitecturalZone
    room_ids: list[str] = Field(default_factory=list)
    target_area: float = 0.0


class ZoneGeometry(BaseModel):
    """某一楼层上某功能分区的几何容器。"""

    zone: ArchitecturalZone
    floor_id: str
    rect: PlacementRect
    room_ids: list[str] = Field(default_factory=list)


class FloorZonePlan(BaseModel):
    floor_id: str
    zones: list[ZoneGeometry] = Field(default_factory=list)
    wet_stack_band: PlacementRect | None = Field(
        default=None,
        description="整栋共享的技术湿区条带（对齐用）；不强制等同功能 SERVICE 区",
    )
    wet_stack_group: WetStackGroup | None = Field(
        default=None,
        description="本方案使用的湿区叠组（通常 WS1）",
    )
