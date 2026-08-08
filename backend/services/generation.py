"""解析需求并调用 solver pipeline。"""

from __future__ import annotations

from fastapi import HTTPException
from packages.schema.locks import LayoutLocks
from packages.schema.program import DesignProgram
from solver.fixtures.benchmark import benchmark_program
from solver.pipeline import PipelineResult, run_pipeline
from solver.program.requirements_normalize import (
    IncompleteRequirementsError,
    normalize_requirements_to_program,
)

from backend.schemas.api import GenerateRequest
from backend.services.form_requirements import ensure_spaces_for_solve


def resolve_program(body: GenerateRequest) -> DesignProgram:
    """从请求体得到 DesignProgram；错误转为 HTTPException。"""
    try:
        if body.use_benchmark:
            program = benchmark_program()
        elif body.requirements is not None:
            requirements = ensure_spaces_for_solve(body.requirements)
            program = normalize_requirements_to_program(requirements)
        else:
            raise HTTPException(
                status_code=400,
                detail="提供 requirements 或设 use_benchmark=true",
            )
    except IncompleteRequirementsError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001 — 表单/规范化错误回给 UI
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if body.candidate_count is not None:
        program.solver_config.candidate_count = body.candidate_count
    if body.return_top_k is not None:
        program.solver_config.return_top_k = body.return_top_k
    if body.base_seed is not None:
        program.solver_config.base_seed = body.base_seed
    return program


def generate_layouts(
    program: DesignProgram,
    locks: LayoutLocks | None = None,
) -> PipelineResult:
    """单次评价在 pipeline 内完成；此处不调用 CompositeEvaluator。"""
    return run_pipeline(program, locks=locks)
