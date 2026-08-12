"""Enrichment pipeline context and stage protocol."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from packages.schema.llm_contract import LLMKnownFacts, LLMRequirementDraft
from packages.schema.requirements import Assumption, UnknownRequirement


@dataclass(frozen=True)
class EnrichResult:
    draft: LLMRequirementDraft
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class StageProvenance:
    """Optional stage provenance record (internal; does not change EnrichResult)."""

    stage: str
    rule: str
    evidence: str = ""


@dataclass
class EnrichmentContext:
    """Mutable state threaded through EnrichmentStage.apply."""

    original: LLMRequirementDraft
    known: LLMKnownFacts
    assumptions: list[Assumption]
    unknown_by_key: dict[str, UnknownRequirement]
    text: str
    notes: list[str] = field(default_factory=list)
    provenance: list[StageProvenance] = field(default_factory=list)
    incoming_unknowns: set[str] = field(default_factory=set)
    dropped_inference_keys: set[str] = field(default_factory=set)
    sparse: bool = False

    def record(
        self,
        stage: str,
        rule: str,
        evidence: str = "",
    ) -> None:
        self.provenance.append(
            StageProvenance(stage=stage, rule=rule, evidence=evidence)
        )


class EnrichmentStage(Protocol):
    def apply(self, context: EnrichmentContext) -> EnrichmentContext: ...
