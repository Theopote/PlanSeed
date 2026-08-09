"""Alpha / Research Solver Profiles — 防止实验功能偷改产品默认。

Alpha Stable（产品默认）::

    Guillotine + axis + heuristic + rect + residential-alpha-v1

Research 预设须 ``experimental=True``，不得成为 API 默认。
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from packages.schema.identity import EVALUATION_VERSION
from packages.schema.program import SolverConfig

GeneratorStrategy = Literal["guillotine", "maxrect"]
SelectionStrategy = Literal["score", "axis", "pareto"]
AssignmentStrategy = Literal["heuristic", "cpsat"]
GeometryBackend = Literal["rect", "shapely-orthogonal"]

PROFILE_ALPHA_STABLE = "alpha-stable"
PROFILE_RESEARCH_PARETO = "research-pareto"
PROFILE_RESEARCH_MAXRECT = "research-maxrect"
PROFILE_RESEARCH_CPSAT = "research-cpsat"


class SolverProfile(BaseModel):
    """一次求解的策略组合（≠ 单字段版本号）。"""

    id: str
    label: str
    generator: GeneratorStrategy = "guillotine"
    selection: SelectionStrategy = "axis"
    assignment: AssignmentStrategy = "heuristic"
    geometry_backend: GeometryBackend = "rect"
    evaluation_version: str = EVALUATION_VERSION
    experimental: bool = Field(
        default=False,
        description="True = Research Lab；不得作为 Alpha 产品默认",
    )


ALPHA_STABLE = SolverProfile(
    id=PROFILE_ALPHA_STABLE,
    label="Alpha Stable",
    generator="guillotine",
    selection="axis",
    assignment="heuristic",
    geometry_backend="rect",
    evaluation_version=EVALUATION_VERSION,
    experimental=False,
)

RESEARCH_PARETO = SolverProfile(
    id=PROFILE_RESEARCH_PARETO,
    label="Research Pareto",
    generator="guillotine",
    selection="pareto",
    assignment="heuristic",
    geometry_backend="rect",
    experimental=True,
)

RESEARCH_MAXRECT = SolverProfile(
    id=PROFILE_RESEARCH_MAXRECT,
    label="Research MaxRect",
    generator="maxrect",
    selection="pareto",
    assignment="heuristic",
    geometry_backend="rect",
    experimental=True,
)

RESEARCH_CPSAT = SolverProfile(
    id=PROFILE_RESEARCH_CPSAT,
    label="Research CP-SAT",
    generator="guillotine",
    selection="axis",
    assignment="cpsat",
    geometry_backend="rect",
    experimental=True,
)

SOLVER_PROFILES: dict[str, SolverProfile] = {
    ALPHA_STABLE.id: ALPHA_STABLE,
    RESEARCH_PARETO.id: RESEARCH_PARETO,
    RESEARCH_MAXRECT.id: RESEARCH_MAXRECT,
    RESEARCH_CPSAT.id: RESEARCH_CPSAT,
}


def get_solver_profile(profile_id: str) -> SolverProfile:
    key = profile_id.strip().lower()
    if key not in SOLVER_PROFILES:
        known = ", ".join(sorted(SOLVER_PROFILES))
        raise KeyError(f"unknown SolverProfile {profile_id!r}; known: {known}")
    return SOLVER_PROFILES[key]


def apply_solver_profile(config: SolverConfig, profile: SolverProfile) -> SolverConfig:
    """把 profile 写入 SolverConfig（不碰 candidate_count / seed 等运行参数）。"""
    return config.model_copy(
        update={
            "generator_strategy": profile.generator,
            "rank_mode": profile.selection,
            "experimental": profile.experimental,
            "profile_id": profile.id,
        }
    )


def pin_alpha_stable_if_needed(config: SolverConfig) -> SolverConfig:
    """产品路径：非 experimental 时强制 Alpha Stable 策略组合。"""
    if config.experimental:
        if config.profile_id:
            return apply_solver_profile(config, get_solver_profile(config.profile_id))
        return config
    return apply_solver_profile(config, ALPHA_STABLE)
