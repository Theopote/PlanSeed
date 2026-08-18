"""ProjectSpec → DesignProgram 规范化。"""

from __future__ import annotations

from packages.schema.constraints import (
    AdjacencyConstraint,
    AreaConstraint,
    ConstraintKind,
    ConstraintSource,
    OrientationConstraint,
    WidthConstraint,
)
from packages.schema.program import DesignProgram, SolverConfig
from packages.schema.project import ProjectSpec
from packages.schema.room import RoomCategory
from packages.schema.topology import RoomEdge, RoomEdgeKind, RoomGraph
from solver.geometry.buildable import apply_buildable_geometry, program_footprint_area
from solver.program.floor_assignment import ensure_floor_assignment


def normalize(spec: ProjectSpec, config: SolverConfig | None = None) -> DesignProgram:
    """
    将 ProjectSpec 规范化为 DesignProgram。

    - FloorAssignmentSolver：显式约束 → 住宅规则 → floor.room_ids
    - 推导 buildable envelope
    - 从 RoomSpec 字段生成 implicit constraints（若未显式提供）
    - 构建初始 RoomGraph
    """
    assignment = ensure_floor_assignment(spec.rooms, spec.floors, spec.constraints)
    program = DesignProgram.from_project(spec, config)
    program.floor_assignment = assignment
    program.constraints = _merge_implicit_constraints(spec, program.constraints)
    program.room_graph = build_room_graph(spec)
    apply_buildable_geometry(program)
    return program


def _merge_implicit_constraints(spec: ProjectSpec, existing: list) -> list:
    by_kind_room: set[tuple] = {
        (c.kind, getattr(c, "room_id", None), getattr(c, "room_a_id", None))
        for c in existing
    }
    merged = list(existing)

    for room in spec.rooms:
        key = (ConstraintKind.AREA, room.id, None)
        if key not in by_kind_room:
            merged.append(
                AreaConstraint(
                    id=f"area-bound-{room.id}",
                    room_id=room.id,
                    min_area=room.resolved_min_area(),
                    max_area=room.resolved_max_area(),
                    target_area=room.target_area,
                    hard=True,
                    source=ConstraintSource.NORMALIZER,
                    source_key=f"rooms.{room.id}.area_bounds",
                )
            )
        if room.min_width is not None:
            key = (ConstraintKind.WIDTH, room.id, None)
            if key not in by_kind_room:
                merged.append(
                    WidthConstraint(
                        id=f"width-min-{room.id}",
                        room_id=room.id,
                        min_width=room.min_width,
                        hard=True,
                        source=ConstraintSource.NORMALIZER,
                        source_key=f"rooms.{room.id}.min_width",
                    )
                )
        if room.preferred_orientation is not None:
            key = (ConstraintKind.ORIENTATION, room.id, None)
            if key not in by_kind_room:
                merged.append(
                    OrientationConstraint(
                        id=f"orient-{room.id}",
                        room_id=room.id,
                        preferred_orientation=room.preferred_orientation.value,
                        hard=False,
                        weight=0.8,
                        source=ConstraintSource.NORMALIZER,
                        source_key=f"rooms.{room.id}.preferred_orientation",
                    )
                )

    if spec.preferences.prefer_open_kitchen_dining:
        kitchen = _find_room(spec, tags=["kitchen"]) or _find_room(spec, names=["餐厅", "厨房"])
        dining = _find_room(spec, tags=["dining"]) or _find_room(spec, names=["餐厅"])
        if kitchen and dining and kitchen.id != dining.id:
            merged.append(
                AdjacencyConstraint(
                    id="pref-kitchen-dining",
                    room_a_id=kitchen.id,
                    room_b_id=dining.id,
                    hard=False,
                    weight=1.0,
                    description="厨房与餐厅邻接偏好",
                    source=ConstraintSource.NORMALIZER,
                    source_key="preferences.prefer_open_kitchen_dining",
                )
            )

    return merged


def _find_room(spec: ProjectSpec, tags: list[str] | None = None, names: list[str] | None = None):
    for room in spec.rooms:
        if tags and any(t in room.tags for t in tags):
            return room
        if names and any(n in room.name for n in names):
            return room
    return None


def build_room_graph(spec: ProjectSpec) -> RoomGraph:
    graph = RoomGraph(room_ids=[r.id for r in spec.rooms])

    for c in spec.constraints:
        if c.kind == ConstraintKind.ADJACENCY:
            graph.add_edge(
                RoomEdge(
                    source_id=c.room_a_id,
                    target_id=c.room_b_id,
                    kind=RoomEdgeKind.ADJACENT,
                    weight=c.weight,
                )
            )
        elif c.kind == ConstraintKind.SEPARATION:
            graph.add_edge(
                RoomEdge(
                    source_id=c.room_a_id,
                    target_id=c.room_b_id,
                    kind=RoomEdgeKind.AVOID,
                    weight=c.weight,
                )
            )

    wet_ids = [r.id for r in spec.rooms if r.category == RoomCategory.WET]
    for i, a in enumerate(wet_ids):
        for b in wet_ids[i + 1 :]:
            graph.add_edge(
                RoomEdge(source_id=a, target_id=b, kind=RoomEdgeKind.NEAR, weight=0.5)
            )

    return graph


def _footprint_area(program: DesignProgram) -> float:
    return program_footprint_area(program)


def _reserved_area_on_floor(program: DesignProgram, floor_id: str) -> float:
    """该层楼梯核 + 用户声明的预扣除竖向空洞（STAIR/ATRIUM）占用面积。"""
    from packages.schema.vertical_void import (
        VerticalVoidType,
        void_covers_floor,
    )
    from solver.vertical.prededuction import (
        resolve_stair_core_spec_for_program,
        stair_void_from_program,
    )

    floor_ids = [f.id for f in program.floors]
    reserved = 0.0
    stair_void = stair_void_from_program(program)
    stair_spec = resolve_stair_core_spec_for_program(program)
    stair_area = float(stair_spec.width * stair_spec.depth)

    if len(program.floors) > 1:
        reserved += stair_area
    elif stair_void is not None and void_covers_floor(
        stair_void, floor_id, floor_ids=floor_ids
    ):
        reserved += stair_area

    for void in program.vertical_voids:
        if void.void_type in (VerticalVoidType.WET_RISER, VerticalVoidType.STAIR):
            continue
        if not void_covers_floor(void, floor_id, floor_ids=floor_ids):
            continue
        if void.width is None or void.depth is None:
            continue
        reserved += float(void.width * void.depth)
    return reserved


def _program_sum_on_floor(program: DesignProgram, floor_id: str) -> float:
    return sum(float(room.target_area) for room in program.rooms_on_floor(floor_id))


def check_program_footprint_fit(
    program: DesignProgram,
    *,
    circulation_allowance_ratio: float = 0.15,
    surplus_ratio_threshold: float = 0.3,
) -> list:
    """
  比较每层「房间目标面积 + 循环空间预留」与可建面积；超额则产出 advisory finding。

    仅依赖 DesignProgram，不依赖 LayoutCandidate；在 pipeline 生成前算一次并复用。
    见 ADR-012 / docs/proposals/program-footprint-mismatch.md。
    """
    from packages.schema.scoring import EvaluationAxis, FindingSeverity
    from solver.evaluation.findings import finding

    findings: list = []
    footprint = _footprint_area(program)
    if footprint <= 0:
        return findings

    recommended = (
        "可考虑：① 增加天井（VerticalVoidSpec / ATRIUM）消化留白；"
        "② 缩小该层用地宽或进深；"
        "③ 增加房间数量或提高现有房间目标面积。"
    )

    for floor in program.floors:
        reserved = _reserved_area_on_floor(program, floor.id)
        program_sum = _program_sum_on_floor(program, floor.id)
        circulation_allowance = footprint * circulation_allowance_ratio
        surplus = footprint - reserved - program_sum - circulation_allowance
        surplus_ratio = surplus / footprint

        if surplus_ratio <= surplus_ratio_threshold:
            continue

        label = floor.label or floor.id
        consumed = footprint - surplus
        findings.append(
            finding(
                id=f"program.footprint_underfilled:{floor.id}",
                category=EvaluationAxis.PROGRAM.value,
                severity=FindingSeverity.WARNING,
                title=f"{label} 房间需求未填满可建面积",
                message=(
                    f"{label} 可建面积 {footprint:.1f}㎡，"
                    f"房间需求+走廊预留合计约 {consumed:.1f}㎡，"
                    f"约有 {surplus:.1f}㎡（占比 {surplus_ratio * 100:.0f}%）"
                    "难以被当前需求自然消化"
                ),
                metric="program_footprint_surplus_ratio",
                measured_value=round(surplus_ratio, 4),
                recommended_action=recommended,
            )
        )
    return findings
