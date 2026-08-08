"""Phase 5 — ProjectStore SQLite。"""

from __future__ import annotations

from pathlib import Path

from packages.persistence import ProjectStore


def test_project_store_roundtrip(tmp_path: Path):
    store = ProjectStore(db_path=tmp_path / "t.db")
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
