"""Program / Candidate → API payload（含 SVG）。"""

from __future__ import annotations

from packages.schema.identity import (
    EVALUATION_VERSION,
    GENERATOR_VERSION,
    SOLVER_VERSION,
)
from packages.schema.layout import LayoutCandidate
from packages.schema.program import DesignProgram
from solver.visualize.svg import render_candidate_svg, render_floor_svg

from backend.schemas.api import (
    CandidatePayload,
    CandidateProvenance,
    ProgramSummary,
    RejectedCandidatePayload,
    RoomPlacementPayload,
    RoomSummary,
    ZonePlacementPayload,
)


def _label_for(index: int) -> str:
    return chr(ord("A") + index) if index < 26 else f"C{index}"


def serialize_program_summary(program: DesignProgram) -> ProgramSummary:
    return ProgramSummary(
        project_id=program.project_id,
        site_width=program.site.width,
        site_depth=program.site.depth,
        floor_count=len(program.floors),
        rooms=[
            RoomSummary(
                id=r.id,
                name=r.name,
                category=r.category.value,
                target_area=r.target_area,
                floor_id=r.floor_id,
            )
            for r in program.rooms
        ],
        floors=[
            {"id": fl.id, "label": fl.label, "room_ids": list(fl.room_ids)}
            for fl in program.floors
        ],
        assumptions=[a.model_dump() for a in program.assumptions],
        unknowns=[u.model_dump() for u in program.unknowns],
    )


def serialize_candidate(
    program: DesignProgram,
    cand: LayoutCandidate,
    index: int,
) -> CandidatePayload:
    labels = {fl.id: fl.label or fl.id for fl in program.floors}
    targets = {r.id: r.target_area for r in program.rooms}
    render_kw = dict(
        floor_width=program.buildable.width,
        floor_depth=program.buildable.depth,
        floor_labels=labels,
        target_areas=targets,
        site=program.site,
        access_graph=program.access_graph,
    )
    svg = render_candidate_svg(cand, **render_kw)
    floor_svgs = {
        fl.floor_id: render_floor_svg(cand, fl.floor_id, **render_kw)
        for fl in cand.floors
    }
    validation = None
    if cand.validation is not None:
        validation = {
            "valid": cand.validation.valid,
            "hard_violations": [
                v.model_dump() for v in cand.validation.hard_violations
            ],
            "soft_violations": [
                v.model_dump() for v in cand.validation.soft_violations
            ],
            "warnings": list(cand.validation.warnings),
        }
    return CandidatePayload(
        id=cand.id,
        seed=cand.seed,
        score=cand.score,
        label=_label_for(index),
        svg=svg,
        floor_svgs=floor_svgs,
        design_score=cand.evaluation,
        validation=validation,
        metrics=dict(cand.metrics),
        provenance=_provenance_payload(cand),
        variant_parent_id=cand.variant_parent_id,
        variant_generation=cand.variant_generation,
        lock_snapshot_id=cand.lock_snapshot_id,
        revision_status="generated",
        mutations=[],
        placements=_placements_payload(cand),
        zones=_zones_payload(cand),
    )


def _placements_payload(cand: LayoutCandidate) -> list[RoomPlacementPayload]:
    out: list[RoomPlacementPayload] = []
    for fl in cand.floors:
        for p in fl.placements:
            r = p.rect
            out.append(
                RoomPlacementPayload(
                    room_id=p.room_id,
                    floor_id=p.floor_id,
                    x=r.x,
                    y=r.y,
                    width=r.width,
                    depth=r.depth,
                    area=round(r.area, 2),
                )
            )
    return out


def _zones_payload(cand: LayoutCandidate) -> list[ZonePlacementPayload]:
    out: list[ZonePlacementPayload] = []
    for z in cand.zone_placements:
        r = z.rect
        kind = z.kind or z.zone
        out.append(
            ZonePlacementPayload(
                id=z.id,
                zone=z.zone,
                kind=kind,
                floor_id=z.floor_id,
                x=r.x,
                y=r.y,
                width=r.width,
                depth=r.depth,
                room_ids=list(z.room_ids),
            )
        )
    return out


def _provenance_payload(cand: LayoutCandidate) -> CandidateProvenance | None:
    if cand.provenance is not None:
        return CandidateProvenance(
            solver_version=cand.provenance.solver_version,
            generator_version=cand.provenance.generator_version,
            evaluation_version=cand.provenance.evaluation_version
            or str(cand.metrics.get("evaluation_version") or EVALUATION_VERSION),
        )
    # 兼容旧候选：从 metrics 回填
    sv = cand.metrics.get("solver_version") or SOLVER_VERSION
    gv = cand.metrics.get("generator_version") or GENERATOR_VERSION
    ev = cand.metrics.get("evaluation_version") or EVALUATION_VERSION
    return CandidateProvenance(
        solver_version=str(sv),
        generator_version=str(gv),
        evaluation_version=str(ev),
    )


def serialize_rejected(cand: LayoutCandidate) -> RejectedCandidatePayload:
    """仅 hard-fail 摘要；不渲染 SVG、不评价。"""
    reasons: list[str] = []
    constraint_ids: list[str] = []
    if cand.validation is not None:
        for v in cand.validation.hard_violations:
            if v.message:
                reasons.append(v.message)
            if v.constraint_id:
                constraint_ids.append(v.constraint_id)
    return RejectedCandidatePayload(
        id=cand.id,
        seed=cand.seed,
        reasons=reasons,
        constraint_ids=constraint_ids,
    )
