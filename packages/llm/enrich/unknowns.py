"""Unknowns stage — precision-first unknown discipline."""

from __future__ import annotations

import re

from packages.llm.enrich._text import _CN_NUM_TOKEN
from packages.llm.enrich.context import EnrichmentContext
from packages.schema.llm_contract import LLMRequirementDraft
from packages.schema.requirements import UnknownRequirement

# 求解阻塞项：仅在「场地未说明」语义下补列 unknown（非一律问卷）
_SITE_UNCERTAIN_RE = re.compile(
    r"场地|地块|用地|宽深|未提供|未知|勿编造|不要编造|未给|未定"
)

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


def critical_value(draft: LLMRequirementDraft, key: str) -> object | None:
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


def is_sparse_requirement(text: str) -> bool:
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


def has_site_dimensions(text: str) -> bool:
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


def text_provides_bedrooms(text: str) -> bool:
    return bool(
        re.search(r"([一二两三四五六七八九十\d]+)\s*卧", text)
        or re.search(r"卧室\s*([一二两三四五六七八九十\d]+)\s*间", text)
        or re.search(r"([一二两三四五六七八九十\d]+)\s*间卧室", text)
        or re.search(r"([一二两三四五六七八九十\d]+)\s*个卧室", text)
        or re.search(r"睡房\s*([一二两三四五六七八九十\d]+)\s*间", text)
        or re.search(r"([一二两三四五六七八九十\d]+)\s*间睡房", text)
        or re.search(r"([一二两三四五六七八九十\d]+)\s*房(?!屋)", text)
        or re.search(r"([一二两三四五六七八九十\d]+)\s*居", text)
        or re.search(r"([一二两三四五六七八九十\d]+)\s*室(?!内)", text)
        or re.search(r"\b\d+\s*bed", text, flags=re.IGNORECASE)
        or re.search(r"床位\s*([一二两三四五六七八九十\d]+)", text)
    )


def text_provides_bathrooms(text: str) -> bool:
    return bool(
        re.search(r"([一二两三四五六七八九十\d]+)\s*卫", text)
        or re.search(r"([一二两三四五六七八九十\d]+)\s*个卫生间", text)
        or re.search(r"([一二两三四五六七八九十\d]+)\s*个洗手间", text)
        or re.search(r"卫浴\s*([一二两三四五六七八九十\d]+)\s*间", text)
        or re.search(r"([一二两三四五六七八九十\d]+)\s*个浴室", text)
        or re.search(r"卫生间\s*([一二两三四五六七八九十\d]+)\s*个?", text)
        or re.search(r"洗手间\s*([一二两三四五六七八九十\d]+)\s*个?", text)
        or re.search(r"卫生间.{0,8}([一二两三四五六七八九十\d]+)", text)
        or re.search(r"\b\d+\s*bath", text, flags=re.IGNORECASE)
    )


def text_provides_floor_count(text: str) -> bool:
    return bool(
        re.search(r"([一二两三四五六七八九十\d]+)\s*层", text)
        or "单层" in text
        or "平层" in text
        or "双层" in text
        or re.search(r"\bF[123]\b", text)
        or re.search(r"层数\s*[=：:]\s*([一二两三四五六七八九十\d]+)", text)
        or re.search(r"楼层\s*[=：:]\s*([一二两三四五六七八九十\d]+)", text)
    )


def explicit_unknown_phrase(key: str, text: str) -> bool:
    """用户明示某项未定 / 别瞎猜。"""
    deferred = "别的以后再说" in text or "其余未定" in text
    if key == "household.bedrooms":
        return bool(
            re.search(r"(?:卧室|睡房).{0,8}(还没|未|没想好|未定)", text)
            or re.search(r"几间.{0,8}(?:卧室|睡房).{0,8}(还没|没想好|未定)", text)
            or (
                "卧室数量" in text
                and re.search(r"还没|未定|没想好", text)
            )
            or deferred
        )
    if key == "household.bathrooms":
        return bool(
            re.search(r"(卫生间|卫浴|洗手间).{0,8}(未定|还没|未说明)", text)
            or "卫生间数量" in text
            or deferred
        )
    if key == "floor_count":
        return bool(
            re.search(r"(层数|楼层).{0,6}(未|还没)", text)
            or re.search(r"几层.{0,16}(还没|没想好|未定)", text)
            or deferred
        )
    if key == "household.has_garage":
        return bool(
            re.search(r"不提车库|不要瞎加车库|未说明车库|车库未定", text)
        )
    return False


def should_mark_unknown(
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
        if has_site_dimensions(text):
            return False
        return bool(text.strip())
    if key == "floor_count":
        if text_provides_floor_count(text):
            return False
        return sparse or explicit_unknown_phrase(key, text)
    if key == "household.bedrooms":
        if text_provides_bedrooms(text):
            return False
        return sparse or explicit_unknown_phrase(key, text)
    if key == "household.bathrooms":
        if text_provides_bathrooms(text):
            return False
        return sparse or explicit_unknown_phrase(key, text)
    if key == "household.has_garage":
        return explicit_unknown_phrase(key, text)
    return False


def priority_for_unknown(key: str) -> str:
    if key in ("site.width", "site.depth"):
        return "blocking"
    if key in ("floor_count", "household.bedrooms"):
        return "recommended"
    return "optional"


class UnknownsStage:
    def apply(self, context: EnrichmentContext) -> EnrichmentContext:
        text = context.text
        known = context.known
        notes = context.notes
        unknown_by_key = context.unknown_by_key
        assumed_keys = {a.key for a in context.assumptions}

        tmp = context.original.model_copy(update={"known": known})
        sparse = is_sparse_requirement(text)
        context.sparse = sparse
        incoming_unknowns = context.incoming_unknowns

        # 剔除 LLM 问卷式 / 无策略依据的 unknowns（抬 unknown precision）
        for key in list(unknown_by_key):
            if key not in _MANAGED_UNKNOWN_KEYS:
                unknown_by_key.pop(key, None)
                notes.append(f"剔除非托管 unknown:{key}")
                context.record("unknown", "drop_unmanaged", key)
                continue
            val = critical_value(tmp, key)
            if val is not None:
                unknown_by_key.pop(key, None)
                notes.append(f"已知剔除 unknown:{key}")
                context.record("unknown", "drop_known", key)
                continue
            if should_mark_unknown(
                key, text, sparse=sparse, assumed_keys=assumed_keys
            ):
                continue
            # 保留调用方已声明的 unknown：site / 未给出的标量；车库仅明示未定
            if key in incoming_unknowns:
                if key == "household.has_garage":
                    if explicit_unknown_phrase(key, text):
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
            context.record("unknown", "drop_policy", key)

        for key in (
            "floor_count",
            "site.width",
            "site.depth",
            "household.bedrooms",
            "household.bathrooms",
            "household.has_garage",
        ):
            val = critical_value(tmp, key)
            if val is not None:
                continue
            if not should_mark_unknown(
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
                    priority=priority_for_unknown(key),  # type: ignore[arg-type]
                )
                notes.append(f"补列 unknown:{key}")
                context.record("unknown", "add", key)
        return context
