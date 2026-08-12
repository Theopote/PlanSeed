"""集中运行时上限 — Phase 7.5-I（禁止散落 magic numbers）。

改阈值只改此处；SolverConfig / API Field 引用这些常量。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SolverLimits:
    max_floors: int = 3
    max_rooms: int = 48
    max_candidates: int = 256
    max_return_top_k: int = 32
    max_connection_repairs: int = 32
    max_connection_reslices: int = 8
    # API 生成请求可再收紧（见 ApiLimits）


@dataclass(frozen=True)
class ApiLimits:
    max_nl_text_chars: int = 8000
    max_project_name_chars: int = 200
    max_generate_candidates: int = 64
    max_generate_return_top_k: int = 16
    max_rejected_samples: int = 8
    max_base_seed: int = 1_000_000
    max_mutation_batch: int = 1  # 单次 preview/commit 一条 mutation
    max_package_bytes: int = 32 * 1024 * 1024
    max_package_uncompressed_bytes: int = 80 * 1024 * 1024
    max_package_members: int = 256
    max_svg_chars: int = 2_000_000


@dataclass(frozen=True)
class RuntimeLimits:
    solver: SolverLimits
    api: ApiLimits


SOLVER_LIMITS = SolverLimits()
API_LIMITS = ApiLimits()
RUNTIME_LIMITS = RuntimeLimits(solver=SOLVER_LIMITS, api=API_LIMITS)
