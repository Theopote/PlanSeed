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
