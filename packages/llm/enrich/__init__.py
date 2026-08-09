"""Requirement Draft enricher — Hybrid Semantic Parser 的确定性抽取段。

正式架构见 docs/hybrid-semantic-parser.md：
  Local LLM + Deterministic Extraction + Vocabulary + Semantic Gate + Repair

原则：
- 只恢复原文**显式**出现的事实；不确定则留空
- 禁止制造设计意图（假阳性关系比漏报更贵）
- 规则须是一般语言规律，禁止为单条 benchmark 句式硬编码
- Assumption：仅 user_authorized；丢弃 llm_inference（Alpha）
- **不要无限扩 regex**：新模板须能用一句话说明一般规律；Blind 失败不得逐案补丁
"""

from __future__ import annotations

from packages.llm.enrich.assumptions import (
    AssumptionsStage,
    filter_llm_inference_assumptions,
    normalize_assumption_key,
)
from packages.llm.enrich.context import (
    EnrichmentContext,
    EnrichmentStage,
    EnrichResult,
    StageProvenance,
)
from packages.llm.enrich.floor_preferences import FloorPreferencesStage
from packages.llm.enrich.orientation import OrientationStage
from packages.llm.enrich.relations import (
    RelationsStage,
    extract_relation_intents,
    relation_evidenced_in_text,
)
from packages.llm.enrich.scalar import ScalarStage
from packages.llm.enrich.spaces import SpacesStage, extract_space_names
from packages.llm.enrich.unknowns import UnknownsStage
from packages.schema.llm_contract import LLMRequirementDraft

__all__ = [
    "EnrichResult",
    "EnrichmentContext",
    "EnrichmentStage",
    "StageProvenance",
    "enrich_requirement_draft",
    "extract_relation_intents",
    "extract_space_names",
    "normalize_assumption_key",
    "relation_evidenced_in_text",
]

# 与原 monolithic enrich_requirement_draft 相同的阶段顺序：
# （初始化先丢弃 llm_inference）→ scalar → assumptions → unknowns
# → spaces → relations → floor → orientation
_ENRICHMENT_STAGES: tuple[EnrichmentStage, ...] = (
    ScalarStage(),
    AssumptionsStage(),
    UnknownsStage(),
    SpacesStage(),
    RelationsStage(),
    FloorPreferencesStage(),
    OrientationStage(),
)


def _create_enrichment_context(draft: LLMRequirementDraft) -> EnrichmentContext:
    # Alpha：丢弃 llm_inference 假设（污染 Assumption Precision）
    assumptions = filter_llm_inference_assumptions(list(draft.assumptions))
    # 兼容旧 Draft：无 source 字段时 pydantic 默认为 llm_inference → 已丢弃
    # 若 reason 明示用户假设且 key 规范化后保留机会：由原文再抽
    unknown_by_key = {
        normalize_assumption_key(u.key): u.model_copy(
            update={"key": normalize_assumption_key(u.key)}
        )
        for u in draft.unknowns
    }
    return EnrichmentContext(
        original=draft,
        known=draft.known.model_copy(deep=True),
        assumptions=assumptions,
        unknown_by_key=unknown_by_key,
        text=(draft.raw_text or "").strip(),
        notes=[],
        incoming_unknowns=set(unknown_by_key),
    )


def enrich_requirement_draft(draft: LLMRequirementDraft) -> EnrichResult:
    context = _create_enrichment_context(draft)
    for stage in _ENRICHMENT_STAGES:
        context = stage.apply(context)
    new_draft = draft.model_copy(
        update={
            "known": context.known,
            "assumptions": context.assumptions,
            "unknowns": list(context.unknown_by_key.values()),
        }
    )
    return EnrichResult(draft=new_draft, notes=tuple(context.notes))
