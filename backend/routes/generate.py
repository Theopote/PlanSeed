"""方案生成端点 — 编排 only，不重评。"""

from __future__ import annotations

from fastapi import APIRouter
from packages.schema.identity import solver_identity

from backend.schemas.api import (
    MAX_REJECTED_SAMPLES,
    GenerateRequest,
    GenerateResponse,
    PartialRegenerateRequest,
)
from backend.services.generation import (
    generate_layouts,
    resolve_partial_regenerate,
    resolve_solve_input,
)
from backend.services.serialization import (
    serialize_candidate,
    serialize_program_summary,
    serialize_rejected,
)

router = APIRouter(tags=["generate"])


@router.post("/api/generate", response_model=GenerateResponse)
def generate(body: GenerateRequest) -> GenerateResponse:
    resolved = resolve_solve_input(body)
    program = resolved.program
    result = generate_layouts(program, locks=body.locks)
    candidates = [
        serialize_candidate(program, cand, i)
        for i, cand in enumerate(result.top_candidates)
    ]
    invalid = [
        c
        for c in result.all_candidates
        if c.validation is not None and not c.validation.valid
    ]
    invalid.sort(key=lambda c: c.seed)
    rejected_samples = [
        serialize_rejected(c) for c in invalid[:MAX_REJECTED_SAMPLES]
    ]
    return GenerateResponse(
        generated=result.generated,
        valid=result.valid,
        rejected=result.rejected,
        program_summary=serialize_program_summary(program),
        requirement_spec=resolved.requirement_spec,
        candidates=candidates,
        violation_summary=dict(result.violation_summary),
        rejected_candidates=rejected_samples,
        solver_identity=solver_identity(),
    )


@router.post("/api/regenerate/partial", response_model=GenerateResponse)
def regenerate_partial(body: PartialRegenerateRequest) -> GenerateResponse:
    """v0.2-B：RegenerationScope 驱动的局部重生成。"""
    resolved = resolve_solve_input(body)
    program = resolved.program
    locks, _scope = resolve_partial_regenerate(body, program)
    result = generate_layouts(program, locks=locks)
    candidates = [
        serialize_candidate(program, cand, i)
        for i, cand in enumerate(result.top_candidates)
    ]
    invalid = [
        c
        for c in result.all_candidates
        if c.validation is not None and not c.validation.valid
    ]
    invalid.sort(key=lambda c: c.seed)
    rejected_samples = [
        serialize_rejected(c) for c in invalid[:MAX_REJECTED_SAMPLES]
    ]
    return GenerateResponse(
        generated=result.generated,
        valid=result.valid,
        rejected=result.rejected,
        program_summary=serialize_program_summary(program),
        requirement_spec=resolved.requirement_spec,
        candidates=candidates,
        violation_summary=dict(result.violation_summary),
        rejected_candidates=rejected_samples,
        solver_identity=solver_identity(),
    )
