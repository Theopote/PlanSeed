"""MutationCommitPipeline — 编辑几何后重算派生状态（不经 Guillotine）。"""

from __future__ import annotations

from packages.schema.identity import (
    EVALUATION_VERSION,
    SOLVER_VERSION,
)
from packages.schema.layout import (
    FloorLayout,
    LayoutCandidate,
    PlacementRect,
    PlacementSource,
    RoomPlacement,
    ZonePlacement,
)
from packages.schema.locks import LayoutLocks
from packages.schema.program import DesignProgram
from packages.schema.provenance import (
    assignment_strategy_for,
    geometry_backend_for,
    merge_solver_provenance,
    provenance_to_metrics,
)
from packages.schema.scoring import DesignScore

from solver.circulation.exterior_entry import resolve_exterior_entry
from solver.constraints.checker import ConstraintEvaluationResult
from solver.constraints.checker_impl import DefaultConstraintChecker
from solver.evaluation.score import CompositeEvaluator
from solver.locks import check_lock_invariants
from solver.topology.derive_access import ensure_access_graph


def is_stair_placement(p: RoomPlacement) -> bool:
    return p.room_id.startswith("stair-") or (
        p.category == "circulation" and p.name is not None and "楼梯" in p.name
    )


def derive_stair_core_from_placements(
    floors: list[FloorLayout],
    *,
    core_placement: str | None = None,
) -> list[FloorLayout]:
    """
    从 stair-* placements 回填 FloorLayout.stair_*（评价当前几何）。

    core_placement 可来自 locks.stair；无则保持 None。
    """
    out: list[FloorLayout] = []
    for fl in floors:
        stair = next((p for p in fl.placements if is_stair_placement(p)), None)
        if stair is None:
            out.append(fl)
            continue
        r = stair.rect
        out.append(
            fl.model_copy(
                update={
                    "stair_x0": r.x,
                    "stair_y0": r.y,
                    "stair_x1": r.x + r.width,
                    "stair_y1": r.y + r.depth,
                    "core_placement": core_placement
                    if core_placement is not None
                    else fl.core_placement,
                }
            )
        )
    return out


def hydrate_candidate_from_placements(
    *,
    program: DesignProgram,
    placements: list[RoomPlacement],
    candidate_id: str,
    seed: int,
    zones: list[ZonePlacement] | None = None,
    variant_parent_id: str | None = None,
    variant_generation: int = 0,
    lock_snapshot_id: str | None = None,
    core_placement: str | None = None,
) -> LayoutCandidate:
    """由会话 placements 重建 LayoutCandidate；清空门洞/评价派生态，推导楼梯 metadata。"""
    by_floor: dict[str, list[RoomPlacement]] = {}
    for p in placements:
        room = program.room_by_id(p.room_id)
        enriched = p.model_copy(
            update={
                "name": p.name or (room.name if room else p.room_id),
                "category": p.category
                or (room.category.value if room else None),
            }
        )
        by_floor.setdefault(p.floor_id, []).append(enriched)

    floors: list[FloorLayout] = []
    for fl in program.floors:
        floors.append(
            FloorLayout(
                floor_id=fl.id,
                placements=list(by_floor.get(fl.id, [])),
            )
        )
    for fid, pls in by_floor.items():
        if not any(f.floor_id == fid for f in floors):
            floors.append(FloorLayout(floor_id=fid, placements=list(pls)))

    floors = derive_stair_core_from_placements(
        floors, core_placement=core_placement
    )

    return LayoutCandidate(
        id=candidate_id,
        seed=seed,
        floors=floors,
        zone_placements=list(zones or []),
        door_openings=[],
        exterior_entry=None,
        repair_records=[],
        realized_connections=[],
        validation=None,
        evaluation=None,
        score=None,
        variant_parent_id=variant_parent_id,
        variant_generation=variant_generation,
        lock_snapshot_id=lock_snapshot_id,
        metrics={},
    )


def revalidate_candidate(
    *,
    program: DesignProgram,
    placements: list[RoomPlacement],
    locks: LayoutLocks | None = None,
    candidate_id: str = "revalidated",
    seed: int = 0,
    zones: list[ZonePlacement] | None = None,
    variant_parent_id: str | None = None,
    variant_generation: int = 0,
    lock_snapshot_id: str | None = None,
) -> LayoutCandidate:
    """
    用户编辑几何后的权威重算：

    hydrate（含 stair 推导）→ exterior entry → checker
    → lock invariants → evaluate（仅 valid）

    **不**调用 resolve_required_connections（避免回改用户几何）。
    """
    locks = locks or LayoutLocks()
    ensure_access_graph(program)
    candidate = hydrate_candidate_from_placements(
        program=program,
        placements=placements,
        candidate_id=candidate_id,
        seed=seed,
        zones=zones,
        variant_parent_id=variant_parent_id,
        variant_generation=variant_generation,
        lock_snapshot_id=lock_snapshot_id,
        core_placement=locks.stair.core_placement if locks.stair else None,
    )

    resolve_exterior_entry(program, candidate)
    from solver.topology.windows import place_window_openings

    place_window_openings(program, candidate)

    checker = DefaultConstraintChecker()
    validation = checker.check(program, candidate)

    if locks.rooms or locks.stair or locks.zones:
        inv = check_lock_invariants(candidate, locks)
        if inv.hard_violations or inv.soft_violations or inv.warnings:
            merged = ConstraintEvaluationResult(
                hard_violations=list(validation.hard_violations),
                soft_violations=list(validation.soft_violations),
                warnings=list(validation.warnings),
            )
            merged.extend(inv)
            validation = merged.to_candidate_validation()
        candidate.metrics["lock_invariant_ok"] = not bool(inv.hard_violations)
    else:
        candidate.metrics["lock_invariant_ok"] = True

    candidate.validation = validation
    prev = candidate.provenance
    candidate.provenance = merge_solver_provenance(
        prev,
        solver_version=SOLVER_VERSION,
        evaluation_version=EVALUATION_VERSION,
        assignment_strategy=assignment_strategy_for(program),
        geometry_backend=geometry_backend_for(program),
    )
    candidate.metrics.update(provenance_to_metrics(candidate.provenance))
    candidate.metrics["revision_source"] = "mutation_revalidate"

    if validation.valid:
        evaluation: DesignScore = CompositeEvaluator().evaluate(program, candidate)
        candidate.evaluation = evaluation
        candidate.score = evaluation.total_score
    else:
        candidate.evaluation = None
        candidate.score = None

    return candidate


def placement_from_flat(
    *,
    room_id: str,
    floor_id: str,
    x: float,
    y: float,
    width: float,
    depth: float,
) -> RoomPlacement:
    source = (
        PlacementSource.GENERATED
        if room_id.startswith("stair-") or room_id.startswith("circ-")
        else PlacementSource.PROGRAM
    )
    return RoomPlacement(
        room_id=room_id,
        floor_id=floor_id,
        rect=PlacementRect(x=x, y=y, width=width, depth=depth),
        source=source,
        name=room_id,
    )
