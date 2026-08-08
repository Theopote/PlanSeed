"""PlanSeed 求解 / 评价身份签名。

用于解释历史分数与 regression：同一几何在不同 evaluation_version 下分数可变。
引擎进程身份仍用 health 的 engine_version；此处是算法契约版本。
"""

from __future__ import annotations

# 独立于 pyproject package version；刻意手工 bump。
SOLVER_VERSION = "0.4"
GENERATOR_VERSION = "guillotine-lock-v1"
EVALUATION_VERSION = "residential-alpha-v1"


def solver_identity() -> dict[str, str]:
    """稳定键名，便于持久化与 API 序列化。"""
    return {
        "solver_version": SOLVER_VERSION,
        "generator_version": GENERATOR_VERSION,
        "evaluation_version": EVALUATION_VERSION,
    }
