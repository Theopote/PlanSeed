"""Assumption stage — Alpha: drop llm_inference; keep user_authorized only."""

from __future__ import annotations

import re

from packages.llm.enrich._text import parse_cn_int
from packages.llm.enrich.context import EnrichmentContext
from packages.schema.requirements import Assumption

_ASSUMPTION_KEY_ALIASES: dict[str, str] = {
    "bedrooms": "household.bedrooms",
    "bathrooms": "household.bathrooms",
    "has_garage": "household.has_garage",
    "occupants": "household.occupants",
    "floor_count": "floor_count",
    "width": "site.width",
    "depth": "site.depth",
    "site_width": "site.width",
    "site_depth": "site.depth",
}


def normalize_assumption_key(key: str) -> str:
    k = (key or "").strip()
    return _ASSUMPTION_KEY_ALIASES.get(k, k)


def extract_user_authorized_assumptions(
    text: str,
    assumptions: list[Assumption],
    notes: list[str],
) -> None:
    """仅当用户明确说「假设」时授权 assumption。"""
    keys = {a.key for a in assumptions}
    m = re.search(r"假设为\s*([一二两三四五六七八九十\d]+)\s*间", text)
    if m and "household.bedrooms" not in keys:
        n = parse_cn_int(m.group(1))
        if n is not None and 1 <= n <= 10:
            assumptions.append(
                Assumption(
                    key="household.bedrooms",
                    value=n,
                    reason="用户明确要求按假设处理卧室数",
                    source="user_authorized",
                )
            )
            notes.append(f"assumption.user_authorized.bedrooms={n}")


def filter_llm_inference_assumptions(
    assumptions: list[Assumption],
) -> tuple[list[Assumption], list[Assumption]]:
    """Keep user/default assumptions; return dropped llm_inference separately.

    Dropped items must surface as unknowns (ADR-003)；不得无声消失。
    """
    kept: list[Assumption] = []
    dropped: list[Assumption] = []
    for raw in assumptions:
        item = raw.model_copy(update={"key": normalize_assumption_key(raw.key)})
        if (item.source or "llm_inference") == "llm_inference":
            dropped.append(item)
        else:
            kept.append(item)
    return kept, dropped


class AssumptionsStage:
    """用户授权 assumption 抽取（llm_inference 过滤在 pipeline 初始化完成）。"""

    def apply(self, context: EnrichmentContext) -> EnrichmentContext:
        extract_user_authorized_assumptions(
            context.text, context.assumptions, context.notes
        )
        context.record("assumption", "user_authorized")
        return context
