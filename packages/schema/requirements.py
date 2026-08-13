"""用户需求模型 — LLM 输出目标，不直接输出 DesignProgram。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from packages.schema.site import CardinalEdge, CardinalOrientation, SetbackSpec

RelationKind = Literal[
    "adjacency",  # 共享边界级邻接（遗留；禁止当靠近/连通/通行的万能桶）
    "near",  # 靠近 / 邻近（不必连通、不必通行）
    "separation",  # 远离 / 私密分离
    "access",  # 可通行 / 内部相连（≠ 仅邻近）
    "open_connection",  # 开敞连通（客餐厅等）
    "visual_connection",  # 视线联系（预留）
]
RelationStrength = Literal["required", "preferred"]

AssumptionSource = Literal[
    "user_authorized",  # 用户明确授权假设
    "planseed_default",  # 产品确认的默认
    "llm_inference",  # 模型推断（不进 canonical assumptions/unknowns；记入 parser audit）
]

UnknownPriority = Literal[
    "blocking",  # 阻塞求解
    "recommended",  # 影响设计质量，应提示
    "optional",  # 可省略
]


class Assumption(BaseModel):
    """可解释推断；Alpha 优先 user_authorized / planseed_default。"""

    key: str
    value: str | int | float | bool
    reason: str = ""
    source: AssumptionSource = "llm_inference"


class UnknownRequirement(BaseModel):
    """用户未提供且未推断的信息。"""

    key: str
    description: str = ""
    priority: UnknownPriority = "recommended"


class SiteRequirements(BaseModel):
    width: float | None = Field(default=None, ge=6, le=60)
    depth: float | None = Field(default=None, ge=6, le=60)
    north_angle: float | None = Field(default=None, ge=0, lt=360)
    entrance_edge: CardinalEdge | None = None
    road_edges: list[CardinalEdge] = Field(default_factory=list)
    setbacks: SetbackSpec | None = None


class HouseholdRequirements(BaseModel):
    occupants: int | None = Field(default=None, ge=1, le=20)
    bedrooms: int | None = Field(default=None, ge=1, le=10)
    bathrooms: int | None = Field(default=None, ge=1, le=8)
    has_garage: bool | None = None
    notes: str = ""


class SpaceRequirement(BaseModel):
    """用户表达的空间需求（不含坐标）。"""

    id: str | None = None
    name: str
    category: str | None = None
    target_area: float | None = Field(default=None, gt=0)
    floor_preference: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    preferred_orientation: CardinalOrientation | None = None
    min_width: float | None = Field(default=None, gt=0)


class DesignPreferences(BaseModel):
    prefer_south_facing_living: bool | None = None
    prefer_open_kitchen_dining: bool | None = None
    prefer_compact_footprint: bool | None = None
    prefer_short_corridor: bool | None = None
    quiet_zone_away_from_entry: bool | None = None
    wet_stack_preference: bool | None = None


class RelationIntent(BaseModel):
    """软关系意图（名称级）；Normalizer 后续可编译为 Constraint。"""

    a: str = Field(min_length=1, description="空间名或 id")
    b: str = Field(min_length=1)
    kind: RelationKind = "adjacency"
    strength: RelationStrength = "preferred"
    note: str = ""


class RequirementSpec(BaseModel):
    """
    用户自然语言或表单表达的需求。

    RequirementSpec → normalize → DesignProgram
    """

    raw_text: str | None = None
    site: SiteRequirements = Field(default_factory=SiteRequirements)
    household: HouseholdRequirements = Field(default_factory=HouseholdRequirements)
    spaces: list[SpaceRequirement] = Field(default_factory=list)
    preferences: DesignPreferences = Field(default_factory=DesignPreferences)
    floor_count: int | None = Field(default=None, ge=1, le=3)

    assumptions: list[Assumption] = Field(default_factory=list)
    unknowns: list[UnknownRequirement] = Field(default_factory=list)
    relation_intents: list[RelationIntent] = Field(
        default_factory=list,
        description="Phase 6：名称级邻接/通行意图；Normalizer 可暂忽略",
    )
