"""Phase 8.3 — CP-SAT floor assignment research tests。"""

from __future__ import annotations

import pytest

ortools = pytest.importorskip("ortools")

from packages.schema.constraints import AdjacencyConstraint, FloorConstraint
from packages.schema.floor_assignment import FloorAssignmentSource
from packages.schema.room import FloorSpec, RoomCategory, RoomSpec
from solver.assignment.cpsat_floor import (
    assign_floors_cpsat,
)


def _floors() -> list[FloorSpec]:
    return [
        FloorSpec(id="F1", label="1层", room_ids=[]),
        FloorSpec(id="F2", label="2层", room_ids=[]),
    ]


def test_cpsat_respects_hard_floor_constraint():
    rooms = [
        RoomSpec(id="living", name="客厅", category=RoomCategory.PUBLIC, target_area=24),
        RoomSpec(id="bed", name="主卧", category=RoomCategory.PRIVATE, target_area=18, tags=["master"]),
    ]
    floors = _floors()
    constraints = [
        FloorConstraint(id="fc1", room_id="living", floor_id="F1"),
        FloorConstraint(id="fc2", room_id="bed", floor_id="F2"),
    ]
    assignment = assign_floors_cpsat(rooms, floors, constraints)
    assert assignment.floor_id_for("living") == "F1"
    assert assignment.floor_id_for("bed") == "F2"


def test_cpsat_prefers_adjacency_same_floor():
    rooms = [
        RoomSpec(id="kitchen", name="厨房", category=RoomCategory.WET, target_area=10, tags=["kitchen"]),
        RoomSpec(id="dining", name="餐厅", category=RoomCategory.PUBLIC, target_area=12, tags=["dining"]),
        RoomSpec(id="bed", name="次卧", category=RoomCategory.PRIVATE, target_area=12),
    ]
    floors = _floors()
    constraints = [
        AdjacencyConstraint(id="adj1", room_a_id="kitchen", room_b_id="dining"),
    ]
    assignment = assign_floors_cpsat(rooms, floors, constraints)
    assert assignment.floor_id_for("kitchen") == assignment.floor_id_for("dining")


def test_cpsat_assigns_all_rooms():
    rooms = [
        RoomSpec(id="r1", name="客厅", category=RoomCategory.PUBLIC, target_area=24),
        RoomSpec(id="r2", name="主卧", category=RoomCategory.PRIVATE, target_area=18, tags=["master"]),
        RoomSpec(
            id="r3",
            name="车库",
            category=RoomCategory.OTHER,
            target_area=15,
            tags=["garage"],
        ),
    ]
    assignment = assign_floors_cpsat(rooms, _floors(), [])
    assert {d.room_id for d in assignment.decisions} == {"r1", "r2", "r3"}
    # 未硬固定的由 CPSAT 源标记
    soft = [d for d in assignment.decisions if d.source == FloorAssignmentSource.CPSAT]
    assert soft


def test_cpsat_apply_writes_floor_ids():
    rooms = [
        RoomSpec(id="a", name="客厅", category=RoomCategory.PUBLIC, target_area=20),
        RoomSpec(id="b", name="卧室", category=RoomCategory.PRIVATE, target_area=12),
    ]
    floors = _floors()
    assignment = assign_floors_cpsat(rooms, floors, [])
    assignment.apply(rooms, floors)
    assert all(r.floor_id for r in rooms)
    assert set(floors[0].room_ids) | set(floors[1].room_ids) == {"a", "b"}


def test_cpsat_empty_rooms():
    assert assign_floors_cpsat([], _floors(), []).decisions == []
