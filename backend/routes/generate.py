"""方案生成端点 — 编排 only，不重评。"""

from __future__ import annotations

from fastapi import APIRouter
from packages.schema.identity import solver_identity

from backend.schemas.api import (
    MAX_REJECTED_SAMPLES,
    GenerateRequest,
    GenerateResponse,
)
from backend.services.generation import generate_layouts, resolve_program
from backend.services.serialization import (
    serialize_candidate,
    serialize_program_summary,
    serialize_rejected,
)

router = APIRouter(tags=["generate"])


@router.post("/api/generate", response_model=GenerateResponse)
def generate(body: GenerateRequest) -> GenerateResponse:
    program = resolve_program(body)
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
        candidates=candidates,
        violation_summary=dict(result.violation_summary),
        rejected_candidates=rejected_samples,
        solver_identity=solver_identity(),
    )
