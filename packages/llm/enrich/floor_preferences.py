"""Floor preference stage — F1 / 楼下 placement cues."""

from __future__ import annotations

import re

from packages.llm.enrich._text import surface_forms_for_space
from packages.llm.enrich.context import EnrichmentContext
from packages.llm.vocabulary import canonical_zh_for_alias


def text_has_floor1_pref(name: str, text: str) -> bool:
    """一般规律：某空间放/在/住一层或楼下；老人房含 paraphrase。"""
    for surf in surface_forms_for_space(name):
        for pat in (
            f"{surf}放一层",
            f"{surf}在一层",
            f"{surf}置于一层",
            f"{surf}住一层",
            f"{surf}放楼下",
            f"{surf}在楼下",
            f"{surf}住楼下",
            f"一层放{surf}",
            f"一层布置{surf}",
        ):
            if pat in text:
                return True
    if name == "老人房":
        if re.search(
            r"老人最好住楼下|老人住楼下|父母.{0,10}不要上楼|"
            r"首层安排一间老人|给父母准备的卧室不要上楼|"
            r"一楼留.{0,8}老人|老人.{0,12}一楼|老人房.{0,6}一楼|"
            r"别让老人上二楼|不要让老人上楼",
            text,
        ):
            return True
    return False


class FloorPreferencesStage:
    def apply(self, context: EnrichmentContext) -> EnrichmentContext:
        known = context.known
        text = context.text
        notes = context.notes

        space_names = {
            canonical_zh_for_alias(s.name.strip())
            for s in known.spaces
            if s.name
        }
        space_by_name = {
            canonical_zh_for_alias(s.name): i for i, s in enumerate(known.spaces)
        }
        for name in list(space_names):
            i = space_by_name.get(name)
            if i is None:
                continue
            sp = known.spaces[i]
            if not sp.floor_preference and text_has_floor1_pref(name, text):
                known.spaces[i] = sp.model_copy(update={"floor_preference": ["F1"]})
                notes.append(f"楼层偏好:{name}=F1")
                context.record("floor_preference", "F1", name)
        return context
