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


def test_enrich_does_not_questionnaire_optional_unknowns():
    """precision-first：结构化简述不把 has_garage 等做成问卷。"""
    draft = LLMRequirementDraft(
        raw_text="两层三卧",
        known={"floor_count": 2, "household": {"bedrooms": 3}},  # type: ignore[arg-type]
        unknowns=[
            {"key": "household.has_garage", "description": "未说明车库"},
            {"key": "site.entrance_edge", "description": "入口"},
        ],
    )
    out = enrich_requirement_draft(draft)
    keys = {u.key for u in out.draft.unknowns}
    assert "household.has_garage" not in keys
    assert "site.entrance_edge" not in keys
    assert "site.width" in keys
    assert "site.depth" in keys


def test_enrich_foyer_access_and_elder_floor_paraphrase():
    """门厅/玄关表面形式 + 老人楼下 paraphrase（一般规律）。"""
    out = enrich_requirement_draft(
        LLMRequirementDraft(raw_text="两层三卧两卫有车库，车库连着玄关，起居室朝南")
    )
    assert any(
        r.kind == "access" and {r.a, r.b} == {"车库", "门厅"}
        for r in out.draft.known.relation_intents
    )
    assert out.draft.known.preferences.prefer_south_facing_living is True

    elder = enrich_requirement_draft(
        LLMRequirementDraft(raw_text="两层四卧，老人最好住楼下，书房朝北")
    )
    sp = next(s for s in elder.draft.known.spaces if s.name == "老人房")
    assert sp.floor_preference == ["F1"]
    study = next(s for s in elder.draft.known.spaces if s.name == "书房")
    assert str(study.preferred_orientation) == "north"


def test_enrich_best_near_and_dont_lean_separation():
    near = enrich_requirement_draft(
        LLMRequirementDraft(raw_text="两层四卧，餐厅最好挨着厨房")
    )
    assert any(
        r.kind == "near" and {r.a, r.b} == {"厨房", "餐厅"}
        for r in near.draft.known.relation_intents
    )
    sep = enrich_requirement_draft(
        LLMRequirementDraft(
            raw_text="两层三卧，主卧安静一点，不要靠着客厅，儿童房挨着主卧"
        )
    )
    kinds = {(frozenset((r.a, r.b)), r.kind) for r in sep.draft.known.relation_intents}
    assert (frozenset({"主卧", "客厅"}), "separation") in kinds
    assert (frozenset({"儿童房", "主卧"}), "near") in kinds


def test_enrich_keeps_cued_relations():
    draft = LLMRequirementDraft(
        raw_text="两层三卧，厨房靠近餐厅，客厅朝南",
        known={  # type: ignore[arg-type]
            "floor_count": 2,
            "spaces": [{"name": "厨房"}, {"name": "餐厅"}],
            "relation_intents": [
                {"a": "厨房", "b": "餐厅", "kind": "near"},
            ],
        },
    )
    out = enrich_requirement_draft(draft)
    assert any(
        r.kind == "near"
        and {r.a, r.b} == {"厨房", "餐厅"}
        for r in out.draft.known.relation_intents
    )


def test_enrich_strips_ungrounded_llm_relations():
    draft = LLMRequirementDraft(
        raw_text="两层三卧，客厅朝南",
        known={  # type: ignore[arg-type]
            "floor_count": 2,
            "spaces": [{"name": "客厅"}, {"name": "厨房"}, {"name": "餐厅"}],
            "relation_intents": [
                {"a": "厨房", "b": "餐厅", "kind": "near"},
            ],
        },
    )
    out = enrich_requirement_draft(draft)
    assert out.draft.known.relation_intents == []

def test_enrich_extracts_scalars_from_raw_text():
    draft = LLMRequirementDraft(raw_text="两层三卧两卫带车库，客厅朝南")
    out = enrich_requirement_draft(draft)
    assert out.draft.known.floor_count == 2
    assert out.draft.known.household.bedrooms == 3
    assert out.draft.known.household.bathrooms == 2
    assert out.draft.known.household.has_garage is True
    assert any(s.name == "客厅" for s in out.draft.known.spaces)
    assert out.draft.known.preferences.prefer_south_facing_living is True


def test_enrich_oral_chinese_site_and_scalars():
    """口语中文数字场地/卫浴/车位（Development 一般规律，非 Blind 逐案）。"""
    site = enrich_requirement_draft(
        LLMRequirementDraft(raw_text="两层三卧两卫，地块大约十一乘十三米")
    )
    assert site.draft.known.site.width == 11
    assert site.draft.known.site.depth == 13

    wd = enrich_requirement_draft(
        LLMRequirementDraft(raw_text="宽十五米深十八米，三层楼，六间卧室")
    )
    assert wd.draft.known.site.width == 15
    assert wd.draft.known.site.depth == 18
    assert wd.draft.known.floor_count == 3
    assert wd.draft.known.household.bedrooms == 6

    bath = enrich_requirement_draft(
        LLMRequirementDraft(raw_text="四居室复式，两层，三个卫生间")
    )
    assert bath.draft.known.household.bathrooms == 3
    assert bath.draft.known.household.bedrooms == 4

    park = enrich_requirement_draft(
        LLMRequirementDraft(raw_text="三层四卧，卫生间先按三个算，车位要有")
    )
    assert park.draft.known.household.has_garage is True
    assert any(s.name == "车库" for s in park.draft.known.spaces)

    no_park = enrich_requirement_draft(
        LLMRequirementDraft(raw_text="平层两卧，没有车位，场地未定")
    )
    assert no_park.draft.known.household.has_garage is False


def test_enrich_south_living_either_order_and_garage_soft():
    """南向客厅语序；有车库更好≠has_garage。"""
    south = enrich_requirement_draft(
        LLMRequirementDraft(raw_text="两层三卧，南向客厅，地块未定")
    )
    assert south.draft.known.preferences.prefer_south_facing_living is True
    living = next(s for s in south.draft.known.spaces if s.name == "客厅")
    assert str(living.preferred_orientation) == "south"

    soft = enrich_requirement_draft(
        LLMRequirementDraft(raw_text="两层三卧，有车库更好，场地未定")
    )
    assert soft.draft.known.household.has_garage is None


def test_enrich_rejects_global_near_cue_false_positive():
    """两端共现 + 文中别处「近」不足以保留 near。"""
    draft = LLMRequirementDraft(
        raw_text="两层三卧，客厅朝南，厨房和餐厅都要，书房近一点采光",
        known={  # type: ignore[arg-type]
            "floor_count": 2,
            "spaces": [{"name": "厨房"}, {"name": "餐厅"}, {"name": "书房"}],
            "relation_intents": [
                {"a": "厨房", "b": "餐厅", "kind": "near"},
            ],
        },
    )
    out = enrich_requirement_draft(draft)
    assert not any(
        r.kind == "near" and {r.a, r.b} == {"厨房", "餐厅"}
        for r in out.draft.known.relation_intents
    )
    grounded = enrich_requirement_draft(
        LLMRequirementDraft(raw_text="两层三卧，厨房和餐厅近一点")
    )
    assert any(
        r.kind == "near" and {r.a, r.b} == {"厨房", "餐厅"}
        for r in grounded.draft.known.relation_intents
    )


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
