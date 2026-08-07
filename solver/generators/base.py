"""CandidateGenerator 协议与 Guillotine 占位实现。"""

from __future__ import annotations

from typing import Protocol

from packages.schema.layout import LayoutCandidate
from packages.schema.program import DesignProgram


class CandidateGenerator(Protocol):
    """统一候选生成接口。"""

    def generate(self, program: DesignProgram, seed: int) -> LayoutCandidate:
        """从 DesignProgram 生成单个 LayoutCandidate。"""
        ...


class GuillotineGenerator:
    """
    递归 Guillotine 切分生成器。

    Phase 0 仅占位；算法逻辑将在 Phase 1 从 reference/floorplan-generator.html 迁移。
    """

    def generate(self, program: DesignProgram, seed: int) -> LayoutCandidate:
        raise NotImplementedError(
            "GuillotineGenerator 将在 Phase 1 实现。"
            "参考 reference/floorplan-generator.html 中的 layoutRooms / layoutFloor。"
        )
