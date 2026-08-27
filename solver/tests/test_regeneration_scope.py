"""RegenerationScope — 局部重生成作用域。"""

from __future__ import annotations

from packages.schema.regeneration import RegenerationScope
from solver.fixtures.benchmark import benchmark_program
from solver.generators.guillotine import GuillotineGenerator
from solver.regeneration.scope import (
    derive_affected_neighbors,
    enrich_regeneration_scope,
    locks_from_regeneration_scope,
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
