"""统一约束模型 — hard / soft 分离。"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, Field


class ConstraintKind(StrEnum):
    ADJACENCY = "adjacency"
    SEPARATION = "separation"
    ORIENTATION = "orientation"
    FLOOR = "floor"
    ALIGNMENT = "alignment"
    AREA = "area"
    WIDTH = "width"
    ACCESS = "access"


class ConstraintSource(StrEnum):
    USER = "user"
    NORMALIZER = "normalizer"
    DEFAULT_RULE = "default_rule"
    SYSTEM = "system"


class ConstraintBase(BaseModel):
    id: str
    kind: ConstraintKind
    hard: bool = True
    weight: float = Field(default=1.0, ge=0)
    description: str = ""
    source: ConstraintSource = ConstraintSource.USER
    source_key: str | None = None


class AdjacencyConstraint(ConstraintBase):
    kind: Literal[ConstraintKind.ADJACENCY] = ConstraintKind.ADJACENCY
    room_a_id: str
    room_b_id: str
    share_wall: bool = True


class SeparationConstraint(ConstraintBase):
    kind: Literal[ConstraintKind.SEPARATION] = ConstraintKind.SEPARATION
    room_a_id: str
    room_b_id: str
    min_distance: float = Field(default=0.0, ge=0)


class OrientationConstraint(ConstraintBase):
    kind: Literal[ConstraintKind.ORIENTATION] = ConstraintKind.ORIENTATION
    room_id: str
    preferred_orientation: str
    hard: bool = False
    weight: float = 0.8


class FloorConstraint(ConstraintBase):
    kind: Literal[ConstraintKind.FLOOR] = ConstraintKind.FLOOR
    room_id: str
    floor_id: str


class AlignmentConstraint(ConstraintBase):
    """跨层对齐约束，如湿区竖向叠置、楼梯轴对齐。"""

    kind: Literal[ConstraintKind.ALIGNMENT] = ConstraintKind.ALIGNMENT
    room_ids: list[str] = Field(default_factory=list)
    axis: Literal["x", "y"] = "x"
    alignment_group: str = Field(description='对齐组标识，如 "wet_zone" / "stair"')


class AreaConstraint(ConstraintBase):
    kind: Literal[ConstraintKind.AREA] = ConstraintKind.AREA
    room_id: str
    min_area: float | None = None
    max_area: float | None = None
    target_area: float | None = None


class WidthConstraint(ConstraintBase):
    kind: Literal[ConstraintKind.WIDTH] = ConstraintKind.WIDTH
    room_id: str
    min_width: float = Field(gt=0)


class AccessConstraint(ConstraintBase):
    kind: Literal[ConstraintKind.ACCESS] = ConstraintKind.ACCESS
    room_id: str
    requires_exterior: bool = False
    requires_stair_reach: bool = True


Constraint = Annotated[
    AdjacencyConstraint
    | SeparationConstraint
    | OrientationConstraint
    | FloorConstraint
    | AlignmentConstraint
    | AreaConstraint
    | WidthConstraint
    | AccessConstraint,
    Field(discriminator="kind"),
]
