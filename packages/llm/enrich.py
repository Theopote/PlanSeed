"""Requirement Draft enricher — 高置信度确定性抽取（Phase 6.7.1 precision-first）。

原则：
- 只恢复原文**显式**出现的事实；不确定则留空
- 禁止制造设计意图（假阳性关系比漏报更贵）
- 规则须是一般语言规律，禁止为单条 benchmark 句式硬编码
- Assumption：仅 user_authorized；丢弃 llm_inference（Alpha）
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from packages.llm.vocabulary import (
    ENTRY_ALIAS_GROUP,
    all_space_lexicon_zh,
    canonical_zh_for_alias,
)
from packages.schema.llm_contract import LLMRequirementDraft
from packages.schema.requirements import (
    Assumption,
    RelationIntent,
    RelationKind,
    SpaceRequirement,
    UnknownRequirement,
)
from packages.schema.site import CardinalOrientation

# 求解阻塞项：仅在「场地未说明」语义下补列 unknown（非一律问卷）
_SITE_UNCERTAIN_RE = re.compile(
    r"场地|地块|用地|宽深|未提供|未知|勿编造|不要编造|未给|未定"
)

_CN_NUM: dict[str, int] = {
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
}

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

_ORIENT_PHRASES: tuple[tuple[str, CardinalOrientation], ...] = (
    ("朝南", CardinalOrientation.SOUTH),
    ("朝北", CardinalOrientation.NORTH),
    ("朝东", CardinalOrientation.EAST),
    ("朝西", CardinalOrientation.WEST),
)

# 高置信关系模板：(模式字符串格式化用 {a}{b}, kind)
# 一般规律：显式二元谓词，不把「靠近」与「连通」混为 adjacency
_REL_TEMPLATES: tuple[tuple[str, RelationKind], ...] = (
    ("{a}靠近{b}", "near"),
    ("{a}远离{b}", "separation"),
    ("{a}与{b}连通", "open_connection"),
    ("{a}和{b}连通", "open_connection"),
    ("{a}与{b}开敞连通", "open_connection"),
    ("{a}与{b}内部相连", "access"),
    ("{a}和{b}内部相连", "access"),
    ("{a}与{b}相连", "access"),
    ("{a}和{b}相连", "access"),
    ("{a}保持私密远离{b}", "separation"),
    ("{a}私密远离{b}", "separation"),
)


@dataclass(frozen=True)
class EnrichResult:
    draft: LLMRequirementDraft
    notes: tuple[str, ...] = ()


def normalize_assumption_key(key: str) -> str:
    k = (key or "").strip()
    return _ASSUMPTION_KEY_ALIASES.get(k, k)


def _parse_cn_int(token: str) -> int | None:
    token = (token or "").strip()
    if not token:
        return None
    if token.isdigit():
        return int(token)
    return _CN_NUM.get(token)


def extract_space_names(text: str) -> list[str]:
    """从原文抽取空间规范名（词表命中；复合「客餐厅」→客厅+餐厅）。"""
    if not text:
        return []
    found: list[str] = []
    # 一般复合词：客餐厅 = 客厅 + 餐厅（开敞/连通语境常见）
    if "客餐厅" in text:
        found.extend(["客厅", "餐厅"])
    for name in all_space_lexicon_zh():
        if name in text:
            canon = canonical_zh_for_alias(name)
            if canon not in found:
                found.append(canon)
    return found


def extract_relation_intents(text: str, space_names: set[str]) -> list[RelationIntent]:
    """
    仅抽取高置信显式关系；端点须已在空间集合中。

    precision-first：不扫全词表笛卡尔积臆造关系。
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
            for tmpl, kind in _REL_TEMPLATES:
                if tmpl.format(a=a, b=b) in text:
                    add(a, b, kind)

    # 客餐厅 + 连通/开敞 → 客厅 open_connection 餐厅（复合词一般规律）
    if "客餐厅" in text and ("连通" in text or "开敞" in text):
        add("客厅", "餐厅", "open_connection")

    return out


# 复合空间词 → 隐含端点（一般构词，非单案硬编码）
_COMPOUND_ENDPOINT_HINTS: tuple[tuple[str, frozenset[str]], ...] = (
    ("客餐厅", frozenset({"客厅", "餐厅"})),
    ("餐厨", frozenset({"餐厅", "厨房"})),
    ("厨餐", frozenset({"厨房", "餐厅"})),
)


def _endpoint_mentioned_in_text(name: str, text: str) -> bool:
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


def relation_evidenced_in_text(rel: RelationIntent, text: str) -> bool:
    """关系是否能在原文找到证据（过滤无端点支撑的假阳性）。

    保留条件：两端均在原文出现（含别名/复合词），或命中高置信模板。
    不要求谓词与 kind 完全同形——paraphrase 由 LLM 承担，enrich 只拦幻觉房间对。
    """
    if not text:
        return False
    a, b = rel.a.strip(), rel.b.strip()
    if _endpoint_mentioned_in_text(a, text) and _endpoint_mentioned_in_text(b, text):
        return True
    variants_a = {a, canonical_zh_for_alias(a)} | (
        set(ENTRY_ALIAS_GROUP) if a in ENTRY_ALIAS_GROUP else set()
    )
    variants_b = {b, canonical_zh_for_alias(b)} | (
        set(ENTRY_ALIAS_GROUP) if b in ENTRY_ALIAS_GROUP else set()
    )
    for va in variants_a:
        for vb in variants_b:
            for tmpl, kind in _REL_TEMPLATES:
                if kind != rel.kind and not (
                    rel.kind == "adjacency"
                    and kind in ("near", "open_connection", "access")
                ):
                    if rel.kind != "adjacency":
                        continue
                if tmpl.format(a=va, b=vb) in text or tmpl.format(a=vb, b=va) in text:
                    return True
            if rel.kind in ("open_connection", "adjacency") and "客餐厅" in text:
                if {canonical_zh_for_alias(va), canonical_zh_for_alias(vb)} == {
                    "客厅",
                    "餐厅",
                }:
                    if "连通" in text or "开敞" in text:
                        return True
    return False


def _critical_value(draft: LLMRequirementDraft, key: str) -> object | None:
    k = draft.known
    mapping = {
        "floor_count": k.floor_count,
        "site.width": k.site.width,
        "site.depth": k.site.depth,
        "household.bedrooms": k.household.bedrooms,
        "household.bathrooms": k.household.bathrooms,
        "household.has_garage": k.household.has_garage,
    }
    return mapping.get(key)


def _is_sparse_requirement(text: str) -> bool:
    """无明显住宅结构用语 → 稀疏；才广泛列 unknown。"""
    if not (text or "").strip():
        return True
    if re.search(
        r"[层卧卫]|地块|场地|用地|车库|"
        r"\bF[123]\b|\b\d+\s*bed|\bfloor|\bbath|\bgarage",
        text,
        flags=re.IGNORECASE,
    ):
        return False
    return True


def _extract_scalars_into_known(known, text: str, notes: list[str]) -> None:
    """一般数量表达：N层 / N卧 / N卫 / 带车库 / 宽×深。"""
    if known.floor_count is None:
        m = re.search(r"([一二两三四五六七八九十\d]+)\s*层", text)
        if m:
            n = _parse_cn_int(m.group(1))
            if n in (1, 2, 3):
                known.floor_count = n
                notes.append(f"known.floor_count={n}")
        elif "单层" in text or "平层" in text:
            known.floor_count = 1
            notes.append("known.floor_count=1")

    if known.household.bedrooms is None:
        m = re.search(r"([一二两三四五六七八九十\d]+)\s*卧", text)
        if m:
            n = _parse_cn_int(m.group(1))
            if n is not None and 1 <= n <= 10:
                known.household.bedrooms = n
                notes.append(f"known.bedrooms={n}")

    if known.household.bathrooms is None:
        m = re.search(r"([一二两三四五六七八九十\d]+)\s*卫", text)
        if m:
            n = _parse_cn_int(m.group(1))
            if n is not None and 1 <= n <= 8:
                known.household.bathrooms = n
                notes.append(f"known.bathrooms={n}")

    if known.household.has_garage is None:
        if "带车库" in text or "有车库" in text:
            known.household.has_garage = True
            notes.append("known.has_garage=true")
        elif "无车库" in text or "不要车库" in text:
            known.household.has_garage = False
            notes.append("known.has_garage=false")

    if known.site.width is None or known.site.depth is None:
        m = re.search(
            r"(?:地块|场地|用地)?\s*(?:约\s*)?"
            r"(\d+(?:\.\d+)?)\s*[×xX＊*]\s*(\d+(?:\.\d+)?)",
            text,
        )
        if m:
            w, d = float(m.group(1)), float(m.group(2))
            if known.site.width is None and 6 <= w <= 60:
                known.site.width = w
                notes.append(f"known.site.width={w}")
            if known.site.depth is None and 6 <= d <= 60:
                known.site.depth = d
                notes.append(f"known.site.depth={d}")


def _extract_user_authorized_assumptions(
    text: str,
    assumptions: list[Assumption],
    notes: list[str],
) -> None:
    """仅当用户明确说「假设」时授权 assumption。"""
    keys = {a.key for a in assumptions}
    m = re.search(r"假设为\s*([一二两三四五六七八九十\d]+)\s*间", text)
    if m and "household.bedrooms" not in keys:
        n = _parse_cn_int(m.group(1))
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


def _should_mark_unknown(
    key: str,
    text: str,
    *,
    sparse: bool,
    assumed_keys: set[str],
) -> bool:
    """
    Unknown 纪律（precision-first）：

    - site.*：仅场地语义未说明时列为 blocking
    - floor_count / bedrooms / bathrooms：仅稀疏需求
    - has_garage：不自动列
    """
    if key in assumed_keys:
        return False
    if key in ("site.width", "site.depth"):
        return bool(_SITE_UNCERTAIN_RE.search(text)) or sparse
    if key == "floor_count":
        return sparse
    if key in ("household.bedrooms", "household.bathrooms"):
        return sparse
    return False


def _priority_for_unknown(key: str) -> str:
    if key in ("site.width", "site.depth"):
        return "blocking"
    if key in ("floor_count", "household.bedrooms"):
        return "recommended"
    return "optional"


def enrich_requirement_draft(draft: LLMRequirementDraft) -> EnrichResult:
    notes: list[str] = []
    # Alpha：丢弃 llm_inference 假设（污染 Assumption Precision）
    assumptions = [
        a.model_copy(update={"key": normalize_assumption_key(a.key)})
        for a in draft.assumptions
        if (a.source or "llm_inference") != "llm_inference"
    ]
    # 兼容旧 Draft：无 source 字段时 pydantic 默认为 llm_inference → 已丢弃
    # 若 reason 明示用户假设且 key 规范化后保留机会：由原文再抽
    unknown_by_key = {
        normalize_assumption_key(u.key): u.model_copy(
            update={"key": normalize_assumption_key(u.key)}
        )
        for u in draft.unknowns
    }

    known = draft.known.model_copy(deep=True)
    text = (draft.raw_text or "").strip()
    _extract_scalars_into_known(known, text, notes)
    _extract_user_authorized_assumptions(text, assumptions, notes)
    assumed_keys = {a.key for a in assumptions}

    tmp = draft.model_copy(update={"known": known})
    sparse = _is_sparse_requirement(text)
    for key in (
        "floor_count",
        "site.width",
        "site.depth",
        "household.bedrooms",
        "household.bathrooms",
        "household.has_garage",
    ):
        val = _critical_value(tmp, key)
        if val is not None:
            unknown_by_key.pop(key, None)
            continue
        if not _should_mark_unknown(
            key, text, sparse=sparse, assumed_keys=assumed_keys
        ):
            # 不主动补列；已有 unknowns 保留（由评分 / Gate 罚假阳性）
            continue
        if key not in unknown_by_key:
            unknown_by_key[key] = UnknownRequirement(
                key=key,
                description={
                    "floor_count": "未说明层数",
                    "site.width": "未提供用地宽度",
                    "site.depth": "未提供用地深度",
                    "household.bedrooms": "未说明卧室数",
                    "household.bathrooms": "未说明卫浴数",
                }.get(key, "用户未提供"),
                priority=_priority_for_unknown(key),  # type: ignore[arg-type]
            )
            notes.append(f"补列 unknown:{key}")

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
    if added_spaces:
        notes.append("补空间:" + ",".join(added_spaces))

    space_names = {
        canonical_zh_for_alias(s.name.strip())
        for s in known.spaces
        if s.name
    }

    # 关系：先过滤 LLM 无证据关系，再补高置信抽取
    grounded: list[RelationIntent] = []
    for r in known.relation_intents:
        if relation_evidenced_in_text(r, text):
            grounded.append(r)
        else:
            notes.append(f"剔除无证据关系:{r.a}-{r.kind}-{r.b}")

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
    known.relation_intents = grounded

    space_by_name = {canonical_zh_for_alias(s.name): i for i, s in enumerate(known.spaces)}
    for name in list(space_names):
        i = space_by_name.get(name)
        if i is None:
            continue
        sp = known.spaces[i]
        # 一般规律：X放/在一层 → F1
        if not sp.floor_preference and (
            f"{name}放一层" in text
            or f"{name}在一层" in text
            or f"{name}置于一层" in text
        ):
            known.spaces[i] = sp.model_copy(update={"floor_preference": ["F1"]})
            notes.append(f"楼层偏好:{name}=F1")
            sp = known.spaces[i]
        if sp.preferred_orientation is None:
            for phrase, ori in _ORIENT_PHRASES:
                if f"{name}{phrase}" in text:
                    known.spaces[i] = sp.model_copy(
                        update={"preferred_orientation": ori}
                    )
                    notes.append(f"朝向:{name}={ori}")
                    if name == "客厅" and ori == CardinalOrientation.SOUTH:
                        if known.preferences.prefer_south_facing_living is None:
                            known.preferences.prefer_south_facing_living = True
                    break

    if known.preferences.prefer_south_facing_living is None and re.search(
        r"客厅.{0,4}朝南|朝南.{0,4}客厅", text
    ):
        known.preferences.prefer_south_facing_living = True
        notes.append("prefer_south_facing_living")

    new_draft = draft.model_copy(
        update={
            "known": known,
            "assumptions": assumptions,
            "unknowns": list(unknown_by_key.values()),
        }
    )
    return EnrichResult(draft=new_draft, notes=tuple(notes))
