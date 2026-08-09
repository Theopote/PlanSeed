"""住宅需求词汇表 — Hybrid Semantic Parser 的 Vocabulary Normalization 段。

空间别名 / 入口别名（供 enrich · semantic · score 共用）。
正式架构见 docs/hybrid-semantic-parser.md。

Solver 不得直接依赖中文字符串；本模块只服务 Requirement 解析层。
词表可缓慢扩展；禁止为单条 Blind 失败加一次性别名。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class RoomKind(str, Enum):
    LIVING = "living"
    DINING = "dining"
    KITCHEN = "kitchen"
    MASTER_BEDROOM = "master_bedroom"
    BEDROOM = "bedroom"
    CHILD_BEDROOM = "child_bedroom"
    ELDER_BEDROOM = "elder_bedroom"
    GUEST_BEDROOM = "guest_bedroom"
    STUDY = "study"
    BATHROOM = "bathroom"
    GARAGE = "garage"
    FOYER = "foyer"
    ENTRY = "entry"


@dataclass(frozen=True)
class RoomVocab:
    kind: RoomKind
    canonical_zh: str
    aliases_zh: tuple[str, ...] = ()
    aliases_en: tuple[str, ...] = ()

    @property
    def all_zh(self) -> tuple[str, ...]:
        names = (self.canonical_zh, *self.aliases_zh)
        # 长词优先匹配
        return tuple(sorted(set(names), key=len, reverse=True))


RESIDENTIAL_ROOMS: tuple[RoomVocab, ...] = (
    RoomVocab(RoomKind.CHILD_BEDROOM, "儿童房", ("小孩房",)),
    RoomVocab(RoomKind.ELDER_BEDROOM, "老人房", ("父母房",)),
    RoomVocab(RoomKind.MASTER_BEDROOM, "主卧", ("主人房", "主卧室")),
    RoomVocab(RoomKind.GUEST_BEDROOM, "客房", ("客人房",)),
    RoomVocab(RoomKind.BEDROOM, "次卧", ("卧室",)),
    RoomVocab(RoomKind.STUDY, "书房", ("工作室",)),
    RoomVocab(RoomKind.KITCHEN, "厨房", ("厨",)),
    RoomVocab(RoomKind.DINING, "餐厅", ()),
    RoomVocab(RoomKind.LIVING, "客厅", ("起居室",)),
    RoomVocab(RoomKind.FOYER, "门厅", ("玄关", "入户")),
    RoomVocab(RoomKind.ENTRY, "入口", ()),
    RoomVocab(RoomKind.GARAGE, "车库", ()),
    RoomVocab(RoomKind.BATHROOM, "卫生间", ("浴室", "洗手间", "厕所")),
)

# 入口类互通别名（语义等价，供端点解析）
ENTRY_ALIAS_GROUP: frozenset[str] = frozenset({"入口", "门厅", "玄关", "入户"})


def all_space_lexicon_zh() -> tuple[str, ...]:
    """抽取用词表：长词优先、去重。"""
    names: list[str] = []
    seen: set[str] = set()
    for room in RESIDENTIAL_ROOMS:
        for n in room.all_zh:
            if n and n not in seen and len(n) >= 2:
                # 跳过过短易误伤词（如单字「厨」）
                if len(n) < 2:
                    continue
                seen.add(n)
                names.append(n)
    return tuple(sorted(names, key=len, reverse=True))


def canonical_zh_for_alias(name: str) -> str:
    """别名 → 规范中文名；未知则原样返回。

    入口类：门厅/玄关/入户 → 门厅；「入口」保持入口。
    评分端点仍通过 ENTRY_ALIAS_GROUP 互通。
    """
    raw = (name or "").strip()
    if not raw:
        return raw
    for room in RESIDENTIAL_ROOMS:
        if raw == room.canonical_zh or raw in room.aliases_zh:
            return room.canonical_zh
    if raw in ENTRY_ALIAS_GROUP:
        return "门厅"
    return raw


def endpoint_alias_group(name: str) -> frozenset[str]:
    raw = (name or "").strip()
    if raw in ENTRY_ALIAS_GROUP:
        return ENTRY_ALIAS_GROUP
    return frozenset({raw})
