"""Solver / evaluation 身份签名。"""

from __future__ import annotations

from backend.main import create_app
from fastapi.testclient import TestClient
from packages.schema.identity import (
    EVALUATION_VERSION,
    GENERATOR_VERSION,
    SOLVER_VERSION,
    solver_identity,
)
from solver.fixtures.benchmark import benchmark_program
from solver.generators.guillotine import GuillotineGenerator
from solver.pipeline import run_pipeline


def test_solver_identity_keys():
    ident = solver_identity()
    assert ident == {
        "solver_version": SOLVER_VERSION,
        "generator_version": GENERATOR_VERSION,
        "evaluation_version": EVALUATION_VERSION,
    }
    assert SOLVER_VERSION == "0.4"
    assert GENERATOR_VERSION == "guillotine-lock-v4"
    assert EVALUATION_VERSION == "residential-alpha-v1"


def test_generator_stamps_version():
    program = benchmark_program()
    cand = GuillotineGenerator().generate(program, seed=0)
    assert cand.metrics.get("generator_version") == GENERATOR_VERSION
    assert cand.provenance is not None
    assert cand.provenance.generator_version == GENERATOR_VERSION
    assert cand.provenance.solver_version == SOLVER_VERSION


def test_pipeline_evaluation_version():
    program = benchmark_program()
    program.solver_config.candidate_count = 4
    program.solver_config.return_top_k = 2
    result = run_pipeline(program)
    scored = [c for c in result.all_candidates if c.evaluation is not None]
    assert scored
    for c in scored:
        assert c.evaluation is not None
        assert c.evaluation.evaluation_version == EVALUATION_VERSION
        assert c.metrics.get("evaluation_version") == EVALUATION_VERSION
        assert c.metrics.get("solver_version") == SOLVER_VERSION
        assert c.metrics.get("generator_version") == GENERATOR_VERSION
        assert c.provenance is not None
        assert c.provenance.evaluation_version == EVALUATION_VERSION
        assert c.provenance.solver_version == SOLVER_VERSION


def test_health_and_generate_expose_identity():
    client = TestClient(create_app())
    h = client.get("/api/health").json()
    assert h["solver_version"] == SOLVER_VERSION
    assert h["generator_version"] == GENERATOR_VERSION
    assert h["evaluation_version"] == EVALUATION_VERSION
    # Engine Identity Probe 字段仍在
    assert h["service"] == "planseed"
    assert h["api_version"] == "1"
    assert h["engine_version"]

    g = client.post(
        "/api/generate",
        json={"use_benchmark": True, "candidate_count": 4, "return_top_k": 2},
    )
    assert g.status_code == 200
    body = g.json()
    assert body["solver_identity"] == solver_identity()
    top = body["candidates"][0]
    assert top["design_score"]["evaluation_version"] == EVALUATION_VERSION
    prov = top["provenance"]
    assert prov["solver_version"] == SOLVER_VERSION
    assert prov["generator_version"] == GENERATOR_VERSION
    assert prov["evaluation_version"] == EVALUATION_VERSION
    assert isinstance(top["placements"], list)
    assert len(top["placements"]) > 0
    pl = top["placements"][0]
    assert {"room_id", "floor_id", "x", "y", "width", "depth", "area"} <= set(pl)
