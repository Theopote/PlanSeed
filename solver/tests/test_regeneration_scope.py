"""RegenerationScope — 局部重生成作用域。"""

from __future__ import annotations

import pytest
from packages.schema.locks import LayoutLocks, LockedRoomRect, LockedZoneRect
from packages.schema.regeneration import RegenerationScope
from packages.schema.zoning import ArchitecturalZone
from solver.fixtures.benchmark import benchmark_program
from solver.generators.guillotine import GuillotineGenerator
from solver.regeneration.errors import RegenerationScopeError
from solver.regeneration.scope import (
    derive_affected_neighbors,
    enrich_regeneration_scope,
    locks_from_placement_rects,
    locks_from_regeneration_scope,
    merge_layout_locks,
    resolve_locked_room_ids,
)

# benchmark_program 房间 id 为 r1..r10（r1=客厅）


def test_derive_neighbors_from_graph():
    program = benchmark_program()
    scope = RegenerationScope(mutable_rooms=["r1"])
    neighbors_list = derive_affected_neighbors(program, scope.mutable_rooms)
    # 邻接取决于 normalize 后 RoomGraph；允许为空但 r1 应在 program 中
    assert "r1" not in neighbors_list


def test_enrich_fills_neighbors_field():
    program = benchmark_program()
    scope = RegenerationScope(
        mutable_rooms=["r1"],
        affected_neighbors=["r2"],
    )
    enriched = enrich_regeneration_scope(scope, program)
    assert enriched.affected_neighbors == ["r2"]


def test_resolve_locked_defaults_to_complement():
    program = benchmark_program()
    scope = RegenerationScope(mutable_rooms=["r1"])
    locked = resolve_locked_room_ids(scope, program)
    assert "r1" not in locked
    assert "r2" in locked


def test_scope_to_locks_preserves_locked_geometry():
    program = benchmark_program()
    base = GuillotineGenerator().generate(program, seed=0)
    scope = RegenerationScope(mutable_rooms=["r1"])
    locks = locks_from_regeneration_scope(scope, program, base)
    assert locks.rooms
    locked_ids = {r.room_id for r in locks.rooms}
    assert "r1" not in locked_ids
    kitchen_lock = next(r for r in locks.rooms if r.room_id == "r2")
    base_kitchen = _rect_for(base, "r2")
    assert kitchen_lock.x == base_kitchen[0]
    assert kitchen_lock.width == base_kitchen[2]


def test_mutable_room_excluded_from_locks():
    program = benchmark_program()
    base = GuillotineGenerator().generate(program, seed=0)
    scope = RegenerationScope(mutable_rooms=["r1"])
    locks = locks_from_regeneration_scope(scope, program, base)
    locked_ids = {r.room_id for r in locks.rooms}
    assert "r1" not in locked_ids
    assert len(locked_ids) == len(program.rooms) - 1


def test_locked_room_unchanged_under_partial_regen():
    program = benchmark_program()
    base = GuillotineGenerator().generate(program, seed=0)
    scope = RegenerationScope(mutable_rooms=["r1"])
    locks = locks_from_regeneration_scope(scope, program, base)
    regen = GuillotineGenerator().generate(program, seed=1, locks=locks)
    for rid in ("r2", "r5"):
        assert _rect_for(base, rid) == _rect_for(regen, rid)


def test_partial_regen_pipeline_produces_valid_candidates():
    program = benchmark_program()
    program.solver_config.candidate_count = 8
    program.solver_config.return_top_k = 3
    base = GuillotineGenerator().generate(program, seed=0)
    scope = RegenerationScope(mutable_rooms=["r1"])
    locks = locks_from_regeneration_scope(scope, program, base)
    from solver.pipeline import run_pipeline

    result = run_pipeline(program, locks=locks)
    assert result.valid >= 1
    assert result.valid == result.generated


def _rect_for(cand, room_id: str) -> tuple[float, float, float, float]:
    for fl in cand.floors:
        for p in fl.placements:
            if p.room_id == room_id:
                r = p.rect
                return (r.x, r.y, r.width, r.depth)
    raise AssertionError(room_id)


def test_unknown_mutable_raises_scope_error():
    program = benchmark_program()
    with pytest.raises(RegenerationScopeError) as ei:
        resolve_locked_room_ids(RegenerationScope(mutable_rooms=["nope"]), program)
    assert ei.value.code == "unknown_mutable_rooms"


def test_missing_base_placement_raises_scope_error():
    program = benchmark_program()
    scope = RegenerationScope(mutable_rooms=["r1"])
    with pytest.raises(RegenerationScopeError) as ei:
        locks_from_placement_rects(
            scope,
            program,
            [LockedRoomRect(room_id="r2", floor_id="F1", x=0, y=0, width=1, depth=1)],
        )
    assert ei.value.code == "missing_base_placement"


def test_merge_preserves_zone_and_stair_locks():
    program = benchmark_program()
    base = GuillotineGenerator().generate(program, seed=0)
    scope = RegenerationScope(mutable_rooms=["r1"])
    scope_locks = locks_from_regeneration_scope(scope, program, base)
    assert scope_locks.stair is not None
    existing = LayoutLocks(
        rooms=[],
        stair=scope_locks.stair.model_copy(update={"core_placement": "south"}),
        zones=[
            LockedZoneRect(
                zone=ArchitecturalZone.DAY,
                floor_id="F1",
                x=0,
                y=0,
                width=5,
                depth=5,
                room_ids=["r1"],
            )
        ],
    )
    merged = merge_layout_locks(
        existing, scope_locks, mutable_room_ids=scope.mutable_room_ids
    )
    assert merged.stair is not None
    assert merged.stair.core_placement == "south"
    assert len(merged.zones) == 1
    assert "r1" not in {r.room_id for r in merged.rooms}


def test_merge_rejects_conflicting_room_lock():
    scope_locks = LayoutLocks(
        rooms=[
            LockedRoomRect(room_id="r2", floor_id="F1", x=0, y=0, width=3, depth=3)
        ]
    )
    existing = LayoutLocks(
        rooms=[
            LockedRoomRect(room_id="r2", floor_id="F1", x=1, y=1, width=3, depth=3)
        ]
    )
    with pytest.raises(RegenerationScopeError) as ei:
        merge_layout_locks(existing, scope_locks, mutable_room_ids={"r1"})
    assert ei.value.code == "lock_geometry_conflict"
