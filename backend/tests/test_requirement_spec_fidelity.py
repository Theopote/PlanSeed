"""Phase 7.1.1-B — RequirementSpec Python ↔ Desktop JSON fidelity.

共享 fixture：fixtures/requirement_spec_full.json
禁止瘦 map 重建导致 source / priority / north_angle 等语义消失。
不做 OpenAPI 生成。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from backend.main import create_app
from fastapi.testclient import TestClient
from packages.schema.requirements import RequirementSpec

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "fixtures" / "requirement_spec_full.json"

# 必须在 dump / save / reload 后仍存在的语义路径（相对 RequirementSpec JSON）
SEMANTIC_CHECKS: list[tuple[str, object]] = [
    ("site.north_angle", 45.0),
    ("site.entrance_edge", "south"),
    ("site.road_edges", ["south", "east"]),
    ("site.setbacks.north", 1.0),
    ("site.setbacks.south", 2.0),
    ("assumptions.0.source", "user_authorized"),
    ("assumptions.1.source", "planseed_default"),
    ("unknowns.0.priority", "blocking"),
    ("unknowns.1.priority", "optional"),
    ("unknowns.2.priority", "recommended"),
    ("spaces.0.preferred_orientation", "south"),
    ("spaces.0.floor_preference", ["F1"]),
    ("spaces.0.min_width", 3.6),
    ("spaces.1.preferred_orientation", "east"),
    ("relation_intents.0.kind", "near"),
    ("relation_intents.0.strength", "required"),
    ("relation_intents.1.kind", "separation"),
    ("preferences.prefer_south_facing_living", True),
    ("household.notes", "多代同堂，需主卧套房"),
]


def _get_path(data: dict, dotted: str):
    cur: object = data
    for part in dotted.split("."):
        if part.isdigit():
            assert isinstance(cur, list)
            cur = cur[int(part)]
        else:
            assert isinstance(cur, dict), f"{dotted}: expected dict at {part}"
            assert part in cur, f"missing path segment {part} in {dotted}"
            cur = cur[part]
    return cur


def _load_fixture() -> dict:
    assert FIXTURE.is_file(), f"missing fixture {FIXTURE}"
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _assert_semantics(data: dict, *, label: str) -> None:
    for path, expected in SEMANTIC_CHECKS:
        got = _get_path(data, path)
        assert got == expected, f"{label}: {path} expected {expected!r}, got {got!r}"


def test_fixture_validates_as_requirement_spec():
    raw = _load_fixture()
    # strip doc comment key if present
    payload = {k: v for k, v in raw.items() if not k.startswith("_")}
    spec = RequirementSpec.model_validate(payload)
    dumped = spec.model_dump(mode="json")
    _assert_semantics(dumped, label="pydantic-dump")


def test_json_roundtrip_preserves_semantics():
    payload = {k: v for k, v in _load_fixture().items() if not k.startswith("_")}
    spec = RequirementSpec.model_validate(payload)
    again = RequirementSpec.model_validate(json.loads(spec.model_dump_json()))
    _assert_semantics(again.model_dump(mode="json"), label="json-roundtrip")


def test_bad_frontend_rebuild_strips_semantics():
    """文档化危险模式：瘦 shape 重建会丢掉 priority / source / north_angle。"""
    data = {k: v for k, v in _load_fixture().items() if not k.startswith("_")}
    bad = {
        "site": {
            "width": data["site"]["width"],
            "depth": data["site"]["depth"],
            # 故意丢掉 north_angle / entrance_edge / road_edges / setbacks
        },
        "assumptions": [
            {"key": a["key"], "value": a["value"], "reason": a.get("reason", "")}
            # 故意丢掉 source
            for a in data["assumptions"]
        ],
        "unknowns": [
            {"key": u["key"], "description": u.get("description", "")}
            # 故意丢掉 priority
            for u in data["unknowns"]
        ],
        "spaces": [
            {
                "id": s.get("id"),
                "name": s["name"],
                "target_area": s.get("target_area"),
                # 故意丢掉 preferred_orientation / floor_preference / min_width
            }
            for s in data["spaces"]
        ],
        # 故意丢掉 relation_intents
    }
    rebuilt = RequirementSpec.model_validate(bad).model_dump(mode="json")
    assert rebuilt["site"].get("north_angle") is None
    assert rebuilt["assumptions"][0].get("source") == "llm_inference"  # pydantic 默认
    assert rebuilt["unknowns"][0].get("priority") == "recommended"  # pydantic 默认
    assert rebuilt["spaces"][0].get("preferred_orientation") is None
    assert rebuilt["relation_intents"] == []


def test_spread_clone_preserves_semantics():
    """正确模式：{...row} / model_dump 全量保留。"""
    data = {k: v for k, v in _load_fixture().items() if not k.startswith("_")}
    cloned = {
        **data,
        "assumptions": [{**a} for a in data["assumptions"]],
        "unknowns": [{**u} for u in data["unknowns"]],
        "spaces": [{**s} for s in data["spaces"]],
        "relation_intents": [{**r} for r in data["relation_intents"]],
        "site": {
            **data["site"],
            "setbacks": {**data["site"]["setbacks"]},
            "road_edges": list(data["site"]["road_edges"]),
        },
    }
    _assert_semantics(
        RequirementSpec.model_validate(cloned).model_dump(mode="json"),
        label="spread-clone",
    )


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PLANSEED_DB", str(tmp_path / "fidelity.db"))
    return TestClient(create_app())


def test_project_save_reload_preserves_requirement_spec(client: TestClient):
    """Backend → save → reload：canonical RequirementSpec 语义不丢。"""
    spec = {k: v for k, v in _load_fixture().items() if not k.startswith("_")}
    payload = {
        "form": {
            "width": 11,
            "depth": 13,
            "floor_count": 2,
            "bedrooms": 3,
            "bathrooms": 2,
            "has_garage": True,
            "prefer_south_facing_living": True,
        },
        "program": None,
        "requirement_spec": spec,
        "locks": {"rooms": [], "stair": None, "zones": []},
        "candidates": [],
        "selected_id": None,
    }
    created = client.post("/api/projects", json={"name": "Fidelity", "payload": payload})
    assert created.status_code == 200, created.text
    pid = created.json()["id"]
    loaded = client.get(f"/api/projects/{pid}")
    assert loaded.status_code == 200, loaded.text
    body = loaded.json()
    got = body["payload"]["requirement_spec"]
    assert got is not None
    _assert_semantics(got, label="project-store-reload")
    # 再经 Pydantic 确认
    _assert_semantics(
        RequirementSpec.model_validate(got).model_dump(mode="json"),
        label="project-store-revalidate",
    )
