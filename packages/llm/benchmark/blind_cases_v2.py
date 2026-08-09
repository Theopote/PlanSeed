"""Phase 6.7.2 — Blind Set v2（严格独立资格认证语料）。

纪律：
- Blind v1 Gate FAIL 后，Development 仅改一般规律；本集为 **新** 冻结语料
- 禁止在看过 Blind v2 失败后再改解析规则并宣称本集通过
- 若 Gate FAIL：再回 Development 改一般规律，并另开 Blind v3
- 语气偏口语/叙事；刻意避开 v1 / Holdout 原句

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

BLIND_VERSION = "blind-v2"
BLIND_FREEZE_NOTE = (
    "Blind v2 创建时解析层应已相对冻结；本集不得再驱动 enricher 逐案补丁。"
)


def load_blind_cases() -> list[RequirementBenchmarkCase]:
    """Blind Set v2（目标 40–60；口语化住宅需求）。"""
    cases: list[RequirementBenchmarkCase] = [
        # ========== 1. Explicit Facts ==========
        _c(
            "bl2-001",
            "家里想盖两层，卧室四个、卫浴两间，地块宽九米深十二米。",
            tags=["blind", "explicit"],
            expect=ExpectKnown(
                floor_count=2,
                bedrooms=4,
                bathrooms=2,
                site_width=9,
                site_depth=12,
            ),
        ),
        _c(
            "bl2-002",
            "做一层就够，两室一厅一卫，没有车位。宽深还没测，别瞎写。",
            tags=["blind", "explicit", "anti-hallucination"],
            expect=ExpectKnown(
                floor_count=1,
                bedrooms=2,
                bathrooms=1,
                has_garage=False,
            ),
            must_unknown=["site.width", "site.depth"],
        ),
        _c(
            "bl2-003",
            "三层住宅，五间卧室，卫生间四个，双车位。用地尺寸以后补。",
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
            "bl2-004",
            "二层小别墅：三房两厅两卫，带车库。场地大约十三乘十六米。",
            tags=["blind", "explicit"],
            expect=ExpectKnown(
                floor_count=2,
                bedrooms=3,
                bathrooms=2,
                has_garage=True,
                site_width=13,
                site_depth=16,
            ),
        ),
        _c(
            "bl2-005",
            "平层三居，两个卫生间，客厅要南向。地块十乘十一。",
            tags=["blind", "explicit", "orientation"],
            expect=ExpectKnown(
                floor_count=1,
                bedrooms=3,
                bathrooms=2,
                site_width=10,
                site_depth=11,
                prefer_south_facing_living=True,
                space_names_contains=["客厅"],
            ),
        ),
        _c(
            "bl2-006",
            "两层，六个卧室，三个卫生间，要车库。宽十四米、进深十七米。",
            tags=["blind", "explicit"],
            expect=ExpectKnown(
                floor_count=2,
                bedrooms=6,
                bathrooms=3,
                has_garage=True,
                site_width=14,
                site_depth=17,
            ),
        ),
        _c(
            "bl2-007",
            "单层两卧一卫，车库不要。地块宽八米深十米。",
            tags=["blind", "explicit"],
            expect=ExpectKnown(
                floor_count=1,
                bedrooms=2,
                bathrooms=1,
                has_garage=False,
                site_width=8,
                site_depth=10,
            ),
        ),
        _c(
            "bl2-008",
            "复式两层，四居室，卫生间三个，车位要有。场地未定勿编造。",
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
            "bl2-010",
            "两层三卧两卫。厨房靠近餐厅，客厅与餐厅连通。场地以后再说。",
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
            "bl2-011",
            "二层四房两卫。书房挨着主卧，餐厅最好靠近厨房。用地未量。",
            tags=["blind", "intent", "near"],
            expect=ExpectKnown(
                floor_count=2,
                bedrooms=4,
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
            "bl2-012",
            "两层三卧。客餐厅开敞连通，厨房邻近餐厅。宽深未知。",
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
            "bl2-013",
            "一层两卧一卫。卫生间靠近主卧，客厅朝南。地块未定。",
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
            "bl2-014",
            "两层五卧三卫带车库。餐厅和厨房连通，客厅偏南。场地九乘十二。",
            tags=["blind", "intent", "explicit"],
            expect=ExpectKnown(
                floor_count=2,
                bedrooms=5,
                bathrooms=3,
                has_garage=True,
                site_width=9,
                site_depth=12,
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
            "bl2-015",
            "三层四卧。儿童房邻近主卧，书房朝北。用地宽深未给。",
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
                        space_name="书房", orientation=CardinalOrientation.NORTH
                    ),
                ],
            ),
            must_unknown=["site.width", "site.depth"],
        ),
        _c(
            "bl2-016",
            "两层三卧两卫。厨餐靠近一点，客厅与餐厅相连。地块十二乘十四。",
            tags=["blind", "intent"],
            expect=ExpectKnown(
                floor_count=2,
                bedrooms=3,
                bathrooms=2,
                site_width=12,
                site_depth=14,
                space_names_contains=["厨房", "餐厅", "客厅"],
                relations=[
                    ExpectRelation(a="厨房", b="餐厅", kind="near"),
                    ExpectRelation(a="客厅", b="餐厅", kind="access"),
                ],
            ),
        ),
        # ========== 3. Access vs Near ==========
        _c(
            "bl2-020",
            "两层三卧两卫有车库。从车库能进门厅，厨房靠近餐厅。场地未定。",
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
            "bl2-021",
            "二层四卧。车库连着玄关，主卧远离客厅。宽深以后说。",
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
            "bl2-022",
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
            "bl2-023",
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
            "bl2-024",
            "两层四卧两卫。书房和主卧相连，厨房挨着餐厅。地块十五乘十八。",
            tags=["blind", "access_near"],
            expect=ExpectKnown(
                floor_count=2,
                bedrooms=4,
                bathrooms=2,
                site_width=15,
                site_depth=18,
                space_names_contains=["书房", "主卧", "厨房", "餐厅"],
                relations=[
                    ExpectRelation(a="书房", b="主卧", kind="access"),
                    ExpectRelation(a="厨房", b="餐厅", kind="near"),
                ],
            ),
        ),
        _c(
            "bl2-025",
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
            "bl2-030",
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
            "bl2-031",
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
            "bl2-032",
            "两层三卧。老人最好住楼下，儿童房靠近主卧。用地未知。",
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
            "bl2-033",
            "一层三卧两卫。主卧放一层，客厅要南向。地块十一乘十三。",
            tags=["blind", "weak_pref"],
            expect=ExpectKnown(
                floor_count=1,
                bedrooms=3,
                bathrooms=2,
                site_width=11,
                site_depth=13,
                prefer_south_facing_living=True,
                space_names_contains=["主卧", "客厅"],
                floor_preferences=[
                    ExpectFloorPreference(space_name="主卧", floors=["F1"]),
                ],
            ),
        ),
        _c(
            "bl2-034",
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
            "bl2-035",
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
            "bl2-040",
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
            "bl2-041",
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
            "bl2-042",
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
            "bl2-043",
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
            "bl2-044",
            "两层五卧。主卧远离客厅，餐厅与厨房连通。场地十乘十二。",
            tags=["blind", "negative"],
            expect=ExpectKnown(
                floor_count=2,
                bedrooms=5,
                site_width=10,
                site_depth=12,
                space_names_contains=["主卧", "客厅", "餐厅", "厨房"],
                relations=[
                    ExpectRelation(a="主卧", b="客厅", kind="separation"),
                    ExpectRelation(a="餐厅", b="厨房", kind="open_connection"),
                ],
            ),
        ),
        _c(
            "bl2-045",
            "三层四卧两卫。书房尽量避免厨房噪声，客厅朝南。用地未定。",
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
            "bl2-050",
            "想要宽敞一点的独栋，层数和卧室数还没想好，场地也没定。",
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
            "bl2-051",
            "两层三卧，客厅希望大一点，具体面积先别填。宽深未提供。",
            tags=["blind", "ambiguous"],
            expect=ExpectKnown(
                floor_count=2,
                bedrooms=3,
                space_names_contains=["客厅"],
            ),
            must_unknown=["site.width", "site.depth"],
        ),
        _c(
            "bl2-052",
            "帮我做一个舒服的家，有没有车库再说，场地尺寸未知。",
            tags=["blind", "ambiguous"],
            expect=ExpectKnown(),
            must_unknown=["site.width", "site.depth"],
        ),
        _c(
            "bl2-053",
            "三层别墅感觉阔气，卧室大概四五间吧还没定，地块未量。",
            tags=["blind", "ambiguous"],
            expect=ExpectKnown(floor_count=3),
            must_unknown=["household.bedrooms", "site.width", "site.depth"],
        ),
        _c(
            "bl2-054",
            "一层小房子，两卧一卫，采光好就行。用地宽深以后再说。",
            tags=["blind", "ambiguous", "explicit"],
            expect=ExpectKnown(
                floor_count=1,
                bedrooms=2,
                bathrooms=1,
            ),
            must_unknown=["site.width", "site.depth"],
        ),
        _c(
            "bl2-055",
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
            "bl2-060",
            "两层小宅，三卧两卫有车位。从车库能进玄关；主卧不要靠着客厅。"
            "地块大约十二乘十五米。",
            tags=["blind", "mixed", "access_near", "negative"],
            expect=ExpectKnown(
                floor_count=2,
                bedrooms=3,
                bathrooms=2,
                has_garage=True,
                site_width=12,
                site_depth=15,
                space_names_contains=["车库", "门厅", "主卧", "客厅"],
                relations=[
                    ExpectRelation(a="车库", b="门厅", kind="access"),
                    ExpectRelation(a="主卧", b="客厅", kind="separation"),
                ],
            ),
        ),
        _c(
            "bl2-061",
            "平层三室两卫，客厅与餐厅连通，厨房邻近餐厅，客厅朝南。"
            "宽十米深十二米。",
            tags=["blind", "mixed", "intent"],
            expect=ExpectKnown(
                floor_count=1,
                bedrooms=3,
                bathrooms=2,
                site_width=10,
                site_depth=12,
                prefer_south_facing_living=True,
                space_names_contains=["客厅", "餐厅", "厨房"],
                relations=[
                    ExpectRelation(a="客厅", b="餐厅", kind="open_connection"),
                    ExpectRelation(a="厨房", b="餐厅", kind="near"),
                ],
            ),
        ),
        _c(
            "bl2-062",
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
            "bl2-063",
            "两层四卧两卫。餐厅和厨房连通；儿童房远离厨房；车库连着门厅。"
            "用地宽十三米深十六米。",
            tags=["blind", "mixed"],
            expect=ExpectKnown(
                floor_count=2,
                bedrooms=4,
                bathrooms=2,
                has_garage=True,
                site_width=13,
                site_depth=16,
                space_names_contains=["餐厅", "厨房", "儿童房", "车库", "门厅"],
                relations=[
                    ExpectRelation(a="餐厅", b="厨房", kind="open_connection"),
                    ExpectRelation(a="儿童房", b="厨房", kind="separation"),
                    ExpectRelation(a="车库", b="门厅", kind="access"),
                ],
            ),
        ),
        _c(
            "bl2-064",
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
