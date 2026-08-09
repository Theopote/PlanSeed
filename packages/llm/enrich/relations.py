"""Relations stage — precision-first explicit relation extraction."""

from __future__ import annotations

import re

from packages.llm.enrich._text import surface_forms_for_space
from packages.llm.enrich.context import EnrichmentContext
from packages.llm.vocabulary import ENTRY_ALIAS_GROUP, canonical_zh_for_alias
from packages.schema.requirements import RelationIntent, RelationKind

# 高置信关系模板：(模式字符串格式化用 {a}{b}, kind)
# 一般规律：显式二元谓词，不把「靠近」与「连通」混为 adjacency
_REL_TEMPLATES: tuple[tuple[str, RelationKind], ...] = (
    ("{a}靠近{b}", "near"),
    ("{a}挨着{b}", "near"),
    ("{a}紧挨{b}", "near"),
    ("{a}最好挨着{b}", "near"),
    ("{a}尽量挨着{b}", "near"),
    ("{a}最好靠近{b}", "near"),
    ("{a}邻近{b}", "near"),
    ("{a}和{b}近一点", "near"),
    ("{a}与{b}近一点", "near"),
    ("{a}和{b}近一些", "near"),
    ("{a}与{b}近一些", "near"),
    ("{a}和{b}距离近", "near"),
    ("{a}与{b}距离近", "near"),
    ("{a}远离{b}", "separation"),
    ("{a}与{b}连通", "open_connection"),
    ("{a}和{b}连通", "open_connection"),
    ("{a}与{b}开敞连通", "open_connection"),
    ("{a}和{b}开敞连通", "open_connection"),
    ("{a}与{b}内部相连", "access"),
    ("{a}和{b}内部相连", "access"),
    ("{a}与{b}相连", "access"),
    ("{a}和{b}相连", "access"),
    ("{a}连着{b}", "access"),
    ("{a}保持私密远离{b}", "separation"),
    ("{a}私密远离{b}", "separation"),
    ("{a}不要靠着{b}", "separation"),
    ("{a}不要靠{b}", "separation"),
    ("{a}别挨着{b}", "separation"),
    ("不要让{a}靠着{b}", "separation"),
    ("不要让{a}靠{b}", "separation"),
    ("{a}尽量避免{b}", "separation"),
    ("{a}避免{b}噪声", "separation"),
)

# kind → 原文须出现的谓词线索（两端共现不够，防假阳性）
_KIND_CUES: dict[RelationKind, tuple[str, ...]] = {
    "near": ("靠近", "挨着", "邻近", "距离近", "近一点", "近一些", "最好挨"),
    "separation": ("远离", "私密", "不要靠", "避免", "隔开", "安静"),
    "open_connection": ("连通", "开敞"),
    "access": ("相连", "连着", "能进", "直通", "内部相连", "进入"),
    "adjacency": ("相邻", "紧邻", "靠近", "挨着", "连通"),
    "visual_connection": ("望向", "视野", "看见", "看到"),
}

# 复合空间词 → 隐含端点（一般构词，非单案硬编码）
_COMPOUND_ENDPOINT_HINTS: tuple[tuple[str, frozenset[str]], ...] = (
    ("客餐厅", frozenset({"客厅", "餐厅"})),
    ("餐厨", frozenset({"餐厅", "厨房"})),
    ("厨餐", frozenset({"厨房", "餐厅"})),
)


def extract_relation_intents(text: str, space_names: set[str]) -> list[RelationIntent]:
    """
    仅抽取高置信显式关系；端点须已在空间集合中。

    precision-first：不扫全词表笛卡尔积臆造关系。
    模板匹配时枚举表面形式（门厅/玄关/入口），写入规范名。
    """
    if not text or len(space_names) < 2:
        return []
    out: list[RelationIntent] = []
    seen: set[tuple[str, str, str]] = set()

    def add(a: str, b: str, kind: RelationKind) -> None:
        ca, cb = canonical_zh_for_alias(a), canonical_zh_for_alias(b)
        if ca not in space_names or cb not in space_names or ca == cb:
            return
        ends = tuple(sorted((ca, cb)))
        key = (ends[0], ends[1], kind)
        if key in seen:
            return
        seen.add(key)
        out.append(RelationIntent(a=ca, b=cb, kind=kind))

    names = sorted(space_names, key=len, reverse=True)
    for a in names:
        for b in names:
            if a == b:
                continue
            for sa in surface_forms_for_space(a):
                for sb in surface_forms_for_space(b):
                    for tmpl, kind in _REL_TEMPLATES:
                        if tmpl.format(a=sa, b=sb) in text:
                            add(a, b, kind)
                    if f"从{sa}能进{sb}" in text or f"从{sa}进入{sb}" in text:
                        add(a, b, "access")

    # 「A…不要靠着B」：主语可与谓词隔开（同一分句前缀）
    for b in names:
        for sb in surface_forms_for_space(b):
            for m in re.finditer(rf"不要靠着?{re.escape(sb)}", text):
                prefix = text[max(0, m.start() - 24) : m.start()]
                for a in names:
                    if a == b:
                        continue
                    if any(sa in prefix for sa in surface_forms_for_space(a)):
                        add(a, b, "separation")

    if "客餐厅" in text and ("连通" in text or "开敞" in text):
        add("客厅", "餐厅", "open_connection")
    if ("餐厨" in text or "厨餐" in text) and (
        "近" in text or "挨" in text or "靠" in text
    ):
        add("厨房", "餐厅", "near")

    return out


def endpoint_mentioned_in_text(name: str, text: str) -> bool:
    """端点或其别名/复合词是否出现在原文。"""
    if not name or not text:
        return False
    variants = {name, canonical_zh_for_alias(name)}
    if name in ENTRY_ALIAS_GROUP or canonical_zh_for_alias(name) in ENTRY_ALIAS_GROUP:
        variants |= set(ENTRY_ALIAS_GROUP)
    for v in variants:
        if v and v in text:
            return True
    canon = canonical_zh_for_alias(name)
    for compound, ends in _COMPOUND_ENDPOINT_HINTS:
        if compound in text and canon in ends:
            return True
    return False


def kind_cue_in_text(kind: RelationKind, text: str) -> bool:
    return any(c in text for c in _KIND_CUES.get(kind, ()))


def relation_evidenced_in_text(rel: RelationIntent, text: str) -> bool:
    """关系是否有原文证据（precision-first）。

    保留：高置信二元模板 / 从 A 进 B / 分句「不要靠」/ 客餐厅·餐厨复合。
    **不**接受「两端共现 + 全文任意近/靠」——那是关系假阳性主因。
    """
    if not text:
        return False
    a, b = rel.a.strip(), rel.b.strip()
    variants_a = {a, canonical_zh_for_alias(a)}
    variants_b = {b, canonical_zh_for_alias(b)}
    if a in ENTRY_ALIAS_GROUP or canonical_zh_for_alias(a) in ("门厅", "入口"):
        variants_a |= set(ENTRY_ALIAS_GROUP)
    if b in ENTRY_ALIAS_GROUP or canonical_zh_for_alias(b) in ("门厅", "入口"):
        variants_b |= set(ENTRY_ALIAS_GROUP)

    kind_ok = {rel.kind}
    if rel.kind == "adjacency":
        kind_ok |= {"near", "open_connection", "access", "separation"}

    for va in variants_a:
        for vb in variants_b:
            for tmpl, kind in _REL_TEMPLATES:
                if kind not in kind_ok:
                    continue
                if tmpl.format(a=va, b=vb) in text or tmpl.format(a=vb, b=va) in text:
                    return True
            if f"从{va}能进{vb}" in text or f"从{va}进入{vb}" in text:
                if rel.kind in ("access", "adjacency"):
                    return True
            if rel.kind in ("separation", "adjacency"):
                for m in re.finditer(rf"不要靠着?{re.escape(vb)}", text):
                    prefix = text[max(0, m.start() - 24) : m.start()]
                    if va in prefix:
                        return True

    ends = {canonical_zh_for_alias(a), canonical_zh_for_alias(b)}
    if rel.kind in ("open_connection", "adjacency") and "客餐厅" in text:
        if ends == {"客厅", "餐厅"} and ("连通" in text or "开敞" in text):
            return True
    if ("餐厨" in text or "厨餐" in text) and rel.kind in ("near", "adjacency"):
        if ends == {"厨房", "餐厅"} and kind_cue_in_text("near", text):
            return True

    return False


class RelationsStage:
    def apply(self, context: EnrichmentContext) -> EnrichmentContext:
        known = context.known
        text = context.text
        notes = context.notes

        space_names = {
            canonical_zh_for_alias(s.name.strip())
            for s in known.spaces
            if s.name
        }

        # 关系：先过滤 LLM 无证据关系，再补高置信抽取；遗留 adjacency 按线索细化
        grounded: list[RelationIntent] = []
        for r in known.relation_intents:
            if not relation_evidenced_in_text(r, text):
                notes.append(f"剔除无证据关系:{r.a}-{r.kind}-{r.b}")
                context.record(
                    "relation",
                    "drop_unevidenced",
                    f"{r.a}-{r.kind}-{r.b}",
                )
                continue
            kind = r.kind
            if kind == "adjacency":
                if kind_cue_in_text("open_connection", text):
                    kind = "open_connection"
                elif kind_cue_in_text("access", text):
                    kind = "access"
                elif kind_cue_in_text("near", text):
                    kind = "near"
                elif kind_cue_in_text("separation", text):
                    kind = "separation"
            if kind != r.kind:
                notes.append(f"细化关系:{r.kind}->{kind}")
                context.record("relation", "refine", f"{r.kind}->{kind}")
                r = r.model_copy(update={"kind": kind})
            grounded.append(r)

        def rel_key(r: RelationIntent) -> tuple[str, str, str]:
            ends = tuple(
                sorted(
                    (
                        canonical_zh_for_alias(r.a.strip()),
                        canonical_zh_for_alias(r.b.strip()),
                    )
                )
            )
            return (ends[0], ends[1], r.kind)

        seen = {rel_key(r) for r in grounded}
        for r in extract_relation_intents(text, space_names):
            k = rel_key(r)
            if k not in seen:
                grounded.append(r)
                seen.add(k)
                notes.append(f"补关系:{r.a}-{r.kind}-{r.b}")
                context.record(
                    "relation",
                    "add",
                    f"{r.a}-{r.kind}-{r.b}",
                )
        known.relation_intents = grounded
        return context
