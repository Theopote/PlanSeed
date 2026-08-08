"""房间与楼层需求模型 — 输入侧，不含几何坐标。"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from packages.schema.site import CardinalOrientation


class RoomCategory(StrEnum):
    """空间功能分类（对应原型 TYPE_META，并扩展 service/circulation）。"""

    PUBLIC = "public"
    PRIVATE = "private"
    WET = "wet"
    SERVICE = "service"
    CIRCULATION = "circulation"
    OTHER = "other"


class PrivacyLevel(StrEnum):
    PUBLIC = "public"
    SEMI_PRIVATE = "semi_private"
    PRIVATE = "private"


class RoomSpec(BaseModel):
    """
    单个房间的设计需求。

    area 不再作为唯一字段；target_area 表示期望面积，
    min_area / max_area 定义可接受区间。
    """

    id: str
    name: str
    category: RoomCategory

    target_area: float = Field(gt=0, description="目标面积（平方米）")
    min_area: float | None = Field(default=None, gt=0)
    max_area: float | None = Field(default=None, gt=0)

    min_width: float | None = Field(default=None, gt=0, description="最小净宽（米）")

    floor_id: str | None = Field(
        default=None,
        description="强制楼层；为空表示由 floor_preference 或 solver 决定",
    )
    floor_preference: list[str] = Field(
        default_factory=list,
        description='偏好楼层 ID 列表，如 ["F1", "F2"]',
    )

    daylight_required: bool = False
    preferred_orientation: CardinalOrientation | None = None
    privacy_level: PrivacyLevel = PrivacyLevel.PUBLIC
    exterior_access: bool = False

    tags: list[str] = Field(
        default_factory=list,
        description=(
            "语义标签（semantic role），如 kitchen / bedroom / master / elderly_accessible；"
            "Solver 以此判定规则，name 仅作 UI 文本"
        ),
    )

    def resolved_min_area(self) -> float:
        return self.min_area if self.min_area is not None else self.target_area * 0.85

    def resolved_max_area(self) -> float:
        return self.max_area if self.max_area is not None else self.target_area * 1.25


class FloorSpec(BaseModel):
    id: str = Field(description='楼层 ID，如 "F1"')
    label: str = Field(description='显示名，如 "一层"')
    elevation: float = Field(default=0.0, description="标高（米）")
    room_ids: list[str] = Field(
        default_factory=list,
        description="本层包含的房间 ID（也可从 RoomSpec.floor_id 反查）",
    )
