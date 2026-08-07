"""ConstraintChecker 协议。"""

from __future__ import annotations

from typing import Protocol

from packages.schema.layout import CandidateValidation, LayoutCandidate
from packages.schema.program import DesignProgram


class ConstraintChecker(Protocol):
    """约束校验器 — 区分 hard / soft violation。"""

    def check(self, program: DesignProgram, candidate: LayoutCandidate) -> CandidateValidation:
        ...
