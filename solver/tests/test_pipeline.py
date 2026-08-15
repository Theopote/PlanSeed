"""Pipeline、排序与 RequirementSpec 集成测试。"""

from __future__ import annotations

from solver.optimization.rank import layout_similarity
from solver.pipeline import run_pipeline
from solver.program.requirements_normalize import normalize_requirements_to_program
from solver.tests.test_guillotine import benchmark_program


class TestPipeline:
    def test_runs_default_candidate_count(self):
        program = benchmark_program()
        result = run_pipeline(program)
        assert result.generated == program.solver_config.candidate_count
        assert result.generated == 64
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

    def test_evaluation_deterministic_same_seed(self):
        """同 program + seed → 同几何（生成器确定性）。"""
        from solver.generators.guillotine import GuillotineGenerator

        program = benchmark_program()
        gen = GuillotineGenerator()
        a = gen.generate(program, seed=7)
        b = gen.generate(program, seed=7)
        assert a.model_dump_json() == b.model_dump_json()

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

    def test_nonzero_buildable_origin_still_valid(self):
        """Placements are envelope-local; site-space origin must not fail every candidate."""
        program = benchmark_program()
        program.buildable = program.buildable.model_copy(update={"x": 2.0, "y": 1.5})
        program.solver_config.candidate_count = 8
        program.solver_config.return_top_k = 3
        result = run_pipeline(program)
        assert result.valid >= 1
        assert result.top_candidates
        assert all(
            c.validation is not None and c.validation.valid for c in result.top_candidates
        )
        w, d = program.buildable.width, program.buildable.depth
        for c in result.top_candidates:
            for fl in c.floors:
                for p in fl.placements:
                    assert p.rect.x >= -1e-6
                    assert p.rect.y >= -1e-6
                    assert p.rect.right <= w + 1e-6
                    assert p.rect.bottom <= d + 1e-6

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
        from packages.schema.layout import CandidateValidation, LayoutCandidate
        from solver.optimization.rank import rank_candidates

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

    def test_rank_does_not_pad_with_invalid(self):
        from packages.schema.layout import CandidateValidation, LayoutCandidate
        from solver.optimization.rank import rank_candidates

        ok = LayoutCandidate(
            id="ok",
            seed=1,
            floors=[],
            validation=CandidateValidation(valid=True),
            score=80,
        )
        bad = LayoutCandidate(
            id="bad",
            seed=2,
            floors=[],
            validation=CandidateValidation(valid=False),
            score=None,
        )
        ranked = rank_candidates(
            [ok, bad],
            top_k=5,
            min_diversity_threshold=None,
        )
        assert [c.id for c in ranked] == ["ok"]
