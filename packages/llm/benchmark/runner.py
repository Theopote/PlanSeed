"""Requirement Benchmark 运行器（oracle Mock / 任意 LLMProvider）。"""

from __future__ import annotations

from typing import Any

from packages.llm.benchmark.cases import (
    ExpectKnown,
    RequirementBenchmarkCase,
    load_benchmark_cases,
)
from packages.llm.benchmark.report import BenchmarkReport
from packages.llm.benchmark.score import score_requirement_case
from packages.llm.boundary import GeometryForbiddenError
from packages.llm.gate import LLMIngestError, ingest_llm_requirement
from packages.llm.mock import MockLLMProvider
from packages.llm.parser import parse_requirement_text
from packages.llm.provider import LLMProvider
from packages.schema.requirements import RequirementSpec


def expect_to_draft(
    case: RequirementBenchmarkCase,
    *,
    include_raw_text: bool = True,
) -> dict[str, Any]:
    """
    由 gold expect 构造「完美」Draft（供 CI oracle）。

    must_unknown 对应字段故意留空，并写入 unknowns。
    """
    e = case.expect
    unknown_keys = set(case.must_unknown)

    def allowed(key: str) -> bool:
        return key not in unknown_keys

    known: dict[str, Any] = {}
    if e.floor_count is not None and allowed("floor_count"):
        known["floor_count"] = e.floor_count

    site: dict[str, Any] = {}
    if e.site_width is not None and allowed("site.width"):
        site["width"] = e.site_width
    if e.site_depth is not None and allowed("site.depth"):
        site["depth"] = e.site_depth
    if site:
        known["site"] = site

    household: dict[str, Any] = {}
    if e.bedrooms is not None and allowed("household.bedrooms"):
        household["bedrooms"] = e.bedrooms
    if e.bathrooms is not None and allowed("household.bathrooms"):
        household["bathrooms"] = e.bathrooms
    if e.has_garage is not None and allowed("household.has_garage"):
        household["has_garage"] = e.has_garage
    if household:
        known["household"] = household

    prefs: dict[str, Any] = {}
    if e.prefer_south_facing_living is not None:
        prefs["prefer_south_facing_living"] = e.prefer_south_facing_living
    if prefs:
        known["preferences"] = prefs

    spaces: list[dict[str, Any]] = []
    for name in e.space_names_contains:
        spaces.append({"name": name})
    if e.min_spaces:
        while len(spaces) < e.min_spaces:
            spaces.append({"name": f"空间{len(spaces) + 1}"})
    if spaces:
        known["spaces"] = spaces

    unknowns = [
        {"key": k, "description": "用例要求保持未知"} for k in case.must_unknown
    ]
    draft: dict[str, Any] = {
        "known": known,
        "assumptions": [],
        "unknowns": unknowns,
    }
    if include_raw_text:
        draft["raw_text"] = case.text
    return draft


def make_oracle_provider(
    cases: list[RequirementBenchmarkCase] | None = None,
) -> MockLLMProvider:
    """按 user 提示中的需求原文匹配用例，返回 gold Draft。"""
    corpus = {c.text: c for c in (cases or load_benchmark_cases())}

    def reply(system: str, user: str) -> dict[str, Any]:
        for text, case in corpus.items():
            if text in user:
                return expect_to_draft(case)
        # 回退：取 user 末段
        raise RuntimeError(f"oracle 未匹配用例文本：{user[:80]!r}")

    return MockLLMProvider(reply)


def run_benchmark(
    *,
    provider: LLMProvider | None = None,
    cases: list[RequirementBenchmarkCase] | None = None,
    use_oracle: bool = True,
) -> BenchmarkReport:
    """
    跑完整语料。

    默认 use_oracle=True（CI）；传入 provider 且 use_oracle=False 可测真模型。
    """
    corpus = cases or load_benchmark_cases()
    prov: LLMProvider
    if use_oracle:
        prov = make_oracle_provider(corpus)
    else:
        if provider is None:
            raise ValueError("use_oracle=False 时必须提供 provider")
        prov = provider

    report = BenchmarkReport()
    for case in corpus:
        geometry_fail = False
        try:
            parsed = parse_requirement_text(case.text, provider=prov)
            spec = parsed.spec
        except GeometryForbiddenError:
            geometry_fail = True
            spec = RequirementSpec(raw_text=case.text)
        except LLMIngestError:
            # 解析失败：记为空 spec，字段全 miss
            spec = RequirementSpec(raw_text=case.text)
        report.case_scores.append(
            score_requirement_case(case, spec, geometry_fail=geometry_fail)
        )
    return report


def score_draft_against_case(
    case: RequirementBenchmarkCase,
    draft: dict[str, Any],
) -> CaseScore:
    """直接对 Draft/dict 打分（不经 Provider）。"""
    try:
        ingest = ingest_llm_requirement(draft, raw_text=case.text)
        return score_requirement_case(case, ingest.spec)
    except GeometryForbiddenError:
        return score_requirement_case(
            case, RequirementSpec(raw_text=case.text), geometry_fail=True
        )
    except LLMIngestError:
        return score_requirement_case(case, RequirementSpec(raw_text=case.text))
