"""Phase 5.1 — /api/mutations/preview。"""

from __future__ import annotations

from backend.main import create_app
from fastapi.testclient import TestClient
from packages.schema.layout import PlacementRect, PlacementSource, RoomPlacement
from packages.schema.locks import LayoutLocks
from packages.schema.mutation import GeometryMutation, MutationKind
from solver.fixtures.benchmark import benchmark_program
from solver.mutation import preview_mutation


def _client() -> TestClient:
    return TestClient(create_app())


def _placement_payload(p: RoomPlacement) -> dict:
    return {
        "room_id": p.room_id,
        "floor_id": p.floor_id,
        "x": p.rect.x,
        "y": p.rect.y,
        "width": p.rect.width,
        "depth": p.rect.depth,
        "area": p.rect.area,
    }


def test_mutations_preview_matches_authority():
    program = benchmark_program()
    fid = program.floors[0].id
    placements = [
        RoomPlacement(
            room_id="a",
            floor_id=fid,
            rect=PlacementRect(x=0, y=0, width=3, depth=3),
            source=PlacementSource.PROGRAM,
            name="a",
        ),
        RoomPlacement(
            room_id="b",
            floor_id=fid,
            rect=PlacementRect(x=4, y=0, width=3, depth=3),
            source=PlacementSource.PROGRAM,
            name="b",
        ),
    ]
    mut = GeometryMutation(
        kind=MutationKind.MOVE,
        room_id="a",
        floor_id=fid,
        proposed=PlacementRect(x=3.5, y=0, width=3, depth=3),
    )
    expected = preview_mutation(
        program=program,
        placements=placements,
        locks=LayoutLocks(),
        mutation=mut,
    )

    client = _client()
    r = client.post(
        "/api/mutations/preview",
        json={
            "use_benchmark": True,
            "placements": [_placement_payload(p) for p in placements],
            "locks": {"rooms": [], "stair": None, "zones": []},
            "mutation": {
                "kind": "move",
                "room_id": "a",
                "floor_id": fid,
                "proposed": {"x": 3.5, "y": 0, "width": 3, "depth": 3},
                "source": "pointer",
            },
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] == expected.ok
    assert body["ok"] is False
    assert any(x["code"] == "mutation.overlap" for x in body["reasons"])


def test_mutations_preview_ok_move():
    program = benchmark_program()
    fid = program.floors[0].id
    client = _client()
    r = client.post(
        "/api/mutations/preview",
        json={
            "use_benchmark": True,
            "placements": [
                {
                    "room_id": "a",
                    "floor_id": fid,
                    "x": 0,
                    "y": 0,
                    "width": 3,
                    "depth": 3,
                    "area": 9,
                }
            ],
            "locks": {"rooms": [], "stair": None, "zones": []},
            "mutation": {
                "kind": "move",
                "room_id": "a",
                "floor_id": fid,
                "proposed": {"x": 0.3, "y": 0.3, "width": 3, "depth": 3},
                "source": "pointer",
            },
            "snap_module": 0.3,
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["snapped"] is not None
    assert body["snapped"]["x"] == 0.3
    assert body["snapped"]["y"] == 0.3


def test_mutations_revalidate_returns_validated_candidate():
    from solver.pipeline import run_pipeline

    program = benchmark_program()
    program.solver_config.candidate_count = 4
    program.solver_config.return_top_k = 1
    top = run_pipeline(program).top_candidates[0]
    placements = [
        {
            "room_id": p.room_id,
            "floor_id": p.floor_id,
            "x": p.rect.x,
            "y": p.rect.y,
            "width": p.rect.width,
            "depth": p.rect.depth,
            "area": round(p.rect.area, 2),
        }
        for fl in top.floors
        for p in fl.placements
    ]
    zones = [
        {
            "id": z.id,
            "zone": z.zone,
            "kind": z.kind,
            "floor_id": z.floor_id,
            "x": z.rect.x,
            "y": z.rect.y,
            "width": z.rect.width,
            "depth": z.rect.depth,
            "room_ids": list(z.room_ids),
        }
        for z in top.zone_placements
    ]
    client = _client()
    r = client.post(
        "/api/mutations/revalidate",
        json={
            "use_benchmark": True,
            "placements": placements,
            "zones": zones,
            "locks": {"rooms": [], "stair": None, "zones": []},
            "candidate_id": top.id,
            "seed": top.seed,
            "mutations": [
                {
                    "id": "m1",
                    "kind": "move",
                    "room_id": placements[0]["room_id"],
                }
            ],
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["revision_status"] == "validated"
    assert body["id"] == top.id
    assert body["validation"] is not None
    assert len(body["placements"]) == len(placements)
    assert len(body["mutations"]) == 1
    if body["validation"]["valid"]:
        assert body["design_score"] is not None
        assert body["score"] is not None
    assert body["provenance"]["evaluation_version"]
