"""CP-SAT 楼层归属 — Phase 8.3 research。

架构位置：
  RequirementSpec / ProjectSpec
        ↓
  CP-SAT Floor Assignment（本模块，opt-in）
        ↓
  DesignProgram.floors.room_ids
        ↓
  Geometric Packing（Guillotine / MaxRect）
        ↓
  Repair → Evaluation

默认 normalize 仍走 ``FloorAssignmentSolver`` 启发式；本模块不自动接入。
"""

from __future__ import annotations

from dataclasses import dataclass

from packages.schema.constraints import (
    AdjacencyConstraint,
    Constraint,
    ConstraintKind,
    FloorConstraint,
)
from packages.schema.floor_assignment import (
    FloorAssignment,
    FloorAssignmentSource,
    RoomFloorDecision,
)
from packages.schema.room import FloorSpec, RoomCategory, RoomSpec

from solver.semantics.roles import (
    is_garage,
    is_kitchen,
    is_master_bedroom,
)


class CpSatUnavailableError(RuntimeError):
    """未安装 ortools（``uv sync --group research``）。"""


class CpSatFloorAssignError(RuntimeError):
    """模型不可行或求解失败。"""


@dataclass(frozen=True)
class CpSatFloorAssigner:
    """用 CP-SAT 求解楼层归属（硬约束 + 软偏好）。"""

    time_limit_s: float = 2.0
    # 软目标权重
    w_preference: int = 20
    w_adjacency_same_floor: int = 15
    w_kitchen_ground: int = 10
    w_garage_ground: int = 12
    w_master_upper: int = 8

    def solve(
        self,
        rooms: list[RoomSpec],
        floors: list[FloorSpec],
        constraints: list[Constraint] | None = None,
    ) -> FloorAssignment:
        try:
            from ortools.sat.python import cp_model
        except ImportError as exc:
            raise CpSatUnavailableError(
                "ortools 未安装。研究路径：uv sync --group research"
            ) from exc

        if not floors:
            raise CpSatFloorAssignError("至少需要一层")
        if not rooms:
            return FloorAssignment(decisions=[])

        constraints = constraints or []
        floor_ids = [f.id for f in floors]
        ground = floor_ids[0]
        upper = floor_ids[min(1, len(floor_ids) - 1)]
        room_ids = [r.id for r in rooms]
        room_by_id = {r.id: r for r in rooms}

        # 硬固定：explicit sources
        fixed: dict[str, str] = {}
        for c in constraints:
            if c.kind == ConstraintKind.FLOOR and isinstance(c, FloorConstraint):
                if c.room_id in room_by_id and c.floor_id in floor_ids:
                    fixed[c.room_id] = c.floor_id
        for fl in floors:
            for rid in fl.room_ids:
                if rid in room_by_id and rid not in fixed:
                    fixed[rid] = fl.id
        for room in rooms:
            if room.floor_id and room.floor_id in floor_ids and room.id not in fixed:
                fixed[room.id] = room.floor_id

        model = cp_model.CpModel()
        # x[r,f] = room r on floor f
        x: dict[tuple[str, str], cp_model.IntVar] = {}
        for rid in room_ids:
            for fid in floor_ids:
                x[rid, fid] = model.NewBoolVar(f"x_{rid}_{fid}")

        for rid in room_ids:
            model.Add(sum(x[rid, fid] for fid in floor_ids) == 1)
            if rid in fixed:
                model.Add(x[rid, fixed[rid]] == 1)

        soft_terms: list = []

        # floor_preference
        for room in rooms:
            if room.id in fixed:
                continue
            for pref in room.floor_preference:
                if pref in floor_ids:
                    soft_terms.append(self.w_preference * x[room.id, pref])
                    break

        # adjacency → 同层偏好
        for c in constraints:
            if c.kind != ConstraintKind.ADJACENCY or not isinstance(c, AdjacencyConstraint):
                continue
            a, b = c.room_a_id, c.room_b_id
            if a not in room_by_id or b not in room_by_id:
                continue
            for fid in floor_ids:
                both = model.NewBoolVar(f"adj_{a}_{b}_{fid}")
                # both <=> x[a] ∧ x[b]
                model.Add(both <= x[a, fid])
                model.Add(both <= x[b, fid])
                model.Add(both >= x[a, fid] + x[b, fid] - 1)
                soft_terms.append(self.w_adjacency_same_floor * both)

        # 住宅启发式软约束
        for room in rooms:
            if room.id in fixed:
                continue
            if is_kitchen(room) or room.category == RoomCategory.PUBLIC:
                soft_terms.append(self.w_kitchen_ground * x[room.id, ground])
            if is_garage(room):
                soft_terms.append(self.w_garage_ground * x[room.id, ground])
            if is_master_bedroom(room) and upper != ground:
                soft_terms.append(self.w_master_upper * x[room.id, upper])

        if soft_terms:
            model.Maximize(sum(soft_terms))

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = float(self.time_limit_s)
        status = solver.Solve(model)
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            raise CpSatFloorAssignError(
                f"CP-SAT floor assignment failed: status={solver.StatusName(status)}"
            )

        decisions: list[RoomFloorDecision] = []
        for rid in room_ids:
            chosen = next(fid for fid in floor_ids if solver.Value(x[rid, fid]) == 1)
            if rid in fixed:
                source = FloorAssignmentSource.EXPLICIT_FLOOR_ID
                if any(
                    isinstance(c, FloorConstraint) and c.room_id == rid
                    for c in constraints
                ):
                    source = FloorAssignmentSource.EXPLICIT_CONSTRAINT
                reason = f"hard-fixed → {chosen}"
                rule_id = "cpsat.hard_fixed"
            else:
                source = FloorAssignmentSource.CPSAT
                reason = f"CP-SAT assignment → {chosen}"
                rule_id = "cpsat.floor_assign"
            decisions.append(
                RoomFloorDecision(
                    room_id=rid,
                    floor_id=chosen,
                    source=source,
                    source_key="assignment.cpsat_floor",
                    rule_id=rule_id,
                    reason=reason,
                )
            )

        return FloorAssignment(decisions=decisions)


def assign_floors_cpsat(
    rooms: list[RoomSpec],
    floors: list[FloorSpec],
    constraints: list[Constraint] | None = None,
    *,
    time_limit_s: float = 2.0,
) -> FloorAssignment:
    """便捷入口。"""
    return CpSatFloorAssigner(time_limit_s=time_limit_s).solve(
        rooms, floors, constraints
    )
