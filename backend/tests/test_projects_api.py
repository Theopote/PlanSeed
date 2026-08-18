"""Phase 5 / 5.1 — /api/projects。"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from backend.main import create_app
from fastapi.testclient import TestClient
from packages.schema.identity import EVALUATION_VERSION


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db = tmp_path / "api-projects.db"
    monkeypatch.setenv("PLANSEED_DB", str(db))
    app = create_app()
    return TestClient(app)


def test_projects_crud_and_version_mismatch(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("PLANSEED_DB", str(tmp_path / "api-projects.db"))
    r = client.post(
        "/api/projects",
        json={
            "name": "alpha",
            "payload": {
                "form": {"width": 11, "depth": 13},
                "program": {"project_id": "x", "site_width": 11, "site_depth": 13},
                "locks": {"rooms": [], "stair": None, "zones": []},
                "candidates": [
                    {
                        "id": "c1",
                        "seed": 0,
                        "label": "A",
                        "variant_parent_id": None,
                        "variant_generation": 0,
                        "lock_snapshot_id": "abcd",
                        "provenance": {
                            "solver_version": "0.4",
                            "generator_version": "guillotine-lock-v4",
                            "evaluation_version": EVALUATION_VERSION,
                        },
                        "revision_status": "generated",
                    }
                ],
                "selected_id": "c1",
                "schema_versions": {
                    "solver_version": "0.4",
                    "generator_version": "guillotine-lock-v4",
                    "evaluation_version": EVALUATION_VERSION,
                },
            },
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    pid = body["id"]
    assert body["evaluation_version_mismatch"] is False
    assert body["payload"]["project_meta"]["format_version"] == "1"
    assert body["payload"]["schema_versions"]["evaluation_version"] == EVALUATION_VERSION

    listed = client.get("/api/projects")
    assert listed.status_code == 200
    assert any(p["id"] == pid for p in listed.json())

    from packages.persistence import ProjectStore

    store = ProjectStore(db_path=Path(os.environ["PLANSEED_DB"]))
    row = store.get(pid)
    assert row is not None
    row["payload"]["schema_versions"]["evaluation_version"] = "ancient-test"
    store.save(name=row["name"], payload=row["payload"], project_id=pid)

    got = client.get(f"/api/projects/{pid}")
    assert got.status_code == 200
    detail = got.json()
    assert detail["evaluation_version_mismatch"] is True
    assert detail["current_evaluation_version"] == EVALUATION_VERSION

    deleted = client.delete(f"/api/projects/{pid}")
    assert deleted.status_code == 200
    assert client.get(f"/api/projects/{pid}").status_code == 404


def test_save_preserves_old_evaluation_version(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Save 不得把旧评价版本伪装成 current。"""
    monkeypatch.setenv("PLANSEED_DB", str(tmp_path / "preserve-ev.db"))
    r = client.post(
        "/api/projects",
        json={
            "name": "legacy",
            "payload": {
                "form": {},
                "program": None,
                "locks": {"rooms": [], "stair": None, "zones": []},
                "candidates": [
                    {
                        "id": "c1",
                        "seed": 1,
                        "label": "A",
                        "revision_status": "dirty",
                        "mutations": [
                            {
                                "id": "m1",
                                "kind": "move",
                                "room_id": "bedroom-1",
                                "before": {"x": 0, "y": 0, "width": 3, "depth": 3},
                                "after": {"x": 0.3, "y": 0, "width": 3, "depth": 3},
                            }
                        ],
                        "provenance": {
                            "solver_version": "0.3",
                            "generator_version": "old-gen",
                            "evaluation_version": "ancient-eval",
                        },
                    }
                ],
                "selected_id": "c1",
                "schema_versions": {
                    "solver_version": "0.3",
                    "generator_version": "old-gen",
                    "evaluation_version": "ancient-eval",
                },
            },
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["payload"]["schema_versions"]["evaluation_version"] == "ancient-eval"
    assert body["evaluation_version_mismatch"] is True
    assert body["payload"]["candidates"][0]["revision_status"] == "dirty"
    assert len(body["payload"]["candidates"][0]["mutations"]) == 1

    # 再次保存仍保留 ancient-eval
    pid = body["id"]
    again = client.post(
        "/api/projects",
        json={
            "name": "legacy",
            "id": pid,
            "payload": body["payload"],
        },
    )
    assert again.status_code == 200, again.text
    assert (
        again.json()["payload"]["schema_versions"]["evaluation_version"]
        == "ancient-eval"
    )
    assert again.json()["evaluation_version_mismatch"] is True


def test_planseed_export_import_roundtrip(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("PLANSEED_DB", str(tmp_path / "pkg.db"))
    r = client.post(
        "/api/projects",
        json={
            "name": "导出宅",
            "payload": {
                "form": {"width": 14},
                "candidates": [{"id": "c9", "seed": 1, "label": "A"}],
                "selected_id": "c9",
                "schema_versions": {
                    "solver_version": "0.4",
                    "generator_version": "g",
                    "evaluation_version": "ancient-pkg",
                },
            },
        },
    )
    assert r.status_code == 200, r.text
    pid = r.json()["id"]

    exp = client.get(f"/api/projects/{pid}/package")
    assert exp.status_code == 200, exp.text
    assert exp.headers["content-type"].startswith("application/zip")
    assert ".planseed" in exp.headers.get("content-disposition", "")

    # 清空库后再导入
    monkeypatch.setenv("PLANSEED_DB", str(tmp_path / "pkg-import.db"))
    imp = client.post(
        "/api/projects/import",
        content=exp.content,
        headers={"Content-Type": "application/zip"},
    )
    assert imp.status_code == 200, imp.text
    body = imp.json()
    assert body["id"] == pid
    assert body["name"] == "导出宅"
    assert body["payload"]["form"]["width"] == 14
    assert body["payload"]["schema_versions"]["evaluation_version"] == "ancient-pkg"
    assert body["evaluation_version_mismatch"] is True


def test_planseed_full_fidelity_roundtrip(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Alpha RQ：RequirementSpec / Program / Candidates / locks / mutations / provenance 不丢。"""
    from packages.schema.identity import (
        EVALUATION_VERSION,
        GENERATOR_VERSION,
        SELECTION_VERSION,
        SOLVER_VERSION,
    )

    monkeypatch.setenv("PLANSEED_DB", str(tmp_path / "fidelity.db"))
    payload = {
        "form": {"width": 12, "depth": 15, "floors": 2},
        "requirement_spec": {
            "floor_count": 2,
            "household": {"bedrooms": 3, "bathrooms": 2, "has_garage": False},
            "site": {"width": 12, "depth": 15},
            "spaces": [
                {"id": "living", "name": "客厅", "category": "living", "target_area": 28}
            ],
            "assumptions": [
                {
                    "id": "a1",
                    "text": "默认退线 0",
                    "source": "planseed_default",
                }
            ],
            "unknowns": [],
        },
        "program": {
            "project_id": "prog-1",
            "site_width": 12,
            "site_depth": 15,
            "rooms": [
                {"id": "living", "name": "客厅", "category": "living", "target_area": 28}
            ],
        },
        "locks": {
            "rooms": [{"room_id": "living", "floor_id": "F1", "x": 1, "y": 1, "width": 4, "depth": 5}],
            "stair": None,
            "zones": [],
        },
        "candidates": [
            {
                "id": "c-fidelity",
                "seed": 42,
                "label": "A",
                "score": 77.5,
                "revision_status": "validated",
                "revision_id": "c-fidelity:val:abcd1234",
                "variant_parent_id": None,
                "variant_generation": 0,
                "lock_snapshot_id": "lock-snap-1",
                "mutations": [
                    {
                        "id": "m1",
                        "kind": "nudge_room",
                        "source": "user",
                        "room_id": "living",
                        "dx": 0.3,
                        "dy": 0.0,
                    }
                ],
                "provenance": {
                    "solver_version": SOLVER_VERSION,
                    "generator_strategy": "guillotine",
                    "generator_version": GENERATOR_VERSION,
                    "selection_strategy": "axis-diverse",
                    "selection_version": SELECTION_VERSION,
                    "evaluation_version": EVALUATION_VERSION,
                    "assignment_strategy": "heuristic",
                    "geometry_backend": "rect",
                },
            }
        ],
        "selected_id": "c-fidelity",
        "schema_versions": {
            "solver_version": SOLVER_VERSION,
            "generator_strategy": "guillotine",
            "generator_version": GENERATOR_VERSION,
            "selection_strategy": "axis-diverse",
            "selection_version": SELECTION_VERSION,
            "evaluation_version": EVALUATION_VERSION,
            "assignment_strategy": "heuristic",
            "geometry_backend": "rect",
        },
    }
    saved = client.post("/api/projects", json={"name": "保真宅", "payload": payload})
    assert saved.status_code == 200, saved.text
    pid = saved.json()["id"]

    pkg = client.get(f"/api/projects/{pid}/package")
    assert pkg.status_code == 200, pkg.text

    assert client.delete(f"/api/projects/{pid}").status_code == 200
    assert client.get(f"/api/projects/{pid}").status_code == 404

    restored = client.post(
        "/api/projects/import",
        content=pkg.content,
        headers={"Content-Type": "application/zip"},
    )
    assert restored.status_code == 200, restored.text
    body = restored.json()
    assert body["id"] == pid
    assert body["name"] == "保真宅"
    p = body["payload"]

    assert p["form"]["width"] == 12
    assert p["requirement_spec"]["floor_count"] == 2
    assert p["requirement_spec"]["spaces"][0]["id"] == "living"
    assert p["requirement_spec"]["assumptions"][0]["source"] == "planseed_default"
    assert p["program"]["rooms"][0]["id"] == "living"
    assert p["locks"]["rooms"][0]["room_id"] == "living"
    assert p["selected_id"] == "c-fidelity"

    cand = p["candidates"][0]
    assert cand["revision_status"] == "validated"
    assert cand["revision_id"] == "c-fidelity:val:abcd1234"
    assert cand["lock_snapshot_id"] == "lock-snap-1"
    assert cand["mutations"][0]["id"] == "m1"
    assert cand["mutations"][0]["dx"] == 0.3
    prov = cand["provenance"]
    assert prov["solver_version"] == SOLVER_VERSION
    assert prov["generator_strategy"] == "guillotine"
    assert prov["selection_strategy"] == "axis-diverse"
    assert prov["geometry_backend"] == "rect"

    sv = p["schema_versions"]
    assert sv["selection_version"] == SELECTION_VERSION
    assert sv["assignment_strategy"] == "heuristic"
    assert body["evaluation_version_mismatch"] is False


def test_planseed_import_rejects_bad_zip(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("PLANSEED_DB", str(tmp_path / "bad.db"))
    bad = client.post(
        "/api/projects/import",
        content=b"not-a-zip",
        headers={"Content-Type": "application/zip"},
    )
    assert bad.status_code == 400
    detail = bad.json()["detail"]
    assert detail["code"] == "not_zip"


def test_import_validates_before_write_and_conflict(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from packages.persistence.planseed_package import pack_planseed

    monkeypatch.setenv("PLANSEED_DB", str(tmp_path / "import-gate.db"))
    saved = client.post(
        "/api/projects",
        json={
            "name": "local",
            "id": "same-id",
            "payload": {"form": {}, "candidates": []},
        },
    )
    assert saved.status_code == 200, saved.text

    blob = pack_planseed(
        project_id="same-id",
        name="incoming",
        updated_at="2020-01-01T00:00:00+00:00",
        payload={"form": {"width": 9}, "candidates": []},
        app_version="0.1.1",
    )
    blocked = client.post(
        "/api/projects/import",
        content=blob,
        headers={"Content-Type": "application/zip"},
    )
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["code"] == "project_exists"
    assert client.get("/api/projects/same-id").json()["name"] == "local"

    overwritten = client.post(
        "/api/projects/import?overwrite=true",
        content=blob,
        headers={"Content-Type": "application/zip"},
    )
    assert overwritten.status_code == 200, overwritten.text
    assert overwritten.json()["name"] == "incoming"

    poison = pack_planseed(
        project_id="poison",
        name="poison",
        updated_at="2020-01-01T00:00:00+00:00",
        payload={"form": {}, "candidates": {}},
        app_version="0.1.1",
    )
    rejected = client.post(
        "/api/projects/import",
        content=poison,
        headers={"Content-Type": "application/zip"},
    )
    assert rejected.status_code == 400
    assert client.get("/api/projects/poison").status_code == 404
