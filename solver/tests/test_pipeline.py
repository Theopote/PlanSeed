"""Pipeline、排序与 RequirementSpec 集成测试。"""

from __future__ import annotations

from packages.schema.requirements import RequirementSpec, SiteRequirements
from solver.optimization.rank import layout_similarity
from solver.pipeline import run_pipeline
from solver.program.requirements_normalize import normalize_requirements
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

    def test_at_least_one_valid_candidate(self):
        program = benchmark_program()
        result = run_pipeline(program)
        assert result.valid >= 1

    def test_multiple_distinct_layouts(self):
        program = benchmark_program()
        result = run_pipeline(program)
        jsons = {c.model_dump_json() for c in result.all_candidates}
        assert len(jsons) > 1

    def test_requirement_spec_normalize(self):
        req = RequirementSpec(site=SiteRequirements(width=11, depth=13), floor_count=2)
        program = normalize_requirements(req)
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
