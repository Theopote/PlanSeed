"""Phase 6.2 — NL → JSON → RequirementSpec 结构化解析编排。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from packages.llm.boundary import SYSTEM_PROMPT_SKELETON
from packages.llm.gate import IngestResult, LLMIngestError, ingest_llm_requirement
from packages.llm.provider import LLMProvider
from packages.llm.semantic import RequirementSemanticValidator
from packages.schema.llm_contract import LLMRequirementDraft
from packages.schema.requirements import RequirementSpec

USER_PROMPT_TEMPLATE = """请将下列住宅设计需求解析为 LLMRequirementDraft JSON。

只输出一个 JSON object，字段：
- known: 用户明确说出的事实（floor_count / site / household / spaces / preferences / relation_intents）
- assumptions: 你采用的显式默认（须含 key、value、reason）；不确定则不要猜
- unknowns: 用户未提供且你未推断的项（key + description）

禁止输出几何（x/y、墙、门、SVG、placements）。
不要擅自编造卧室数、卫生间数、场地宽深等关键未知。

用户需求：
{text}
"""


def build_user_prompt(text: str) -> str:
    cleaned = text.strip()
    if not cleaned:
        raise LLMIngestError("需求文本为空")
    return USER_PROMPT_TEMPLATE.format(text=cleaned)


@dataclass(frozen=True)
class ParseResult:
    """NL 解析结果（事实源 = spec）。"""

    text: str
    raw: dict[str, Any]
    ingest: IngestResult
    attempts: int = 1
    repair_notes: tuple[str, ...] = ()

    @property
    def draft(self) -> LLMRequirementDraft:
        return self.ingest.draft

    @property
    def spec(self) -> RequirementSpec:
        return self.ingest.spec

    @property
    def repaired(self) -> bool:
        return self.attempts > 1


class StructuredRequirementParser:
    """
    NL→RequirementSpec 入口。

    - parse()：单次（6.2）
    - parse_with_repair()：有限修复（6.3）
    """

    def __init__(
        self,
        provider: LLMProvider,
        *,
        system: str = SYSTEM_PROMPT_SKELETON,
        validator: RequirementSemanticValidator | None = None,
        enrich: bool = True,
    ) -> None:
        self.provider = provider
        self.system = system
        self.validator = validator
        self.enrich = enrich

    def parse(self, text: str) -> ParseResult:
        user = build_user_prompt(text)
        raw = self.provider.complete_json(system=self.system, user=user)
        ingest = ingest_llm_requirement(
            raw,
            raw_text=text.strip(),
            validator=self.validator,
            enrich=self.enrich,
        )
        return ParseResult(text=text.strip(), raw=raw, ingest=ingest)

    def parse_with_repair(
        self,
        text: str,
        *,
        max_repairs: int = 2,
    ) -> ParseResult:
        from packages.llm.repair import parse_with_repair as _parse_with_repair

        return _parse_with_repair(self, text, max_repairs=max_repairs)


def parse_requirement_text(
    text: str,
    *,
    provider: LLMProvider,
    system: str = SYSTEM_PROMPT_SKELETON,
    validator: RequirementSemanticValidator | None = None,
    enrich: bool = True,
) -> ParseResult:
    """便捷函数：等价于 StructuredRequirementParser(...).parse(text)。"""
    return StructuredRequirementParser(
        provider,
        system=system,
        validator=validator,
        enrich=enrich,
    ).parse(text)
