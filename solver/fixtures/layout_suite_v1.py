"""Layout Benchmark Suite v1 — 住宅 generator 资格用例集。

单 case（11×13 两层）不足以判定 MaxRect 是否进入 Alpha pool。
本套覆盖场地形态 / 层数 / 程序张力 / locks。

用法：
  uv run python -m solver.benchmark --suite v1 --count 32
  uv run python -m solver.benchmark --suite v1 --cases B01,B03 --count 8
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from packages.schema.constraints import (
    AdjacencyConstraint,
    ConstraintKind,
    ConstraintSource,
    OrientationConstraint,
    SeparationConstraint,
)
from packages.schema.locks import LayoutLocks, LockedRoomRect, LockedZoneRect
from packages.schema.program import DesignProgram
from packages.schema.project import ProjectSpec
from packages.schema.room import FloorSpec, RoomCategory, RoomSpec
from packages.schema.site import SiteSpec
from packages.schema.zoning import ArchitecturalZone

from solver.generators.guillotine import GuillotineGenerator
from solver.program.normalize import normalize

SUITE_ID = "layout-benchmark-suite-v1"
SUITE_VERSION = "v1"


@dataclass(frozen=True)
class LayoutSuiteCaseMeta:
    id: str
    title: str
    description: str


@dataclass
class LayoutSuiteCase:
    """可运行用例：program + 可选 locks。"""

    meta: LayoutSuiteCaseMeta
    program: DesignProgram
    locks: LayoutLocks | None = None


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
) -> DesignProgram:
    floors = _floors_from_rooms(rooms, floor_labels)
    spec = ProjectSpec(
        site=SiteSpec(width=width, depth=depth, stair_width=1.8, stair_depth=4.2),
        floors=floors,
        rooms=rooms,
    )
    program = normalize(spec)
    if constraints:
        program.constraints = list(program.constraints) + list(constraints)
    return program


def _compact_single(width: float, depth: float, *, bedrooms: int) -> DesignProgram:
    """单层紧凑 / 三卧变体。"""
    rooms = [
        _room("living", "客厅", RoomCategory.PUBLIC, 18 if bedrooms <= 2 else 22, "F1"),
        _room("kitchen", "厨房", RoomCategory.WET, 10, "F1", tags=["kitchen"]),
        _room("bath1", "卫生间", RoomCategory.WET, 4, "F1"),
        _room("bed1", "主卧", RoomCategory.PRIVATE, 14, "F1"),
    ]
    if bedrooms >= 2:
        rooms.append(_room("bed2", "次卧1", RoomCategory.PRIVATE, 11, "F1"))
    if bedrooms >= 3:
        rooms.append(_room("bed3", "次卧2", RoomCategory.PRIVATE, 11, "F1"))
        rooms.append(_room("bath2", "次卫", RoomCategory.WET, 3.5, "F1"))
    return _program(
        width=width,
        depth=depth,
        rooms=rooms,
        floor_labels={"F1": "一层"},
    )


def _two_floor_base(
    width: float,
    depth: float,
    *,
    with_garage: bool,
) -> DesignProgram:
    rooms = [
        _room("living", "客厅", RoomCategory.PUBLIC, 24, "F1"),
        _room("kitchen", "餐厅+厨房", RoomCategory.WET, 16, "F1", tags=["kitchen"]),
        _room("bath1", "卫生间", RoomCategory.WET, 4, "F1"),
        _room("master", "主卧", RoomCategory.PRIVATE, 18, "F2"),
        _room("ensuite", "主卫", RoomCategory.WET, 5, "F2", tags=["ensuite", "master_bath"]),
        _room("bed2", "次卧1", RoomCategory.PRIVATE, 12, "F2"),
        _room("bed3", "次卧2", RoomCategory.PRIVATE, 12, "F2"),
        _room("bath2", "公共卫生间", RoomCategory.WET, 4, "F2"),
        _room("study", "书房", RoomCategory.OTHER, 9, "F2"),
    ]
    if with_garage:
        rooms.insert(
            3,
            _room("garage", "车库", RoomCategory.OTHER, 18, "F1", tags=["garage"]),
        )
    return _program(
        width=width,
        depth=depth,
        rooms=rooms,
        floor_labels={"F1": "一层", "F2": "二层"},
    )


def _three_floor() -> DesignProgram:
    rooms = [
        _room("garage", "车库", RoomCategory.OTHER, 20, "F1", tags=["garage"]),
        _room("entry", "门厅", RoomCategory.PUBLIC, 8, "F1"),
        _room("bath0", "卫生间", RoomCategory.WET, 3.5, "F1"),
        _room("living", "客厅", RoomCategory.PUBLIC, 26, "F2"),
        _room("kitchen", "厨房", RoomCategory.WET, 14, "F2", tags=["kitchen"]),
        _room("dining", "餐厅", RoomCategory.PUBLIC, 12, "F2"),
        _room("bath1", "卫生间", RoomCategory.WET, 4, "F2"),
        _room("master", "主卧", RoomCategory.PRIVATE, 18, "F3"),
        _room("ensuite", "主卫", RoomCategory.WET, 5, "F3", tags=["ensuite", "master_bath"]),
        _room("bed2", "次卧1", RoomCategory.PRIVATE, 12, "F3"),
        _room("bed3", "次卧2", RoomCategory.PRIVATE, 11, "F3"),
        _room("bath2", "公共卫生间", RoomCategory.WET, 4, "F3"),
    ]
    return _program(
        width=11,
        depth=13,
        rooms=rooms,
        floor_labels={"F1": "一层", "F2": "二层", "F3": "三层"},
    )


def _high_privacy() -> DesignProgram:
    program = _two_floor_base(11, 13, with_garage=False)
    extras = [
        SeparationConstraint(
            id="sep-living-master",
            kind=ConstraintKind.SEPARATION,
            room_a_id="living",
            room_b_id="master",
            min_distance=4.0,
            hard=False,
            weight=1.2,
            source=ConstraintSource.USER,
            description="公区与主卧拉开",
        ),
        SeparationConstraint(
            id="sep-kitchen-bed2",
            kind=ConstraintKind.SEPARATION,
            room_a_id="kitchen",
            room_b_id="bed2",
            min_distance=3.0,
            hard=False,
            weight=1.0,
            source=ConstraintSource.USER,
        ),
        OrientationConstraint(
            id="orient-master-south",
            kind=ConstraintKind.ORIENTATION,
            room_id="master",
            preferred_orientation="south",
            hard=False,
            weight=1.0,
            source=ConstraintSource.USER,
        ),
    ]
    program.constraints = list(program.constraints) + extras
    return program


def _open_living_dining() -> DesignProgram:
    rooms = [
        _room("living", "客厅", RoomCategory.PUBLIC, 28, "F1", tags=["open_plan"]),
        _room("dining", "餐厅", RoomCategory.PUBLIC, 14, "F1", tags=["open_plan"]),
        _room("kitchen", "厨房", RoomCategory.WET, 12, "F1", tags=["kitchen"]),
        _room("bath1", "卫生间", RoomCategory.WET, 4, "F1"),
        _room("bed1", "主卧", RoomCategory.PRIVATE, 16, "F1"),
        _room("bed2", "次卧", RoomCategory.PRIVATE, 12, "F1"),
        _room("bath2", "次卫", RoomCategory.WET, 3.5, "F1"),
    ]
    program = _program(
        width=12,
        depth=14,
        rooms=rooms,
        floor_labels={"F1": "一层"},
    )
    program.constraints = list(program.constraints) + [
        AdjacencyConstraint(
            id="adj-living-dining",
            kind=ConstraintKind.ADJACENCY,
            room_a_id="living",
            room_b_id="dining",
            share_wall=True,
            hard=False,
            weight=1.2,
            source=ConstraintSource.USER,
            description="开敞起居餐厨",
        ),
        AdjacencyConstraint(
            id="adj-dining-kitchen",
            kind=ConstraintKind.ADJACENCY,
            room_a_id="dining",
            room_b_id="kitchen",
            share_wall=True,
            hard=False,
            weight=1.2,
            source=ConstraintSource.USER,
        ),
    ]
    return program


def _multi_wet() -> DesignProgram:
    rooms = [
        _room("living", "客厅", RoomCategory.PUBLIC, 22, "F1"),
        _room("kitchen", "厨房", RoomCategory.WET, 12, "F1", tags=["kitchen"]),
        _room("bath1", "客卫", RoomCategory.WET, 4, "F1"),
        _room("laundry", "洗衣间", RoomCategory.WET, 5, "F1", tags=["laundry"]),
        _room("master", "主卧", RoomCategory.PRIVATE, 16, "F2"),
        _room("ensuite", "主卫", RoomCategory.WET, 5, "F2", tags=["ensuite", "master_bath"]),
        _room("bed2", "次卧1", RoomCategory.PRIVATE, 12, "F2"),
        _room("bath2", "次卫", RoomCategory.WET, 4, "F2"),
        _room("bath3", "公卫", RoomCategory.WET, 4, "F2"),
        _room("powder", "化妆间", RoomCategory.WET, 3, "F2"),
    ]
    return _program(
        width=12,
        depth=14,
        rooms=rooms,
        floor_labels={"F1": "一层", "F2": "二层"},
    )


def _locks_from_seed_program(
    program: DesignProgram,
    *,
    room_ids: list[str] | None = None,
    zone_kinds: list[ArchitecturalZone] | None = None,
) -> LayoutLocks:
    """用 Guillotine seed=0 冻结几何，确保 locks 对程序可满足。"""
    base = GuillotineGenerator().generate(program, seed=0)
    rooms: list[LockedRoomRect] = []
    for rid in room_ids or []:
        for fl in base.floors:
            for p in fl.placements:
                if p.room_id == rid:
                    rooms.append(
                        LockedRoomRect(
                            room_id=p.room_id,
                            floor_id=p.floor_id,
                            x=p.rect.x,
                            y=p.rect.y,
                            width=p.rect.width,
                            depth=p.rect.depth,
                        )
                    )
    zones: list[LockedZoneRect] = []
    wanted = set(zone_kinds or [])
    for z in base.zone_placements:
        if z.zone in wanted:
            zones.append(
                LockedZoneRect(
                    zone=z.zone,
                    floor_id=z.floor_id,
                    x=z.rect.x,
                    y=z.rect.y,
                    width=z.rect.width,
                    depth=z.rect.depth,
                    room_ids=list(z.room_ids),
                    zone_id=z.id,
                )
            )
    return LayoutLocks(rooms=rooms, zones=zones)


_CASE_BUILDERS: dict[str, tuple[LayoutSuiteCaseMeta, Callable[[], LayoutSuiteCase]]] = {}


def _register(
    meta: LayoutSuiteCaseMeta,
    builder: Callable[[], LayoutSuiteCase],
) -> None:
    _CASE_BUILDERS[meta.id] = (meta, builder)


def _reg_simple(meta: LayoutSuiteCaseMeta, program_fn: Callable[[], DesignProgram]) -> None:
    def _build() -> LayoutSuiteCase:
        return LayoutSuiteCase(meta=meta, program=program_fn(), locks=None)

    _register(meta, _build)


_reg_simple(
    LayoutSuiteCaseMeta("B01", "8×10 单层紧凑", "小基地单层 1–2 卧"),
    lambda: _compact_single(8, 10, bedrooms=2),
)
_reg_simple(
    LayoutSuiteCaseMeta("B02", "10×12 单层 3卧", "单层三卧两卫"),
    lambda: _compact_single(10, 12, bedrooms=3),
)
_reg_simple(
    LayoutSuiteCaseMeta("B03", "11×13 两层", "标准两层（原单 case 基线）"),
    lambda: _two_floor_base(11, 13, with_garage=False),
)
_reg_simple(
    LayoutSuiteCaseMeta("B04", "12×16 两层+车库", "底层含车库"),
    lambda: _two_floor_base(12, 16, with_garage=True),
)
_reg_simple(
    LayoutSuiteCaseMeta("B05", "9×18 窄长", "窄长基地两层"),
    lambda: _two_floor_base(9, 18, with_garage=False),
)
_reg_simple(
    LayoutSuiteCaseMeta("B06", "16×10 宽浅", "宽浅基地两层"),
    lambda: _two_floor_base(16, 10, with_garage=False),
)
_reg_simple(
    LayoutSuiteCaseMeta("B07", "三层", "车库层 + 起居 + 卧室"),
    _three_floor,
)
_reg_simple(
    LayoutSuiteCaseMeta("B08", "高 privacy", "分离/朝向软约束加压"),
    _high_privacy,
)
_reg_simple(
    LayoutSuiteCaseMeta("B09", "open living/dining", "开敞起居餐厨邻接"),
    _open_living_dining,
)
_reg_simple(
    LayoutSuiteCaseMeta("B10", "多 wet spaces", "多层多卫生间+洗衣"),
    _multi_wet,
)


def _build_b11() -> LayoutSuiteCase:
    meta = LayoutSuiteCaseMeta("B11", "room locks", "钉死客厅几何后再生")
    program = _two_floor_base(11, 13, with_garage=False)
    locks = _locks_from_seed_program(program, room_ids=["living"])
    return LayoutSuiteCase(meta=meta, program=program, locks=locks)


def _build_b12() -> LayoutSuiteCase:
    meta = LayoutSuiteCaseMeta("B12", "zone locks", "钉死 day zone envelope 后再生")
    program = _two_floor_base(11, 13, with_garage=False)
    locks = _locks_from_seed_program(program, zone_kinds=[ArchitecturalZone.DAY])
    return LayoutSuiteCase(meta=meta, program=program, locks=locks)


_register(
    LayoutSuiteCaseMeta("B11", "room locks", "钉死客厅几何后再生"),
    _build_b11,
)
_register(
    LayoutSuiteCaseMeta("B12", "zone locks", "钉死 day zone envelope 后再生"),
    _build_b12,
)


def list_suite_case_ids() -> list[str]:
    return sorted(_CASE_BUILDERS.keys())


def load_suite_case(case_id: str) -> LayoutSuiteCase:
    key = case_id.upper().strip()
    if key not in _CASE_BUILDERS:
        known = ", ".join(list_suite_case_ids())
        raise KeyError(f"unknown suite case {case_id!r}; known: {known}")
    _meta, builder = _CASE_BUILDERS[key]
    return builder()


def iter_suite_cases(
    case_ids: list[str] | None = None,
) -> list[LayoutSuiteCase]:
    ids = case_ids or list_suite_case_ids()
    return [load_suite_case(cid) for cid in ids]
