"""PlanSeed 求解 / 评价 / 选优身份签名。

用于解释历史分数与 regression：同一几何在不同 evaluation_version 下分数可变；
同一分池在不同 selection_version 下 Top-K 可变。
引擎进程身份仍用 health 的 engine_version；此处是算法契约版本。
"""

from __future__ import annotations

# 独立于 pyproject package version；刻意手工 bump。
SOLVER_VERSION = "0.5"
GENERATOR_VERSION = "guillotine-lock-v4"
EVALUATION_VERSION = "residential-alpha-v1"
# Alpha 默认 Top-K：score + 轴叙事 + 几何 diversity（8.1）。Pareto 为 opt-in。
SELECTION_VERSION = "axis-diversity-v1"

_SELECTION_BY_MODE: dict[str, str] = {
    "axis": "axis-diversity-v1",
    "pareto": "pareto-top1-axes-v2",
    "score": "score-only-v1",
    "geom": "geom-diversity-v1",
}


def selection_version_for(mode: str) -> str:
    """按实际 rank_mode 解析选优签名（opt-in 模式与默认可区分）。"""
    return _SELECTION_BY_MODE.get(mode, f"rank-{mode}")


def solver_identity() -> dict[str, str]:
    """稳定键名，便于持久化与 API 序列化。"""
    return {
        "solver_version": SOLVER_VERSION,
        "generator_version": GENERATOR_VERSION,
        "evaluation_version": EVALUATION_VERSION,
        "selection_version": SELECTION_VERSION,
    }
