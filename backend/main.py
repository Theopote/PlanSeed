"""PlanSeed FastAPI — 桌面 UI 最小后端。"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from packages.schema.requirements import RequirementSpec
from packages.schema.scoring import DesignScore
from solver.evaluation.score import CompositeEvaluator
from solver.fixtures.benchmark import benchmark_program
from solver.pipeline import run_pipeline
from solver.program.requirements_normalize import (
    IncompleteRequirementsError,
    normalize_requirements_to_program,
)
from solver.visualize.svg import render_candidate_svg

app = FastAPI(title="PlanSeed API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:1420",
        "http://127.0.0.1:1420",
        "tauri://localhost",
        "https://tauri.localhost",
        "http://tauri.localhost",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class GenerateRequest(BaseModel):
    """生成请求：基准案例或 RequirementSpec。"""

    use_benchmark: bool = False
    requirements: RequirementSpec | None = None
    # 调试时可压低候选数（仍受 SolverConfig 上限逻辑约束时由 program 覆盖）
    candidate_count: int | None = Field(default=None, ge=1, le=64)
    return_top_k: int | None = Field(default=None, ge=1, le=16)


class RoomSummary(BaseModel):
    id: str
    name: str
    category: str
    target_area: float
    floor_id: str | None = None


class ProgramSummary(BaseModel):
    project_id: str
    site_width: float
    site_depth: float
    floor_count: int
    rooms: list[RoomSummary]
    floors: list[dict[str, Any]]
    assumptions: list[dict[str, Any]] = Field(default_factory=list)
    unknowns: list[dict[str, Any]] = Field(default_factory=list)


class CandidatePayload(BaseModel):
    id: str
    seed: int
    score: float | None
    label: str
    svg: str
    design_score: DesignScore | None = None
    validation: dict[str, Any] | None = None
    metrics: dict[str, Any] = Field(default_factory=dict)


class GenerateResponse(BaseModel):
    generated: int
    valid: int
    rejected: int
    program_summary: ProgramSummary
    candidates: list[CandidatePayload]


def _label_for(index: int) -> str:
    return chr(ord("A") + index) if index < 26 else f"C{index}"


@app.get("/api/health")
def health() -> dict[str, bool | str]:
    return {"ok": True, "service": "planseed"}


@app.post("/api/generate", response_model=GenerateResponse)
def generate(body: GenerateRequest) -> GenerateResponse:
    try:
        if body.use_benchmark:
            program = benchmark_program()
        elif body.requirements is not None:
            program = normalize_requirements_to_program(body.requirements)
        else:
            raise HTTPException(
                status_code=400,
                detail="提供 requirements 或设 use_benchmark=true",
            )
    except IncompleteRequirementsError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 — 表单/规范化错误回给 UI
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if body.candidate_count is not None:
        program.solver_config.candidate_count = body.candidate_count
    if body.return_top_k is not None:
        program.solver_config.return_top_k = body.return_top_k

    result = run_pipeline(program)
    evaluator = CompositeEvaluator()
    labels = {fl.id: fl.label or fl.id for fl in program.floors}
    targets = {r.id: r.target_area for r in program.rooms}
    w = program.buildable.width
    d = program.buildable.depth

    candidates: list[CandidatePayload] = []
    for i, cand in enumerate(result.top_candidates):
        design_score: DesignScore | None = None
        if cand.validation is not None and cand.validation.valid:
            design_score = evaluator.evaluate(program, cand)
            cand.score = design_score.total_score
        svg = render_candidate_svg(
            cand,
            floor_width=w,
            floor_depth=d,
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
        candidates.append(
            CandidatePayload(
                id=cand.id,
                seed=cand.seed,
                score=cand.score,
                label=_label_for(i),
                svg=svg,
                design_score=design_score,
                validation=validation,
                metrics=dict(cand.metrics),
            )
        )

    summary = ProgramSummary(
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

    return GenerateResponse(
        generated=result.generated,
        valid=result.valid,
        rejected=result.rejected,
        program_summary=summary,
        candidates=candidates,
    )
