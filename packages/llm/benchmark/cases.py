"""Requirement Benchmark — 用例模型与 Development 语料（Phase 6.6 / 6.7.1）。

Qualification Holdout 见 `holdout_cases.py`；本文件不得单独作为 Alpha 证据。
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from packages.schema.requirements import RelationKind
from packages.schema.site import CardinalOrientation


class ExpectRelation(BaseModel):
    """期望的设计关系意图（端点无序匹配；kind 可选）。"""

    a: str
    b: str
    kind: RelationKind | None = None


class ExpectFloorPreference(BaseModel):
    """期望某空间的楼层偏好（须全部出现在 floor_preference 中）。"""

    space_name: str
    floors: list[str] = Field(min_length=1)


class ExpectOrientation(BaseModel):
    """期望某空间的朝向偏好。"""

    space_name: str
    orientation: CardinalOrientation


class ExpectAssumption(BaseModel):
    """期望显式列入 assumptions（须有可展示的 reason）。"""

    key: str
    value: str | int | float | bool | None = None
    reason: str = "用例期望的显式假设"
    require_reason: bool = True


class ExpectKnown(BaseModel):
    """用例中用户已明确、解析后必须命中的 known。"""

    floor_count: int | None = None
    bedrooms: int | None = None
    bathrooms: int | None = None
    site_width: float | None = None
    site_depth: float | None = None
    has_garage: bool | None = None
    prefer_south_facing_living: bool | None = None
    space_names_contains: list[str] = Field(default_factory=list)
    min_spaces: int | None = None
    # Phase 6.7 — 设计意图
    relations: list[ExpectRelation] = Field(default_factory=list)
    floor_preferences: list[ExpectFloorPreference] = Field(default_factory=list)
    orientations: list[ExpectOrientation] = Field(default_factory=list)


class RequirementBenchmarkCase(BaseModel):
    id: str
    text: str
    tags: list[str] = Field(default_factory=list)
    expect: ExpectKnown = Field(default_factory=ExpectKnown)
    # 这些 key 不得装进 known；且必须显式出现在 unknowns（Detection Recall）
    must_unknown: list[str] = Field(default_factory=list)
    # 允许/期望的显式假设（Assumption Precision）
    expect_assumptions: list[ExpectAssumption] = Field(default_factory=list)


def _c(
    id: str,
    text: str,
    *,
    tags: list[str] | None = None,
    expect: ExpectKnown | None = None,
    must_unknown: list[str] | None = None,
    expect_assumptions: list[ExpectAssumption] | None = None,
) -> RequirementBenchmarkCase:
    return RequirementBenchmarkCase(
        id=id,
        text=text,
        tags=tags or [],
        expect=expect or ExpectKnown(),
        must_unknown=must_unknown or [],
        expect_assumptions=expect_assumptions or [],
    )


def load_benchmark_cases() -> list[RequirementBenchmarkCase]:
    """
    Development Benchmark（原 62 条）。

    Phase 6.7.1：本集合已驱动 enricher 迭代，**不得**单独作为 Qualification 证据。
    Qualification 请用 `load_holdout_cases()`。
    """
    cases: list[RequirementBenchmarkCase] = [
        _c(
            "rb-001",
            "两层三卧两卫，客厅朝南，地块大约十一乘十三米",
            tags=["basic", "site"],
            expect=ExpectKnown(
                floor_count=2,
                bedrooms=3,
                bathrooms=2,
                site_width=11,
                site_depth=13,
                prefer_south_facing_living=True,
            ),
        ),
        _c(
            "rb-002",
            "一层两居室，不要车库",
            tags=["basic", "1f"],
            expect=ExpectKnown(floor_count=1, bedrooms=2, has_garage=False),
            must_unknown=["site.width", "site.depth"],
        ),
        _c(
            "rb-003",
            "三层别墅，四间卧室，带车库，客厅最好朝南",
            tags=["3f", "garage"],
            expect=ExpectKnown(
                floor_count=3,
                bedrooms=4,
                has_garage=True,
                prefer_south_facing_living=True,
            ),
            must_unknown=["site.width"],
        ),
        _c(
            "rb-004",
            "小两口住，一层就够，一室一厅一卫",
            tags=["1f", "compact"],
            expect=ExpectKnown(floor_count=1, bedrooms=1, bathrooms=1),
            must_unknown=["site.width", "site.depth"],
        ),
        _c(
            "rb-005",
            "地块宽 12 米、深 15 米，两层三房",
            tags=["site"],
            expect=ExpectKnown(
                floor_count=2, bedrooms=3, site_width=12, site_depth=15
            ),
        ),
        _c(
            "rb-006",
            "只要说一下：想要带车库的两层住宅",
            tags=["sparse"],
            expect=ExpectKnown(floor_count=2, has_garage=True),
            must_unknown=["household.bedrooms", "site.width"],
        ),
        _c(
            "rb-007",
            "三卧两卫两层，场地 10×12",
            tags=["site"],
            expect=ExpectKnown(
                floor_count=2,
                bedrooms=3,
                bathrooms=2,
                site_width=10,
                site_depth=12,
            ),
        ),
        _c(
            "rb-008",
            "四居室复式，两层，三个卫生间",
            tags=["basic"],
            expect=ExpectKnown(floor_count=2, bedrooms=4, bathrooms=3),
            must_unknown=["site.width"],
        ),
        _c(
            "rb-009",
            "平层大平层，单层，五房两厅三卫",
            tags=["1f"],
            expect=ExpectKnown(floor_count=1, bedrooms=5, bathrooms=3),
        ),
        _c(
            "rb-010",
            "两层，卧室三间，客厅要朝南",
            tags=["orientation"],
            expect=ExpectKnown(
                floor_count=2,
                bedrooms=3,
                prefer_south_facing_living=True,
            ),
            must_unknown=["site.width"],
        ),
        _c(
            "rb-011",
            "帮我做一个独栋：层数两层，卧室 3，卫生间 2，车库有",
            tags=["garage"],
            expect=ExpectKnown(
                floor_count=2, bedrooms=3, bathrooms=2, has_garage=True
            ),
        ),
        _c(
            "rb-012",
            "场地宽十五米深十八米，三层楼，六间卧室",
            tags=["site", "3f"],
            expect=ExpectKnown(
                floor_count=3,
                bedrooms=6,
                site_width=15,
                site_depth=18,
            ),
        ),
        _c(
            "rb-013",
            "没有说地块多大，就两层两卧一卫",
            tags=["unknown-site"],
            expect=ExpectKnown(floor_count=2, bedrooms=2, bathrooms=1),
            must_unknown=["site.width", "site.depth"],
        ),
        _c(
            "rb-014",
            "一层带院子感，三房两厅两卫，车库不要",
            tags=["1f"],
            expect=ExpectKnown(
                floor_count=1, bedrooms=3, bathrooms=2, has_garage=False
            ),
        ),
        _c(
            "rb-015",
            "两层住宅，地块 9 米宽 11 米深",
            tags=["site", "sparse"],
            expect=ExpectKnown(floor_count=2, site_width=9, site_depth=11),
            must_unknown=["household.bedrooms"],
        ),
        _c(
            "rb-016",
            "三卧朝南客厅，两层，两卫",
            tags=["orientation"],
            expect=ExpectKnown(
                floor_count=2,
                bedrooms=3,
                bathrooms=2,
                prefer_south_facing_living=True,
            ),
        ),
        _c(
            "rb-017",
            "我想要两层的房子，卧室数量还没想好",
            tags=["unknown-bed"],
            expect=ExpectKnown(floor_count=2),
            must_unknown=["household.bedrooms", "site.width"],
        ),
        _c(
            "rb-018",
            "四层不行，就做三层，四房三卫带车库",
            tags=["3f"],
            expect=ExpectKnown(
                floor_count=3, bedrooms=4, bathrooms=3, has_garage=True
            ),
        ),
        _c(
            "rb-019",
            "11x13 场地，两层，三居",
            tags=["site"],
            expect=ExpectKnown(
                floor_count=2, bedrooms=3, site_width=11, site_depth=13
            ),
        ),
        _c(
            "rb-020",
            "单层两室一厅，地块宽 8 深 10",
            tags=["1f", "site"],
            expect=ExpectKnown(
                floor_count=1, bedrooms=2, site_width=8, site_depth=10
            ),
        ),
        _c(
            "rb-021",
            "两层五卧，卫生间四个，要车库",
            tags=["large"],
            expect=ExpectKnown(
                floor_count=2, bedrooms=5, bathrooms=4, has_garage=True
            ),
        ),
        _c(
            "rb-022",
            "简要：F2，3bed，南向客厅",
            tags=["short"],
            expect=ExpectKnown(
                floor_count=2,
                bedrooms=3,
                prefer_south_facing_living=True,
            ),
        ),
        _c(
            "rb-023",
            "地块 14 乘 16，三层楼房，卧室 5 间",
            tags=["site", "3f"],
            expect=ExpectKnown(
                floor_count=3,
                bedrooms=5,
                site_width=14,
                site_depth=16,
            ),
        ),
        _c(
            "rb-024",
            "两层两卫三房，不提车库也不要瞎加车库",
            tags=["no-hallucinate"],
            expect=ExpectKnown(floor_count=2, bedrooms=3, bathrooms=2),
            must_unknown=["household.has_garage", "site.width"],
        ),
        _c(
            "rb-025",
            "一层一卧一卫，给老人住",
            tags=["1f", "compact"],
            expect=ExpectKnown(floor_count=1, bedrooms=1, bathrooms=1),
        ),
        _c(
            "rb-026",
            "两层，宽 12 深 12，四房两厅两卫",
            tags=["site"],
            expect=ExpectKnown(
                floor_count=2,
                bedrooms=4,
                bathrooms=2,
                site_width=12,
                site_depth=12,
            ),
        ),
        _c(
            "rb-027",
            "三层小别墅 三室两厅两卫 客厅朝南",
            tags=["3f", "orientation"],
            expect=ExpectKnown(
                floor_count=3,
                bedrooms=3,
                bathrooms=2,
                prefer_south_facing_living=True,
            ),
        ),
        _c(
            "rb-028",
            "只要场地：宽 13 米，深 17 米，别的以后再说",
            tags=["site-only"],
            expect=ExpectKnown(site_width=13, site_depth=17),
            must_unknown=["household.bedrooms", "floor_count"],
        ),
        _c(
            "rb-029",
            "两层带车库，卧室两间，卫生间一间",
            tags=["garage"],
            expect=ExpectKnown(
                floor_count=2, bedrooms=2, bathrooms=1, has_garage=True
            ),
        ),
        _c(
            "rb-030",
            "三卧两层，卫生间数量未定",
            tags=["unknown-bath"],
            expect=ExpectKnown(floor_count=2, bedrooms=3),
            must_unknown=["household.bathrooms", "site.width"],
        ),
        _c(
            "rb-031",
            "一层三房两卫，地块约 10×14",
            tags=["1f", "site"],
            expect=ExpectKnown(
                floor_count=1,
                bedrooms=3,
                bathrooms=2,
                site_width=10,
                site_depth=14,
            ),
        ),
        _c(
            "rb-032",
            "做个两层的，客厅朝南，三室一厅两卫",
            tags=["orientation"],
            expect=ExpectKnown(
                floor_count=2,
                bedrooms=3,
                bathrooms=2,
                prefer_south_facing_living=True,
            ),
        ),
        _c(
            "rb-033",
            "六居室太大了，改成两层四卧两卫",
            tags=["basic"],
            expect=ExpectKnown(floor_count=2, bedrooms=4, bathrooms=2),
        ),
        _c(
            "rb-034",
            "场地 16x20，两层，卧室 3，有车库",
            tags=["site", "garage"],
            expect=ExpectKnown(
                floor_count=2,
                bedrooms=3,
                site_width=16,
                site_depth=20,
                has_garage=True,
            ),
        ),
        _c(
            "rb-035",
            "一层房子，两卧一卫，客厅朝南",
            tags=["1f", "orientation"],
            expect=ExpectKnown(
                floor_count=1,
                bedrooms=2,
                bathrooms=1,
                prefer_south_facing_living=True,
            ),
        ),
        _c(
            "rb-036",
            "三层，两卫，四房，无车库",
            tags=["3f"],
            expect=ExpectKnown(
                floor_count=3, bedrooms=4, bathrooms=2, has_garage=False
            ),
        ),
        _c(
            "rb-037",
            "宽 11 深 13，层数两层，卧室数三",
            tags=["site"],
            expect=ExpectKnown(
                floor_count=2, bedrooms=3, site_width=11, site_depth=13
            ),
        ),
        _c(
            "rb-038",
            "小型两层住宅，一卫两房",
            tags=["compact"],
            expect=ExpectKnown(floor_count=2, bedrooms=2, bathrooms=1),
            must_unknown=["site.width"],
        ),
        _c(
            "rb-039",
            "需要书房吗？先不定。先定两层三卧两卫朝南客厅",
            tags=["orientation"],
            expect=ExpectKnown(
                floor_count=2,
                bedrooms=3,
                bathrooms=2,
                prefer_south_facing_living=True,
            ),
        ),
        _c(
            "rb-040",
            "地块正方形 12×12，一层三卧",
            tags=["site", "1f"],
            expect=ExpectKnown(
                floor_count=1, bedrooms=3, site_width=12, site_depth=12
            ),
        ),
        _c(
            "rb-041",
            "两层别墅，五室两厅三卫，带车库，南向客厅",
            tags=["large", "garage", "orientation"],
            expect=ExpectKnown(
                floor_count=2,
                bedrooms=5,
                bathrooms=3,
                has_garage=True,
                prefer_south_facing_living=True,
            ),
        ),
        _c(
            "rb-042",
            "还没想好地块，两层两房一卫即可",
            tags=["unknown-site"],
            expect=ExpectKnown(floor_count=2, bedrooms=2, bathrooms=1),
            must_unknown=["site.width", "site.depth"],
        ),
        _c(
            "rb-043",
            "三层 卧室三 卫生间二 场地 13 乘 15",
            tags=["3f", "site"],
            expect=ExpectKnown(
                floor_count=3,
                bedrooms=3,
                bathrooms=2,
                site_width=13,
                site_depth=15,
            ),
        ),
        _c(
            "rb-044",
            "一层，车库要，两室一厅一卫",
            tags=["1f", "garage"],
            expect=ExpectKnown(
                floor_count=1, bedrooms=2, bathrooms=1, has_garage=True
            ),
        ),
        _c(
            "rb-045",
            "两层住宅需求：床位三间，卫浴两间，朝南客厅，不提尺寸",
            tags=["orientation", "unknown-site"],
            expect=ExpectKnown(
                floor_count=2,
                bedrooms=3,
                bathrooms=2,
                prefer_south_facing_living=True,
            ),
            must_unknown=["site.width", "site.depth"],
        ),
        _c(
            "rb-046",
            "做成两层，宽九米深十二米，三房两卫",
            tags=["site"],
            expect=ExpectKnown(
                floor_count=2,
                bedrooms=3,
                bathrooms=2,
                site_width=9,
                site_depth=12,
            ),
        ),
        _c(
            "rb-047",
            "仅知：楼层=2，卧室=4",
            tags=["sparse"],
            expect=ExpectKnown(floor_count=2, bedrooms=4),
            must_unknown=["site.width", "household.bathrooms"],
        ),
        _c(
            "rb-048",
            "三层大宅，六房四卫，车库双车位就算有车库，客厅朝南",
            tags=["3f", "large", "orientation"],
            expect=ExpectKnown(
                floor_count=3,
                bedrooms=6,
                bathrooms=4,
                has_garage=True,
                prefer_south_facing_living=True,
            ),
        ),
        _c(
            "rb-049",
            "平房一层，三室一厅一卫，地块 10 乘 10",
            tags=["1f", "site"],
            expect=ExpectKnown(
                floor_count=1,
                bedrooms=3,
                bathrooms=1,
                site_width=10,
                site_depth=10,
            ),
        ),
        _c(
            "rb-050",
            "两层三卧，地块宽十一深十三，两卫，朝南客厅，不要车库",
            tags=["full"],
            expect=ExpectKnown(
                floor_count=2,
                bedrooms=3,
                bathrooms=2,
                site_width=11,
                site_depth=13,
                prefer_south_facing_living=True,
                has_garage=False,
            ),
        ),
        _c(
            "rb-051",
            "请解析：2层、3卧、2卫、客厅南、场地11x13、无车库",
            tags=["full", "structured"],
            expect=ExpectKnown(
                floor_count=2,
                bedrooms=3,
                bathrooms=2,
                site_width=11,
                site_depth=13,
                prefer_south_facing_living=True,
                has_garage=False,
            ),
        ),
        _c(
            "rb-052",
            "一层两卧，场地未提供请勿编造宽深",
            tags=["anti-hallucination"],
            expect=ExpectKnown(floor_count=1, bedrooms=2),
            must_unknown=["site.width", "site.depth"],
        ),
        # —— Phase 6.7：设计意图（关系 / 楼层偏好 / 朝向）——
        _c(
            "rb-053",
            "两层三卧，厨房靠近餐厅，客厅与餐厅连通",
            tags=["relation", "intent"],
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
            "rb-054",
            "两层三卧，主卧远离入口，儿童房靠近主卧",
            tags=["relation", "intent"],
            expect=ExpectKnown(
                floor_count=2,
                bedrooms=3,
                space_names_contains=["主卧", "入口", "儿童房"],
                relations=[
                    ExpectRelation(a="主卧", b="入口", kind="separation"),
                    ExpectRelation(a="儿童房", b="主卧", kind="near"),
                ],
            ),
            must_unknown=["site.width"],
        ),
        _c(
            "rb-055",
            "两层四卧，老人房放一层，书房朝北",
            tags=["floor_pref", "orientation", "intent"],
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
            "rb-056",
            "两层三卧两卫带车库，车库与门厅内部相连，客厅朝南",
            tags=["relation", "garage", "orientation", "intent"],
            expect=ExpectKnown(
                floor_count=2,
                bedrooms=3,
                bathrooms=2,
                has_garage=True,
                prefer_south_facing_living=True,
                space_names_contains=["车库", "门厅"],
                relations=[
                    ExpectRelation(a="车库", b="门厅", kind="access"),
                ],
            ),
            must_unknown=["site.width"],
        ),
        _c(
            "rb-057",
            "三层四卧，老人房放一层，主卧远离客厅，儿童房靠近主卧",
            tags=["relation", "floor_pref", "intent", "3f"],
            expect=ExpectKnown(
                floor_count=3,
                bedrooms=4,
                space_names_contains=["老人房", "主卧", "客厅", "儿童房"],
                floor_preferences=[
                    ExpectFloorPreference(space_name="老人房", floors=["F1"]),
                ],
                relations=[
                    ExpectRelation(a="主卧", b="客厅", kind="separation"),
                    ExpectRelation(a="儿童房", b="主卧", kind="near"),
                ],
            ),
            must_unknown=["site.width", "site.depth"],
        ),
        _c(
            "rb-058",
            "两层三卧，客餐厅连通，客房保持私密远离客厅",
            tags=["relation", "intent"],
            expect=ExpectKnown(
                floor_count=2,
                bedrooms=3,
                space_names_contains=["客厅", "餐厅", "客房"],
                relations=[
                    ExpectRelation(a="客厅", b="餐厅", kind="open_connection"),
                    ExpectRelation(a="客房", b="客厅", kind="separation"),
                ],
            ),
            must_unknown=["site.width"],
        ),
        _c(
            "rb-059",
            "一层两卧，厨房靠近餐厅；场地宽深未知勿编造",
            tags=["relation", "intent", "anti-hallucination", "1f"],
            expect=ExpectKnown(
                floor_count=1,
                bedrooms=2,
                space_names_contains=["厨房", "餐厅"],
                relations=[
                    ExpectRelation(a="厨房", b="餐厅", kind="near"),
                ],
            ),
            must_unknown=["site.width", "site.depth"],
        ),
        _c(
            "rb-060",
            "两层四卧，客厅朝南，书房朝北，老人房放一层",
            tags=["orientation", "floor_pref", "intent"],
            expect=ExpectKnown(
                floor_count=2,
                bedrooms=4,
                prefer_south_facing_living=True,
                space_names_contains=["客厅", "书房", "老人房"],
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
                floor_preferences=[
                    ExpectFloorPreference(space_name="老人房", floors=["F1"]),
                ],
            ),
            must_unknown=["site.width"],
        ),
        # —— Unknown Detection / Assumption：稀疏需求必须显式列 unknowns ——
        _c(
            "rb-061",
            "给我设计一个三口之家。",
            tags=["sparse", "unknown-detection", "anti-hallucination"],
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
            "rb-062",
            "两层小住宅，卧室数先按普通三口之家假设为三间，但必须标明是假设；场地宽深未知",
            tags=["assumption", "unknown-detection"],
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
    ]
    return cases


def benchmark_case_count() -> int:
    return len(load_benchmark_cases())
