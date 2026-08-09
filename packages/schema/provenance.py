"""Solver 2.0 算法溯源 — SolverProvenance。

老三件套（solver / generator / evaluation）不足以解释：
generator strategy · selection · assignment · geometry backend。

CandidateProvenance 为兼容别名（同构）。
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from packages.schema.floor_assignment import FloorAssignmentSource
from packages.schema.identity import (
    EVALUATION_VERSION,
    GENERATOR_VERSION,
    SELECTION_VERSION,
    SOLVER_VERSION,
    selection_strategy_for,
    selection_version_for,
)

# 稳定策略标识（≠ version 字符串）
DEFAULT_GENERATOR_STRATEGY = "guillotine"
DEFAULT_SELECTION_STRATEGY = "axis-diverse"
DEFAULT_ASSIGNMENT_STRATEGY = "heuristic"
DEFAULT_GEOMETRY_BACKEND = "rect"

GEOMETRY_BACKEND_RECT = "rect"
GEOMETRY_BACKEND_SHAPELY_ORTHOGONAL = "shapely-orthogonal"
ASSIGNMENT_HEURISTIC = "heuristic"
ASSIGNMENT_CPSAT = "cpsat"


class SolverProvenance(BaseModel):
    """完整求解溯源；写入候选 / 报告 / 快照 / benchmark。"""

    solver_version: str = Field(default=SOLVER_VERSION)
    generator_strategy: str = Field(
        default=DEFAULT_GENERATOR_STRATEGY,
        description="guillotine | maxrect | …",
    )
    generator_version: str = Field(default=GENERATOR_VERSION)
    selection_strategy: str | None = Field(
        default=None,
        description="axis-diverse | pareto | score | geom-diverse；ranking 后写入",
    )
    selection_version: str | None = Field(
        default=None,
        description="选优规则包版本；与 selection_strategy 成对",
    )
    evaluation_version: str | None = Field(
        default=None,
        description="评价完成后写入；生成瞬间可为 None",
    )
    assignment_strategy: str = Field(
        default=DEFAULT_ASSIGNMENT_STRATEGY,
        description="heuristic | cpsat",
    )
    geometry_backend: str = Field(
        default=DEFAULT_GEOMETRY_BACKEND,
        description="rect | shapely-orthogonal",
    )


# 兼容旧名：LayoutCandidate.provenance 类型与序列化仍可用 CandidateProvenance
CandidateProvenance = SolverProvenance


def assignment_strategy_for(program: Any) -> str:
    """从 DesignProgram.floor_assignment 推断赋值策略。"""
    fa = getattr(program, "floor_assignment", None)
    if fa is None:
        return ASSIGNMENT_HEURISTIC
    decisions = getattr(fa, "decisions", None) or []
    if any(getattr(d, "source", None) == FloorAssignmentSource.CPSAT for d in decisions):
        return ASSIGNMENT_CPSAT
    return ASSIGNMENT_HEURISTIC


def geometry_backend_for(program: Any) -> str:
    """Alpha 默认 Rect packing；不规则多边形场地标记 shapely-orthogonal 意图。"""
    site = getattr(program, "site", None)
    if site is None:
        return GEOMETRY_BACKEND_RECT
    if getattr(site, "buildable_polygon", None) is not None:
        return GEOMETRY_BACKEND_SHAPELY_ORTHOGONAL
    if getattr(site, "site_polygon", None) is not None:
        return GEOMETRY_BACKEND_SHAPELY_ORTHOGONAL
    return GEOMETRY_BACKEND_RECT


def build_solver_provenance(
    *,
    generator_strategy: str = DEFAULT_GENERATOR_STRATEGY,
    generator_version: str = GENERATOR_VERSION,
    program: Any | None = None,
    selection_strategy: str | None = None,
    selection_version: str | None = None,
    evaluation_version: str | None = None,
    assignment_strategy: str | None = None,
    geometry_backend: str | None = None,
) -> SolverProvenance:
    """构造一次求解溯源；program 可推断 assignment / geometry。"""
    assign = assignment_strategy
    geom = geometry_backend
    if program is not None:
        if assign is None:
            assign = assignment_strategy_for(program)
        if geom is None:
            geom = geometry_backend_for(program)
    return SolverProvenance(
        solver_version=SOLVER_VERSION,
        generator_strategy=generator_strategy,
        generator_version=generator_version,
        selection_strategy=selection_strategy,
        selection_version=selection_version,
        evaluation_version=evaluation_version,
        assignment_strategy=assign or DEFAULT_ASSIGNMENT_STRATEGY,
        geometry_backend=geom or DEFAULT_GEOMETRY_BACKEND,
    )


def merge_solver_provenance(
    prev: SolverProvenance | None,
    **updates: Any,
) -> SolverProvenance:
    """保留已有字段，仅覆盖显式传入的非 None 更新。"""
    base = (
        prev.model_dump()
        if prev is not None
        else build_solver_provenance().model_dump()
    )
    for key, value in updates.items():
        if value is not None:
            base[key] = value
    return SolverProvenance.model_validate(base)


def stamp_selection_provenance(
    provenance: SolverProvenance | None,
    *,
    rank_mode: str,
) -> SolverProvenance:
    """ranking 后写入 selection_strategy / selection_version。"""
    return merge_solver_provenance(
        provenance,
        selection_strategy=selection_strategy_for(rank_mode),
        selection_version=selection_version_for(rank_mode),
    )


def alpha_solver_provenance() -> SolverProvenance:
    """产品默认路径溯源（Guillotine + axis + heuristic + rect）。"""
    return SolverProvenance(
        solver_version=SOLVER_VERSION,
        generator_strategy=DEFAULT_GENERATOR_STRATEGY,
        generator_version=GENERATOR_VERSION,
        selection_strategy=DEFAULT_SELECTION_STRATEGY,
        selection_version=SELECTION_VERSION,
        evaluation_version=EVALUATION_VERSION,
        assignment_strategy=DEFAULT_ASSIGNMENT_STRATEGY,
        geometry_backend=DEFAULT_GEOMETRY_BACKEND,
    )


def provenance_to_metrics(prov: SolverProvenance) -> dict[str, str]:
    """metrics 镜像，供旧读法 / benchmark。"""
    return {
        key: str(value)
        for key, value in prov.model_dump(exclude_none=True).items()
    }
