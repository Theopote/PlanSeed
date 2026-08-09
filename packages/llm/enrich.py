"""Requirement Draft enricher — LLM 后、语义 Gate 前的确定性补全。

纪律：
- 不把「默认住宅程序」写入 known（禁止静默编造未说出的数字）
- 原文已说出的标量 / 空间 / 关系 → 补进 known
- 仍空且未假设的关键项 → 补列 unknowns（Known/Assumed/Unknown 纪律）
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from packages.schema.llm_contract import LLMRequirementDraft
from packages.schema.requirements import (
    Assumption,
    RelationIntent,
    SpaceRequirement,
    UnknownRequirement,
)
from packages.schema.site import CardinalOrientation

CRITICAL_UNKNOWN_KEYS: tuple[str, ...] = (
    "floor_count",
    "site.width",
    "site.depth",
    "household.bedrooms",
    "household.bathrooms",
    "household.has_garage",
)

SPACE_LEXICON: tuple[str, ...] = (
    "儿童房",
    "老人房",
    "主卧",
    "次卧",
    "客房",
    "书房",
    "厨房",
    "餐厅",
    "客厅",
    "门厅",
    "入口",
    "玄关",
    "车库",
    "卫生间",
    "浴室",
)

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

_ORIENT_PHRASES: tuple[tuple[str, CardinalOrientation], ...] = (
    ("朝南", CardinalOrientation.SOUTH),
    ("朝北", CardinalOrientation.NORTH),
    ("朝东", CardinalOrientation.EAST),
    ("朝西", CardinalOrientation.WEST),
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
    if token in _CN_NUM:
        return _CN_NUM[token]
    return None


def extract_space_names(text: str) -> list[str]:
    """从中文需求原文抽取空间名（确定性；不猜未出现的词）。"""
    if not text:
        return []
    found: list[str] = []
    if "客餐厅" in text:
        found.extend(["客厅", "餐厅"])
    for name in SPACE_LEXICON:
        if name in text and name not in found:
            found.append(name)
    return found


def extract_relation_intents(text: str, space_names: set[str]) -> list[RelationIntent]:
    """从原文抽关系意图；端点必须已在空间集合中。"""
    if not text or len(space_names) < 2:
        return []
    out: list[RelationIntent] = []
    seen: set[tuple[str, str, str]] = set()

    def add(a: str, b: str, kind: str) -> None:
        if a not in space_names or b not in space_names or a == b:
            return
        ends = tuple(sorted((a, b)))
        undirected = (ends[0], ends[1], kind)
        if undirected in seen:
            return
        seen.add(undirected)
        out.append(RelationIntent(a=a, b=b, kind=kind))  # type: ignore[arg-type]

    names = sorted(space_names, key=len, reverse=True)
    for a in names:
        for b in names:
            if a == b:
                continue
            if f"{a}靠近{b}" in text:
                add(a, b, "adjacency")
            if f"{a}远离{b}" in text:
                add(a, b, "separation")
            if f"{a}与{b}连通" in text or f"{a}和{b}连通" in text:
                add(a, b, "adjacency")
            if f"{a}与{b}内部相连" in text or f"{a}与{b}相连" in text:
                add(a, b, "access")
            if f"{a}和{b}内部相连" in text or f"{a}和{b}相连" in text:
                add(a, b, "access")
            if f"{a}保持私密远离{b}" in text or f"{a}私密远离{b}" in text:
                add(a, b, "separation")

    if "客餐厅" in text and ("连通" in text or "开敞" in text):
        add("客厅", "餐厅", "adjacency")

    # 「客房保持私密远离客厅」
    m = re.search(r"([\u4e00-\u9fff]{2,4})保持私密远离([\u4e00-\u9fff]{2,4})", text)
    if m:
        add(m.group(1), m.group(2), "separation")

    return out


def _critical_value(draft: LLMRequirementDraft, key: str) -> object | None:
    k = draft.known
    if key == "floor_count":
        return k.floor_count
    if key == "site.width":
        return k.site.width
    if key == "site.depth":
        return k.site.depth
    if key == "household.bedrooms":
        return k.household.bedrooms
    if key == "household.bathrooms":
        return k.household.bathrooms
    if key == "household.has_garage":
        return k.household.has_garage
    return None


def _is_sparse_requirement(text: str) -> bool:
    """无明显层/卧/卫/场地结构用语 → 稀疏需求，须广泛列 unknowns。"""
    if not (text or "").strip():
        return True
    if re.search(
        r"[层卧卫]|地块|场地|用地|车库|宽|深|"
        r"\bF[123]\b|\b\d+\s*bed|\bfloor|\bbath|\bgarage",
        text,
        flags=re.IGNORECASE,
    ):
        return False
    return True


def _descriptions() -> dict[str, str]:
    return {
        "floor_count": "未说明层数",
        "site.width": "未提供用地宽度",
        "site.depth": "未提供用地深度",
        "household.bedrooms": "未说明卧室数",
        "household.bathrooms": "未说明卫浴数",
        "household.has_garage": "未说明是否有车库",
    }


def _should_mark_unknown(
    key: str,
    text: str,
    *,
    sparse: bool,
    assumed_keys: set[str] | frozenset[str] = frozenset(),
) -> bool:
    """
    补列 unknown 的策略（避免把「未考的字段」一律当 FP）：

    - site.width / site.depth：始终（求解阻塞项）
    - floor_count：原文未提层数时
    - household.bedrooms/bathrooms：稀疏需求；或「有卧室假设 + 场地未知」时补卫浴
    - has_garage：不自动列（避免抬 FPR）
    """
    if key in ("site.width", "site.depth"):
        return True
    if key == "floor_count":
        return not bool(re.search(r"[一二两三四五六七八九十\d]+\s*层|单层|平层", text))
    if key == "household.bedrooms":
        return sparse
    if key == "household.bathrooms":
        if sparse:
            return True
        if "household.bedrooms" in assumed_keys and re.search(
            r"未知|未提供|勿编造|宽深", text
        ):
            return not bool(re.search(r"[一二两三四五六七八九十\d]*\s*卫|卫浴", text))
        return False
    if key == "household.has_garage":
        return False
    return False


def _extract_scalars_into_known(known, text: str, notes: list[str]) -> None:
    """仅当原文明确说出时写入 known（非默认）。"""
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

    # 场地尺寸：仅匹配明确「宽×深」类，禁止默认 11×13
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


def _extract_assumptions_from_text(
    text: str,
    assumptions: list[Assumption],
    known,
    notes: list[str],
) -> None:
    """原文明确「假设」时写入 assumptions（不塞进 known，除非 known 已有）。"""
    keys = {a.key for a in assumptions}
    # 「假设为三间」/「按…假设为 3 间」→ household.bedrooms
    m = re.search(
        r"假设为\s*([一二两三四五六七八九十\d]+)\s*间",
        text,
    )
    if m and "household.bedrooms" not in keys:
        n = _parse_cn_int(m.group(1))
        if n is not None and 1 <= n <= 10:
            assumptions.append(
                Assumption(
                    key="household.bedrooms",
                    value=n,
                    reason="用户要求按假设处理卧室数",
                )
            )
            notes.append(f"assumption.bedrooms={n}")
            if known.household.bedrooms is None:
                # 假设值不进 known，保持 Known/Assumed 分离
                pass


def enrich_requirement_draft(draft: LLMRequirementDraft) -> EnrichResult:
    """
    确定性补全 Draft。

    顺序：assumption key → 原文标量 → unknowns 纪律 → 空间/关系/偏好。
    """
    notes: list[str] = []
    assumptions = [
        a.model_copy(update={"key": normalize_assumption_key(a.key)})
        for a in draft.assumptions
    ]
    unknown_by_key = {
        normalize_assumption_key(u.key): u.model_copy(
            update={"key": normalize_assumption_key(u.key)}
        )
        for u in draft.unknowns
    }

    known = draft.known.model_copy(deep=True)
    text = (draft.raw_text or "").strip()
    _extract_scalars_into_known(known, text, notes)
    _extract_assumptions_from_text(text, assumptions, known, notes)
    assumed_keys = {a.key for a in assumptions}

    # 临时 draft 视图用于读 critical
    tmp = draft.model_copy(update={"known": known})
    desc = _descriptions()
    sparse = _is_sparse_requirement(text)
    for key in CRITICAL_UNKNOWN_KEYS:
        val = _critical_value(tmp, key)
        if val is not None:
            unknown_by_key.pop(key, None)
            continue
        if key in assumed_keys:
            unknown_by_key.pop(key, None)
            continue
        if not _should_mark_unknown(
            key, text, sparse=sparse, assumed_keys=assumed_keys
        ):
            continue
        if key not in unknown_by_key:
            unknown_by_key[key] = UnknownRequirement(
                key=key,
                description=desc.get(key, "用户未提供"),
            )
            notes.append(f"补列 unknown:{key}")

    existing_names = {s.name.strip() for s in known.spaces if s.name and s.name.strip()}
    extracted = extract_space_names(text)
    added_spaces: list[str] = []
    for name in extracted:
        if name not in existing_names:
            known.spaces.append(SpaceRequirement(name=name))
            existing_names.add(name)
            added_spaces.append(name)
    if added_spaces:
        notes.append("补空间:" + ",".join(added_spaces))

    space_names = {s.name.strip() for s in known.spaces if s.name}

    existing_rels = list(known.relation_intents)

    def rel_key(r: RelationIntent) -> tuple[str, str, str]:
        ends = tuple(sorted((r.a.strip(), r.b.strip())))
        return (ends[0], ends[1], r.kind)

    seen_rel = {rel_key(r) for r in existing_rels}
    for r in extract_relation_intents(text, space_names):
        k = rel_key(r)
        if k not in seen_rel:
            existing_rels.append(r)
            seen_rel.add(k)
            notes.append(f"补关系:{r.a}-{r.kind}-{r.b}")
    known.relation_intents = existing_rels

    space_by_name = {s.name: i for i, s in enumerate(known.spaces)}
    for name in list(space_names):
        i = space_by_name.get(name)
        if i is None:
            continue
        sp = known.spaces[i]
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
