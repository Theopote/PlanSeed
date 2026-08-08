"""方案生成端点 — 编排 only，不重评。"""

from __future__ import annotations

from fastapi import APIRouter

from backend.schemas.api import GenerateRequest, GenerateResponse
from backend.services.generation import generate_layouts, resolve_program
from backend.services.serialization import (
    serialize_candidate,
    serialize_program_summary,
)

router = APIRouter(tags=["generate"])


@router.post("/api/generate", response_model=GenerateResponse)
def generate(body: GenerateRequest) -> GenerateResponse:
    program = resolve_program(body)
    result = generate_layouts(program)
    candidates = [
        serialize_candidate(program, cand, i)
        for i, cand in enumerate(result.top_candidates)
    ]
    return GenerateResponse(
        generated=result.generated,
        valid=result.valid,
        rejected=result.rejected,
        program_summary=serialize_program_summary(program),
        candidates=candidates,
    )
