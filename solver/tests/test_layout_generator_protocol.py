"""Phase 8.0-A — LayoutGenerator Protocol + pipeline 注入。"""

from __future__ import annotations

from packages.schema.layout import LayoutCandidate
from packages.schema.locks import LayoutLocks
from packages.schema.program import DesignProgram
from packages.schema.topology import TopologyPlan
from solver.fixtures.benchmark import benchmark_program
from solver.generators import GuillotineGenerator, LayoutGenerator
from solver.generators.base import CandidateGenerator
from solver.pipeline import run_pipeline


def test_guillotine_is_layout_generator():
    gen = GuillotineGenerator()
    assert isinstance(gen, LayoutGenerator)
    assert gen.strategy_id == "guillotine"
    assert CandidateGenerator is LayoutGenerator


def test_generate_accepts_optional_topology():
    program = benchmark_program()
    gen = GuillotineGenerator()
    # 缺省与显式 None 等价路径
    a = gen.generate(program, seed=3)
    b = gen.generate(program, seed=3, topology=None)
    assert a.model_dump(exclude={"score", "metrics", "validation", "evaluation"}) == b.model_dump(
        exclude={"score", "metrics", "validation", "evaluation"}
    )


def test_generate_with_injected_topology_deterministic():
    program = benchmark_program()
    gen = GuillotineGenerator()
    topology = gen._topology_planner.plan(program)
    assert isinstance(topology, TopologyPlan)
    a = gen.generate(program, seed=5, topology=topology)
    b = gen.generate(program, seed=5, topology=topology)
    assert a.model_dump(exclude={"score", "metrics", "validation", "evaluation"}) == b.model_dump(
        exclude={"score", "metrics", "validation", "evaluation"}
    )


def test_pipeline_default_still_guillotine():
    program = benchmark_program()
    program.solver_config.candidate_count = 2
    program.solver_config.return_top_k = 1
    result = run_pipeline(program)
    assert result.generated == 2


def test_pipeline_accepts_injected_generator():
    program = benchmark_program()
    program.solver_config.candidate_count = 1
    program.solver_config.return_top_k = 1

    class _RecordingGen:
        strategy_id = "recording"

        def __init__(self) -> None:
            self.calls = 0
            self._inner = GuillotineGenerator()

        def generate(
            self,
            program: DesignProgram,
            seed: int,
            locks: LayoutLocks | None = None,
            topology: TopologyPlan | None = None,
        ) -> LayoutCandidate:
            self.calls += 1
            return self._inner.generate(program, seed, locks=locks, topology=topology)

    gen = _RecordingGen()
    assert isinstance(gen, LayoutGenerator)
    result = run_pipeline(program, generator=gen)
    assert gen.calls == 1
    assert result.generated == 1
