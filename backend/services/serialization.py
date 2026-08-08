"""Program / Candidate → API payload（含 SVG）。"""

from __future__ import annotations

from packages.schema.layout import LayoutCandidate
from packages.schema.program import DesignProgram
from solver.visualize.svg import render_candidate_svg

from backend.schemas.api import CandidatePayload, ProgramSummary, RoomSummary


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
    svg = render_candidate_svg(
        cand,
        floor_width=program.buildable.width,
        floor_depth=program.buildable.depth,
        floor_labels=labels,
        target_areas=targets,
        site=program.site,
        access_graph=program.access_graph,
    )
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
        design_score=cand.evaluation,
        validation=validation,
        metrics=dict(cand.metrics),
    )
