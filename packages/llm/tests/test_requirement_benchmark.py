"""Phase 6.6/6.7 — Requirement Benchmark。"""

from __future__ import annotations

from packages.llm.benchmark import (
    ExpectAssumption,
    ExpectFloorPreference,
    ExpectKnown,
    ExpectOrientation,
    ExpectRelation,
    RequirementBenchmarkCase,
    benchmark_case_count,
    expect_to_draft,
    load_benchmark_cases,
    run_benchmark,
    score_draft_against_case,
    score_requirement_case,
)
from packages.llm.semantic import RequirementSemanticValidator
from packages.schema.requirements import (
    Assumption,
    HouseholdRequirements,
    RelationIntent,
    RequirementSpec,
    SiteRequirements,
    SpaceRequirement,
    UnknownRequirement,
)
from packages.schema.site import CardinalOrientation


def test_corpus_size_at_least_50():
    assert benchmark_case_count() >= 50
    ids = [c.id for c in load_benchmark_cases()]
    assert len(ids) == len(set(ids))
    assert any(c.id.startswith("rb-05") for c in load_benchmark_cases())


def test_intent_cases_present():
    intent = [c for c in load_benchmark_cases() if "intent" in c.tags]
    assert len(intent) >= 5
    assert any(c.expect.relations for c in intent)


def test_unknown_detection_cases_present():
    tagged = [c for c in load_benchmark_cases() if "unknown-detection" in c.tags]
    assert len(tagged) >= 2
    assert any(c.expect_assumptions for c in load_benchmark_cases())


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
        unknowns=[
            UnknownRequirement(key="site.width"),
            UnknownRequirement(key="site.depth"),
        ],
    )
    scored = score_requirement_case(case, halluc)
    assert not scored.passed
    assert "site.width" in scored.hallucinations


def test_unknown_detection_requires_listing():
    """字段留空不够：must_unknown 必须显式出现在 unknowns。"""
    case = RequirementBenchmarkCase(
        id="t-unk-list",
        text="给我设计一个三口之家。",
        must_unknown=["household.bedrooms", "site.width"],
    )
    silent = RequirementSpec(floor_count=None)
    scored = score_requirement_case(case, silent)
    assert not scored.passed
    assert set(scored.missed_unknowns) == {"household.bedrooms", "site.width"}
    assert scored.unknown_tp == 0

    listed = RequirementSpec(
        unknowns=[
            UnknownRequirement(key="household.bedrooms", description="未说"),
            UnknownRequirement(key="site.width", description="未说"),
        ],
    )
    assert score_requirement_case(case, listed).passed


def test_assumption_precision_requires_reason():
    case = RequirementBenchmarkCase(
        id="t-assume",
        text="卧室先假设为三",
        expect=ExpectKnown(floor_count=2),
        expect_assumptions=[
            ExpectAssumption(key="household.bedrooms", value=3, require_reason=True),
        ],
    )
    no_reason = RequirementSpec(
        floor_count=2,
        assumptions=[Assumption(key="household.bedrooms", value=3, reason="")],
    )
    scored = score_requirement_case(case, no_reason)
    assert not scored.passed
    assert scored.assumption_hits == 0

    with_reason = RequirementSpec(
        floor_count=2,
        assumptions=[
            Assumption(
                key="household.bedrooms",
                value=3,
                reason="按三口之家假设",
            )
        ],
    )
    assert score_requirement_case(case, with_reason).passed


def test_score_relations_and_floor_pref():
    case = RequirementBenchmarkCase(
        id="t-rel",
        text="厨房靠近餐厅，老人房一层",
        expect=ExpectKnown(
            relations=[ExpectRelation(a="厨房", b="餐厅", kind="adjacency")],
            floor_preferences=[
                ExpectFloorPreference(space_name="老人房", floors=["F1"]),
            ],
            orientations=[
                ExpectOrientation(
                    space_name="书房",
                    orientation=CardinalOrientation.NORTH,
                ),
            ],
            space_names_contains=["厨房", "餐厅", "老人房", "书房"],
        ),
    )
    good = RequirementSpec(
        spaces=[
            SpaceRequirement(name="厨房"),
            SpaceRequirement(name="餐厅"),
            SpaceRequirement(name="老人房", floor_preference=["F1"]),
            SpaceRequirement(
                name="书房",
                preferred_orientation=CardinalOrientation.NORTH,
            ),
        ],
        relation_intents=[
            RelationIntent(a="餐厅", b="厨房", kind="adjacency"),
        ],
    )
    assert score_requirement_case(case, good).passed

    bad = RequirementSpec(
        spaces=[
            SpaceRequirement(name="厨房"),
            SpaceRequirement(name="餐厅"),
            SpaceRequirement(name="老人房"),
            SpaceRequirement(name="书房"),
        ],
        relation_intents=[],
    )
    scored = score_requirement_case(case, bad)
    assert not scored.passed
    assert scored.relation_hits == 0


def test_oracle_draft_includes_intent():
    case = RequirementBenchmarkCase(
        id="t-oracle-intent",
        text="厨房靠近餐厅",
        expect=ExpectKnown(
            floor_count=2,
            space_names_contains=["厨房", "餐厅"],
            relations=[ExpectRelation(a="厨房", b="餐厅", kind="adjacency")],
            floor_preferences=[
                ExpectFloorPreference(space_name="老人房", floors=["F1"]),
            ],
        ),
        must_unknown=["site.width"],
    )
    draft = expect_to_draft(case)
    assert "relation_intents" in draft["known"]
    names = {s["name"] for s in draft["known"]["spaces"]}
    assert "老人房" in names
    scored = score_draft_against_case(case, draft)
    assert scored.passed


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
    assert report.relation_recall == 1.0
    assert report.floor_preference_accuracy == 1.0
    assert report.orientation_accuracy == 1.0
    assert report.unknown_detection_recall == 1.0
    assert report.unknown_false_positive_rate == 0.0
    assert report.assumption_precision == 1.0
    summary = report.summary()
    assert summary["case_count"] >= 50
    assert summary["mode"] == "oracle"
    assert "unknown_detection_recall" in summary
    assert "assumption_precision" in summary


def test_relation_endpoint_soft_issues_per_side():
    """一端幻觉也要 soft warning（不能被另一端掩盖）。"""
    spec = RequirementSpec(
        spaces=[SpaceRequirement(name="厨房")],
        relation_intents=[
            RelationIntent(a="厨房", b="幻觉餐厅", kind="adjacency"),
        ],
    )
    result = RequirementSemanticValidator().validate_spec(spec)
    codes = {i.code for i in result.issues}
    assert "req.relation_b_unknown" in codes
    assert "req.relation_a_unknown" not in codes
    assert result.ok  # soft only

    both = RequirementSpec(
        spaces=[SpaceRequirement(name="客厅")],
        relation_intents=[
            RelationIntent(a="厨房X", b="餐厅Y", kind="adjacency"),
        ],
    )
    both_r = RequirementSemanticValidator().validate_spec(both)
    both_codes = {i.code for i in both_r.issues}
    assert "req.relation_a_unknown" in both_codes
    assert "req.relation_b_unknown" in both_codes
