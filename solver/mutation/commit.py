"""MutationCommitPipeline — 编辑几何后重算派生状态（不经 Guillotine）。"""

from __future__ import annotations

from packages.schema.identity import (
    EVALUATION_VERSION,
    GENERATOR_VERSION,
    SOLVER_VERSION,
)
from packages.schema.layout import (
    CandidateProvenance,
    FloorLayout,
    LayoutCandidate,
    PlacementRect,
    PlacementSource,
    RoomPlacement,
    ZonePlacement,
)
from packages.schema.locks import LayoutLocks
from packages.schema.program import DesignProgram
from packages.schema.scoring import DesignScore

from solver.circulation.exterior_entry import resolve_exterior_entry
from solver.constraints.checker import ConstraintEvaluationResult
from solver.constraints.checker_impl import DefaultConstraintChecker
from solver.evaluation.score import CompositeEvaluator
from solver.locks import check_lock_invariants
from solver.topology.derive_access import ensure_access_graph


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
) -> LayoutCandidate:
    """由会话 placements 重建 LayoutCandidate；清空派生态。"""
    by_floor: dict[str, list[RoomPlacement]] = {}
    for p in placements:
        # 用 program 补全 name/category
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
    # 程序未列出的楼层（防御）
    for fid, pls in by_floor.items():
        if not any(f.floor_id == fid for f in floors):
            floors.append(FloorLayout(floor_id=fid, placements=list(pls)))

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

    hydrate → exterior entry → checker（门洞 + realized access）
    → optional lock invariants → evaluate（仅 valid）

    **不**调用 resolve_required_connections（避免回改用户几何）。
    """
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
    )

    resolve_exterior_entry(program, candidate)

    checker = DefaultConstraintChecker()
    validation = checker.check(program, candidate)

    locks = locks or LayoutLocks()
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
    candidate.provenance = CandidateProvenance(
        solver_version=SOLVER_VERSION,
        generator_version=GENERATOR_VERSION,
        evaluation_version=EVALUATION_VERSION,
    )
    candidate.metrics["solver_version"] = SOLVER_VERSION
    candidate.metrics["generator_version"] = GENERATOR_VERSION
    candidate.metrics["evaluation_version"] = EVALUATION_VERSION
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
