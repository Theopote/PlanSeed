"""Phase 5 — ProjectStore SQLite · Phase 7.5-C migrations。"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from packages.persistence import CURRENT_VERSION, ProjectStore
from packages.persistence.migrations import get_user_version, migrate


def test_project_store_roundtrip(tmp_path: Path):
    store = ProjectStore(db_path=tmp_path / "t.db")
    assert store.schema_version == CURRENT_VERSION
    saved = store.save(
        name="demo",
        payload={
            "form": {"width": 11},
            "program": {"project_id": "p1"},
            "locks": {"rooms": [], "stair": None, "zones": []},
            "candidates": [
                {
                    "id": "c1",
                    "label": "A",
                    "variant_parent_id": None,
                    "variant_generation": 0,
                }
            ],
            "selected_id": "c1",
            "schema_versions": {
                "solver_version": "s",
                "generator_version": "g",
                "evaluation_version": "e-old",
            },
        },
    )
    assert saved["id"]
    listed = store.list_projects()
    assert len(listed) == 1
    assert listed[0].name == "demo"
    got = store.get(saved["id"])
    assert got is not None
    assert got["payload"]["candidates"][0]["id"] == "c1"
    assert store.delete(saved["id"]) is True
    assert store.get(saved["id"]) is None


def test_project_store_update(tmp_path: Path):
    store = ProjectStore(db_path=tmp_path / "u.db")
    first = store.save(name="v1", payload={"form": {}})
    second = store.save(
        name="v2",
        payload={"form": {"width": 12}},
        project_id=first["id"],
    )
    assert second["id"] == first["id"]
    loaded = store.get(first["id"])
    assert loaded is not None
    assert loaded["payload"]["form"]["width"] == 12
    assert len(store.list_projects()) == 1


def _write_legacy_v0_db(path: Path, *, project_id: str, name: str, payload: dict) -> None:
    """模拟 Phase 5 时代库：有 projects 表、无 PRAGMA user_version（=0）。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(path)) as conn:
        conn.execute(
            """
            CREATE TABLE projects (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                payload_json TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "INSERT INTO projects (id, name, updated_at, payload_json) VALUES (?, ?, ?, ?)",
            (project_id, name, "2024-01-01T00:00:00+00:00", json.dumps(payload)),
        )
        conn.execute("PRAGMA user_version = 0")
        conn.commit()


def test_legacy_v0_db_migrates_and_preserves_data(tmp_path: Path):
    db = tmp_path / "legacy.db"
    pid = "legacy-proj-1"
    payload = {"form": {"width": 15, "depth": 20}, "selected_id": "c-legacy"}
    _write_legacy_v0_db(db, project_id=pid, name="旧项目", payload=payload)

    with sqlite3.connect(str(db)) as conn:
        assert get_user_version(conn) == 0

    store = ProjectStore(db_path=db)
    assert store.schema_version == CURRENT_VERSION

    got = store.get(pid)
    assert got is not None
    assert got["name"] == "旧项目"
    assert got["payload"]["form"]["width"] == 15
    assert got["payload"]["selected_id"] == "c-legacy"
    assert len(store.list_projects()) == 1


def test_migrate_idempotent(tmp_path: Path):
    db = tmp_path / "idem.db"
    with sqlite3.connect(str(db)) as conn:
        assert migrate(conn) == CURRENT_VERSION
        assert migrate(conn) == CURRENT_VERSION
        assert get_user_version(conn) == CURRENT_VERSION
        conn.commit()
