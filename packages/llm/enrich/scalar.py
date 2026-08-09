"""Scalar extraction stage — floor / bedrooms / bathrooms / garage / site size."""

from __future__ import annotations

import re

from packages.llm.enrich._text import (
    _CN_NUM_TOKEN,
    explicit_garage_true,
    parse_cn_int,
    parse_measure_token,
)
from packages.llm.enrich.context import EnrichmentContext


def extract_scalars_into_known(known, text: str, notes: list[str]) -> None:
    """一般数量表达：N层 / N卧 / N卫 / 带车库 / 宽×深。"""
    if known.floor_count is None:
        m = (
            re.search(r"([一二两三四五六七八九十\d]+)\s*层", text)
            or re.search(r"层数\s*[=：:]\s*([一二两三四五六七八九十\d]+)", text)
            or re.search(r"楼层\s*[=：:]\s*([一二两三四五六七八九十\d]+)", text)
            or re.search(r"\bF([123])\b", text)
        )
        if m:
            n = parse_cn_int(m.group(1))
            if n in (1, 2, 3):
                known.floor_count = n
                notes.append(f"known.floor_count={n}")
        elif "单层" in text or "平层" in text:
            known.floor_count = 1
            notes.append("known.floor_count=1")
        elif "双层" in text:
            known.floor_count = 2
            notes.append("known.floor_count=2")

    if known.household.bedrooms is None:
        m = (
            re.search(r"([一二两三四五六七八九十\d]+)\s*卧", text)
            or re.search(r"卧室\s*([一二两三四五六七八九十\d]+)\s*间", text)
            or re.search(r"([一二两三四五六七八九十\d]+)\s*间卧室", text)
            or re.search(r"([一二两三四五六七八九十\d]+)\s*个卧室", text)
            or re.search(r"睡房\s*([一二两三四五六七八九十\d]+)\s*间", text)
            or re.search(r"([一二两三四五六七八九十\d]+)\s*间睡房", text)
            or re.search(r"床位\s*([一二两三四五六七八九十\d]+)\s*间", text)
            or re.search(r"卧室数\s*([一二两三四五六七八九十\d]+)", text)
            or re.search(r"([一二两三四五六七八九十\d]+)\s*房(?!屋)", text)
            or re.search(r"([一二两三四五六七八九十\d]+)\s*居", text)
            or re.search(r"([一二两三四五六七八九十\d]+)\s*室(?!内)", text)
            or re.search(r"(\d+)\s*bed", text, flags=re.IGNORECASE)
        )
        if m:
            n = parse_cn_int(m.group(1))
            if n is not None and 1 <= n <= 10:
                known.household.bedrooms = n
                notes.append(f"known.bedrooms={n}")

    if known.household.bathrooms is None:
        m = (
            re.search(r"([一二两三四五六七八九十\d]+)\s*卫", text)
            or re.search(r"([一二两三四五六七八九十\d]+)\s*个卫生间", text)
            or re.search(r"([一二两三四五六七八九十\d]+)\s*个洗手间", text)
            or re.search(r"卫浴\s*([一二两三四五六七八九十\d]+)\s*间", text)
            or re.search(r"([一二两三四五六七八九十\d]+)\s*个浴室", text)
            or re.search(r"卫生间\s*([一二两三四五六七八九十\d]+)\s*个?", text)
            or re.search(r"洗手间\s*([一二两三四五六七八九十\d]+)\s*个?", text)
            or re.search(r"卫生间.{0,8}([一二两三四五六七八九十\d]+)", text)
        )
        if m:
            n = parse_cn_int(m.group(1))
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
        elif explicit_garage_true(text):
            known.household.has_garage = True
            notes.append("known.has_garage=true")

    if known.site.width is None or known.site.depth is None:
        m = re.search(
            rf"(?:地块|场地|用地)?\s*(?:大约|约\s*)?"
            rf"({_CN_NUM_TOKEN})\s*[×xX＊*乘]\s*({_CN_NUM_TOKEN})\s*米?",
            text,
        )
        if m:
            w, d = parse_measure_token(m.group(1)), parse_measure_token(m.group(2))
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
                w = parse_measure_token(mw.group(1))
                if w is not None and 6 <= w <= 60:
                    known.site.width = w
                    notes.append(f"known.site.width={w}")
            if md and known.site.depth is None:
                d = parse_measure_token(md.group(1))
                if d is not None and 6 <= d <= 60:
                    known.site.depth = d
                    notes.append(f"known.site.depth={d}")


class ScalarStage:
    def apply(self, context: EnrichmentContext) -> EnrichmentContext:
        extract_scalars_into_known(context.known, context.text, context.notes)
        context.record("scalar", "extract_scalars")
        return context
