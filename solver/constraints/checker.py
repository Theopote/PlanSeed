"""ConstraintChecker 协议与统一评价结果。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from packages.schema.layout import CandidateValidation, LayoutCandidate, Violation
from packages.schema.program import DesignProgram


@dataclass
class ConstraintEvaluationResult:
    """
    单次 / 子检查的统一输出。

    子检查不得自行丢弃 soft；聚合层合并后决定 valid。
    """

    hard_violations: list[Violation] = field(default_factory=list)
    soft_violations: list[Violation] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @classmethod
    def empty(cls) -> ConstraintEvaluationResult:
        return cls()

    @classmethod
    def from_violations(cls, violations: list[Violation]) -> ConstraintEvaluationResult:
        """按 Violation.hard 分流；不丢弃任何条目。"""
        hard = [v for v in violations if v.hard]
        soft = [v for v in violations if not v.hard]
        return cls(hard_violations=hard, soft_violations=soft)

    @classmethod
    def from_optional(cls, violation: Violation | None) -> ConstraintEvaluationResult:
        if violation is None:
            return cls.empty()
        return cls.from_violations([violation])

    def merge(self, other: ConstraintEvaluationResult) -> ConstraintEvaluationResult:
        return ConstraintEvaluationResult(
            hard_violations=self.hard_violations + other.hard_violations,
            soft_violations=self.soft_violations + other.soft_violations,
            warnings=self.warnings + other.warnings,
        )

    def extend(self, other: ConstraintEvaluationResult) -> None:
        self.hard_violations.extend(other.hard_violations)
        self.soft_violations.extend(other.soft_violations)
        self.warnings.extend(other.warnings)

    @property
    def valid(self) -> bool:
        return len(self.hard_violations) == 0

    def to_candidate_validation(self) -> CandidateValidation:
        return CandidateValidation(
            valid=self.valid,
            hard_violations=list(self.hard_violations),
            soft_violations=list(self.soft_violations),
            warnings=list(self.warnings),
        )


class ConstraintChecker(Protocol):
    """约束校验器 — 区分 hard / soft violation。"""

    def check(self, program: DesignProgram, candidate: LayoutCandidate) -> CandidateValidation:
        ...
