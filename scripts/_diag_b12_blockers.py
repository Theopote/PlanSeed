"""深挖 B12 未过门槛候选的几何原因。"""

from __future__ import annotations

from solver.evaluation.architectural_gate import evaluate_architectural_gate
from solver.fixtures.design_suite_v2 import load_suite_case
from solver.pipeline import run_pipeline
from solver.semantics.roles import is_guest_bath
from solver.topology.access import (
    _is_passable_corridor_fragment,
    build_realized_access_graph,
)
from solver.topology.constants import MIN_ACCESS_WALL, MIN_CORRIDOR_SLIVER_SHORT
from solver.topology.doors import shared_boundary_between


def main() -> None:
    program = load_suite_case("B12").program
    program.solver_config.candidate_count = 16
    program.solver_config.return_top_k = 5
    program.solver_config.base_seed = 42
    result = run_pipeline(program)
    guests = [r for r in program.rooms if is_guest_bath(r)]
    print(f"guests={[g.id for g in guests]}")
    for c in result.all_candidates:
        if not (c.validation and c.validation.valid):
            continue
        gate = evaluate_architectural_gate(program, c)
        if gate.passed:
            continue
        codes = [b.code for b in gate.blockers]
        print(f"\n{c.id} seed={c.seed} blockers={codes}")
        by_id = {}
        for fl in c.floors:
            for p in fl.placements:
                by_id[p.room_id] = p
        graph = build_realized_access_graph(program, c)
        adj = {}
        for conn in graph.connections:
            adj.setdefault(conn.a, set()).add(conn.b)
            adj.setdefault(conn.b, set()).add(conn.a)
        for g in guests:
            gp = by_id.get(g.id)
            if gp is None:
                continue
            walls = []
            for rid, other in by_id.items():
                if rid == g.id or other.floor_id != gp.floor_id:
                    continue
                for thr in (MIN_CORRIDOR_SLIVER_SHORT, MIN_ACCESS_WALL):
                    b = shared_boundary_between(gp, other, min_length=thr)
                    if b is not None:
                        walls.append(f"{rid}/{other.category}@>={thr:.1f}({b.length:.2f})")
                        break
            circs = [
                p
                for p in by_id.values()
                if p.floor_id == gp.floor_id and str(p.room_id).startswith("circ-")
            ]
            circ_info = []
            for p in circs:
                short = min(p.rect.width, p.rect.depth)
                circ_info.append(
                    f"{p.room_id} short={short:.2f} passable={_is_passable_corridor_fragment(p)}"
                )
            print(f"  {g.id} graph_nb={sorted(adj.get(g.id, ()))}")
            print(f"  {g.id} walls={walls}")
            print(f"  {g.id} circs={circ_info}")


if __name__ == "__main__":
    main()
