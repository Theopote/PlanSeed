"""Phase 5 — /api/projects。"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.main import create_app
from packages.schema.identity import EVALUATION_VERSION


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db = tmp_path / "api-projects.db"
    monkeypatch.setenv("PLANSEED_DB", str(db))
    # 重新绑定 store 用 env
    app = create_app()
    return TestClient(app)


def test_projects_crud_and_version_mismatch(client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PLANSEED_DB", str(tmp_path / "api-projects.db"))
    # 保存
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
                    }
                ],
                "selected_id": "c1",
            },
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    pid = body["id"]
    assert body["evaluation_version_mismatch"] is False

    listed = client.get("/api/projects")
    assert listed.status_code == 200
    assert any(p["id"] == pid for p in listed.json())

    # 直接改库中版本以模拟旧快照
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
