"""Solver 内部使用的规范化设计程序。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from packages.schema.constraints import Constraint
from packages.schema.entry import ExteriorEntrySpec
from packages.schema.floor_assignment import FloorAssignment
from packages.schema.limits import SOLVER_LIMITS
from packages.schema.project import ProjectSpec
from packages.schema.requirements import Assumption, UnknownRequirement
from packages.schema.room import FloorSpec, RoomSpec
from packages.schema.site import Polygon2D, Rect2D, SiteSpec
from packages.schema.topology import AccessGraph, RoomGraph, TopologyPlan
from packages.schema.vertical_void import VerticalVoidSpec, validate_vertical_voids_for_floors

RankMode = Literal["score", "axis", "pareto"]
GeneratorStrategyName = Literal["guillotine", "maxrect"]


class SolverConfig(BaseModel):
    candidate_count: int = Field(default=64, ge=1, le=SOLVER_LIMITS.max_candidates)
    return_top_k: int = Field(default=5, ge=1, le=SOLVER_LIMITS.max_return_top_k)
    base_seed: int = Field(default=42)
    snap_module: float = Field(default=0.3, gt=0)
    min_diversity_threshold: float | None = Field(
        default=0.85,
        ge=0.0,
        le=1.0,
        description="Top-K 多样性阈值；None 关闭，仅按分数排序",
    )
    rank_mode: RankMode = Field(
        default="axis",
        description=(
            "Top-K selection: "
            "score=纯总分；"
            "axis=Alpha Stable 默认；"
            "pareto=Experimental（须 experimental=True）"
        ),
    )
    generator_strategy: GeneratorStrategyName = Field(
        default="guillotine",
        description="Alpha Stable 默认 guillotine；maxrect 为 Experimental",
    )
    experimental: bool = Field(
        default=False,
        description="True 才允许 Research Lab 策略（MaxRect / Pareto / …）影响求解",
    )
    profile_id: str | None = Field(
        default=None,
        description="SolverProfile id（如 alpha-stable）；产品路径由 pin 写入",
    )
    max_wet_stacks: int = Field(
        default=1,
        ge=1,
        le=2,
        description="技术湿区叠组上限；MVP=1，未来可扩到 2（WS1/WS2）",
    )
    max_connection_repairs: int = Field(
        default=8,
        ge=0,
        le=SOLVER_LIMITS.max_connection_repairs,
        description="ConnectionResolver 最大修补次数（含 gap/lengthen）",
    )
    max_connection_reslices: int = Field(
        default=3,
        ge=0,
        le=SOLVER_LIMITS.max_connection_reslices,
        description="跨区局部重切上限",
    )
    max_modified_area_ratio: float = Field(
        default=0.25,
        ge=0.0,
        le=1.0,
        description="修补累计 |Δarea| / 程序总面积上限；超出 → hard",
    )


class DesignProgram(BaseModel):
    """
    normalize(ProjectSpec) 的输出。

    包含 solver 可直接消费的结构化程序，不含 UI 元数据。
    """

    project_id: str
    site: SiteSpec
    buildable: Rect2D
    buildable_free_rects: list[Rect2D] = Field(
        default_factory=list,
        description="可建 free rect 分解；空列表表示退化为单一 buildable 矩形",
    )
    buildable_polygon: Polygon2D | None = Field(
        default=None,
        description="resolved 可建多边形；irregular 路径用于 boundary / site 评价",
    )
    floors: list[FloorSpec]
    rooms: list[RoomSpec]
    constraints: list[Constraint]
    room_graph: RoomGraph | None = None
    topology_plan: TopologyPlan | None = Field(
        default=None,
        description="由 RoomGraph 派生的生成前拓扑计划；可由 TopologyPlanner 填充",
    )
    access_graph: AccessGraph | None = Field(
        default=None,
        description="可达图（SpaceConnection）；Phase 2.1 填充，先于 Door",
    )
    exterior_entry_spec: ExteriorEntrySpec | None = Field(
        default=None,
        description="对外入口需求；空则用 SiteSpec.entrance_edge / road_edges",
    )
    floor_assignment: FloorAssignment | None = Field(
        default=None,
        description="楼层归属决策（可解释）；由 FloorAssignmentSolver 产出",
    )
    assumptions: list[Assumption] = Field(
        default_factory=list,
        description="规范化时采用的可解释假设",
    )
    unknowns: list[UnknownRequirement] = Field(
        default_factory=list,
        description="用户未提供且未推断的信息",
    )
    solver_config: SolverConfig = Field(default_factory=SolverConfig)
    vertical_voids: list[VerticalVoidSpec] = Field(
        default_factory=list,
        description="竖向空洞 / 对齐规格（ADR-010）",
    )

    @model_validator(mode="after")
    def _validate_vertical_voids(self) -> DesignProgram:
        if self.vertical_voids:
            validate_vertical_voids_for_floors(self.vertical_voids, self.floors)
        return self

    @model_validator(mode="after")
    def _unique_room_ids(self) -> DesignProgram:
        ids = [r.id for r in self.rooms]
        if len(ids) != len(set(ids)):
            raise ValueError("DesignProgram.rooms 含重复 id")
        return self

    def rooms_on_floor(self, floor_id: str) -> list[RoomSpec]:
        floor = next((f for f in self.floors if f.id == floor_id), None)
        if floor is None:
            return []
        if floor.room_ids:
            id_set = set(floor.room_ids)
            return [r for r in self.rooms if r.id in id_set]
        # room_ids 为空时退化为 floor_id / preference（normalize 后不应走到这里）
        return [
            r
            for r in self.rooms
            if r.floor_id == floor_id or floor_id in r.floor_preference
        ]

    def assigned_room_ids(self) -> set[str]:
        ids = {rid for fl in self.floors for rid in fl.room_ids}
        if ids:
            return ids
        return {r.id for r in self.rooms if r.floor_id}

    def unassigned_rooms(self) -> list[RoomSpec]:
        covered = self.assigned_room_ids()
        return [r for r in self.rooms if r.id not in covered]

    def room_by_id(self, room_id: str) -> RoomSpec | None:
        return next((r for r in self.rooms if r.id == room_id), None)

    @classmethod
    def from_project(cls, spec: ProjectSpec, config: SolverConfig | None = None) -> DesignProgram:
        envelope = spec.site.buildable_envelope
        if envelope is None:
            raise ValueError("SiteSpec must derive buildable_envelope")
        return cls(
            project_id=spec.id,
            site=spec.site,
            buildable=envelope,
            floors=spec.floors,
            rooms=spec.rooms,
            constraints=spec.constraints,
            vertical_voids=list(spec.vertical_voids),
            solver_config=config or SolverConfig(),
        )
