"""Spaces stage — lexicon-based space name extraction."""

from __future__ import annotations

import re

from packages.llm.enrich.context import EnrichmentContext
from packages.llm.vocabulary import all_space_lexicon_zh, canonical_zh_for_alias
from packages.schema.requirements import SpaceRequirement


def extract_space_names(text: str) -> list[str]:
    """从原文抽取空间规范名（词表命中；复合词展开）。"""
    if not text:
        return []
    found: list[str] = []
    if "客餐厅" in text:
        found.extend(["客厅", "餐厅"])
    if "餐厨" in text or "厨餐" in text:
        found.extend(["厨房", "餐厅"])
    # 老人/父母卧室 paraphrase → 老人房
    if re.search(r"老人(?:房|卧室)|父母(?:房|卧室)|给父母准备的卧室", text):
        found.append("老人房")
    elif re.search(
        r"老人最好住|老人住楼下|首层安排一间老人|"
        r"一楼留.{0,8}老人|别让老人|不要让老人上楼",
        text,
    ):
        found.append("老人房")
    for name in all_space_lexicon_zh():
        if name in text:
            canon = canonical_zh_for_alias(name)
            if canon not in found:
                found.append(canon)
    return found


class SpacesStage:
    def apply(self, context: EnrichmentContext) -> EnrichmentContext:
        known = context.known
        text = context.text
        notes = context.notes

        existing_names = {
            canonical_zh_for_alias(s.name.strip())
            for s in known.spaces
            if s.name and s.name.strip()
        }
        added_spaces: list[str] = []
        for name in extract_space_names(text):
            if name not in existing_names:
                known.spaces.append(SpaceRequirement(name=name))
                existing_names.add(name)
                added_spaces.append(name)
        # 车位/双车位等明示有停车时补「车库」空间（词表无「车位」别名）
        if (
            known.household.has_garage is True
            and "车库" not in existing_names
            and re.search(r"车位|车库", text)
        ):
            known.spaces.append(SpaceRequirement(name="车库"))
            existing_names.add("车库")
            added_spaces.append("车库")
        if added_spaces:
            notes.append("补空间:" + ",".join(added_spaces))
            context.record("spaces", "add", ",".join(added_spaces))
        return context
