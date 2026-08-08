"""Phase 6.6 — Requirement Benchmark。"""

from __future__ import annotations

from packages.llm.benchmark import (
    ExpectKnown,
    RequirementBenchmarkCase,
    benchmark_case_count,
    expect_to_draft,
    load_benchmark_cases,
    run_benchmark,
    score_draft_against_case,
    score_requirement_case,
)
from packages.schema.requirements import (
    HouseholdRequirements,
    RequirementSpec,
    SiteRequirements,
)


def test_corpus_size_at_least_50():
    assert benchmark_case_count() >= 50
    ids = [c.id for c in load_benchmark_cases()]
    assert len(ids) == len(set(ids))


def test_score_hit_and_miss():
    case = RequirementBenchmarkCase(
        id="t-hit",
        text="两层三卧",
        expect=ExpectKnown(floor_count=2, bedrooms=3),
    )
    good = RequirementSpec(
        floor_count=2,
        household=HouseholdRequirements(bedrooms=3),
    )
    assert score_requirement_case(case, good).passed

    bad = RequirementSpec(
        floor_count=1,
        household=HouseholdRequirements(bedrooms=3),
    )
    scored = score_requirement_case(case, bad)
    assert not scored.passed
    assert scored.field_hits == 1
    assert scored.field_total == 2


def test_score_hallucination_on_must_unknown():
    case = RequirementBenchmarkCase(
        id="t-hall",
        text="两层，地块未定",
        expect=ExpectKnown(floor_count=2),
        must_unknown=["site.width", "site.depth"],
    )
    halluc = RequirementSpec(
        floor_count=2,
        site=SiteRequirements(width=11, depth=13),
    )
    scored = score_requirement_case(case, halluc)
    assert not scored.passed
    assert "site.width" in scored.hallucinations


def test_oracle_draft_respects_must_unknown():
    case = RequirementBenchmarkCase(
        id="t-oracle",
        text="两层两卧，场地未知",
        expect=ExpectKnown(floor_count=2, bedrooms=2),
        must_unknown=["site.width", "site.depth"],
    )
    draft = expect_to_draft(case)
    assert "site" not in draft["known"] or "width" not in draft["known"].get(
        "site", {}
    )
    assert any(u["key"] == "site.width" for u in draft["unknowns"])
    scored = score_draft_against_case(case, draft)
    assert scored.passed


def test_run_benchmark_oracle_perfect():
    report = run_benchmark(use_oracle=True)
    assert report.case_count >= 50
    assert report.field_accuracy == 1.0
    assert report.case_pass_rate == 1.0
    assert report.hallucination_rate == 0.0
    assert report.geometry_fails == 0
    summary = report.summary()
    assert summary["case_count"] >= 50
