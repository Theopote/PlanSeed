"""Phase 6.7.2 — Blind Set v1（严格独立资格认证语料 — **已归档**）。

Blind v1 Gate FAIL；当前严格资格见 `blind_cases_v2.py`。
本文件保留作对照，不得再作为默认 `--set blind` 语料。
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
    _normalize_must_unknown,
)
from packages.schema.site import CardinalOrientation

BLIND_VERSION = "blind-v1"
BLIND_FREEZE_NOTE = (
    "Blind v1 创建时解析层应已冻结；本集不得再驱动 enricher 逐案补丁。"
)


def load_blind_cases() -> list[RequirementBenchmarkCase]:
    """Blind Set v1（目标 40–60；口语化住宅需求）。"""
    cases: list[RequirementBenchmarkCase] = [
        # ========== 1. Explicit Facts ==========
        _c(
            "bl-001",
            "我们打算盖两层小楼，家里准备三个卧室、两个卫生间，地块大概十二米宽、十四米进深。",
            tags=["blind", "explicit"],
            expect=ExpectKnown(
                floor_count=2,
                bedrooms=3,
                bathrooms=2,
                site_width=12,
                site_depth=14,
            ),
        ),
        _c(
            "bl-002",
            "平层就行，两间卧室一个卫生间，车库暂时不要。地块尺寸还没量过，先别瞎填。",
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
            "bl-003",
            "三层别墅，四间卧室，卫生间先按三个算，车位要有。用地宽深以后再说。",
            tags=["blind", "explicit", "3f"],
            expect=ExpectKnown(
                floor_count=3,
                bedrooms=4,
                bathrooms=3,
                has_garage=True,
                space_names_contains=["车库"],
            ),
            must_unknown=["site.width", "site.depth"],
        ),
        _c(
            "bl-004",
            "简单说：二层，五房两厅三卫，带车库。场地约十五乘十八。",
            tags=["blind", "explicit"],
            expect=ExpectKnown(
                floor_count=2,
                bedrooms=5,
                bathrooms=3,
                has_garage=True,
                site_width=15,
                site_depth=18,
            ),
        ),
        _c(
            "bl-005",
            "一层大平层，三室两厅两卫，客厅希望能朝南。地块大概十乘十二米。",
            tags=["blind", "explicit", "orientation"],
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
            "bl-006",
            "两层就够了，卧室数量我还没想清楚，卫生间两个。地块宽深未知，不要编造。",
            tags=["blind", "explicit", "unknown"],
            expect=ExpectKnown(floor_count=2, bathrooms=2),
            must_unknown=[
                "household.bedrooms",
                "site.width",
                "site.depth",
            ],
        ),
        _c(
            "bl-007",
            "家里四口人，想做两层住宅，先按四间卧室规划，卫生间两个，车库有更好。",
            tags=["blind", "explicit"],
            expect=ExpectKnown(
                floor_count=2,
                bedrooms=4,
                bathrooms=2,
                has_garage=True,
            ),
            must_unknown=["site.width", "site.depth"],
        ),
        _c(
            "bl-008",
            "用地十一米宽、十三米深，做两层，三居室两卫，车库未定。",
            tags=["blind", "explicit"],
            expect=ExpectKnown(
                floor_count=2,
                bedrooms=3,
                bathrooms=2,
                site_width=11,
                site_depth=13,
            ),
            must_unknown=["household.has_garage"],
        ),
        # ========== 2. Design Intent Paraphrase (near / open) ==========
        _c(
            "bl-010",
            "两层三卧。做饭的时候端菜不想走太远，厨房跟餐厅最好挨得近一点；客厅和餐厅希望能开敞打通。",
            tags=["blind", "intent", "near", "open"],
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
            "bl-011",
            "两层小住宅。厨房靠近餐厅方便端菜；客厅与餐厅连通成大空间。地块还没定。",
            tags=["blind", "intent", "near", "open"],
            expect=ExpectKnown(
                floor_count=2,
                space_names_contains=["厨房", "餐厅", "客厅"],
                relations=[
                    ExpectRelation(a="厨房", b="餐厅", kind="near"),
                    ExpectRelation(a="客厅", b="餐厅", kind="open_connection"),
                ],
            ),
            must_unknown=["site.width", "site.depth", "household.bedrooms"],
        ),
        _c(
            "bl-012",
            "一家四口，两层。儿童房希望离主卧近一些，方便夜里照顾；厨房靠近餐厅，别隔太远。",
            tags=["blind", "intent", "near"],
            expect=ExpectKnown(
                floor_count=2,
                space_names_contains=["儿童房", "主卧", "厨房", "餐厅"],
                relations=[
                    ExpectRelation(a="儿童房", b="主卧", kind="near"),
                    ExpectRelation(a="厨房", b="餐厅", kind="near"),
                ],
            ),
            must_unknown=["site.width", "site.depth", "household.bedrooms"],
        ),
        _c(
            "bl-013",
            "两层。书房想挨着主卧，晚上加班方便；餐厅就放在厨房旁边。",
            tags=["blind", "intent", "near"],
            expect=ExpectKnown(
                floor_count=2,
                space_names_contains=["书房", "主卧", "餐厅", "厨房"],
                relations=[
                    ExpectRelation(a="书房", b="主卧", kind="near"),
                    ExpectRelation(a="餐厅", b="厨房", kind="near"),
                ],
            ),
            must_unknown=["site.width", "site.depth", "household.bedrooms"],
        ),
        _c(
            "bl-014",
            "两层三卧两卫。客厅与餐厅连通成大起居区，厨房靠近餐厅，方便传菜。",
            tags=["blind", "intent", "open", "near"],
            expect=ExpectKnown(
                floor_count=2,
                bedrooms=3,
                bathrooms=2,
                space_names_contains=["客厅", "餐厅", "厨房"],
                relations=[
                    ExpectRelation(a="客厅", b="餐厅", kind="open_connection"),
                    ExpectRelation(a="厨房", b="餐厅", kind="near"),
                ],
            ),
            must_unknown=["site.width", "site.depth"],
        ),
        _c(
            "bl-015",
            "两层。卫生间最好离主卧近一点，夜里方便。地块未知。",
            tags=["blind", "intent", "near"],
            expect=ExpectKnown(
                floor_count=2,
                space_names_contains=["卫生间", "主卧"],
                relations=[
                    ExpectRelation(a="卫生间", b="主卧", kind="near"),
                ],
            ),
            must_unknown=["site.width", "site.depth", "household.bedrooms"],
        ),        _c(
            "bl-016",
            "叙事一点：我们喜欢做饭时家人能聊得上，所以厨房靠近餐厅；客厅与餐厅连通成一片。两层，三卧。",
            tags=["blind", "intent", "near", "open"],
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
            "bl-017",
            "两层四卧。客房靠近客厅，方便客人走动。场地以后再量。",
            tags=["blind", "intent", "near"],
            expect=ExpectKnown(
                floor_count=2,
                bedrooms=4,
                space_names_contains=["客房", "客厅"],
                relations=[
                    ExpectRelation(a="客房", b="客厅", kind="near"),
                ],
            ),
            must_unknown=["site.width", "site.depth"],
        ),
        # ========== 3. Access vs Near ==========
        _c(
            "bl-020",
            "两层三卧带车库。车停好之后希望能从车库进入门厅，不想再绕到正门。",
            tags=["blind", "access_near", "access"],
            expect=ExpectKnown(
                floor_count=2,
                bedrooms=3,
                has_garage=True,
                space_names_contains=["车库", "门厅"],
                relations=[
                    ExpectRelation(a="车库", b="门厅", kind="access"),
                ],
            ),
            must_unknown=["site.width", "site.depth"],
        ),
        _c(
            "bl-021",
            "两层三卧有车库。车库靠近入口就行，不一定非要内部相通进屋。",
            tags=["blind", "access_near", "near"],
            expect=ExpectKnown(
                floor_count=2,
                bedrooms=3,
                has_garage=True,
                space_names_contains=["车库", "入口"],
                relations=[
                    ExpectRelation(a="车库", b="入口", kind="near"),
                ],
            ),
            must_unknown=["site.width", "site.depth"],
        ),
        _c(
            "bl-022",
            "两层带车库。希望车库与门厅内部相连，下雨天不用淋雨进家。",
            tags=["blind", "access_near", "access"],
            expect=ExpectKnown(
                floor_count=2,
                has_garage=True,
                space_names_contains=["车库", "门厅"],
                relations=[
                    ExpectRelation(a="车库", b="门厅", kind="access"),
                ],
            ),
            must_unknown=["site.width", "site.depth", "household.bedrooms"],
        ),
        _c(
            "bl-023",
            "两层三卧。车库靠近玄关布置，主要是停车方便，门还是走正门。",
            tags=["blind", "access_near", "near"],
            expect=ExpectKnown(
                floor_count=2,
                bedrooms=3,
                has_garage=True,
                space_names_contains=["车库", "门厅"],
                relations=[
                    ExpectRelation(a="车库", b="门厅", kind="near"),
                ],
            ),
            must_unknown=["site.width", "site.depth"],
        ),
        _c(
            "bl-024",
            "两层。厨房还是想做成可以关门的，但厨房靠近餐厅——近归近，不等于开敞连通。",
            tags=["blind", "access_near", "near"],
            expect=ExpectKnown(
                floor_count=2,
                space_names_contains=["厨房", "餐厅"],
                relations=[
                    ExpectRelation(a="厨房", b="餐厅", kind="near"),
                ],
            ),
            must_unknown=["site.width", "site.depth", "household.bedrooms"],
        ),
        _c(
            "bl-025",
            "两层三卧两卫带车库，客厅朝南。进家路线：从车库能进门厅。",
            tags=["blind", "access_near", "access", "orientation"],
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
            "bl-026",
            "两层带车库。地下室停车的话，希望从车库能进门厅，别绕室外。",
            tags=["blind", "access_near", "access"],
            expect=ExpectKnown(
                floor_count=2,
                has_garage=True,
                space_names_contains=["车库", "门厅"],
                relations=[
                    ExpectRelation(a="车库", b="门厅", kind="access"),
                ],
            ),
            must_unknown=["site.width", "site.depth", "household.bedrooms"],
        ),
        _c(
            "bl-027",
            "两层四卧。车库靠近入口就行，内部相连不是硬性要求。",
            tags=["blind", "access_near", "near"],
            expect=ExpectKnown(
                floor_count=2,
                bedrooms=4,
                has_garage=True,
                space_names_contains=["车库", "入口"],
                relations=[
                    ExpectRelation(a="车库", b="入口", kind="near"),
                ],
            ),
            must_unknown=["site.width", "site.depth"],
        ),
        # ========== 4. Weak Preference ==========
        _c(
            "bl-030",
            "两层三卧。如果条件允许，书房朝北采光柔和一些；客厅还是尽量朝南。",
            tags=["blind", "weak_pref", "orientation"],
            expect=ExpectKnown(
                floor_count=2,
                bedrooms=3,
                prefer_south_facing_living=True,
                space_names_contains=["书房", "客厅"],
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
            "bl-031",
            "两层四卧。书房能朝北最好，实在不行也行；老人房尽量放一层。",
            tags=["blind", "weak_pref", "orientation", "floor_pref"],
            expect=ExpectKnown(
                floor_count=2,
                bedrooms=4,
                space_names_contains=["书房", "老人房"],
                orientations=[
                    ExpectOrientation(
                        space_name="书房",
                        orientation=CardinalOrientation.NORTH,
                    ),
                ],
                floor_preferences=[
                    ExpectFloorPreference(space_name="老人房", floors=["F1"]),
                ],
            ),
            must_unknown=["site.width", "site.depth"],
        ),
        _c(
            "bl-032",
            "两层。客厅最好朝南，不是说绝对必须，但优先考虑。地块未知。",
            tags=["blind", "weak_pref", "orientation"],
            expect=ExpectKnown(
                floor_count=2,
                prefer_south_facing_living=True,
                space_names_contains=["客厅"],
            ),
            must_unknown=["site.width", "site.depth", "household.bedrooms"],
        ),
        _c(
            "bl-033",
            "两层三卧。主卧若能朝南更好；书房朝东也行。场地以后再定。",
            tags=["blind", "weak_pref", "orientation"],
            expect=ExpectKnown(
                floor_count=2,
                bedrooms=3,
                space_names_contains=["主卧", "书房"],
                orientations=[
                    ExpectOrientation(
                        space_name="主卧",
                        orientation=CardinalOrientation.SOUTH,
                    ),
                    ExpectOrientation(
                        space_name="书房",
                        orientation=CardinalOrientation.EAST,
                    ),
                ],
            ),
            must_unknown=["site.width", "site.depth"],
        ),
        _c(
            "bl-034",
            "两层。有老人同住的话，一楼留个能长期住的房间比较省心；具体叫不叫老人房都行。",
            tags=["blind", "weak_pref", "floor_pref"],
            expect=ExpectKnown(
                floor_count=2,
                space_names_contains=["老人房"],
                floor_preferences=[
                    ExpectFloorPreference(space_name="老人房", floors=["F1"]),
                ],
            ),
            must_unknown=["site.width", "site.depth", "household.bedrooms"],
        ),
        _c(
            "bl-035",
            "两层四卧两卫。起居室尽量朝南；车库未定。",
            tags=["blind", "weak_pref", "orientation"],
            expect=ExpectKnown(
                floor_count=2,
                bedrooms=4,
                bathrooms=2,
                prefer_south_facing_living=True,
                space_names_contains=["客厅"],
            ),
            must_unknown=["site.width", "site.depth", "household.has_garage"],
        ),
        _c(
            "bl-036",
            "两层。条件允许的话儿童房离主卧近一些；不是硬性约束。",
            tags=["blind", "weak_pref", "near"],
            expect=ExpectKnown(
                floor_count=2,
                space_names_contains=["儿童房", "主卧"],
                relations=[
                    ExpectRelation(a="儿童房", b="主卧", kind="near"),
                ],
            ),
            must_unknown=["site.width", "site.depth", "household.bedrooms"],
        ),
        _c(
            "bl-037",
            "两层三卧。餐厅朝东吃早饭舒服，能做到就做，做不到也不强求。",
            tags=["blind", "weak_pref", "orientation"],
            expect=ExpectKnown(
                floor_count=2,
                bedrooms=3,
                space_names_contains=["餐厅"],
                orientations=[
                    ExpectOrientation(
                        space_name="餐厅",
                        orientation=CardinalOrientation.EAST,
                    ),
                ],
            ),
            must_unknown=["site.width", "site.depth"],
        ),
        # ========== 5. Negative Constraints ==========
        _c(
            "bl-040",
            "两层三卧。主卧不要靠着客厅，晚上电视声会吵；儿童房可以靠近主卧。",
            tags=["blind", "negative", "separation"],
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
            "bl-041",
            "两层。儿童房不要紧邻厨房，油烟和吵闹都不好；主卧也远离入口比较安静。",
            tags=["blind", "negative", "separation"],
            expect=ExpectKnown(
                floor_count=2,
                space_names_contains=["儿童房", "厨房", "主卧", "入口"],
                relations=[
                    ExpectRelation(a="儿童房", b="厨房", kind="separation"),
                    ExpectRelation(a="主卧", b="入口", kind="separation"),
                ],
            ),
            must_unknown=["site.width", "site.depth", "household.bedrooms"],
        ),
        _c(
            "bl-042",
            "老人腿脚不方便，不想让他们天天上下楼，最好一楼留个能长期住的房间。两层四卧。",
            tags=["blind", "negative", "floor_pref"],
            expect=ExpectKnown(
                floor_count=2,
                bedrooms=4,
                space_names_contains=["老人房"],
                floor_preferences=[
                    ExpectFloorPreference(space_name="老人房", floors=["F1"]),
                ],
            ),
            must_unknown=["site.width", "site.depth"],
        ),
        _c(
            "bl-043",
            "两层三卧。老人房放一层，别安排二楼；客房远离客厅，客人要有隐私。",
            tags=["blind", "negative", "floor_pref", "separation"],
            expect=ExpectKnown(
                floor_count=2,
                bedrooms=3,
                space_names_contains=["老人房", "客房", "客厅"],
                floor_preferences=[
                    ExpectFloorPreference(space_name="老人房", floors=["F1"]),
                ],
                relations=[
                    ExpectRelation(a="客房", b="客厅", kind="separation"),
                ],
            ),
            must_unknown=["site.width", "site.depth"],
        ),
        _c(
            "bl-044",
            "两层。主卧想安静，不要靠着客厅；书房远离儿童房，免得吵。",
            tags=["blind", "negative", "separation"],
            expect=ExpectKnown(
                floor_count=2,
                space_names_contains=["主卧", "客厅", "书房", "儿童房"],
                relations=[
                    ExpectRelation(a="主卧", b="客厅", kind="separation"),
                    ExpectRelation(a="书房", b="儿童房", kind="separation"),
                ],
            ),
            must_unknown=["site.width", "site.depth", "household.bedrooms"],
        ),
        _c(
            "bl-045",
            "两层四卧。卫生间远离餐厅，观感更好；厨房靠近餐厅就行。",
            tags=["blind", "negative", "separation", "near"],
            expect=ExpectKnown(
                floor_count=2,
                bedrooms=4,
                space_names_contains=["卫生间", "餐厅", "厨房"],
                relations=[
                    ExpectRelation(a="卫生间", b="餐厅", kind="separation"),
                    ExpectRelation(a="厨房", b="餐厅", kind="near"),
                ],
            ),
            must_unknown=["site.width", "site.depth"],
        ),
        _c(
            "bl-046",
            "两层。父母偶尔过来住，老人房放一层别上楼；儿童房靠近主卧。",
            tags=["blind", "negative", "floor_pref", "near"],
            expect=ExpectKnown(
                floor_count=2,
                space_names_contains=["老人房", "儿童房", "主卧"],
                floor_preferences=[
                    ExpectFloorPreference(space_name="老人房", floors=["F1"]),
                ],
                relations=[
                    ExpectRelation(a="儿童房", b="主卧", kind="near"),
                ],
            ),
            must_unknown=["site.width", "site.depth", "household.bedrooms"],
        ),
        _c(
            "bl-047",
            "两层三卧。主卧远离入口，减少走动噪音；客厅朝南。",
            tags=["blind", "negative", "separation", "orientation"],
            expect=ExpectKnown(
                floor_count=2,
                bedrooms=3,
                prefer_south_facing_living=True,
                space_names_contains=["主卧", "客厅", "入口"],
                relations=[
                    ExpectRelation(a="主卧", b="入口", kind="separation"),
                ],
            ),
            must_unknown=["site.width", "site.depth"],
        ),        # ========== 6. Ambiguous / anti-hallucination ==========
        _c(
            "bl-050",
            "希望房子宽敞一点，住着舒服。其他都还没想好。",
            tags=["blind", "ambiguous", "anti-hallucination"],
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
            "bl-051",
            "给我们设计一个三口之家的小住宅吧，具体层数卧室先不定。",
            tags=["blind", "ambiguous", "anti-hallucination"],
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
            "bl-052",
            "两层小住宅可以，但面积目标我还不清楚，别替我假设两百平。场地宽深也未知。",
            tags=["blind", "ambiguous", "anti-hallucination"],
            expect=ExpectKnown(floor_count=2),
            must_unknown=["site.width", "site.depth", "household.bedrooms"],
        ),
        _c(
            "bl-053",
            "想要采光好、通风好的独栋，卧室卫浴车库都还没想。别编造场地尺寸。",
            tags=["blind", "ambiguous", "anti-hallucination"],
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
            "bl-054",
            "两层三卧。风格现代一点就行——这不是平面指标，场地尺寸未提供。",
            tags=["blind", "ambiguous", "anti-hallucination"],
            expect=ExpectKnown(floor_count=2, bedrooms=3),
            must_unknown=["site.width", "site.depth"],
        ),
        _c(
            "bl-055",
            "卧室数先按普通三口之家假设为三间，但必须标明是假设；两层，场地宽深未知。",
            tags=["blind", "ambiguous", "assumption"],
            expect=ExpectKnown(floor_count=2),
            must_unknown=["site.width", "site.depth", "household.bathrooms"],
            expect_assumptions=[
                ExpectAssumption(
                    key="household.bedrooms",
                    value=3,
                    reason="用户要求按普通三口之家假设卧室数",
                ),
            ],
        ),
        _c(
            "bl-056",
            "先做个两层的框架方案，房间怎么分以后再聊；地块还没买。",
            tags=["blind", "ambiguous", "anti-hallucination"],
            expect=ExpectKnown(floor_count=2),
            must_unknown=[
                "site.width",
                "site.depth",
                "household.bedrooms",
                "household.bathrooms",
            ],
        ),
        _c(
            "bl-057",
            "我们一家想住得宽松些，具体几层几卧还在商量。不要替我填数字。",
            tags=["blind", "ambiguous", "anti-hallucination"],
            expect=ExpectKnown(),
            must_unknown=[
                "floor_count",
                "site.width",
                "site.depth",
                "household.bedrooms",
                "household.bathrooms",
            ],
        ),
        # ========== Mixed / longer narrative ==========
        _c(
            "bl-060",
            "一家四口，父母偶尔过来住。我希望儿童房离主卧近一些，厨房靠近餐厅，"
            "不过厨房还是想做成可以关门的。客厅最好朝南，地块目前还没最后确定。两层，先按三卧两卫想。",
            tags=["blind", "mixed", "near", "orientation"],
            expect=ExpectKnown(
                floor_count=2,
                bedrooms=3,
                bathrooms=2,
                prefer_south_facing_living=True,
                space_names_contains=["儿童房", "主卧", "厨房", "餐厅", "客厅"],
                relations=[
                    ExpectRelation(a="儿童房", b="主卧", kind="near"),
                    ExpectRelation(a="厨房", b="餐厅", kind="near"),
                ],
            ),
            must_unknown=["site.width", "site.depth"],
        ),
        _c(
            "bl-061",
            "两层四卧两卫带车库。希望从车库能进门厅；主卧不要靠着客厅；老人房放一层；书房朝北更好。地块约十三乘十五。",
            tags=["blind", "mixed", "access", "negative", "floor_pref"],
            expect=ExpectKnown(
                floor_count=2,
                bedrooms=4,
                bathrooms=2,
                has_garage=True,
                site_width=13,
                site_depth=15,
                space_names_contains=["车库", "门厅", "主卧", "客厅", "老人房", "书房"],
                relations=[
                    ExpectRelation(a="车库", b="门厅", kind="access"),
                    ExpectRelation(a="主卧", b="客厅", kind="separation"),
                ],
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
        ),
        _c(
            "bl-062",
            "平层三室两厅两卫，不要车库。客厅朝南。宽深先按十米乘十二米。",
            tags=["blind", "mixed", "explicit", "1f"],
            expect=ExpectKnown(
                floor_count=1,
                bedrooms=3,
                bathrooms=2,
                has_garage=False,
                site_width=10,
                site_depth=12,
                prefer_south_facing_living=True,
                space_names_contains=["客厅"],
            ),
        ),
        _c(
            "bl-063",
            "三层，卧室四间，卫生间三，有车库。客餐厅开敞，主卧远离客厅。场地未定勿猜。",
            tags=["blind", "mixed", "3f", "open", "negative"],
            expect=ExpectKnown(
                floor_count=3,
                bedrooms=4,
                bathrooms=3,
                has_garage=True,
                space_names_contains=["客厅", "餐厅", "主卧"],
                relations=[
                    ExpectRelation(a="客厅", b="餐厅", kind="open_connection"),
                    ExpectRelation(a="主卧", b="客厅", kind="separation"),
                ],
            ),
            must_unknown=["site.width", "site.depth"],
        ),
        _c(
            "bl-064",
            "两层小宅。车库靠近入口即可；厨房挨着餐厅；儿童房远离厨房。卧室三间两卫。",
            tags=["blind", "mixed", "access_near", "near", "negative"],
            expect=ExpectKnown(
                floor_count=2,
                bedrooms=3,
                bathrooms=2,
                has_garage=True,
                space_names_contains=["车库", "入口", "厨房", "餐厅", "儿童房"],
                relations=[
                    ExpectRelation(a="车库", b="入口", kind="near"),
                    ExpectRelation(a="厨房", b="餐厅", kind="near"),
                    ExpectRelation(a="儿童房", b="厨房", kind="separation"),
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
