"""Phase 8.0-B — MaxRect packing strategy。"""

from __future__ import annotations

import json

from solver.fixtures.benchmark import benchmark_program
from solver.generators import GuillotineGenerator, LayoutGenerator, MaxRectGenerator
from solver.geometry.maxrects import prune_free_list, update_free_rects
from solver.geometry.rect import Rect
from solver.pipeline import run_pipeline


def _geom_dump(cand) -> str:
    return json.dumps(
        cand.model_dump(exclude={"score", "metrics", "validation", "evaluation"}),
        sort_keys=True,
        default=str,
    )


def test_maxrect_is_layout_generator():
    gen = MaxRectGenerator()
    assert isinstance(gen, LayoutGenerator)
    assert gen.strategy_id == "maxrect"
    assert gen.generator_version == "maxrect-v1"


def test_maxrect_deterministic_same_seed():
    program = benchmark_program()
    gen = MaxRectGenerator()
    a = gen.generate(program, seed=11)
    b = gen.generate(program, seed=11)
    assert _geom_dump(a) == _geom_dump(b)


def test_maxrect_places_all_program_rooms():
    program = benchmark_program()
    cand = MaxRectGenerator().generate(program, seed=0)
    placed = {
        p.room_id
        for fl in cand.floors
        for p in fl.placements
        if not p.room_id.startswith("stair-")
    }
    expected = {r.id for r in program.rooms}
    assert expected <= placed
    assert cand.provenance is not None
    assert cand.provenance.generator_version == "maxrect-v1"


def test_maxrect_differs_from_guillotine_on_same_seed():
    program = benchmark_program()
    g = GuillotineGenerator().generate(program, seed=7)
    m = MaxRectGenerator().generate(program, seed=7)
    assert _geom_dump(g) != _geom_dump(m)


def test_pipeline_with_maxrect_generator():
    program = benchmark_program()
    program.solver_config.candidate_count = 2
    program.solver_config.return_top_k = 1
    result = run_pipeline(program, generator=MaxRectGenerator())
    assert result.generated == 2
    assert all(
        c.provenance and c.provenance.generator_version == "maxrect-v1"
        for c in result.all_candidates
    )


def test_prune_and_update_free_rects():
    outer = Rect(x=0, y=0, width=10, depth=10)
    used = Rect(x=0, y=0, width=4, depth=4)
    free = update_free_rects([outer], used)
    assert free
    assert all(r.area > 0 for r in free)
    # 内含矩形应被 prune
    nested = Rect(x=4, y=0, width=1, depth=1)
    pruned = prune_free_list(free + [nested])
    assert all(
        not (r.x == 4 and r.width == 1 and r.depth == 1) for r in pruned
    ) or nested not in pruned
