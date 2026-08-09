"""解析需求并调用 solver pipeline。"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException
from packages.schema.locks import LayoutLocks
from packages.schema.program import DesignProgram
from packages.schema.requirements import RequirementSpec
from solver.fixtures.benchmark import benchmark_program, benchmark_requirement_spec
from solver.pipeline import PipelineResult, run_pipeline
from solver.program.requirements_normalize import (
    IncompleteRequirementsError,
    normalize_requirements_to_program,
)

from backend.schemas.api import GenerateRequest
from backend.services.form_requirements import ensure_spaces_for_solve


@dataclass(frozen=True)
class ResolvedSolveInput:
    """求解输入：DesignProgram + 可追踪的 RequirementSpec（ensure_spaces 后）。"""

    program: DesignProgram
    requirement_spec: RequirementSpec | None


def resolve_solve_input(body: GenerateRequest) -> ResolvedSolveInput:
    """从请求体得到 DesignProgram 与 canonical RequirementSpec。"""
    try:
        if body.use_benchmark:
            spec = benchmark_requirement_spec()
            program = benchmark_program()
        elif body.requirements is not None:
            spec = ensure_spaces_for_solve(body.requirements)
            program = normalize_requirements_to_program(spec)
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

    apply_solver_overrides(program, body)
    return ResolvedSolveInput(program=program, requirement_spec=spec)


def apply_solver_overrides(program: DesignProgram, body: GenerateRequest) -> None:
    if body.candidate_count is not None:
        program.solver_config.candidate_count = body.candidate_count
    if body.return_top_k is not None:
        program.solver_config.return_top_k = body.return_top_k
    if body.base_seed is not None:
        program.solver_config.base_seed = body.base_seed


def resolve_program(body: GenerateRequest) -> DesignProgram:
    """兼容旧调用；新代码请用 resolve_solve_input。"""
    return resolve_solve_input(body).program


def generate_layouts(
    program: DesignProgram,
    locks: LayoutLocks | None = None,
) -> PipelineResult:
    """单次评价在 pipeline 内完成；此处不调用 CompositeEvaluator。

    Alpha 产品路径：非 experimental 时钉死 ``alpha-stable``（Guillotine + axis + …）。
    """
    from packages.schema.solver_profile import pin_alpha_stable_if_needed
    from solver.locks import LockValidationError

    cfg = pin_alpha_stable_if_needed(program.solver_config)
    if cfg is not program.solver_config:
        program = program.model_copy(update={"solver_config": cfg})

    try:
        return run_pipeline(program, locks=locks)
    except LockValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "message": str(exc),
                "issues": [
                    {"code": i.code, "message": i.message, "hard": i.hard}
                    for i in exc.result.issues
                ],
            },
        ) from exc
