"""Shared text helpers for deterministic enrichment stages."""

from __future__ import annotations

import re

from packages.llm.vocabulary import ENTRY_ALIAS_GROUP, RESIDENTIAL_ROOMS

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

_CN_NUM_TOKEN = r"[一二两三四五六七八九十]+|\d+(?:\.\d+)?"


def parse_cn_int(token: str) -> int | None:
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


def parse_measure_token(token: str) -> float | None:
    token = (token or "").strip()
    if not token:
        return None
    if re.fullmatch(r"\d+(?:\.\d+)?", token):
        return float(token)
    n = parse_cn_int(token)
    return float(n) if n is not None else None


def surface_forms_for_space(canon: str) -> tuple[str, ...]:
    """规范名的表面形式（含别名），用于楼层/朝向/关系短语匹配。"""
    forms = {canon}
    for room in RESIDENTIAL_ROOMS:
        if room.canonical_zh == canon:
            forms.update(room.aliases_zh)
            forms.add(room.canonical_zh)
    if canon in ENTRY_ALIAS_GROUP or canon in ("门厅", "入口"):
        forms |= set(ENTRY_ALIAS_GROUP)
    return tuple(sorted(forms, key=len, reverse=True))


def living_prefers_south(text: str) -> bool:
    """客厅/起居 ↔ 朝南/南向（语序不限；一般规律）。"""
    return bool(
        re.search(
            r"(?:客厅|起居室).{0,6}(?:朝南|要南向|南向)|"
            r"(?:朝南|南向).{0,4}(?:客厅|起居室)",
            text,
        )
    )


def garage_soft_preference(text: str) -> bool:
    """软偏好：更好/也行/最好有 — 不定 has_garage=True。"""
    return bool(
        re.search(
            r"有车库更好|车库有更好|最好有车库|有车库也行|车库优先",
            text,
        )
    )


def explicit_garage_true(text: str) -> bool:
    """明示需要停车；仅软偏好时返回 False。"""
    hard = bool(
        re.search(r"带车库|要车库|车位要有|双车位|得有(?:个)?车库", text)
        or re.search(r"车库要(?!更好)", text)
        or re.search(r"车库有(?!更好)", text)
        or ("有车库" in text and "有车库更好" not in text and "有车库也行" not in text)
        or ("有车位" in text and "没有车位" not in text)
        or (re.search(r"车位.{0,4}要", text) and "不要车位" not in text)
        # 把车库当房间谈（连着/靠近/从…进）⇒ 需要车库
        or re.search(r"从车库|车库连着|车库靠近|车库与|车库和", text)
    )
    if not hard:
        return False
    if garage_soft_preference(text) and not re.search(
        r"带车库|要车库|车位要有|双车位|得有(?:个)?车库", text
    ):
        if "有车库更好" in text or "车库有更好" in text or "最好有车库" in text:
            return False
    return True
