"""Phase 6.7 / 6.7.1 — Requirement enricher（precision-first）。"""

from __future__ import annotations

from packages.llm.benchmark.cases import (
    ExpectKnown,
    ExpectRelation,
    RequirementBenchmarkCase,
)
from packages.llm.benchmark.runner import score_draft_against_case
from packages.llm.enrich import (
    enrich_requirement_draft,
    extract_relation_intents,
    extract_space_names,
)
from packages.llm.gate import ingest_llm_requirement
from packages.schema.llm_contract import LLMRequirementDraft


def test_extract_spaces_and_relations_from_text():
    text = "两层三卧，厨房靠近餐厅，客厅与餐厅连通"
    names = extract_space_names(text)
    assert set(names) >= {"厨房", "餐厅", "客厅"}
    rels = extract_relation_intents(text, set(names))
    kinds = {(tuple(sorted((r.a, r.b))), r.kind) for r in rels}
    assert ((tuple(sorted(("厨房", "餐厅"))), "near")) in kinds
    assert ((tuple(sorted(("客厅", "餐厅"))), "open_connection")) in kinds


def test_enrich_fills_unknowns_without_inventing_site():
    draft = LLMRequirementDraft(
        raw_text="两层三卧，场地未提供请勿编造宽深",
        known={"floor_count": 2, "household": {"bedrooms": 3}},  # type: ignore[arg-type]
    )
    out = enrich_requirement_draft(draft)
    keys = {u.key for u in out.draft.unknowns}
    assert "site.width" in keys
    assert "site.depth" in keys
    assert out.draft.known.site.width is None
    assert out.draft.known.floor_count == 2


def test_enrich_does_not_always_add_site_unknowns():
    """precision-first：无场地不确定语义时不主动问卷式补列 site。"""
    draft = LLMRequirementDraft(
        raw_text="两层三卧",
        known={"floor_count": 2, "household": {"bedrooms": 3}},  # type: ignore[arg-type]
    )
    out = enrich_requirement_draft(draft)
    keys = {u.key for u in out.draft.unknowns}
    assert "site.width" not in keys
    assert "site.depth" not in keys


def test_enrich_extracts_scalars_from_raw_text():
    draft = LLMRequirementDraft(raw_text="两层三卧两卫带车库，客厅朝南")
    out = enrich_requirement_draft(draft)
    assert out.draft.known.floor_count == 2
    assert out.draft.known.household.bedrooms == 3
    assert out.draft.known.household.bathrooms == 2
    assert out.draft.known.household.has_garage is True
    assert any(s.name == "客厅" for s in out.draft.known.spaces)
    assert out.draft.known.preferences.prefer_south_facing_living is True


def test_enrich_drops_llm_inference_assumptions():
    draft = LLMRequirementDraft(
        raw_text="两层三卧",
        known={"floor_count": 2},  # type: ignore[arg-type]
        assumptions=[
            {
                "key": "household.bathrooms",
                "value": 2,
                "reason": "常见默认",
                "source": "llm_inference",
            }
        ],
    )
    out = enrich_requirement_draft(draft)
    assert out.draft.assumptions == []


def test_ingest_enrich_recovers_intent_case():
    """LLM 漏列空间/关系时，enrich 应恢复原文显式意图。"""
    case = RequirementBenchmarkCase(
        id="t-enrich-053",
        text="两层三卧，厨房靠近餐厅，客厅与餐厅连通，场地未定",
        expect=ExpectKnown(
            floor_count=2,
            bedrooms=3,
            space_names_contains=["厨房", "餐厅", "客厅"],
            relations=[
                ExpectRelation(a="厨房", b="餐厅", kind="near"),
                ExpectRelation(a="客厅", b="餐厅", kind="open_connection"),
            ],
        ),
        must_unknown=["site.width", "site.depth"],
    )
    sparse = {
        "known": {"floor_count": 2},
        "assumptions": [],
        "unknowns": [],
    }
    scored = score_draft_against_case(case, sparse)
    assert scored.space_ok
    assert all(r.hit for r in scored.relations)
    assert not scored.missed_unknowns
    assert scored.passed


def test_ingest_enrich_sparse_unknown_detection():
    case = RequirementBenchmarkCase(
        id="t-enrich-061",
        text="给我设计一个三口之家。",
        expect=ExpectKnown(),
        must_unknown=[
            "floor_count",
            "site.width",
            "site.depth",
            "household.bedrooms",
            "household.bathrooms",
        ],
    )
    sparse = {"known": {}, "assumptions": [], "unknowns": []}
    scored = score_draft_against_case(case, sparse)
    assert not scored.missed_unknowns
    assert scored.passed


def test_enrich_can_be_disabled():
    raw = {
        "raw_text": "两层三卧，场地未提供",
        "known": {},
        "assumptions": [],
        "unknowns": [],
    }
    with_e = ingest_llm_requirement(raw, enrich=True)
    assert with_e.draft.known.floor_count == 2
    assert any(u.key == "site.width" for u in with_e.draft.unknowns)

    bare = ingest_llm_requirement(raw, enrich=False)
    assert bare.draft.known.floor_count is None
    assert bare.draft.unknowns == []
