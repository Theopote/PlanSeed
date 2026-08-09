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

import re
from dataclasses import dataclass

from packages.llm.vocabulary import (
    ENTRY_ALIAS_GROUP,
    RESIDENTIAL_ROOMS,
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

# 高置信关系模板：(模式字符串格式化用 {a}{b}, kind)
# 一般规律：显式二元谓词，不把「靠近」与「连通」混为 adjacency
_REL_TEMPLATES: tuple[tuple[str, RelationKind], ...] = (
    ("{a}靠近{b}", "near"),
    ("{a}挨着{b}", "near"),
    ("{a}最好挨着{b}", "near"),
    ("{a}尽量挨着{b}", "near"),
    ("{a}最好靠近{b}", "near"),
    ("{a}邻近{b}", "near"),
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

_ORIENT_PHRASES: tuple[tuple[str, CardinalOrientation], ...] = (
    ("朝南", CardinalOrientation.SOUTH),
    ("朝北", CardinalOrientation.NORTH),
    ("朝东", CardinalOrientation.EAST),
    ("朝西", CardinalOrientation.WEST),
    ("要南向", CardinalOrientation.SOUTH),
    ("要北向", CardinalOrientation.NORTH),
    ("南向", CardinalOrientation.SOUTH),
    ("北向", CardinalOrientation.NORTH),
    ("东向", CardinalOrientation.EAST),
    ("西向", CardinalOrientation.WEST),
    ("偏南", CardinalOrientation.SOUTH),
    ("偏北", CardinalOrientation.NORTH),
    ("偏东", CardinalOrientation.EAST),
    ("偏西", CardinalOrientation.WEST),
)


@dataclass(frozen=True)
class EnrichResult:
    draft: LLMRequirementDraft
    notes: tuple[str, ...] = ()


def normalize_assumption_key(key: str) -> str:
    k = (key or "").strip()
    return _ASSUMPTION_KEY_ALIASES.get(k, k)


def _parse_cn_int(token: str) -> int | None:
    """解析中文/阿拉伯整数（含十一～十九、二十～三十等常见量词）。"""
    token = (token or "").strip()
    if not token:
        return None
    if token.isdigit():
        return int(token)
    if token in _CN_NUM:
        return _CN_NUM[token]
    # 十一～十九
    if token.startswith("十") and len(token) == 2:
        ones = _CN_NUM.get(token[1])
        if ones is not None and ones < 10:
            return 10 + ones
    if token == "十":
        return 10
    # 二十、三十…（场地尺寸偶见）
    if len(token) >= 2 and token[1] == "十":
        tens = _CN_NUM.get(token[0])
        if tens is not None and 2 <= tens <= 5:
            if len(token) == 2:
                return tens * 10
            ones = _CN_NUM.get(token[2])
            if ones is not None and ones < 10:
                return tens * 10 + ones
    return None


_CN_NUM_TOKEN = r"[一二两三四五六七八九十]+|\d+(?:\.\d+)?"


def _parse_measure_token(token: str) -> float | None:
    token = (token or "").strip()
    if not token:
        return None
    if re.fullmatch(r"\d+(?:\.\d+)?", token):
        return float(token)
    n = _parse_cn_int(token)
    return float(n) if n is not None else None


def _surface_forms_for_space(canon: str) -> tuple[str, ...]:
    """规范名的表面形式（含别名），用于楼层/朝向/关系短语匹配。"""
    forms = {canon}
    for room in RESIDENTIAL_ROOMS:
        if room.canonical_zh == canon:
            forms.update(room.aliases_zh)
            forms.add(room.canonical_zh)
    if canon in ENTRY_ALIAS_GROUP or canon in ("门厅", "入口"):
        forms |= set(ENTRY_ALIAS_GROUP)
    return tuple(sorted(forms, key=len, reverse=True))


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
            for sa in _surface_forms_for_space(a):
                for sb in _surface_forms_for_space(b):
                    for tmpl, kind in _REL_TEMPLATES:
                        if tmpl.format(a=sa, b=sb) in text:
                            add(a, b, kind)
                    if f"从{sa}能进{sb}" in text or f"从{sa}进入{sb}" in text:
                        add(a, b, "access")

    # 「A…不要靠着B」：主语可与谓词隔开（同一分句前缀）
    for b in names:
        for sb in _surface_forms_for_space(b):
            for m in re.finditer(rf"不要靠着?{re.escape(sb)}", text):
                prefix = text[max(0, m.start() - 24) : m.start()]
                for a in names:
                    if a == b:
                        continue
                    if any(sa in prefix for sa in _surface_forms_for_space(a)):
                        add(a, b, "separation")

    if "客餐厅" in text and ("连通" in text or "开敞" in text):
        add("客厅", "餐厅", "open_connection")
    if ("餐厨" in text or "厨餐" in text) and (
        "近" in text or "挨" in text or "靠" in text
    ):
        add("厨房", "餐厅", "near")

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


def _kind_cue_in_text(kind: RelationKind, text: str) -> bool:
    return any(c in text for c in _KIND_CUES.get(kind, ()))


def relation_evidenced_in_text(rel: RelationIntent, text: str) -> bool:
    """关系是否有原文证据（precision-first）。

    保留：高置信模板，或「两端均出现 + kind 谓词线索」。
    仅两端共现不够（LLM 常给共现房间乱加 near/adjacency）。
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
            if f"从{va}能进{vb}" in text or f"从{va}进入{vb}" in text:
                if rel.kind in ("access", "adjacency"):
                    return True
            # 分句主语 + 不要靠着
            if rel.kind in ("separation", "adjacency"):
                for m in re.finditer(rf"不要靠着?{re.escape(vb)}", text):
                    prefix = text[max(0, m.start() - 24) : m.start()]
                    if va in prefix:
                        return True

    if not (
        _endpoint_mentioned_in_text(a, text) and _endpoint_mentioned_in_text(b, text)
    ):
        return False

    ends = {canonical_zh_for_alias(a), canonical_zh_for_alias(b)}
    if rel.kind in ("open_connection", "adjacency") and "客餐厅" in text:
        if ends == {"客厅", "餐厅"} and ("连通" in text or "开敞" in text):
            return True
    if ("餐厨" in text or "厨餐" in text) and rel.kind in ("near", "adjacency"):
        if ends == {"厨房", "餐厅"} and (
            _kind_cue_in_text("near", text) or "近" in text
        ):
            return True

    return _kind_cue_in_text(rel.kind, text)

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
        m = (
            re.search(r"([一二两三四五六七八九十\d]+)\s*层", text)
            or re.search(r"层数\s*[=：:]\s*([一二两三四五六七八九十\d]+)", text)
            or re.search(r"楼层\s*[=：:]\s*([一二两三四五六七八九十\d]+)", text)
            or re.search(r"\bF([123])\b", text)
        )
        if m:
            n = _parse_cn_int(m.group(1))
            if n in (1, 2, 3):
                known.floor_count = n
                notes.append(f"known.floor_count={n}")
        elif "单层" in text or "平层" in text:
            known.floor_count = 1
            notes.append("known.floor_count=1")

    if known.household.bedrooms is None:
        m = (
            re.search(r"([一二两三四五六七八九十\d]+)\s*卧", text)
            or re.search(r"卧室\s*([一二两三四五六七八九十\d]+)\s*间", text)
            or re.search(r"([一二两三四五六七八九十\d]+)\s*间卧室", text)
            or re.search(r"([一二两三四五六七八九十\d]+)\s*个卧室", text)
            or re.search(r"床位\s*([一二两三四五六七八九十\d]+)\s*间", text)
            or re.search(r"卧室数\s*([一二两三四五六七八九十\d]+)", text)
            or re.search(r"([一二两三四五六七八九十\d]+)\s*房(?!屋)", text)
            or re.search(r"([一二两三四五六七八九十\d]+)\s*居", text)
            or re.search(r"([一二两三四五六七八九十\d]+)\s*室(?!内)", text)
            or re.search(r"(\d+)\s*bed", text, flags=re.IGNORECASE)
        )
        if m:
            n = _parse_cn_int(m.group(1))
            if n is not None and 1 <= n <= 10:
                known.household.bedrooms = n
                notes.append(f"known.bedrooms={n}")

    if known.household.bathrooms is None:
        m = (
            re.search(r"([一二两三四五六七八九十\d]+)\s*卫", text)
            or re.search(r"([一二两三四五六七八九十\d]+)\s*个卫生间", text)
            or re.search(r"卫浴\s*([一二两三四五六七八九十\d]+)\s*间", text)
            or re.search(r"([一二两三四五六七八九十\d]+)\s*个浴室", text)
            or re.search(r"卫生间\s*([一二两三四五六七八九十\d]+)\s*个?", text)
            or re.search(r"卫生间.{0,8}([一二两三四五六七八九十\d]+)", text)
        )
        if m:
            n = _parse_cn_int(m.group(1))
            if n is not None and 1 <= n <= 8:
                known.household.bathrooms = n
                notes.append(f"known.bathrooms={n}")

    if known.household.has_garage is None:
        # 否定优先（避免「没有车位」命中「有车位」子串）
        if (
            "无车库" in text
            or "不要车库" in text
            or "车库不要" in text
            or "车库暂时不要" in text
            or ("暂时不要" in text and "车库" in text)
            or "没有车库" in text
            or "没有车位" in text
            or "不要车位" in text
            or "无车位" in text
        ):
            known.household.has_garage = False
            notes.append("known.has_garage=false")
        elif (
            "带车库" in text
            or "有车库" in text
            or "要车库" in text
            or "车库要" in text
            or "车库有" in text
            or "车位要有" in text
            or "有车位" in text
            or "双车位" in text
            or re.search(r"车位.{0,4}(要|有)", text)
        ):
            known.household.has_garage = True
            notes.append("known.has_garage=true")

    if known.site.width is None or known.site.depth is None:
        m = re.search(
            rf"(?:地块|场地|用地)?\s*(?:大约|约\s*)?"
            rf"({_CN_NUM_TOKEN})\s*[×xX＊*乘]\s*({_CN_NUM_TOKEN})\s*米?",
            text,
        )
        if m:
            w, d = _parse_measure_token(m.group(1)), _parse_measure_token(m.group(2))
            if w is not None and known.site.width is None and 6 <= w <= 60:
                known.site.width = w
                notes.append(f"known.site.width={w}")
            if d is not None and known.site.depth is None and 6 <= d <= 60:
                known.site.depth = d
                notes.append(f"known.site.depth={d}")
        else:
            # 「宽 12 米、深 15 米」/「十二米宽、十四米进深」/「宽十五米深十八米」
            mw = (
                re.search(
                    rf"(?:宽|宽度)\s*({_CN_NUM_TOKEN})\s*米?",
                    text,
                )
                or re.search(
                    rf"({_CN_NUM_TOKEN})\s*米\s*宽",
                    text,
                )
            )
            md = (
                re.search(
                    rf"(?:深|进深)\s*({_CN_NUM_TOKEN})\s*米?",
                    text,
                )
                or re.search(
                    rf"({_CN_NUM_TOKEN})\s*米\s*(?:深|进深)",
                    text,
                )
            )
            if mw and known.site.width is None:
                w = _parse_measure_token(mw.group(1))
                if w is not None and 6 <= w <= 60:
                    known.site.width = w
                    notes.append(f"known.site.width={w}")
            if md and known.site.depth is None:
                d = _parse_measure_token(md.group(1))
                if d is not None and 6 <= d <= 60:
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


def _has_site_dimensions(text: str) -> bool:
    return bool(
        re.search(
            rf"(?:大约|约\s*)?({_CN_NUM_TOKEN})\s*[×xX＊*乘]\s*({_CN_NUM_TOKEN})",
            text,
        )
        or re.search(rf"(?:宽|宽度)\s*({_CN_NUM_TOKEN})", text)
        or re.search(rf"(?:深|进深)\s*({_CN_NUM_TOKEN})", text)
        or re.search(rf"({_CN_NUM_TOKEN})\s*米\s*宽", text)
        or re.search(rf"({_CN_NUM_TOKEN})\s*米\s*(?:深|进深)", text)
    )


def _text_provides_bedrooms(text: str) -> bool:
    return bool(
        re.search(r"([一二两三四五六七八九十\d]+)\s*卧", text)
        or re.search(r"卧室\s*([一二两三四五六七八九十\d]+)\s*间", text)
        or re.search(r"([一二两三四五六七八九十\d]+)\s*间卧室", text)
        or re.search(r"([一二两三四五六七八九十\d]+)\s*个卧室", text)
        or re.search(r"([一二两三四五六七八九十\d]+)\s*房(?!屋)", text)
        or re.search(r"([一二两三四五六七八九十\d]+)\s*居", text)
        or re.search(r"([一二两三四五六七八九十\d]+)\s*室(?!内)", text)
        or re.search(r"\b\d+\s*bed", text, flags=re.IGNORECASE)
        or re.search(r"床位\s*([一二两三四五六七八九十\d]+)", text)
    )


def _text_provides_bathrooms(text: str) -> bool:
    return bool(
        re.search(r"([一二两三四五六七八九十\d]+)\s*卫", text)
        or re.search(r"([一二两三四五六七八九十\d]+)\s*个卫生间", text)
        or re.search(r"卫浴\s*([一二两三四五六七八九十\d]+)\s*间", text)
        or re.search(r"([一二两三四五六七八九十\d]+)\s*个浴室", text)
        or re.search(r"卫生间\s*([一二两三四五六七八九十\d]+)\s*个?", text)
        or re.search(r"卫生间.{0,8}([一二两三四五六七八九十\d]+)", text)
        or re.search(r"\b\d+\s*bath", text, flags=re.IGNORECASE)
    )


def _text_provides_floor_count(text: str) -> bool:
    return bool(
        re.search(r"([一二两三四五六七八九十\d]+)\s*层", text)
        or "单层" in text
        or "平层" in text
        or re.search(r"\bF[123]\b", text)
        or re.search(r"层数\s*[=：:]\s*([一二两三四五六七八九十\d]+)", text)
        or re.search(r"楼层\s*[=：:]\s*([一二两三四五六七八九十\d]+)", text)
    )


def _explicit_unknown_phrase(key: str, text: str) -> bool:
    """用户明示某项未定 / 别瞎猜。"""
    deferred = "别的以后再说" in text or "其余未定" in text
    if key == "household.bedrooms":
        return bool(
            re.search(r"卧室.{0,8}(还没|未|没想好|未定)", text)
            or (
                "卧室数量" in text
                and re.search(r"还没|未定|没想好", text)
            )
            or deferred
        )
    if key == "household.bathrooms":
        return bool(
            re.search(r"(卫生间|卫浴).{0,8}(未定|还没|未说明)", text)
            or "卫生间数量" in text
            or deferred
        )
    if key == "floor_count":
        return bool(
            re.search(r"(层数|楼层).{0,6}(未|还没)", text) or deferred
        )
    if key == "household.has_garage":
        return bool(
            re.search(r"不提车库|不要瞎加车库|未说明车库|车库未定", text)
        )
    return False


def _should_mark_unknown(
    key: str,
    text: str,
    *,
    sparse: bool,
    assumed_keys: set[str],
) -> bool:
    """
    Unknown 纪律（precision-first）：

    - site.*：值缺失且原文无尺寸 → blocking
    - bedrooms/bathrooms/floor：稀疏、明示未定、或原文未给出该标量时不主动问卷；
      主动补列仅 sparse / 明示未定（保留 incoming 见 enrich）
    - has_garage：仅明示「不要瞎加」类
    """
    if key in assumed_keys:
        return False
    if key in ("site.width", "site.depth"):
        if _has_site_dimensions(text):
            return False
        return bool(text.strip())
    if key == "floor_count":
        if _text_provides_floor_count(text):
            return False
        return sparse or _explicit_unknown_phrase(key, text)
    if key == "household.bedrooms":
        if _text_provides_bedrooms(text):
            return False
        return sparse or _explicit_unknown_phrase(key, text)
    if key == "household.bathrooms":
        if _text_provides_bathrooms(text):
            return False
        return sparse or _explicit_unknown_phrase(key, text)
    if key == "household.has_garage":
        return _explicit_unknown_phrase(key, text)
    return False


_MANAGED_UNKNOWN_KEYS = frozenset(
    {
        "floor_count",
        "site.width",
        "site.depth",
        "household.bedrooms",
        "household.bathrooms",
        "household.has_garage",
    }
)

def _priority_for_unknown(key: str) -> str:
    if key in ("site.width", "site.depth"):
        return "blocking"
    if key in ("floor_count", "household.bedrooms"):
        return "recommended"
    return "optional"


def _text_has_floor1_pref(name: str, text: str) -> bool:
    """一般规律：某空间放/在/住一层或楼下；老人房含 paraphrase。"""
    for surf in _surface_forms_for_space(name):
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


def _orientation_for_space(name: str, text: str) -> CardinalOrientation | None:
    for surf in _surface_forms_for_space(name):
        for phrase, ori in _ORIENT_PHRASES:
            if f"{surf}{phrase}" in text:
                return ori
    return None


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
    incoming_unknowns = set(unknown_by_key)

    # 剔除 LLM 问卷式 / 无策略依据的 unknowns（抬 unknown precision）
    for key in list(unknown_by_key):
        if key not in _MANAGED_UNKNOWN_KEYS:
            unknown_by_key.pop(key, None)
            notes.append(f"剔除非托管 unknown:{key}")
            continue
        val = _critical_value(tmp, key)
        if val is not None:
            unknown_by_key.pop(key, None)
            notes.append(f"已知剔除 unknown:{key}")
            continue
        if _should_mark_unknown(
            key, text, sparse=sparse, assumed_keys=assumed_keys
        ):
            continue
        # 保留调用方已声明的 unknown：site / 未给出的标量；车库仅明示未定
        if key in incoming_unknowns:
            if key == "household.has_garage":
                if _explicit_unknown_phrase(key, text):
                    continue
            elif key in ("site.width", "site.depth"):
                continue
            elif key in (
                "floor_count",
                "household.bedrooms",
                "household.bathrooms",
            ):
                continue
        unknown_by_key.pop(key, None)
        notes.append(f"策略剔除 unknown:{key}")

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
            continue
        if not _should_mark_unknown(
            key, text, sparse=sparse, assumed_keys=assumed_keys
        ):
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
                    "household.has_garage": "未说明是否需要车库",
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
            continue
        kind = r.kind
        if kind == "adjacency":
            if _kind_cue_in_text("open_connection", text):
                kind = "open_connection"
            elif _kind_cue_in_text("access", text):
                kind = "access"
            elif _kind_cue_in_text("near", text) or "近" in text:
                kind = "near"
            elif _kind_cue_in_text("separation", text):
                kind = "separation"
        if kind != r.kind:
            notes.append(f"细化关系:{r.kind}->{kind}")
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
    known.relation_intents = grounded

    space_by_name = {canonical_zh_for_alias(s.name): i for i, s in enumerate(known.spaces)}
    for name in list(space_names):
        i = space_by_name.get(name)
        if i is None:
            continue
        sp = known.spaces[i]
        if not sp.floor_preference and _text_has_floor1_pref(name, text):
            known.spaces[i] = sp.model_copy(update={"floor_preference": ["F1"]})
            notes.append(f"楼层偏好:{name}=F1")
            sp = known.spaces[i]
        if sp.preferred_orientation is None:
            ori = _orientation_for_space(name, text)
            if ori is not None:
                known.spaces[i] = sp.model_copy(update={"preferred_orientation": ori})
                notes.append(f"朝向:{name}={ori}")
                if name == "客厅" and ori == CardinalOrientation.SOUTH:
                    if known.preferences.prefer_south_facing_living is None:
                        known.preferences.prefer_south_facing_living = True

    if known.preferences.prefer_south_facing_living is None and re.search(
        r"(?:客厅|起居室).{0,4}朝南|朝南.{0,4}(?:客厅|起居室)", text
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
