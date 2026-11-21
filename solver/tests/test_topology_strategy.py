"""TopologyStrategy 物化。"""

from __future__ import annotations

from solver.fixtures.benchmark import benchmark_program
from solver.topology.strategy import apply_topology_strategy, list_builtin_strategies


def test_list_builtin_strategies():
    strategies = list_builtin_strategies()
    assert len(strategies) == 3
    ids = {s.id for s in strategies}
    assert ids == {"family_core", "privacy", "daylight_courtyard"}


def test_apply_family_core_merges_graph():
    program = benchmark_program()
    before = len(program.room_graph.edges) if program.room_graph else 0
    out = apply_topology_strategy(program, "family_core")
    assert out.room_graph is not None
    assert len(out.room_graph.edges) >= before
    assert out.topology_plan is None
