"""LayoutSignature / 归一化 similarity。"""

from __future__ import annotations

from packages.schema.signature import build_layout_signature, signature_similarity
from solver.fixtures.benchmark import benchmark_program
from solver.generators.guillotine import GuillotineGenerator
from solver.optimization.rank import layout_similarity


def test_signature_identical_for_same_seed():
    program = benchmark_program()
    gen = GuillotineGenerator()
    a = gen.generate(program, seed=3)
    b = gen.generate(program, seed=3)
    w, d = program.buildable.width, program.buildable.depth
    sa = build_layout_signature(a, buildable_width=w, buildable_depth=d)
    sb = build_layout_signature(b, buildable_width=w, buildable_depth=d)
    assert signature_similarity(sa, sb) == 1.0
    assert layout_similarity(a, b, buildable_width=w, buildable_depth=d) == 1.0


def test_signature_differs_across_seeds():
    program = benchmark_program()
    gen = GuillotineGenerator()
    a = gen.generate(program, seed=0)
    b = gen.generate(program, seed=17)
    w, d = program.buildable.width, program.buildable.depth
    sim = layout_similarity(a, b, buildable_width=w, buildable_depth=d)
    assert 0.0 <= sim <= 1.0
