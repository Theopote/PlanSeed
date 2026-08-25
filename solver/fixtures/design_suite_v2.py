"""Design Benchmark v2 — 建筑师可接受性用例集（Wave 1: Core B01–B07）。

与 Layout Benchmark Suite v1（generator qualification）独立编号空间。
规格：docs/design-benchmark-v2.md

用法：
  uv run python -m solver.benchmark --suite design-v2 --count 32
  uv run python -m solver.benchmark --suite design-v2 --cases B01,B03 --count 8
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal

from packages.schema.constraints import (
    AdjacencyConstraint,
    ConstraintKind,
    ConstraintSource,
    FloorConstraint,
    OrientationConstraint,
    SeparationConstraint,
)
from packages.schema.program import DesignProgram
from packages.schema.project import ProjectSpec
from packages.schema.room import FloorSpec, RoomCategory, RoomSpec
from packages.schema.site import CardinalEdge, SetbackSpec, SiteSpec

from solver.program.normalize import normalize

SUITE_ID = "design-benchmark-v2"
SUITE_VERSION = "v2"
WAVE_CORE = "core"

Tier = Literal["core", "site", "intent"]


@dataclass(frozen=True)
class DesignSuiteCaseMeta:
    id: str
    title: str
    description: str
    tier: Tier = "core"
    focus_metrics: tuple[str, ...] = ()
    d_grade_hints: tuple[str, ...] = ()


@dataclass
class DesignSuiteCase:
    """可运行用例：program + 评审元数据。"""

    meta: DesignSuiteCaseMeta
    program: DesignProgram
    wave: str = WAVE_CORE


def _room(
    rid: str,
    name: str,
    category: RoomCategory,
    area: float,
    floor_id: str,
    *,
    tags: list[str] | None = None,
) -> RoomSpec:
    return RoomSpec(
        id=rid,
        name=name,
        category=category,
        target_area=area,
        floor_id=floor_id,
        tags=list(tags or []),
    )


def _floors_from_rooms(rooms: list[RoomSpec], labels: dict[str, str]) -> list[FloorSpec]:
    by: dict[str, list[str]] = {}
    for r in rooms:
        assert r.floor_id is not None
        by.setdefault(r.floor_id, []).append(r.id)
    return [
        FloorSpec(id=fid, label=labels.get(fid, fid), room_ids=ids)
        for fid, ids in by.items()
    ]


def _program(
    *,
    width: float,
    depth: float,
    rooms: list[RoomSpec],
    floor_labels: dict[str, str],
    constraints: list | None = None,
    site_kwargs: dict | None = None,
) -> DesignProgram:
    site_kw = {
        "width": width,
        "depth": depth,
        "stair_width": 1.8,
        "stair_depth": 4.2,
    }
    if site_kwargs:
        site_kw.update(site_kwargs)
    floors = _floors_from_rooms(rooms, floor_labels)
    spec = ProjectSpec(
        site=SiteSpec(**site_kw),
        floors=floors,
        rooms=rooms,
    )
    program = normalize(spec)
    if constraints:
        program.constraints = list(program.constraints) + list(constraints)
    return program


def _orient(room_id: str, direction: str, *, weight: float = 1.0) -> OrientationConstraint:
    return OrientationConstraint(
        id=f"orient-{room_id}-{direction}",
        kind=ConstraintKind.ORIENTATION,
        room_id=room_id,
        preferred_orientation=direction,
        hard=False,
        weight=weight,
        source=ConstraintSource.USER,
    )


def _adj(a: str, b: str, *, weight: float = 1.0, desc: str = "") -> AdjacencyConstraint:
    return AdjacencyConstraint(
        id=f"adj-{a}-{b}",
        kind=ConstraintKind.ADJACENCY,
        room_a_id=a,
        room_b_id=b,
        share_wall=True,
        hard=False,
        weight=weight,
        source=ConstraintSource.USER,
        description=desc,
    )


def _sep(a: str, b: str, dist: float, *, weight: float = 1.0) -> SeparationConstraint:
    return SeparationConstraint(
        id=f"sep-{a}-{b}",
        kind=ConstraintKind.SEPARATION,
        room_a_id=a,
        room_b_id=b,
        min_distance=dist,
        hard=False,
        weight=weight,
        source=ConstraintSource.USER,
    )


def _floor(room_id: str, floor_id: str, *, hard: bool = True) -> FloorConstraint:
    return FloorConstraint(
        id=f"floor-{room_id}-{floor_id}",
        kind=ConstraintKind.FLOOR,
        room_id=room_id,
        floor_id=floor_id,
        hard=hard,
        source=ConstraintSource.USER,
    )


def _b01() -> DesignSuiteCase:
    rooms = [
        _room("living", "客厅", RoomCategory.PUBLIC, 16, "F1"),
        _room("kitchen", "厨房", RoomCategory.WET, 9, "F1", tags=["kitchen"]),
        _room("bath1", "卫生间", RoomCategory.WET, 4, "F1"),
        _room("bed1", "主卧", RoomCategory.PRIVATE, 12, "F1"),
        _room("bed2", "次卧", RoomCategory.PRIVATE, 10, "F1"),
    ]
    program = _program(
        width=8,
        depth=12,
        rooms=rooms,
        floor_labels={"F1": "一层"},
        site_kwargs={
            "road_edges": [CardinalEdge.SOUTH],
            "entrance_edge": CardinalEdge.SOUTH,
        },
        constraints=[
            _orient("living", "south"),
            _adj("kitchen", "living", weight=1.0, desc="厨卫邻公共区"),
        ],
    )
    return DesignSuiteCase(
        meta=DesignSuiteCaseMeta(
            id="B01",
            title="8×12 城市窄宅",
            description="窄面宽城市宅，公共区紧凑、卧室靠内",
            tier="core",
            focus_metrics=("spatial", "circulation", "room_proportion"),
            d_grade_hints=("卧室面宽不足", "客厅无外墙", "厨卫无法相邻"),
        ),
        program=program,
    )


def _b02() -> DesignSuiteCase:
    rooms = [
        _room("living", "客厅", RoomCategory.PUBLIC, 24, "F1"),
        _room("kitchen", "餐厨", RoomCategory.WET, 18, "F1", tags=["kitchen"]),
        _room("bath1", "客卫", RoomCategory.WET, 4, "F1"),
        _room("garage", "车库", RoomCategory.OTHER, 20, "F1", tags=["garage"]),
        _room("master", "主卧", RoomCategory.PRIVATE, 18, "F2"),
        _room("ensuite", "主卫", RoomCategory.WET, 5, "F2", tags=["ensuite", "master_bath"]),
        _room("bed2", "次卧1", RoomCategory.PRIVATE, 12, "F2"),
        _room("bed3", "次卧2", RoomCategory.PRIVATE, 12, "F2"),
        _room("bath2", "公卫", RoomCategory.WET, 4, "F2"),
    ]
    program = _program(
        width=12,
        depth=15,
        rooms=rooms,
        floor_labels={"F1": "一层", "F2": "二层"},
        site_kwargs={
            "road_edges": [CardinalEdge.SOUTH],
            "entrance_edge": CardinalEdge.SOUTH,
        },
        constraints=[
            _orient("master", "south"),
            _adj("garage", "living", weight=0.8, desc="车库临道路区"),
        ],
    )
    return DesignSuiteCase(
        meta=DesignSuiteCaseMeta(
            id="B02",
            title="12×15 普通独栋",
            description="标准郊区独栋，公私分层清晰",
            tier="core",
            focus_metrics=("program", "privacy", "technical"),
            d_grade_hints=("二层卧室不可达", "车库背路", "公区过碎"),
        ),
        program=program,
    )


def _b03() -> DesignSuiteCase:
    rooms = [
        _room("living", "客厅", RoomCategory.PUBLIC, 26, "F1"),
        _room("dining", "餐厅", RoomCategory.PUBLIC, 14, "F1"),
        _room("kitchen", "厨房", RoomCategory.WET, 12, "F1", tags=["kitchen"]),
        _room("entry", "门厅", RoomCategory.PUBLIC, 6, "F1"),
        _room("master", "主卧", RoomCategory.PRIVATE, 18, "F2"),
        _room("bed2", "次卧1", RoomCategory.PRIVATE, 12, "F2"),
        _room("bed3", "次卧2", RoomCategory.PRIVATE, 11, "F2"),
        _room("bath1", "卫生间", RoomCategory.WET, 4, "F2"),
        _room("bath2", "次卫", RoomCategory.WET, 4, "F2"),
    ]
    program = _program(
        width=14,
        depth=16,
        rooms=rooms,
        floor_labels={"F1": "一层", "F2": "二层"},
        site_kwargs={
            "setbacks": SetbackSpec(north=0, south=4, east=0, west=0),
            "setback_source": "user",
            "road_edges": [CardinalEdge.SOUTH],
            "entrance_edge": CardinalEdge.SOUTH,
        },
        constraints=[
            _orient("living", "south", weight=1.2),
            _orient("master", "south", weight=1.0),
            _sep("kitchen", "master", 3.0, weight=1.0),
        ],
    )
    return DesignSuiteCase(
        meta=DesignSuiteCaseMeta(
            id="B03",
            title="南向庭院住宅",
            description="生活空间围绕南向庭院组织",
            tier="core",
            focus_metrics=("environment", "site_relationship", "privacy"),
            d_grade_hints=("主要房间背庭院", "庭院被服务空间占据"),
        ),
        program=program,
    )


def _b04() -> DesignSuiteCase:
    rooms = [
        _room("garage1", "车库1", RoomCategory.OTHER, 18, "F1", tags=["garage"]),
        _room("garage2", "车库2", RoomCategory.OTHER, 18, "F1", tags=["garage"]),
        _room("entry", "门厅", RoomCategory.PUBLIC, 8, "F1"),
        _room("laundry", "洗衣间", RoomCategory.WET, 5, "F1", tags=["laundry"]),
        _room("living", "起居", RoomCategory.PUBLIC, 28, "F2"),
        _room("kitchen", "厨房", RoomCategory.WET, 14, "F2", tags=["kitchen"]),
        _room("bed1", "主卧", RoomCategory.PRIVATE, 14, "F2"),
        _room("bed2", "次卧1", RoomCategory.PRIVATE, 12, "F2"),
        _room("bed3", "次卧2", RoomCategory.PRIVATE, 11, "F2"),
        _room("bath1", "主卫", RoomCategory.WET, 4, "F2"),
        _room("bath2", "公卫", RoomCategory.WET, 4, "F2"),
    ]
    program = _program(
        width=14,
        depth=18,
        rooms=rooms,
        floor_labels={"F1": "一层", "F2": "二层"},
        site_kwargs={
            "road_edges": [CardinalEdge.WEST],
            "entrance_edge": CardinalEdge.WEST,
        },
        constraints=[
            _adj("garage1", "entry", weight=1.2),
            _adj("garage2", "entry", weight=1.0),
        ],
    )
    return DesignSuiteCase(
        meta=DesignSuiteCaseMeta(
            id="B04",
            title="双车库住宅",
            description="双车家庭，车库区与服务区成组",
            tier="core",
            focus_metrics=("program", "site_relationship", "circulation"),
            d_grade_hints=("车库无法并排", "起居区被车库挤压"),
        ),
        program=program,
    )


def _b05() -> DesignSuiteCase:
    rooms = [
        _room("living", "客厅", RoomCategory.PUBLIC, 22, "F1"),
        _room("dining", "餐厅", RoomCategory.PUBLIC, 14, "F1"),
        _room("kitchen", "厨房", RoomCategory.WET, 12, "F1", tags=["kitchen"]),
        _room("elder", "老人卧", RoomCategory.PRIVATE, 14, "F1", tags=["elder"]),
        _room("elder_bath", "老人卫", RoomCategory.WET, 5, "F1"),
        _room("bath1", "客卫", RoomCategory.WET, 4, "F1"),
        _room("master", "主卧", RoomCategory.PRIVATE, 18, "F2"),
        _room("ensuite", "主卫", RoomCategory.WET, 5, "F2", tags=["ensuite", "master_bath"]),
        _room("bed2", "次卧1", RoomCategory.PRIVATE, 12, "F2"),
        _room("bed3", "次卧2", RoomCategory.PRIVATE, 11, "F2"),
        _room("bath2", "公卫", RoomCategory.WET, 4, "F2"),
        _room("study", "书房", RoomCategory.OTHER, 10, "F2"),
    ]
    program = _program(
        width=13,
        depth=16,
        rooms=rooms,
        floor_labels={"F1": "一层", "F2": "二层"},
        constraints=[
            _floor("elder", "F1"),
            _floor("elder_bath", "F1"),
            _sep("kitchen", "elder", 3.0, weight=1.2),
        ],
    )
    return DesignSuiteCase(
        meta=DesignSuiteCaseMeta(
            id="B05",
            title="三代同堂",
            description="多代分层，老人套房在一层",
            tier="core",
            focus_metrics=("circulation", "privacy", "program"),
            d_grade_hints=("老人卧在二层", "动线穿越老人卧", "一层无卫生间"),
        ),
        program=program,
    )


def _b06() -> DesignSuiteCase:
    rooms = [
        _room("living", "客厅", RoomCategory.PUBLIC, 22, "F1"),
        _room("kitchen", "餐厨", RoomCategory.WET, 16, "F1", tags=["kitchen"]),
        _room("master", "主卧", RoomCategory.PRIVATE, 16, "F1"),
        _room("bed2", "次卧", RoomCategory.PRIVATE, 12, "F1"),
        _room("bath1", "主卫", RoomCategory.WET, 6, "F1", tags=["accessible"]),
        _room("bath2", "客卫", RoomCategory.WET, 4, "F1"),
        _room("laundry", "洗衣间", RoomCategory.WET, 5, "F1", tags=["laundry"]),
        _room("storage", "储藏", RoomCategory.OTHER, 4, "F1"),
    ]
    program = _program(
        width=12,
        depth=14,
        rooms=rooms,
        floor_labels={"F1": "一层"},
        constraints=[
            _adj("master", "bath1", weight=1.2, desc="主卧近卫生间"),
        ],
    )
    return DesignSuiteCase(
        meta=DesignSuiteCaseMeta(
            id="B06",
            title="一层适老住宅",
            description="全龄一层，动线短、无垂直交通",
            tier="core",
            focus_metrics=("circulation", "room_proportion", "furniture_usability"),
            d_grade_hints=("狭长走廊", "卫生间不可达", "房间极端狭长"),
        ),
        program=program,
    )


def _b07() -> DesignSuiteCase:
    rooms = [
        _room("living", "客厅", RoomCategory.PUBLIC, 24, "F1"),
        _room("kitchen", "餐厨", RoomCategory.WET, 16, "F1", tags=["kitchen"]),
        _room("bath1", "客卫", RoomCategory.WET, 4, "F1"),
        _room("master", "主卧", RoomCategory.PRIVATE, 16, "F2"),
        _room("ensuite", "主卫", RoomCategory.WET, 5, "F2", tags=["ensuite", "master_bath"]),
        _room("bed2", "次卧1", RoomCategory.PRIVATE, 11, "F2"),
        _room("bed3", "次卧2", RoomCategory.PRIVATE, 11, "F2"),
        _room("bed4", "次卧3", RoomCategory.PRIVATE, 11, "F2"),
        _room("bath2", "公卫", RoomCategory.WET, 4, "F2"),
    ]
    bedroom_ids = ("master", "bed2", "bed3", "bed4")
    program = _program(
        width=11,
        depth=14,
        rooms=rooms,
        floor_labels={"F1": "一层", "F2": "二层"},
        constraints=[_floor(rid, "F2") for rid in bedroom_ids]
        + [_floor("ensuite", "F2"), _floor("bath2", "F2")],
    )
    return DesignSuiteCase(
        meta=DesignSuiteCaseMeta(
            id="B07",
            title="两层四卧住宅",
            description="典型四卧家庭，二层私密区完整",
            tier="core",
            focus_metrics=("program", "privacy", "technical"),
            d_grade_hints=("次卧数不足", "一层出现卧室", "楼梯占满核心区"),
        ),
        program=program,
    )


_CASE_BUILDERS: dict[str, Callable[[], DesignSuiteCase]] = {
    "B01": _b01,
    "B02": _b02,
    "B03": _b03,
    "B04": _b04,
    "B05": _b05,
    "B06": _b06,
    "B07": _b07,
}

# Wave 1 仅 Core；Site/Intent 在后续 wave 追加
WAVE1_CASE_IDS: tuple[str, ...] = tuple(_CASE_BUILDERS.keys())


def list_suite_case_ids(*, wave: str | None = None) -> list[str]:
    if wave is None:
        return sorted(_CASE_BUILDERS.keys())
    if wave == WAVE_CORE:
        return list(WAVE1_CASE_IDS)
    return sorted(_CASE_BUILDERS.keys())


def load_suite_case(case_id: str) -> DesignSuiteCase:
    key = case_id.upper().strip()
    if key not in _CASE_BUILDERS:
        known = ", ".join(list_suite_case_ids())
        raise KeyError(f"unknown design suite case {case_id!r}; known: {known}")
    return _CASE_BUILDERS[key]()


def iter_suite_cases(case_ids: list[str] | None = None) -> list[DesignSuiteCase]:
    ids = case_ids or list_suite_case_ids()
    return [load_suite_case(cid) for cid in ids]
