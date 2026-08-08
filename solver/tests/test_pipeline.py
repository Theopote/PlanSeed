"""Pipeline、排序与 RequirementSpec 集成测试。"""

from __future__ import annotations

from packages.schema.requirements import RequirementSpec, SiteRequirements
from solver.optimization.rank import layout_similarity
from solver.pipeline import run_pipeline
from solver.program.requirements_normalize import normalize_requirements_to_program
from solver.tests.test_guillotine import benchmark_program


class TestPipeline:
    def test_runs_32_candidates(self):
        program = benchmark_program()
        result = run_pipeline(program)
        assert result.generated == 32
        assert len(result.top_candidates) <= 5

    def test_valid_candidates_scored(self):
        program = benchmark_program()
        result = run_pipeline(program)
        for c in result.top_candidates:
            if c.validation and c.validation.valid:
                assert c.score is not None
                assert c.score > 0
                assert c.evaluation is not None
                assert c.evaluation.total_score == c.score
                assert c.evaluation.program_score >= 0

    def test_at_least_one_valid_candidate(self):
        # 弱断言保留作 smoke；正式质量门槛见 test_quality_regression.py
        program = benchmark_program()
        result = run_pipeline(program)
        assert result.valid >= 1

    def test_multiple_distinct_layouts(self):
        # 弱断言保留作 smoke；正式质量门槛见 test_quality_regression.py
        program = benchmark_program()
        result = run_pipeline(program)
        jsons = {c.model_dump_json() for c in result.all_candidates}
        assert len(jsons) > 1

    def test_requirement_spec_normalize(self):
        from solver.fixtures.benchmark import benchmark_requirement_spec

        program = normalize_requirements_to_program(benchmark_requirement_spec())
        assert program.buildable.width == 11
        assert len(program.floors) == 2
        assert len(program.rooms) == 10


class TestRanking:
    def test_layout_similarity_identical(self):
        program = benchmark_program()
        from solver.generators.guillotine import GuillotineGenerator

        gen = GuillotineGenerator()
        a = gen.generate(program, seed=5)
        b = gen.generate(program, seed=5)
        assert layout_similarity(a, b) == 1.0

    def test_layout_similarity_different_seeds(self):
        program = benchmark_program()
        from solver.generators.guillotine import GuillotineGenerator

        gen = GuillotineGenerator()
        a = gen.generate(program, seed=0)
        b = gen.generate(program, seed=17)
        sim = layout_similarity(a, b)
        assert 0.0 <= sim <= 1.0

    def test_diversity_avoids_identical_top(self):
        program = benchmark_program()
        result = run_pipeline(program)
        top = result.top_candidates
        assert len(top) >= 2
        # Top 方案两两不应完全相同
        jsons = [c.model_dump_json() for c in top]
        assert len(set(jsons)) == len(jsons)

    def test_diversity_can_be_disabled(self):
        from solver.optimization.rank import rank_candidates
        from packages.schema.layout import CandidateValidation, LayoutCandidate

        def make(seed: int, score: float) -> LayoutCandidate:
            return LayoutCandidate(
                id=f"c-{seed}",
                seed=seed,
                floors=[],
                validation=CandidateValidation(valid=True),
                score=score,
            )

        ranked = rank_candidates(
            [make(1, 90), make(2, 89), make(3, 88)],
            top_k=2,
            min_diversity_threshold=None,
        )
        assert [c.seed for c in ranked] == [1, 2]
