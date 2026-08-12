"""房间与楼层需求模型 — 输入侧，不含几何坐标。"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field, model_validator

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


class SemanticRole(StrEnum):
    """
    语义角色 — Solver 主判定依据（先于 tags / category / name）。

    name 仅 UI；NLP → semantic_role 由 normalize / LLM 负责。
    """

    LIVING = "living"
    DINING = "dining"
    KITCHEN = "kitchen"
    BEDROOM = "bedroom"
    MASTER_BEDROOM = "master_bedroom"
    ELDERLY_BEDROOM = "elderly_bedroom"
    BATHROOM = "bathroom"
    MASTER_BATHROOM = "master_bathroom"
    STUDY = "study"
    GARAGE = "garage"
    STORAGE = "storage"
    LAUNDRY = "laundry"
    FOYER = "foyer"
    HALL = "hall"


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

    semantic_role: SemanticRole | None = Field(
        default=None,
        description="语义角色（优先于 tags）；如 master_bedroom / kitchen",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="附加语义标签；Solver 判定顺序：semantic_role → tags → category → name",
    )

    @model_validator(mode="after")
    def _area_bounds_consistent(self) -> RoomSpec:
        lo, hi, target = self.min_area, self.max_area, self.target_area
        if lo is not None and hi is not None and lo > hi:
            raise ValueError(f"min_area {lo} > max_area {hi}")
        if lo is not None and lo > target:
            raise ValueError(f"min_area {lo} > target_area {target}")
        if hi is not None and hi < target:
            raise ValueError(f"max_area {hi} < target_area {target}")
        return self

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
