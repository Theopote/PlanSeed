"""Phase 6.0 — LLM 结构化输出契约（≠ DesignProgram / 几何）。

LLM 只产出本模块类型；禁止坐标、墙、门、SVG、LayoutCandidate。
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from packages.schema.requirements import (
    Assumption,
    DesignPreferences,
    HouseholdRequirements,
    RelationIntent,
    RequirementSpec,
    SiteRequirements,
    SpaceRequirement,
    UnknownRequirement,
)

__all__ = [
    "LLMKnownFacts",
    "LLMRequirementDraft",
    "RelationIntent",
]


class LLMKnownFacts(BaseModel):
    """用户明确说出的事实（允许字段为空 = 未说）。"""

    floor_count: int | None = Field(default=None, ge=1, le=3)
    site: SiteRequirements = Field(default_factory=SiteRequirements)
    household: HouseholdRequirements = Field(default_factory=HouseholdRequirements)
    spaces: list[SpaceRequirement] = Field(default_factory=list)
    preferences: DesignPreferences = Field(default_factory=DesignPreferences)
    relation_intents: list[RelationIntent] = Field(default_factory=list)


class LLMRequirementDraft(BaseModel):
    """
    LLM 结构化输出目标。

    known / assumptions / unknowns 三层必须可解释；不得含几何。
    """

    raw_text: str | None = None
    known: LLMKnownFacts = Field(default_factory=LLMKnownFacts)
    assumptions: list[Assumption] = Field(default_factory=list)
    unknowns: list[UnknownRequirement] = Field(default_factory=list)

    def to_requirement_spec(self) -> RequirementSpec:
        """合并为会话事实源 RequirementSpec（几何仍禁止）。"""
        k = self.known
        return RequirementSpec(
            raw_text=self.raw_text,
            site=k.site,
            household=k.household,
            spaces=list(k.spaces),
            preferences=k.preferences,
            floor_count=k.floor_count,
            assumptions=list(self.assumptions),
            unknowns=list(self.unknowns),
            relation_intents=list(k.relation_intents),
        )
