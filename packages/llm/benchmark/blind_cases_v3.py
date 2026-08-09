"""Phase 6.7.3 — Blind Set v3（严格独立资格认证语料）。

纪律：
- Blind v2 Gate FAIL 已归档；本集为 **新** 冻结语料
- 禁止在看过 Blind v3 失败后再改解析规则并宣称本集通过
- 不得再驱动 enricher 逐案 regex / 补丁
- 语气偏口语/叙事；刻意避开 v1 / v2 / Holdout 原句

六类：explicit | intent | access_near | weak_pref | negative | ambiguous
"""

from __future__ import annotations

from packages.llm.benchmark.cases import (
    ExpectFloorPreference,
    ExpectKnown,
    ExpectOrientation,
    ExpectRelation,
    RequirementBenchmarkCase,
    _c,
    _normalize_must_unknown,
)
from packages.schema.site import CardinalOrientation

BLIND_VERSION = "blind-v3"
BLIND_FREEZE_NOTE = (
    "Blind v3 创建时解析层应已相对冻结；本集不得再驱动 enricher 逐案补丁。"
)


def load_blind_cases() -> list[RequirementBenchmarkCase]:
    """Blind Set v3（目标 40–60；口语化住宅需求）。"""
    cases: list[RequirementBenchmarkCase] = [
        # ========== 1. Explicit Facts ==========
        _c(
            "bl3-001",
            "我们打算盖两层，睡房四间、卫生间两个，宅基地宽九米深十一米。",
            tags=["blind", "explicit"],
            expect=ExpectKnown(
                floor_count=2,
                bedrooms=4,
                bathrooms=2,
                site_width=9,
                site_depth=11,
            ),
        ),
        _c(
            "bl3-002",
            "单层就够用了，三室一厅一卫，不要车库，地块长短还没量别乱填。",
            tags=["blind", "explicit", "anti-hallucination"],
            expect=ExpectKnown(
                floor_count=1,
                bedrooms=3,
                bathrooms=1,
                has_garage=False,
            ),
            must_unknown=["site.width", "site.depth"],
        ),
        _c(
            "bl3-003",
            "想造个三层，五间卧室四个洗手间，双车位，用地大小回头再报。",
            tags=["blind", "explicit", "3f"],
            expect=ExpectKnown(
                floor_count=3,
                bedrooms=5,
                bathrooms=4,
                has_garage=True,
                space_names_contains=["车库"],
            ),
            must_unknown=["site.width", "site.depth"],
        ),
        _c(
            "bl3-004",
            "双层小洋楼，三房两厅两卫，得有个车库，场地大约十一乘十四米。",
            tags=["blind", "explicit"],
            expect=ExpectKnown(
                floor_count=2,
                bedrooms=3,
                bathrooms=2,
                has_garage=True,
                site_width=11,
                site_depth=14,
            ),
        ),
        _c(
            "bl3-005",
            "一层三居室两卫，南向客厅，地块宽十米进深十三米。",
            tags=["blind", "explicit", "orientation"],
            expect=ExpectKnown(
                floor_count=1,
                bedrooms=3,
                bathrooms=2,
                site_width=10,
                site_depth=13,
                prefer_south_facing_living=True,
                space_names_contains=["客厅"],
            ),
        ),
        _c(
            "bl3-006",
            "两层六卧三卫，车位要有，宽十五米、深十八米。",
            tags=["blind", "explicit"],
            expect=ExpectKnown(
                floor_count=2,
                bedrooms=6,
                bathrooms=3,
                has_garage=True,
                site_width=15,
                site_depth=18,
            ),
        ),
        _c(
            "bl3-007",
            "平层两间卧室一个卫生间，车库不要，宽八米深九米。",
            tags=["blind", "explicit"],
            expect=ExpectKnown(
                floor_count=1,
                bedrooms=2,
                bathrooms=1,
                has_garage=False,
                site_width=8,
                site_depth=9,
            ),
        ),
        _c(
            "bl3-008",
            "跃式两层四居三卫，带车库，用地还没批下来请勿编造尺寸。",
            tags=["blind", "explicit"],
            expect=ExpectKnown(
                floor_count=2,
                bedrooms=4,
                bathrooms=3,
                has_garage=True,
                space_names_contains=["车库"],
            ),
            must_unknown=["site.width", "site.depth"],
        ),
        # ========== 2. Design Intent ==========
        _c(
            "bl3-010",
            "两层三间卧室两卫。厨房紧挨餐厅，客厅与餐厅连通。场地回头再量。",
            tags=["blind", "intent", "near"],
            expect=ExpectKnown(
                floor_count=2,
                bedrooms=3,
                bathrooms=2,
                space_names_contains=["厨房", "餐厅", "客厅"],
                relations=[
                    ExpectRelation(a="厨房", b="餐厅", kind="near"),
                    ExpectRelation(a="客厅", b="餐厅", kind="open_connection"),
                ],
            ),
            must_unknown=["site.width", "site.depth"],
        ),
        _c(
            "bl3-011",
            "二层五房两卫。书房挨着主卧，餐厅最好靠近厨房。宽深没给。",
            tags=["blind", "intent", "near"],
            expect=ExpectKnown(
                floor_count=2,
                bedrooms=5,
                bathrooms=2,
                space_names_contains=["书房", "主卧", "餐厅", "厨房"],
                relations=[
                    ExpectRelation(a="书房", b="主卧", kind="near"),
                    ExpectRelation(a="餐厅", b="厨房", kind="near"),
                ],
            ),
            must_unknown=["site.width", "site.depth"],
        ),
        _c(
            "bl3-012",
            "双层三卧。客餐厅开敞连着，厨房邻近餐厅。尺寸未知。",
            tags=["blind", "intent"],
            expect=ExpectKnown(
                floor_count=2,
                bedrooms=3,
                space_names_contains=["客厅", "餐厅", "厨房"],
                relations=[
                    ExpectRelation(a="客厅", b="餐厅", kind="open_connection"),
                    ExpectRelation(a="厨房", b="餐厅", kind="near"),
                ],
            ),
            must_unknown=["site.width", "site.depth"],
        ),
        _c(
            "bl3-013",
            "一层两卧一卫。卫生间靠近主卧，起居室朝南。地块没定。",
            tags=["blind", "intent", "orientation"],
            expect=ExpectKnown(
                floor_count=1,
                bedrooms=2,
                bathrooms=1,
                prefer_south_facing_living=True,
                space_names_contains=["卫生间", "主卧", "客厅"],
                relations=[
                    ExpectRelation(a="卫生间", b="主卧", kind="near"),
                ],
            ),
            must_unknown=["site.width", "site.depth"],
        ),
        _c(
            "bl3-014",
            "两层六卧三卫带车库。餐厅和厨房连通，客厅偏南。场地八乘十。",
            tags=["blind", "intent", "explicit"],
            expect=ExpectKnown(
                floor_count=2,
                bedrooms=6,
                bathrooms=3,
                has_garage=True,
                site_width=8,
                site_depth=10,
                space_names_contains=["餐厅", "厨房", "客厅"],
                relations=[
                    ExpectRelation(a="餐厅", b="厨房", kind="open_connection"),
                ],
                orientations=[
                    ExpectOrientation(
                        space_name="客厅", orientation=CardinalOrientation.SOUTH
                    ),
                ],
            ),
        ),
        _c(
            "bl3-015",
            "三层四卧。儿童房邻近主卧，书房朝西。用地未量。",
            tags=["blind", "intent", "orientation"],
            expect=ExpectKnown(
                floor_count=3,
                bedrooms=4,
                space_names_contains=["儿童房", "主卧", "书房"],
                relations=[
                    ExpectRelation(a="儿童房", b="主卧", kind="near"),
                ],
                orientations=[
                    ExpectOrientation(
                        space_name="书房", orientation=CardinalOrientation.WEST
                    ),
                ],
            ),
            must_unknown=["site.width", "site.depth"],
        ),
        _c(
            "bl3-016",
            "双层三卧两卫。厨餐靠近一点，客厅连着餐厅。地块十三乘十五。",
            tags=["blind", "intent"],
            expect=ExpectKnown(
                floor_count=2,
                bedrooms=3,
                bathrooms=2,
                site_width=13,
                site_depth=15,
                space_names_contains=["厨房", "餐厅", "客厅"],
                relations=[
                    ExpectRelation(a="厨房", b="餐厅", kind="near"),
                    ExpectRelation(a="客厅", b="餐厅", kind="access"),
                ],
            ),
        ),
        # ========== 3. Access vs Near ==========
        _c(
            "bl3-020",
            "两层三卧两卫要车库。从车库能进玄关，厨房靠近餐厅。场地未定。",
            tags=["blind", "access_near"],
            expect=ExpectKnown(
                floor_count=2,
                bedrooms=3,
                bathrooms=2,
                has_garage=True,
                space_names_contains=["车库", "门厅", "厨房", "餐厅"],
                relations=[
                    ExpectRelation(a="车库", b="门厅", kind="access"),
                    ExpectRelation(a="厨房", b="餐厅", kind="near"),
                ],
            ),
            must_unknown=["site.width", "site.depth"],
        ),
        _c(
            "bl3-021",
            "二层四卧。车库连着门厅，主卧远离客厅。宽深以后再说。",
            tags=["blind", "access_near", "negative"],
            expect=ExpectKnown(
                floor_count=2,
                bedrooms=4,
                has_garage=True,
                space_names_contains=["车库", "门厅", "主卧", "客厅"],
                relations=[
                    ExpectRelation(a="车库", b="门厅", kind="access"),
                    ExpectRelation(a="主卧", b="客厅", kind="separation"),
                ],
            ),
            must_unknown=["site.width", "site.depth"],
        ),
        _c(
            "bl3-022",
            "两层三卧。从门厅进入客厅，餐厅靠近厨房。场地未知。",
            tags=["blind", "access_near"],
            expect=ExpectKnown(
                floor_count=2,
                bedrooms=3,
                space_names_contains=["门厅", "客厅", "餐厅", "厨房"],
                relations=[
                    ExpectRelation(a="门厅", b="客厅", kind="access"),
                    ExpectRelation(a="餐厅", b="厨房", kind="near"),
                ],
            ),
            must_unknown=["site.width", "site.depth"],
        ),
        _c(
            "bl3-023",
            "一层两卧。卫生间与主卧内部相连，车库靠近入口。用地未测。",
            tags=["blind", "access_near"],
            expect=ExpectKnown(
                floor_count=1,
                bedrooms=2,
                has_garage=True,
                space_names_contains=["卫生间", "主卧", "车库", "入口"],
                relations=[
                    ExpectRelation(a="卫生间", b="主卧", kind="access"),
                    ExpectRelation(a="车库", b="入口", kind="near"),
                ],
            ),
            must_unknown=["site.width", "site.depth"],
        ),
        _c(
            "bl3-024",
            "两层四卧两卫。书房和主卧相连，厨房挨着餐厅。地块十六乘十九。",
            tags=["blind", "access_near"],
            expect=ExpectKnown(
                floor_count=2,
                bedrooms=4,
                bathrooms=2,
                site_width=16,
                site_depth=19,
                space_names_contains=["书房", "主卧", "厨房", "餐厅"],
                relations=[
                    ExpectRelation(a="书房", b="主卧", kind="access"),
                    ExpectRelation(a="厨房", b="餐厅", kind="near"),
                ],
            ),
        ),
        _c(
            "bl3-025",
            "三层五卧。从车库进入门厅即可，客厅朝南。场地未提供。",
            tags=["blind", "access_near", "orientation"],
            expect=ExpectKnown(
                floor_count=3,
                bedrooms=5,
                has_garage=True,
                prefer_south_facing_living=True,
                space_names_contains=["车库", "门厅", "客厅"],
                relations=[
                    ExpectRelation(a="车库", b="门厅", kind="access"),
                ],
            ),
            must_unknown=["site.width", "site.depth"],
        ),
        # ========== 4. Weak Preference ==========
        _c(
            "bl3-030",
            "两层三卧两卫。客厅尽量朝南就好，厨房靠近餐厅。宽深未定。",
            tags=["blind", "weak_pref"],
            expect=ExpectKnown(
                floor_count=2,
                bedrooms=3,
                bathrooms=2,
                prefer_south_facing_living=True,
                space_names_contains=["客厅", "厨房", "餐厅"],
                relations=[
                    ExpectRelation(a="厨房", b="餐厅", kind="near"),
                ],
            ),
            must_unknown=["site.width", "site.depth"],
        ),
        _c(
            "bl3-031",
            "二层四房。书房偏北，餐厅最好挨着厨房。场地以后补。",
            tags=["blind", "weak_pref"],
            expect=ExpectKnown(
                floor_count=2,
                bedrooms=4,
                space_names_contains=["书房", "餐厅", "厨房"],
                relations=[
                    ExpectRelation(a="餐厅", b="厨房", kind="near"),
                ],
                orientations=[
                    ExpectOrientation(
                        space_name="书房", orientation=CardinalOrientation.NORTH
                    ),
                ],
            ),
            must_unknown=["site.width", "site.depth"],
        ),
        _c(
            "bl3-032",
            "两层三卧。老人最好住楼下，儿童房和主卧近一点。用地未知。",
            tags=["blind", "weak_pref", "floor"],
            expect=ExpectKnown(
                floor_count=2,
                bedrooms=3,
                space_names_contains=["老人房", "儿童房", "主卧"],
                floor_preferences=[
                    ExpectFloorPreference(space_name="老人房", floors=["F1"]),
                ],
                relations=[
                    ExpectRelation(a="儿童房", b="主卧", kind="near"),
                ],
            ),
            must_unknown=["site.width", "site.depth"],
        ),
        _c(
            "bl3-033",
            "一层三卧两卫。主卧放一层，南向客厅。地块十二乘十四。",
            tags=["blind", "weak_pref"],
            expect=ExpectKnown(
                floor_count=1,
                bedrooms=3,
                bathrooms=2,
                site_width=12,
                site_depth=14,
                prefer_south_facing_living=True,
                space_names_contains=["主卧", "客厅"],
                floor_preferences=[
                    ExpectFloorPreference(space_name="主卧", floors=["F1"]),
                ],
            ),
        ),
        _c(
            "bl3-034",
            "两层四卧。一楼留间老人房，书房朝东。场地未量。",
            tags=["blind", "weak_pref", "floor"],
            expect=ExpectKnown(
                floor_count=2,
                bedrooms=4,
                space_names_contains=["老人房", "书房"],
                floor_preferences=[
                    ExpectFloorPreference(space_name="老人房", floors=["F1"]),
                ],
                orientations=[
                    ExpectOrientation(
                        space_name="书房", orientation=CardinalOrientation.EAST
                    ),
                ],
            ),
            must_unknown=["site.width", "site.depth"],
        ),
        _c(
            "bl3-035",
            "三层别墅。父母房不要上楼，厨房邻近餐厅。宽深未给。",
            tags=["blind", "weak_pref", "floor"],
            expect=ExpectKnown(
                floor_count=3,
                space_names_contains=["老人房", "厨房", "餐厅"],
                floor_preferences=[
                    ExpectFloorPreference(space_name="老人房", floors=["F1"]),
                ],
                relations=[
                    ExpectRelation(a="厨房", b="餐厅", kind="near"),
                ],
            ),
            must_unknown=["site.width", "site.depth"],
        ),
        # ========== 5. Negative Constraints ==========
        _c(
            "bl3-040",
            "两层三卧两卫。主卧不要靠着客厅，儿童房远离厨房。场地未定。",
            tags=["blind", "negative"],
            expect=ExpectKnown(
                floor_count=2,
                bedrooms=3,
                bathrooms=2,
                space_names_contains=["主卧", "客厅", "儿童房", "厨房"],
                relations=[
                    ExpectRelation(a="主卧", b="客厅", kind="separation"),
                    ExpectRelation(a="儿童房", b="厨房", kind="separation"),
                ],
            ),
            must_unknown=["site.width", "site.depth"],
        ),
        _c(
            "bl3-041",
            "二层四房。书房保持私密远离客厅，厨房靠近餐厅。用地未知。",
            tags=["blind", "negative"],
            expect=ExpectKnown(
                floor_count=2,
                bedrooms=4,
                space_names_contains=["书房", "客厅", "厨房", "餐厅"],
                relations=[
                    ExpectRelation(a="书房", b="客厅", kind="separation"),
                    ExpectRelation(a="厨房", b="餐厅", kind="near"),
                ],
            ),
            must_unknown=["site.width", "site.depth"],
        ),
        _c(
            "bl3-042",
            "两层三卧。不要让主卧靠着餐厅，车库连着门厅。宽深以后说。",
            tags=["blind", "negative", "access_near"],
            expect=ExpectKnown(
                floor_count=2,
                bedrooms=3,
                has_garage=True,
                space_names_contains=["主卧", "餐厅", "车库", "门厅"],
                relations=[
                    ExpectRelation(a="主卧", b="餐厅", kind="separation"),
                    ExpectRelation(a="车库", b="门厅", kind="access"),
                ],
            ),
            must_unknown=["site.width", "site.depth"],
        ),
        _c(
            "bl3-043",
            "一层两卧一卫。儿童房不要靠客厅，卫生间靠近主卧。地块未测。",
            tags=["blind", "negative"],
            expect=ExpectKnown(
                floor_count=1,
                bedrooms=2,
                bathrooms=1,
                space_names_contains=["儿童房", "客厅", "卫生间", "主卧"],
                relations=[
                    ExpectRelation(a="儿童房", b="客厅", kind="separation"),
                    ExpectRelation(a="卫生间", b="主卧", kind="near"),
                ],
            ),
            must_unknown=["site.width", "site.depth"],
        ),
        _c(
            "bl3-044",
            "两层五卧。主卧远离客厅，餐厅与厨房连通。场地十一乘十三。",
            tags=["blind", "negative"],
            expect=ExpectKnown(
                floor_count=2,
                bedrooms=5,
                site_width=11,
                site_depth=13,
                space_names_contains=["主卧", "客厅", "餐厅", "厨房"],
                relations=[
                    ExpectRelation(a="主卧", b="客厅", kind="separation"),
                    ExpectRelation(a="餐厅", b="厨房", kind="open_connection"),
                ],
            ),
        ),
        _c(
            "bl3-045",
            "三层四卧两卫。书房尽量避免厨房噪声，起居室朝南。用地未定。",
            tags=["blind", "negative"],
            expect=ExpectKnown(
                floor_count=3,
                bedrooms=4,
                bathrooms=2,
                prefer_south_facing_living=True,
                space_names_contains=["书房", "厨房", "客厅"],
                relations=[
                    ExpectRelation(a="书房", b="厨房", kind="separation"),
                ],
            ),
            must_unknown=["site.width", "site.depth"],
        ),
        # ========== 6. Ambiguous ==========
        _c(
            "bl3-050",
            "想要个通透一点的独栋，几层几间睡房还没想好，场地也没定。",
            tags=["blind", "ambiguous"],
            expect=ExpectKnown(),
            must_unknown=[
                "floor_count",
                "household.bedrooms",
                "site.width",
                "site.depth",
            ],
        ),
        _c(
            "bl3-051",
            "两层三卧，客厅希望宽敞些，具体面积先别填。宽深未提供。",
            tags=["blind", "ambiguous"],
            expect=ExpectKnown(
                floor_count=2,
                bedrooms=3,
                space_names_contains=["客厅"],
            ),
            must_unknown=["site.width", "site.depth"],
        ),
        _c(
            "bl3-052",
            "帮我设计个温馨的家，要不要车库再议，场地尺寸未知。",
            tags=["blind", "ambiguous"],
            expect=ExpectKnown(),
            must_unknown=["site.width", "site.depth"],
        ),
        _c(
            "bl3-053",
            "三层看着气派，卧室大概四五间吧还没定，地块未量。",
            tags=["blind", "ambiguous"],
            expect=ExpectKnown(floor_count=3),
            must_unknown=["household.bedrooms", "site.width", "site.depth"],
        ),
        _c(
            "bl3-054",
            "一层小宅，两卧一卫，采光通透就行。用地宽深以后再说。",
            tags=["blind", "ambiguous", "explicit"],
            expect=ExpectKnown(
                floor_count=1,
                bedrooms=2,
                bathrooms=1,
            ),
            must_unknown=["site.width", "site.depth"],
        ),
        _c(
            "bl3-055",
            "两层四房两卫带车库。厨房靠近餐厅即可，别的随意。场地未定。",
            tags=["blind", "ambiguous", "intent"],
            expect=ExpectKnown(
                floor_count=2,
                bedrooms=4,
                bathrooms=2,
                has_garage=True,
                space_names_contains=["厨房", "餐厅", "车库"],
                relations=[
                    ExpectRelation(a="厨房", b="餐厅", kind="near"),
                ],
            ),
            must_unknown=["site.width", "site.depth"],
        ),
        # ========== Mixed ==========
        _c(
            "bl3-060",
            "两层小家三卧两卫有车位。从车库能进玄关；主卧别挨着客厅。"
            "地块大约十一乘十六米。",
            tags=["blind", "mixed", "access_near", "negative"],
            expect=ExpectKnown(
                floor_count=2,
                bedrooms=3,
                bathrooms=2,
                has_garage=True,
                site_width=11,
                site_depth=16,
                space_names_contains=["车库", "门厅", "主卧", "客厅"],
                relations=[
                    ExpectRelation(a="车库", b="门厅", kind="access"),
                    ExpectRelation(a="主卧", b="客厅", kind="separation"),
                ],
            ),
        ),
        _c(
            "bl3-061",
            "平层三室两卫，客厅与餐厅连通，厨房邻近餐厅，南向客厅。"
            "宽十一米深十三米。",
            tags=["blind", "mixed", "intent"],
            expect=ExpectKnown(
                floor_count=1,
                bedrooms=3,
                bathrooms=2,
                site_width=11,
                site_depth=13,
                prefer_south_facing_living=True,
                space_names_contains=["客厅", "餐厅", "厨房"],
                relations=[
                    ExpectRelation(a="客厅", b="餐厅", kind="open_connection"),
                    ExpectRelation(a="厨房", b="餐厅", kind="near"),
                ],
            ),
        ),
        _c(
            "bl3-062",
            "三层五卧三卫带车库。老人住楼下，书房朝北，厨房靠近餐厅。"
            "场地未提供请勿编造。",
            tags=["blind", "mixed", "floor", "weak_pref"],
            expect=ExpectKnown(
                floor_count=3,
                bedrooms=5,
                bathrooms=3,
                has_garage=True,
                space_names_contains=["老人房", "书房", "厨房", "餐厅", "车库"],
                floor_preferences=[
                    ExpectFloorPreference(space_name="老人房", floors=["F1"]),
                ],
                orientations=[
                    ExpectOrientation(
                        space_name="书房", orientation=CardinalOrientation.NORTH
                    ),
                ],
                relations=[
                    ExpectRelation(a="厨房", b="餐厅", kind="near"),
                ],
            ),
            must_unknown=["site.width", "site.depth"],
        ),
        _c(
            "bl3-063",
            "两层四卧两卫。餐厅和厨房连通；儿童房远离厨房；车库连着门厅。"
            "用地宽十三米深十七米。",
            tags=["blind", "mixed"],
            expect=ExpectKnown(
                floor_count=2,
                bedrooms=4,
                bathrooms=2,
                has_garage=True,
                site_width=13,
                site_depth=17,
                space_names_contains=["餐厅", "厨房", "儿童房", "车库", "门厅"],
                relations=[
                    ExpectRelation(a="餐厅", b="厨房", kind="open_connection"),
                    ExpectRelation(a="儿童房", b="厨房", kind="separation"),
                    ExpectRelation(a="车库", b="门厅", kind="access"),
                ],
            ),
        ),
        _c(
            "bl3-064",
            "二层三卧。厨房最好挨着餐厅；主卧安静一点不要靠着客厅；"
            "别让老人上二楼。场地未定。",
            tags=["blind", "mixed", "negative", "floor"],
            expect=ExpectKnown(
                floor_count=2,
                bedrooms=3,
                space_names_contains=["厨房", "餐厅", "主卧", "客厅", "老人房"],
                floor_preferences=[
                    ExpectFloorPreference(space_name="老人房", floors=["F1"]),
                ],
                relations=[
                    ExpectRelation(a="厨房", b="餐厅", kind="near"),
                    ExpectRelation(a="主卧", b="客厅", kind="separation"),
                ],
            ),
            must_unknown=["site.width", "site.depth"],
        ),
    ]
    assert len(cases) >= 40, len(cases)
    ids = [c.id for c in cases]
    assert len(ids) == len(set(ids))
    return [_normalize_must_unknown(c) for c in cases]


def blind_case_count() -> int:
    return len(load_blind_cases())
