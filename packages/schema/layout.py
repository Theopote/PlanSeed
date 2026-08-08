"""Solver 输出几何模型 — 与 RoomSpec 严格分离。"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class PlacementSource(StrEnum):
    PROGRAM = "program"
    GENERATED = "generated"


class PlacementRect(BaseModel):
    x: float = Field(ge=0)
    y: float = Field(ge=0)
    width: float = Field(gt=0)
    depth: float = Field(gt=0)

    @property
    def area(self) -> float:
        return self.width * self.depth

    @property
    def aspect_ratio(self) -> float:
        short = min(self.width, self.depth)
        long = max(self.width, self.depth)
        return long / max(short, 0.01)

    @property
    def right(self) -> float:
        return self.x + self.width

    @property
    def bottom(self) -> float:
        return self.y + self.depth


class RoomPlacement(BaseModel):
    """Solver 将房间放置在何处。"""

    room_id: str
    floor_id: str
    rect: PlacementRect
    source: PlacementSource = PlacementSource.PROGRAM
    name: str | None = None
    category: str | None = None

    @property
    def area(self) -> float:
        return self.rect.area

    @property
    def aspect_ratio(self) -> float:
        return self.rect.aspect_ratio


class FloorLayout(BaseModel):
    floor_id: str
    placements: list[RoomPlacement] = Field(default_factory=list)
    wet_zone_x0: float | None = Field(default=None, description="湿区带左边界（跨层对齐用）")
    wet_zone_x1: float | None = None
    wet_zone_y0: float | None = None
    wet_zone_y1: float | None = None
    stair_x0: float | None = None
    stair_y0: float | None = None
    stair_x1: float | None = None
    stair_y1: float | None = None
    core_placement: str | None = Field(
        default=None,
        description="楼梯核区位 north/south/east/west/center",
    )


class Violation(BaseModel):
    constraint_id: str
    room_ids: list[str] = Field(default_factory=list)
    message: str
    measured_value: float | None = None
    required_value: float | None = None
    hard: bool = True
    source: str | None = None


class CandidateValidation(BaseModel):
    valid: bool
    hard_violations: list[Violation] = Field(default_factory=list)
    soft_violations: list[Violation] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class LayoutCandidate(BaseModel):
    id: str
    seed: int
    floors: list[FloorLayout] = Field(default_factory=list)
    validation: CandidateValidation | None = None
    score: float | None = None
    metrics: dict[str, float | int | str | bool] = Field(default_factory=dict)
