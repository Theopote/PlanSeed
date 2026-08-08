"""Phase 5.1.1 — RequirementSpec 往返 + stair hydrate。"""

from __future__ import annotations

from pathlib import Path

import pytest
from backend.main import create_app
from fastapi.testclient import TestClient
from packages.schema.layout import (
    FloorLayout,
    PlacementRect,
    PlacementSource,
    RoomPlacement,
)
from packages.schema.locks import LayoutLocks
from solver.evaluation.vertical import compute_vertical_metrics
from solver.fixtures.benchmark import benchmark_program
from solver.mutation.commit import (
    derive_stair_core_from_placements,
    hydrate_candidate_from_placements,
    revalidate_candidate,
)
from solver.pipeline import run_pipeline


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PLANSEED_DB", str(tmp_path / "fidelity.db"))
    return TestClient(create_app())


def test_generate_returns_requirement_spec(client: TestClient):
    r = client.post(
        "/api/generate",
        json={
            "use_benchmark": False,
            "candidate_count": 4,
            "return_top_k": 1,
            "requirements": {
                "site": {"width": 11, "depth": 13},
                "household": {
                    "bedrooms": 3,
                    "bathrooms": 2,
                    "has_garage": True,
                },
                "preferences": {"prefer_south_facing_living": True},
                "floor_count": 2,
            },
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    spec = body["requirement_spec"]
    assert spec is not None
    assert spec["site"]["width"] == 11
    assert len(spec["spaces"]) > 0
    # 不应只有 ProgramSummary
    assert body["program_summary"]["site_width"] == 11


def test_project_save_roundtrip_requirement_spec(client: TestClient):
    gen = client.post(
        "/api/generate",
        json={
            "use_benchmark": True,
            "candidate_count": 4,
            "return_top_k": 1,
        },
    )
    assert gen.status_code == 200, gen.text
    g = gen.json()
    spec = g["requirement_spec"]
    assert spec is not None

    saved = client.post(
        "/api/projects",
        json={
            "name": "fidelity",
            "payload": {
                "form": {"width": 11, "depth": 13},
                "program": g["program_summary"],
                "requirement_spec": spec,
                "locks": {"rooms": [], "stair": None, "zones": []},
                "candidates": g["candidates"],
                "selected_id": g["candidates"][0]["id"],
            },
        },
    )
    assert saved.status_code == 200, saved.text
    pid = saved.json()["id"]
    assert saved.json()["payload"]["requirement_spec"] is not None
    assert len(saved.json()["payload"]["requirement_spec"]["spaces"]) > 0

    got = client.get(f"/api/projects/{pid}")
    assert got.status_code == 200
    loaded = got.json()["payload"]["requirement_spec"]
    assert loaded is not None
    assert len(loaded.get("spaces") or []) == len(spec.get("spaces") or [])


def test_derive_stair_core_fills_floor_metadata():
    floors = [
        FloorLayout(
            floor_id="F1",
            placements=[
                RoomPlacement(
                    room_id="stair-F1",
                    floor_id="F1",
                    rect=PlacementRect(x=1, y=2, width=1.8, depth=4.2),
                    source=PlacementSource.GENERATED,
                )
            ],
        ),
        FloorLayout(
            floor_id="F2",
            placements=[
                RoomPlacement(
                    room_id="stair-F2",
                    floor_id="F2",
                    rect=PlacementRect(x=1, y=2, width=1.8, depth=4.2),
                    source=PlacementSource.GENERATED,
                )
            ],
        ),
    ]
    derived = derive_stair_core_from_placements(floors, core_placement="center")
    assert derived[0].stair_x0 == 1.0
    assert derived[0].stair_y0 == 2.0
    assert derived[0].stair_x1 == pytest.approx(2.8)
    assert derived[0].stair_y1 == pytest.approx(6.2)
    assert derived[0].core_placement == "center"
    assert derived[1].stair_x0 == 1.0


def test_revalidate_hydrates_stair_so_vertical_can_detect_misalignment():
    program = benchmark_program()
    program.solver_config.candidate_count = 4
    program.solver_config.return_top_k = 1
    top = run_pipeline(program).top_candidates[0]
    placements = [p for fl in top.floors for p in fl.placements]

    # 错位 F2 楼梯
    moved = []
    for p in placements:
        if p.room_id.startswith("stair-") and p.floor_id != program.floors[0].id:
            moved.append(
                p.model_copy(
                    update={
                        "rect": PlacementRect(
                            x=p.rect.x + 1.5,
                            y=p.rect.y,
                            width=p.rect.width,
                            depth=p.rect.depth,
                        )
                    }
                )
            )
        else:
            moved.append(p)

    cand = revalidate_candidate(
        program=program,
        placements=moved,
        locks=LayoutLocks(),
        candidate_id=top.id,
        seed=top.seed,
        zones=list(top.zone_placements),
    )
    # 楼梯 metadata 已从 placements 推导
    for fl in cand.floors:
        stairs = [p for p in fl.placements if p.room_id.startswith("stair-")]
        if stairs:
            assert fl.stair_x0 is not None
            assert fl.stair_y0 is not None

    metrics = compute_vertical_metrics(cand)
    assert metrics["stair_alignment"] == 0.0


def test_missing_stair_metadata_is_not_perfect():
    """有楼梯 placement 但缺 stair_* → 不得默认 stair_alignment=1。"""
    from packages.schema.layout import (
        FloorLayout,
        LayoutCandidate,
        PlacementRect,
        PlacementSource,
        RoomPlacement,
    )

    floors = [
        FloorLayout(
            floor_id="F1",
            placements=[
                RoomPlacement(
                    room_id="stair-F1",
                    floor_id="F1",
                    rect=PlacementRect(x=0, y=0, width=1.8, depth=4),
                    source=PlacementSource.GENERATED,
                )
            ],
            # 故意不填 stair_*
        ),
        FloorLayout(
            floor_id="F2",
            placements=[
                RoomPlacement(
                    room_id="stair-F2",
                    floor_id="F2",
                    rect=PlacementRect(x=0, y=0, width=1.8, depth=4),
                    source=PlacementSource.GENERATED,
                )
            ],
        ),
    ]
    cand = LayoutCandidate(id="c", seed=0, floors=floors)
    assert compute_vertical_metrics(cand)["stair_alignment"] == 0.0


def test_hydrate_without_stair_leaves_none():
    program = benchmark_program()
    cand = hydrate_candidate_from_placements(
        program=program,
        placements=[
            RoomPlacement(
                room_id="living",
                floor_id=program.floors[0].id,
                rect=PlacementRect(x=0, y=0, width=4, depth=4),
                source=PlacementSource.PROGRAM,
            )
        ],
        candidate_id="x",
        seed=0,
    )
    assert cand.floors[0].stair_x0 is None
