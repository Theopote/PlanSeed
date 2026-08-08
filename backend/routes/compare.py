"""POST /api/compare — 候选评价差分（Python 单一事实源；前端只展示）。"""

from __future__ import annotations

from fastapi import APIRouter

from backend.schemas.api import CompareRequest, CompareResponse
from solver.evaluation.compare import compare_evaluations

router = APIRouter(tags=["compare"])


@router.post("/api/compare", response_model=CompareResponse)
def compare_candidates(body: CompareRequest) -> CompareResponse:
    cmp = compare_evaluations(
        body.evaluation_a,
        body.evaluation_b,
        label_a=body.label_a,
        label_b=body.label_b,
    )
    return CompareResponse(
        label_a=cmp.label_a,
        label_b=cmp.label_b,
        rows=[
            {
                "key": r.key,
                "label": r.label,
                "score_a": r.score_a,
                "score_b": r.score_b,
            }
            for r in cmp.rows
        ],
        advantages_a=list(cmp.advantages_a),
        advantages_b=list(cmp.advantages_b),
    )
