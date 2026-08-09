"""LayoutGenerator — Phase 8.0-A packing strategy 协议。

Guillotine 是默认 Strategy，不再是唯一生成器身份。
同一 DesignProgram + seed（+ locks / topology）必须确定性。
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from packages.schema.layout import LayoutCandidate
from packages.schema.locks import LayoutLocks
from packages.schema.program import DesignProgram
from packages.schema.topology import TopologyPlan


@runtime_checkable
class LayoutGenerator(Protocol):
    """几何 packing strategy：一次 seed → 一个 LayoutCandidate。

    多样本由 ``run_pipeline`` 按 ``SolverConfig.candidate_count`` 换 seed 调用。
    ``program.solver_config`` 为权威配置（不另传 SolverConfig，避免双源）。
    ``topology`` 可选注入；缺省由实现内部 TopologyPlanner 推导。
    """

    @property
    def strategy_id(self) -> str:
        """稳定策略标识（benchmark / provenance）。"""
        ...

    def generate(
        self,
        program: DesignProgram,
        seed: int,
        locks: LayoutLocks | None = None,
        topology: TopologyPlan | None = None,
    ) -> LayoutCandidate:
        """从 DesignProgram 生成单个 LayoutCandidate。"""
        ...


# 旧文档名
CandidateGenerator = LayoutGenerator
