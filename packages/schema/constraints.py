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
    """
    几何邻接（共享墙偏好）— 不等于可通行。

    Kitchen—Dining 可用本约束表达「贴邻」而不要求门；
    Hall—Bedroom 可通行请用 SpaceConnection → AccessGraph。
    """

    kind: Literal[ConstraintKind.ADJACENCY] = ConstraintKind.ADJACENCY
    room_a_id: str
    room_b_id: str
    share_wall: bool = True


class SeparationConstraint(ConstraintBase):
    """同层平面空间分离约束；跨层房间不适用（竖向关系用 Alignment / 未来 Vertical*）。"""

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
    alignment_group: str = Field(
        description='对齐组标识，如 "wet_stack" / "stair"（"wet_zone" 为兼容别名）'
    )


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
    """通行约束（≠ 几何邻接）。

    requires_exterior: 对外通行（EXTERIOR_ENTRY 实化边），非单纯贴外墙/采光。
    requires_stair_reach: 字段保留；上层可达性由 RealizedAccessGraph（access.unreachable_room）统一校验。
    """

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
