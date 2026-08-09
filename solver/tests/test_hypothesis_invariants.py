"""Phase 7.5-G — Hypothesis 核心不变量（Rect / locks / mutation / access / checker）。

目标是捕获「不应发生」的破坏，而非穷尽覆盖率。
"""

from __future__ import annotations

import math
from itertools import permutations

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from packages.schema.layout import PlacementRect, PlacementSource, RoomPlacement
from packages.schema.lineage import locks_fingerprint
from packages.schema.locks import LayoutLocks, LockedRoomRect
from packages.schema.mutation import GeometryMutation, MutationKind
from solver.constraints.checker_impl import DefaultConstraintChecker
from solver.fixtures.benchmark import benchmark_program
from solver.generators.guillotine import GuillotineGenerator
from solver.geometry.rect import (
    Rect,
    contains,
    intersection,
    intersects,
    shared_edge_length,
)
from solver.geometry.snap import snap_value
from solver.mutation import preview_mutation
from solver.topology.access import build_realized_access_graph
from solver.topology.doors import place_door_openings

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

_finite = st.floats(
    min_value=-50.0,
    max_value=50.0,
    allow_nan=False,
    allow_infinity=False,
)
_pos = st.floats(min_value=0.05, max_value=40.0, allow_nan=False, allow_infinity=False)
_nonneg = st.floats(min_value=0.0, max_value=40.0, allow_nan=False, allow_infinity=False)


@st.composite
def rects(draw: st.DrawFn) -> Rect:
    return Rect(
        x=draw(_nonneg),
        y=draw(_nonneg),
        width=draw(_pos),
        depth=draw(_pos),
    )


# ---------------------------------------------------------------------------
# Rect
# ---------------------------------------------------------------------------


@given(rects())
@settings(max_examples=80, deadline=None)
def test_rect_area_nonnegative_and_finite(r: Rect):
    assert r.area >= 0.0
    assert math.isfinite(r.area)
    assert math.isfinite(r.aspect_ratio)
    assert r.right == pytest.approx(r.x + r.width)
    assert r.bottom == pytest.approx(r.y + r.depth)


@given(rects(), rects())
@settings(max_examples=80, deadline=None)
def test_rect_intersection_consistent_with_intersects(a: Rect, b: Rect):
    inter = intersection(a, b)
    if intersects(a, b):
        if inter is None:
            # 边界贴齐（零面积）允许
            return
        assert inter.area >= 0.0
        assert math.isfinite(inter.area)
        assert contains(a, inter) or inter.area == pytest.approx(0.0, abs=1e-9)
        assert contains(b, inter) or inter.area == pytest.approx(0.0, abs=1e-9)
    else:
        assert inter is None


@given(rects(), rects())
@settings(max_examples=60, deadline=None)
def test_shared_edge_length_symmetric_nonnegative(a: Rect, b: Rect):
    ab = shared_edge_length(a, b)
    ba = shared_edge_length(b, a)
    assert ab >= 0.0 and ba >= 0.0
    assert math.isfinite(ab) and math.isfinite(ba)
    assert ab == pytest.approx(ba, abs=1e-9)


@given(
    st.floats(min_value=-20, max_value=20, allow_nan=False, allow_infinity=False),
    st.floats(min_value=0.05, max_value=5.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=60, deadline=None)
def test_snap_value_finite_multiple(value: float, module: float):
    s = snap_value(value, module)
    assert math.isfinite(s)
    # 模数网格：s / module ≈ 整数
    assert abs(s / module - round(s / module)) < 1e-9


# ---------------------------------------------------------------------------
# Locks fingerprint
# ---------------------------------------------------------------------------


@st.composite
def locked_room_lists(draw: st.DrawFn) -> list[LockedRoomRect]:
    n = draw(st.integers(min_value=0, max_value=4))
    rooms: list[LockedRoomRect] = []
    used: set[str] = set()
    for _ in range(n):
        rid = draw(st.text(min_size=1, max_size=8, alphabet="abcdef"))
        if rid in used:
            continue
        used.add(rid)
        rooms.append(
            LockedRoomRect(
                room_id=rid,
                floor_id=draw(st.sampled_from(["F1", "F2"])),
                x=draw(_nonneg),
                y=draw(_nonneg),
                width=draw(_pos),
                depth=draw(_pos),
            )
        )
    return rooms


@given(locked_room_lists())
@settings(max_examples=50, deadline=None)
def test_locks_fingerprint_order_independent(rooms: list[LockedRoomRect]):
    fps = {
        locks_fingerprint(LayoutLocks(rooms=list(order)))
        for order in (permutations(rooms) if len(rooms) <= 4 else [rooms, list(reversed(rooms))])
    }
    assert len(fps) == 1
    fp = next(iter(fps))
    assert len(fp) == 16
    assert all(c in "0123456789abcdef" for c in fp)


@given(locked_room_lists())
@settings(max_examples=40, deadline=None)
def test_locks_fingerprint_deterministic(rooms: list[LockedRoomRect]):
    locks = LayoutLocks(rooms=rooms)
    assert locks_fingerprint(locks) == locks_fingerprint(locks)
    assert locks_fingerprint(locks.model_dump()) == locks_fingerprint(locks)


# ---------------------------------------------------------------------------
# Mutation / access / checker — 用确定性种子采样，避免过慢
# ---------------------------------------------------------------------------


_SEED = st.integers(min_value=0, max_value=64)


def _flat_placements(cand) -> list[RoomPlacement]:
    return [p for fl in cand.floors for p in fl.placements]


@given(_SEED)
@settings(
    max_examples=24,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)
def test_checker_does_not_crash_on_generated(seed: int):
    program = benchmark_program()
    program.solver_config.candidate_count = 2
    program.solver_config.return_top_k = 1
    cand = GuillotineGenerator().generate(program, seed=seed)
    validation = DefaultConstraintChecker().check(program, cand)
    assert validation is not None
    assert isinstance(validation.valid, bool)
    for v in validation.hard_violations + validation.soft_violations:
        assert isinstance(v.message, str)
        assert isinstance(v.room_ids, list)


@given(_SEED)
@settings(
    max_examples=20,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)
def test_access_graph_and_doors_do_not_crash(seed: int):
    program = benchmark_program()
    program.solver_config.candidate_count = 2
    program.solver_config.return_top_k = 1
    cand = GuillotineGenerator().generate(program, seed=seed)
    # 门洞标注不得崩溃；共边门应有有限几何
    doors = place_door_openings(program, cand)
    for d in doors:
        assert math.isfinite(d.x) and math.isfinite(d.y)
        assert d.width > 0 and math.isfinite(d.width)
    graph = build_realized_access_graph(program, cand)
    assert graph is not None
    for node in graph.node_ids:
        assert isinstance(node, str) and node
    for conn in graph.connections:
        assert conn.a and conn.b


@given(_SEED, st.floats(min_value=-2.0, max_value=8.0, allow_nan=False, allow_infinity=False))
@settings(
    max_examples=24,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
def test_preview_mutation_no_crash_and_no_nan(seed: int, dx: float):
    program = benchmark_program()
    program.solver_config.candidate_count = 2
    program.solver_config.return_top_k = 1
    cand = GuillotineGenerator().generate(program, seed=seed)
    placements = _flat_placements(cand)
    target = next(
        (p for p in placements if not p.room_id.startswith("stair-")),
        None,
    )
    if target is None:
        return
    mut = GeometryMutation(
        kind=MutationKind.MOVE,
        room_id=target.room_id,
        floor_id=target.floor_id,
        proposed=PlacementRect(
            x=max(0.0, target.rect.x + dx),
            y=target.rect.y,
            width=target.rect.width,
            depth=target.rect.depth,
        ),
    )
    result = preview_mutation(
        program=program,
        placements=placements,
        locks=LayoutLocks(),
        mutation=mut,
    )
    assert isinstance(result.ok, bool)
    if result.snapped is not None:
        assert math.isfinite(result.snapped.x)
        assert math.isfinite(result.snapped.y)
        assert result.snapped.width > 0
        assert result.snapped.depth > 0


@given(_SEED)
@settings(
    max_examples=16,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
def test_locked_room_regenerate_geometry_unchanged(seed: int):
    """锁不变量：Room Lock 后 regenerate，该房间矩形不变。"""
    program = benchmark_program()
    program.solver_config.candidate_count = 3
    program.solver_config.return_top_k = 1
    base = GuillotineGenerator().generate(program, seed=seed)
    room = next(
        (
            p
            for fl in base.floors
            for p in fl.placements
            if p.source == PlacementSource.PROGRAM
            and not p.room_id.startswith("stair-")
        ),
        None,
    )
    if room is None:
        return
    lock = LockedRoomRect(
        room_id=room.room_id,
        floor_id=room.floor_id,
        x=room.rect.x,
        y=room.rect.y,
        width=room.rect.width,
        depth=room.rect.depth,
    )
    again = GuillotineGenerator().generate(
        program,
        seed=(seed + 17) % 65,
        locks=LayoutLocks(rooms=[lock]),
    )
    locked = next(
        p
        for fl in again.floors
        for p in fl.placements
        if p.room_id == room.room_id
    )
    assert locked.rect.x == pytest.approx(lock.x)
    assert locked.rect.y == pytest.approx(lock.y)
    assert locked.rect.width == pytest.approx(lock.width)
    assert locked.rect.depth == pytest.approx(lock.depth)


@given(_SEED)
@settings(
    max_examples=16,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
def test_preview_rejects_overlap_with_locked_peer(seed: int):
    """mutation：移入其他锁定房间占位 → lock_overlap / overlap。"""
    program = benchmark_program()
    program.solver_config.candidate_count = 2
    program.solver_config.return_top_k = 1
    cand = GuillotineGenerator().generate(program, seed=seed)
    placements = [
        p
        for p in _flat_placements(cand)
        if p.source == PlacementSource.PROGRAM and not p.room_id.startswith("stair-")
    ]
    if len(placements) < 2:
        return
    a, b = placements[0], placements[1]
    if a.floor_id != b.floor_id:
        return
    locks = LayoutLocks(
        rooms=[
            LockedRoomRect(
                room_id=b.room_id,
                floor_id=b.floor_id,
                x=b.rect.x,
                y=b.rect.y,
                width=b.rect.width,
                depth=b.rect.depth,
            )
        ]
    )
    mut = GeometryMutation(
        kind=MutationKind.MOVE,
        room_id=a.room_id,
        floor_id=a.floor_id,
        proposed=PlacementRect(
            x=b.rect.x,
            y=b.rect.y,
            width=a.rect.width,
            depth=a.rect.depth,
        ),
    )
    result = preview_mutation(
        program=program,
        placements=placements,
        locks=locks,
        mutation=mut,
    )
    assert result.ok is False
    codes = {r.code for r in result.reasons}
    assert codes & {"mutation.lock_overlap", "mutation.overlap"}
