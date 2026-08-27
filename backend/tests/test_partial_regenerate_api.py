"""v0.2-B：局部重生成 API E2E — 模拟 Desktop 工作流。"""

from __future__ import annotations

from backend.main import create_app
from backend.schemas.api import PartialRegenerateRequest, RoomPlacementPayload
from backend.services.generation import resolve_partial_regenerate, resolve_solve_input
from fastapi.testclient import TestClient
from packages.schema.regeneration import RegenerationScope
import pytest


def _client() -> TestClient:
    return TestClient(create_app())


def _rect(p: dict) -> tuple[float, float, float, float]:
    return (p["x"], p["y"], p["width"], p["depth"])


def _program_placements(candidate: dict, program: dict) -> list[dict]:
    """与 desktop/src/lib/regeneration.ts programPlacementsFromCandidate 对齐。"""
    program_ids = {r["id"] for r in program["rooms"]}
    return [
        p
        for p in candidate.get("placements") or []
        if p["room_id"] in program_ids or str(p["room_id"]).startswith("stair-")
    ]


@pytest.fixture
def benchmark_session() -> dict:
    client = _client()
    gen = client.post(
        "/api/generate",
        json={"use_benchmark": True, "candidate_count": 8, "return_top_k": 3},
    )
    assert gen.status_code == 200, gen.text
    body = gen.json()
    assert body["candidates"], "benchmark 应返回候选"
    return body


def test_partial_regenerate_e2e_desktop_flow(benchmark_session: dict):
    """Generate → 选候选 → partial regen → API 契约与锁语义。"""
    client = _client()
    base = benchmark_session["candidates"][0]
    program = benchmark_session["program_summary"]
    req_spec = benchmark_session["requirement_spec"]
    mutable_room = program["rooms"][0]["id"]
    locked_rooms = [r["id"] for r in program["rooms"] if r["id"] != mutable_room]

    base_placements = _program_placements(base, program)
    assert base_placements, "应有 program 放置"
    max_seed = max(c["seed"] for c in benchmark_session["candidates"])
    base_map = {p["room_id"]: p for p in base_placements}

    partial = client.post(
        "/api/regenerate/partial",
        json={
            "use_benchmark": False,
            "requirements": req_spec,
            "candidate_count": 8,
            "return_top_k": 3,
            "base_seed": max_seed + 1,
            "regeneration_scope": {
                "mutable_rooms": [mutable_room],
                "locked_rooms": [],
                "affected_neighbors": [],
                "preserve_topology": True,
                "preserve_floor_assignment": True,
            },
            "base_placements": base_placements,
        },
    )
    assert partial.status_code == 200, partial.text
    body = partial.json()
    assert body["generated"] == 8
    assert body["valid"] >= 1, body.get("violation_summary")
    assert body["program_summary"]["rooms"]
    assert body["requirement_spec"] is not None
    assert body["solver_identity"] is not None
    # requirements 路径 normalize 后 project_id 为 from-requirements（与 benchmark 直出不同）
    assert body["program_summary"]["project_id"] == "from-requirements"
    assert body["rejected"] == body["generated"] - body["valid"]

    resolved = resolve_solve_input(
        PartialRegenerateRequest(
            use_benchmark=False,
            requirements=req_spec,
            candidate_count=8,
            return_top_k=3,
            base_seed=max_seed + 1,
            regeneration_scope=RegenerationScope(
                mutable_rooms=[mutable_room],
                preserve_topology=True,
                preserve_floor_assignment=True,
            ),
            base_placements=[
                RoomPlacementPayload(**p) for p in base_placements
            ],
        )
    )
    locks, _scope = resolve_partial_regenerate(
        PartialRegenerateRequest(
            use_benchmark=False,
            requirements=req_spec,
            regeneration_scope=RegenerationScope(mutable_rooms=[mutable_room]),
            base_placements=[RoomPlacementPayload(**p) for p in base_placements],
        ),
        resolved.program,
    )
    locked_ids = {r.room_id for r in locks.rooms}
    assert mutable_room not in locked_ids
    assert locked_ids == set(locked_rooms)
    for rid in ("r2", "r5"):
        lock = next(r for r in locks.rooms if r.room_id == rid)
        base = base_map[rid]
        assert (lock.x, lock.y, lock.width, lock.depth) == _rect(base)

    for cand in body["candidates"]:
        cand_map = {p["room_id"]: p for p in cand.get("placements") or []}
        for rid in ("r2", "r5"):
            if rid not in cand_map:
                continue
            assert _rect(base_map[rid]) == _rect(cand_map[rid])


def test_partial_regenerate_rejects_empty_placements():
    client = _client()
    gen = client.post(
        "/api/generate",
        json={"use_benchmark": True, "candidate_count": 4, "return_top_k": 2},
    )
    assert gen.status_code == 200
    req_spec = gen.json()["requirement_spec"]

    bad = client.post(
        "/api/regenerate/partial",
        json={
            "use_benchmark": False,
            "requirements": req_spec,
            "regeneration_scope": {
                "mutable_rooms": ["r1"],
                "preserve_topology": True,
                "preserve_floor_assignment": True,
            },
            "base_placements": [],
        },
    )
    assert bad.status_code == 422
