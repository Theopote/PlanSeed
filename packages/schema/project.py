"""顶层项目规格 — LLM / UI 输入的统一入口。"""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from packages.schema.constraints import Constraint
from packages.schema.limits import SOLVER_LIMITS
from packages.schema.room import FloorSpec, RoomSpec
from packages.schema.site import SiteSpec
from packages.schema.vertical_void import VerticalVoidSpec, validate_vertical_voids_for_floors


class HouseholdSpec(BaseModel):
    """住户与使用需求摘要。"""

    occupants: int = Field(default=4, ge=1, le=20)
    bedrooms: int = Field(default=3, ge=1, le=10)
    bathrooms: int = Field(default=2, ge=1, le=8)
    has_garage: bool = True
    notes: str = ""


class PreferencesSpec(BaseModel):
    """全局偏好 — 可转化为 soft constraints。"""

    prefer_south_facing_living: bool = True
    prefer_open_kitchen_dining: bool = True
    prefer_compact_footprint: bool = False
    prefer_short_corridor: bool = True
    quiet_zone_away_from_entry: bool = True


class ProjectSpec(BaseModel):
    """
    Schema v2 根对象。

    输入：用户 / LLM 描述的设计意图。
    输出几何由 LayoutCandidate 承载，不在此模型中。
    """

    id: str = Field(default="project-1")
    name: str = Field(default="未命名项目")
    version: str = Field(default="2.0")

    site: SiteSpec
    household: HouseholdSpec = Field(default_factory=HouseholdSpec)
    floors: list[FloorSpec] = Field(min_length=1, max_length=SOLVER_LIMITS.max_floors)
    rooms: list[RoomSpec] = Field(min_length=1, max_length=SOLVER_LIMITS.max_rooms)
    constraints: list[Constraint] = Field(default_factory=list)
    preferences: PreferencesSpec = Field(default_factory=PreferencesSpec)
    vertical_voids: list[VerticalVoidSpec] = Field(
        default_factory=list,
        description="竖向空洞 / 对齐规格（ADR-010）；空则 solver 沿用隐式楼梯核",
    )

    @model_validator(mode="after")
    def _validate_vertical_voids(self) -> ProjectSpec:
        if self.vertical_voids:
            validate_vertical_voids_for_floors(self.vertical_voids, self.floors)
        return self

    @model_validator(mode="after")
    def _unique_room_ids(self) -> ProjectSpec:
        ids = [r.id for r in self.rooms]
        if len(ids) != len(set(ids)):
            raise ValueError("ProjectSpec.rooms 含重复 id")
        return self

    @property
    def floor_count(self) -> int:
        return len(self.floors)

    def room_by_id(self, room_id: str) -> RoomSpec | None:
        return next((r for r in self.rooms if r.id == room_id), None)

    def rooms_on_floor(self, floor_id: str) -> list[RoomSpec]:
        floor = next((f for f in self.floors if f.id == floor_id), None)
        if floor is None:
            return []
        if floor.room_ids:
            id_set = set(floor.room_ids)
            return [r for r in self.rooms if r.id in id_set]
        return [r for r in self.rooms if r.floor_id == floor_id or floor_id in r.floor_preference]
