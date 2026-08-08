"""Solver 内部使用的规范化设计程序。"""

from __future__ import annotations

from pydantic import BaseModel, Field

from packages.schema.constraints import Constraint
from packages.schema.floor_assignment import FloorAssignment
from packages.schema.project import ProjectSpec
from packages.schema.requirements import Assumption, UnknownRequirement
from packages.schema.room import FloorSpec, RoomSpec
from packages.schema.site import Rect2D, SiteSpec
from packages.schema.topology import AccessGraph, RoomGraph, TopologyPlan


class SolverConfig(BaseModel):
    candidate_count: int = Field(default=32, ge=1, le=256)
    return_top_k: int = Field(default=5, ge=1, le=32)
    base_seed: int = Field(default=42)
    snap_module: float = Field(default=0.3, gt=0)
    min_diversity_threshold: float | None = Field(
        default=0.85,
        ge=0.0,
        le=1.0,
        description="Top-K 多样性阈值；None 关闭，仅按分数排序",
    )
    max_wet_stacks: int = Field(
        default=1,
        ge=1,
        le=2,
        description="技术湿区叠组上限；MVP=1，未来可扩到 2（WS1/WS2）",
    )


class DesignProgram(BaseModel):
    """
    normalize(ProjectSpec) 的输出。

    包含 solver 可直接消费的结构化程序，不含 UI 元数据。
    """

    project_id: str
    site: SiteSpec
    buildable: Rect2D
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
            solver_config=config or SolverConfig(),
        )
