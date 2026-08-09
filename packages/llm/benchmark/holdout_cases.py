"""Phase 6.7.1 — Qualification Holdout（≥30；日常开发勿逐案盯失败调规则）。

原则：
- 与 Development（cases.py 62 条）隔离
- 含 paraphrase：同一意图多种自然说法
- gold 为人工确认的 known / relation / unknown / floor / orientation
"""

from __future__ import annotations

from packages.llm.benchmark.cases import (
    ExpectAssumption,
    ExpectFloorPreference,
    ExpectKnown,
    ExpectOrientation,
    ExpectRelation,
    RequirementBenchmarkCase,
    _c,
)
from packages.schema.site import CardinalOrientation

HOLDOUT_VERSION = "holdout-v1"


def load_holdout_cases() -> list[RequirementBenchmarkCase]:
    """Qualification Holdout v1（≥30）。"""
    cases: list[RequirementBenchmarkCase] = [
        # —— 基础标量 / 场地 ——
        _c(
            "ho-001",
            "两层三卧两卫，客厅朝南，地块约 12×14 米",
            tags=["holdout", "basic", "paraphrase"],
            expect=ExpectKnown(
                floor_count=2,
                bedrooms=3,
                bathrooms=2,
                site_width=12,
                site_depth=14,
                prefer_south_facing_living=True,
                space_names_contains=["客厅"],
            ),
        ),
        _c(
            "ho-002",
            "做一套两层的小住宅，三个卧室两个卫生间，起居室尽量朝南",
            tags=["holdout", "basic", "paraphrase"],
            expect=ExpectKnown(
                floor_count=2,
                bedrooms=3,
                bathrooms=2,
                prefer_south_facing_living=True,
                space_names_contains=["客厅"],
            ),
            must_unknown=["site.width", "site.depth"],
        ),
        _c(
            "ho-003",
            "一层两卧一卫，场地尺寸未定请不要猜",
            tags=["holdout", "anti-hallucination", "1f"],
            expect=ExpectKnown(floor_count=1, bedrooms=2, bathrooms=1),
            must_unknown=["site.width", "site.depth"],
        ),
        _c(
            "ho-004",
            "三层四卧，带车库",
            tags=["holdout", "garage", "3f"],
            expect=ExpectKnown(
                floor_count=3,
                bedrooms=4,
                has_garage=True,
                space_names_contains=["车库"],
            ),
            must_unknown=["site.width", "site.depth"],
        ),
        # —— 楼层偏好 paraphrase ——
        _c(
            "ho-010",
            "两层四卧，老人房放一层，书房朝北",
            tags=["holdout", "floor_pref", "orientation", "paraphrase"],
            expect=ExpectKnown(
                floor_count=2,
                bedrooms=4,
                space_names_contains=["老人房", "书房"],
                floor_preferences=[
                    ExpectFloorPreference(space_name="老人房", floors=["F1"]),
                ],
                orientations=[
                    ExpectOrientation(
                        space_name="书房",
                        orientation=CardinalOrientation.NORTH,
                    ),
                ],
            ),
            must_unknown=["site.width", "site.depth"],
        ),
        _c(
            "ho-011",
            "两层四卧，老人最好住楼下，书房朝北",
            tags=["holdout", "floor_pref", "orientation", "paraphrase"],
            expect=ExpectKnown(
                floor_count=2,
                bedrooms=4,
                space_names_contains=["老人房", "书房"],
                floor_preferences=[
                    ExpectFloorPreference(space_name="老人房", floors=["F1"]),
                ],
                orientations=[
                    ExpectOrientation(
                        space_name="书房",
                        orientation=CardinalOrientation.NORTH,
                    ),
                ],
            ),
            must_unknown=["site.width", "site.depth"],
        ),
        _c(
            "ho-012",
            "两层四卧，给父母准备的卧室不要上楼，书房朝北",
            tags=["holdout", "floor_pref", "orientation", "paraphrase"],
            expect=ExpectKnown(
                floor_count=2,
                bedrooms=4,
                space_names_contains=["老人房", "书房"],
                floor_preferences=[
                    ExpectFloorPreference(space_name="老人房", floors=["F1"]),
                ],
                orientations=[
                    ExpectOrientation(
                        space_name="书房",
                        orientation=CardinalOrientation.NORTH,
                    ),
                ],
            ),
            must_unknown=["site.width", "site.depth"],
        ),
        _c(
            "ho-013",
            "两层四卧，首层安排一间老人卧室，书房朝北",
            tags=["holdout", "floor_pref", "orientation", "paraphrase"],
            expect=ExpectKnown(
                floor_count=2,
                bedrooms=4,
                space_names_contains=["老人房", "书房"],
                floor_preferences=[
                    ExpectFloorPreference(space_name="老人房", floors=["F1"]),
                ],
                orientations=[
                    ExpectOrientation(
                        space_name="书房",
                        orientation=CardinalOrientation.NORTH,
                    ),
                ],
            ),
            must_unknown=["site.width", "site.depth"],
        ),
        # —— near / open_connection / separation paraphrase ——
        _c(
            "ho-020",
            "两层三卧，厨房靠近餐厅，客厅与餐厅连通",
            tags=["holdout", "relation", "paraphrase"],
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
        ),
        _c(
            "ho-021",
            "两层三卧，餐厨距离近一点，客餐厅开敞连通",
            tags=["holdout", "relation", "paraphrase"],
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
        ),
        _c(
            "ho-022",
            "两层三卧，做饭端菜方便，餐厅最好挨着厨房，客厅和餐厅连通",
            tags=["holdout", "relation", "paraphrase"],
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
        ),
        _c(
            "ho-023",
            "两层三卧，主卧远离客厅，儿童房靠近主卧",
            tags=["holdout", "relation", "paraphrase"],
            expect=ExpectKnown(
                floor_count=2,
                bedrooms=3,
                space_names_contains=["主卧", "客厅", "儿童房"],
                relations=[
                    ExpectRelation(a="主卧", b="客厅", kind="separation"),
                    ExpectRelation(a="儿童房", b="主卧", kind="near"),
                ],
            ),
            must_unknown=["site.width", "site.depth"],
        ),
        _c(
            "ho-024",
            "两层三卧，主卧安静一点，不要靠着客厅，儿童房挨着主卧",
            tags=["holdout", "relation", "paraphrase"],
            expect=ExpectKnown(
                floor_count=2,
                bedrooms=3,
                space_names_contains=["主卧", "客厅", "儿童房"],
                relations=[
                    ExpectRelation(a="主卧", b="客厅", kind="separation"),
                    ExpectRelation(a="儿童房", b="主卧", kind="near"),
                ],
            ),
            must_unknown=["site.width", "site.depth"],
        ),
        _c(
            "ho-025",
            "两层三卧，主卧尽量避免客厅噪声，儿童房靠近主卧",
            tags=["holdout", "relation", "paraphrase"],
            expect=ExpectKnown(
                floor_count=2,
                bedrooms=3,
                space_names_contains=["主卧", "客厅", "儿童房"],
                relations=[
                    ExpectRelation(a="主卧", b="客厅", kind="separation"),
                    ExpectRelation(a="儿童房", b="主卧", kind="near"),
                ],
            ),
            must_unknown=["site.width", "site.depth"],
        ),
        # —— access / garage-entry ——
        _c(
            "ho-030",
            "两层三卧两卫带车库，车库与门厅内部相连，客厅朝南",
            tags=["holdout", "access", "garage", "paraphrase"],
            expect=ExpectKnown(
                floor_count=2,
                bedrooms=3,
                bathrooms=2,
                has_garage=True,
                prefer_south_facing_living=True,
                space_names_contains=["车库", "门厅", "客厅"],
                relations=[
                    ExpectRelation(a="车库", b="门厅", kind="access"),
                ],
            ),
            must_unknown=["site.width", "site.depth"],
        ),
        _c(
            "ho-031",
            "两层三卧两卫有车库，车库连着玄关，起居室朝南",
            tags=["holdout", "access", "garage", "paraphrase"],
            expect=ExpectKnown(
                floor_count=2,
                bedrooms=3,
                bathrooms=2,
                has_garage=True,
                prefer_south_facing_living=True,
                space_names_contains=["车库", "门厅", "客厅"],
                relations=[
                    ExpectRelation(a="车库", b="门厅", kind="access"),
                ],
            ),
            must_unknown=["site.width", "site.depth"],
        ),
        _c(
            "ho-032",
            "两层三卧两卫带车库，从车库能进门厅，客厅朝南",
            tags=["holdout", "access", "garage", "paraphrase"],
            expect=ExpectKnown(
                floor_count=2,
                bedrooms=3,
                bathrooms=2,
                has_garage=True,
                prefer_south_facing_living=True,
                space_names_contains=["车库", "门厅", "客厅"],
                relations=[
                    ExpectRelation(a="车库", b="门厅", kind="access"),
                ],
            ),
            must_unknown=["site.width", "site.depth"],
        ),
        # —— orientation ——
        _c(
            "ho-040",
            "两层三卧，客厅朝南，书房朝北",
            tags=["holdout", "orientation", "paraphrase"],
            expect=ExpectKnown(
                floor_count=2,
                bedrooms=3,
                prefer_south_facing_living=True,
                space_names_contains=["客厅", "书房"],
                orientations=[
                    ExpectOrientation(
                        space_name="客厅",
                        orientation=CardinalOrientation.SOUTH,
                    ),
                    ExpectOrientation(
                        space_name="书房",
                        orientation=CardinalOrientation.NORTH,
                    ),
                ],
            ),
            must_unknown=["site.width", "site.depth"],
        ),
        _c(
            "ho-041",
            "两层三卧，起居室要南向，书房偏北",
            tags=["holdout", "orientation", "paraphrase"],
            expect=ExpectKnown(
                floor_count=2,
                bedrooms=3,
                prefer_south_facing_living=True,
                space_names_contains=["客厅", "书房"],
                orientations=[
                    ExpectOrientation(
                        space_name="客厅",
                        orientation=CardinalOrientation.SOUTH,
                    ),
                    ExpectOrientation(
                        space_name="书房",
                        orientation=CardinalOrientation.NORTH,
                    ),
                ],
            ),
            must_unknown=["site.width", "site.depth"],
        ),
        # —— sparse / unknown / assumption ——
        _c(
            "ho-050",
            "给我们家做个住宅设计。",
            tags=["holdout", "sparse", "unknown-detection"],
            expect=ExpectKnown(),
            must_unknown=[
                "floor_count",
                "site.width",
                "site.depth",
                "household.bedrooms",
                "household.bathrooms",
            ],
        ),
        _c(
            "ho-051",
            "两层小宅，卧室数先按三口之家假设为三间并标明是假设；场地宽深未知",
            tags=["holdout", "assumption", "unknown-detection"],
            expect=ExpectKnown(floor_count=2),
            must_unknown=["site.width", "site.depth", "household.bathrooms"],
            expect_assumptions=[
                ExpectAssumption(
                    key="household.bedrooms",
                    value=3,
                    require_reason=True,
                ),
            ],
        ),
        _c(
            "ho-052",
            "一层，两间卧室，地块未提供宽深",
            tags=["holdout", "unknown-detection", "1f"],
            expect=ExpectKnown(floor_count=1, bedrooms=2),
            must_unknown=["site.width", "site.depth"],
        ),
        # —— 更多基础 / 关系 ——
        _c(
            "ho-060",
            "两层五卧三卫，带车库",
            tags=["holdout", "basic"],
            expect=ExpectKnown(
                floor_count=2,
                bedrooms=5,
                bathrooms=3,
                has_garage=True,
                space_names_contains=["车库"],
            ),
            must_unknown=["site.width", "site.depth"],
        ),
        _c(
            "ho-061",
            "三层，主卧远离入口，儿童房靠近主卧",
            tags=["holdout", "relation", "3f"],
            expect=ExpectKnown(
                floor_count=3,
                space_names_contains=["主卧", "入口", "儿童房"],
                relations=[
                    ExpectRelation(a="主卧", b="入口", kind="separation"),
                    ExpectRelation(a="儿童房", b="主卧", kind="near"),
                ],
            ),
            must_unknown=["site.width", "site.depth", "household.bedrooms"],
        ),
        _c(
            "ho-062",
            "两层，客餐厅连通，客房保持私密远离客厅",
            tags=["holdout", "relation"],
            expect=ExpectKnown(
                floor_count=2,
                space_names_contains=["客厅", "餐厅", "客房"],
                relations=[
                    ExpectRelation(a="客厅", b="餐厅", kind="open_connection"),
                    ExpectRelation(a="客房", b="客厅", kind="separation"),
                ],
            ),
            must_unknown=["site.width", "site.depth", "household.bedrooms"],
        ),
        _c(
            "ho-063",
            "两层三卧，厨房靠近餐厅；场地未知勿编造",
            tags=["holdout", "relation", "anti-hallucination"],
            expect=ExpectKnown(
                floor_count=2,
                bedrooms=3,
                space_names_contains=["厨房", "餐厅"],
                relations=[ExpectRelation(a="厨房", b="餐厅", kind="near")],
            ),
            must_unknown=["site.width", "site.depth"],
        ),
        _c(
            "ho-064",
            "两层，书房朝东，老人房在一层",
            tags=["holdout", "orientation", "floor_pref"],
            expect=ExpectKnown(
                floor_count=2,
                space_names_contains=["书房", "老人房"],
                orientations=[
                    ExpectOrientation(
                        space_name="书房",
                        orientation=CardinalOrientation.EAST,
                    ),
                ],
                floor_preferences=[
                    ExpectFloorPreference(space_name="老人房", floors=["F1"]),
                ],
            ),
            must_unknown=["site.width", "site.depth", "household.bedrooms"],
        ),
        _c(
            "ho-065",
            "一层三卧两卫，客厅朝南，地块 10×12",
            tags=["holdout", "basic", "1f"],
            expect=ExpectKnown(
                floor_count=1,
                bedrooms=3,
                bathrooms=2,
                site_width=10,
                site_depth=12,
                prefer_south_facing_living=True,
                space_names_contains=["客厅"],
            ),
        ),
        _c(
            "ho-066",
            "两层四卧，餐厅最好挨着厨房",
            tags=["holdout", "relation", "paraphrase"],
            expect=ExpectKnown(
                floor_count=2,
                bedrooms=4,
                space_names_contains=["餐厅", "厨房"],
                relations=[ExpectRelation(a="厨房", b="餐厅", kind="near")],
            ),
            must_unknown=["site.width", "site.depth"],
        ),
        _c(
            "ho-067",
            "两层，不要让主卧靠着客厅，儿童房靠近主卧",
            tags=["holdout", "relation", "paraphrase"],
            expect=ExpectKnown(
                floor_count=2,
                space_names_contains=["主卧", "客厅", "儿童房"],
                relations=[
                    ExpectRelation(a="主卧", b="客厅", kind="separation"),
                    ExpectRelation(a="儿童房", b="主卧", kind="near"),
                ],
            ),
            must_unknown=["site.width", "site.depth", "household.bedrooms"],
        ),
    ]
    assert len(cases) >= 30, len(cases)
    ids = [c.id for c in cases]
    assert len(ids) == len(set(ids))
    return cases


def holdout_case_count() -> int:
    return len(load_holdout_cases())
