"""私密空间直接门连接硬约束回归。"""

from __future__ import annotations

from packages.schema.layout import (
    DoorOpening,
    FloorLayout,
    LayoutCandidate,
    PlacementRect,
    PlacementSource,
    RoomPlacement,
)
from packages.schema.program import DesignProgram, SolverConfig
from packages.schema.room import FloorSpec, RoomCategory, RoomSpec
from packages.schema.site import SiteSpec
from solver.constraints.checker_impl import DefaultConstraintChecker
from solver.fixtures.benchmark import benchmark_program
from solver.pipeline import run_pipeline
from solver.topology.doors import place_door_openings


def _placement(
    room_id: str,
    *,
    x: float,
    y: float,
    w: float,
    d: float,
    cat: str,
    name: str | None = None,
) -> RoomPlacement:
    return RoomPlacement(
        room_id=room_id,
        floor_id="F1",
        rect=PlacementRect(x=x, y=y, width=w, depth=d),
        source=PlacementSource.PROGRAM,
        name=name or room_id,
        category=cat,
    )


def _categories_by_id(candidate: LayoutCandidate) -> dict[str, str]:
    out: dict[str, str] = {}
    for fl in candidate.floors:
        for p in fl.placements:
            if p.category:
                out[p.room_id] = p.category.lower()
    return out


def _unacceptable_private_private_door_pairs(
    openings: list[DoorOpening],
    categories: dict[str, str],
) -> list[tuple[str, str]]:
    """非被迫妥协的私密-私密直连（应被算法绕开）。"""
    bad: list[tuple[str, str]] = []
    for op in openings:
        if op.forced_private_adjacency:
            continue
        ca = categories.get(op.room_a_id, "")
        cb = categories.get(op.room_b_id, "")
        if ca == "private" and cb == "private":
            bad.append((op.room_a_id, op.room_b_id))
    return bad


def _private_private_door_pairs(
    openings: list[DoorOpening],
    categories: dict[str, str],
) -> list[tuple[str, str]]:
    bad: list[tuple[str, str]] = []
    for op in openings:
        ca = categories.get(op.room_a_id, "")
        cb = categories.get(op.room_b_id, "")
        if ca == "private" and cb == "private":
            bad.append((op.room_a_id, op.room_b_id))
    return bad


def _wet_private_fanout(
    openings: list[DoorOpening],
    categories: dict[str, str],
) -> dict[str, set[str]]:
    wet_private: dict[str, set[str]] = {}
    for op in openings:
        ca = categories.get(op.room_a_id, "")
        cb = categories.get(op.room_b_id, "")
        if ca == "wet" and cb == "private":
            wet_private.setdefault(op.room_a_id, set()).add(op.room_b_id)
        elif cb == "wet" and ca == "private":
            wet_private.setdefault(op.room_b_id, set()).add(op.room_a_id)
    return wet_private


class TestPrivatePrivateDoorBlocking:
    def test_seed44_top_candidate_has_no_private_private_or_wet_fanout(self) -> None:
        program = benchmark_program()
        program.solver_config.candidate_count = 64
        result = run_pipeline(program)
        top = result.top_candidates[0]
        assert top.validation is not None and top.validation.valid

        openings = top.door_openings or place_door_openings(program, top)
        categories = _categories_by_id(top)

        private_pairs = _unacceptable_private_private_door_pairs(openings, categories)
        assert private_pairs == [], f"unacceptable private-private doors: {private_pairs}"

        fanout = _wet_private_fanout(openings, categories)
        over = {wid: privs for wid, privs in fanout.items() if len(privs) > 1}
        assert over == {}, f"wet-private fanout: {over}"

        pair_keys = {
            frozenset({op.room_a_id, op.room_b_id}) for op in openings
        }
        assert frozenset({"r5", "r8"}) not in pair_keys
        assert not (
            "r6" in fanout and len(fanout["r6"]) > 1
        ), f"r6 should not serve multiple bedrooms: {fanout.get('r6')}"

    def test_spanning_tree_routes_via_circulation_not_private_private(self) -> None:
        """两卧室共墙，仅走廊可同时贴边；不得开卧室-卧室门。"""
        program = DesignProgram(
            project_id="privacy-route",
            site=SiteSpec(width=6, depth=6),
            buildable=SiteSpec(width=6, depth=6).buildable_envelope,
            floors=[FloorSpec(id="F1", label="一层", room_ids=["hall", "bed_a", "bed_b"])],
            rooms=[
                RoomSpec(
                    id="hall",
                    name="走廊",
                    category=RoomCategory.CIRCULATION,
                    target_area=12,
                    floor_id="F1",
                ),
                RoomSpec(
                    id="bed_a",
                    name="卧室A",
                    category=RoomCategory.PRIVATE,
                    target_area=9,
                    floor_id="F1",
                ),
                RoomSpec(
                    id="bed_b",
                    name="卧室B",
                    category=RoomCategory.PRIVATE,
                    target_area=9,
                    floor_id="F1",
                ),
            ],
            constraints=[],
            solver_config=SolverConfig(),
        )
        hall = _placement("hall", x=0, y=0, w=6, d=3, cat="circulation", name="走廊")
        bed_a = _placement("bed_a", x=0, y=3, w=3, d=3, cat="private", name="卧室A")
        bed_b = _placement("bed_b", x=3, y=3, w=3, d=3, cat="private", name="卧室B")
        candidate = LayoutCandidate(
            id="route-via-hall",
            seed=0,
            floors=[FloorLayout(floor_id="F1", placements=[hall, bed_a, bed_b])],
        )

        place_door_openings(program, candidate)
        from solver.topology.access import (
            build_realized_connections,
            unreachable_occupied_rooms,
        )

        build_realized_connections(program, candidate)
        unreachable = unreachable_occupied_rooms(program, candidate)
        assert unreachable == [], f"rooms unreachable without private-private door: {unreachable}"

        openings = candidate.door_openings
        categories = _categories_by_id(candidate)
        assert _unacceptable_private_private_door_pairs(openings, categories) == []

        door_pairs = {frozenset({op.room_a_id, op.room_b_id}) for op in openings}
        assert frozenset({"bed_a", "bed_b"}) not in door_pairs
        assert frozenset({"hall", "bed_a"}) in door_pairs
        assert frozenset({"hall", "bed_b"}) in door_pairs

    def test_wet_private_fanout_rejected_when_more_than_one_bedroom(self) -> None:
        program = DesignProgram(
            project_id="wet-fanout",
            site=SiteSpec(width=10, depth=10),
            buildable=SiteSpec(width=10, depth=10).buildable_envelope,
            floors=[
                FloorSpec(
                    id="F1",
                    label="一层",
                    room_ids=["bath", "bed1", "bed2", "bed3"],
                )
            ],
            rooms=[
                RoomSpec(
                    id="bath",
                    name="卫生间",
                    category=RoomCategory.WET,
                    target_area=6,
                    floor_id="F1",
                ),
                RoomSpec(
                    id="bed1",
                    name="卧1",
                    category=RoomCategory.PRIVATE,
                    target_area=9,
                    floor_id="F1",
                ),
                RoomSpec(
                    id="bed2",
                    name="卧2",
                    category=RoomCategory.PRIVATE,
                    target_area=9,
                    floor_id="F1",
                ),
                RoomSpec(
                    id="bed3",
                    name="卧3",
                    category=RoomCategory.PRIVATE,
                    target_area=9,
                    floor_id="F1",
                ),
            ],
            constraints=[],
            solver_config=SolverConfig(),
        )
        bath = _placement("bath", x=3, y=3, w=3, d=3, cat="wet", name="卫生间")
        bed1 = _placement("bed1", x=3, y=0, w=3, d=3, cat="private", name="卧1")
        bed2 = _placement("bed2", x=6, y=3, w=3, d=3, cat="private", name="卧2")
        bed3 = _placement("bed3", x=3, y=6, w=3, d=3, cat="private", name="卧3")
        candidate = LayoutCandidate(
            id="wet-fanout",
            seed=0,
            floors=[FloorLayout(floor_id="F1", placements=[bath, bed1, bed2, bed3])],
        )

        place_door_openings(program, candidate)
        categories = _categories_by_id(candidate)
        fanout = _wet_private_fanout(candidate.door_openings, categories)
        bath_privates = fanout.get("bath", set())

        validation = DefaultConstraintChecker().check(program, candidate)
        if len(bath_privates) > 1:
            assert not validation.valid
            assert any(
                v.constraint_id == "privacy.wet_private_fanout"
                for v in validation.hard_violations
            )
        else:
            assert len(bath_privates) <= 1

    def test_benchmark_private_private_rate_in_top_candidates(self, capsys) -> None:
        """统计 Top 候选 private-private 直连比例（修复后应显著下降）。"""
        hits = 0
        total = 0
        for seed in range(101):
            program = benchmark_program()
            program.solver_config.base_seed = seed
            program.solver_config.candidate_count = 64
            program.solver_config.return_top_k = 1
            result = run_pipeline(program)
            if not result.top_candidates:
                continue
            top = result.top_candidates[0]
            total += 1
            openings = top.door_openings or place_door_openings(program, top)
            categories = _categories_by_id(top)
            if _unacceptable_private_private_door_pairs(openings, categories):
                hits += 1

        rate = hits / total if total else 0.0
        print(
            f"[privacy-direct-connection] seeds 0-100 top-1 with unacceptable "
            f"private-private door: {hits}/{total} ({rate:.1%})"
        )
        captured = capsys.readouterr()
        assert "private-private door" in captured.out
        assert hits == 0, f"expected 0 unacceptable private-private in top candidates, got {hits}"

    def test_forced_private_adjacency_when_no_alternative_path(self) -> None:
        """两卧室紧挨、仅能通过卧室-卧室边连通次卧 → 保留边并标记 forced。"""
        program = DesignProgram(
            project_id="forced-pp",
            site=SiteSpec(width=6, depth=6),
            buildable=SiteSpec(width=6, depth=6).buildable_envelope,
            floors=[
                FloorSpec(id="F1", label="一层", room_ids=["hall", "bed_a", "bed_b"])
            ],
            rooms=[
                RoomSpec(
                    id="hall",
                    name="过厅",
                    category=RoomCategory.CIRCULATION,
                    target_area=9,
                    floor_id="F1",
                ),
                RoomSpec(
                    id="bed_a",
                    name="卧室A",
                    category=RoomCategory.PRIVATE,
                    target_area=9,
                    floor_id="F1",
                ),
                RoomSpec(
                    id="bed_b",
                    name="卧室B",
                    category=RoomCategory.PRIVATE,
                    target_area=9,
                    floor_id="F1",
                ),
            ],
            constraints=[],
            solver_config=SolverConfig(),
        )
        # bed_b 仅与 bed_a 共墙，次卧无法经走廊绕行
        hall = _placement("hall", x=0, y=0, w=3, d=3, cat="circulation", name="过厅")
        bed_a = _placement("bed_a", x=0, y=3, w=3, d=3, cat="private", name="卧室A")
        bed_b = _placement("bed_b", x=3, y=3, w=3, d=3, cat="private", name="卧室B")
        candidate = LayoutCandidate(
            id="forced-pp",
            seed=0,
            floors=[FloorLayout(floor_id="F1", placements=[hall, bed_a, bed_b])],
        )

        place_door_openings(program, candidate)
        forced = [
            op
            for op in candidate.door_openings
            if frozenset({op.room_a_id, op.room_b_id}) == frozenset({"bed_a", "bed_b"})
        ]
        assert len(forced) == 1
        assert forced[0].forced_private_adjacency is True

        checker = DefaultConstraintChecker()
        soft = checker._check_forced_private_adjacency(program, candidate)
        assert any(
            v.constraint_id == "privacy.forced_private_adjacency"
            for v in soft.soft_violations
        )

        from solver.topology.access import (
            build_realized_connections,
            unreachable_occupied_rooms,
        )

        build_realized_connections(program, candidate)
        unreachable = unreachable_occupied_rooms(program, candidate)
        assert unreachable == [], f"bed_b should stay reachable via forced door: {unreachable}"
