"""Phase 7.2.2 — PNG Final Export 测试。"""

from __future__ import annotations

import struct
from pathlib import Path

import pytest
from backend.main import create_app
from backend.services.export.png_exporter import fit_pixel_size, rasterize_svg_to_png
from fastapi.testclient import TestClient
from packages.schema.scoring import DesignScore


def _score() -> dict:
    return DesignScore(
        program_score=80,
        spatial_score=78,
        circulation_score=75,
        privacy_score=80,
        environment_score=70,
        technical_score=76,
        robustness_score=74,
        total_score=76.0,
        findings=[],
    ).model_dump(mode="json")


def _svg(label: str = "F1", *, w: int = 100, h: int = 80) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}">'
        f'<rect width="{w}" height="{h}" fill="#eeeeee"/>'
        f'<text x="4" y="20" font-size="12">{label}</text></svg>'
    )


def _candidate(**overrides) -> dict:
    base = {
        "id": "c-a",
        "seed": 42,
        "score": 76.0,
        "label": "A",
        "svg": _svg("ALL"),
        "floor_svgs": {"F1": _svg("F1"), "F2": _svg("F2")},
        "design_score": _score(),
        "provenance": {
            "solver_version": "test-s",
            "generator_version": "test-g",
            "evaluation_version": "test-e",
        },
        "revision_status": "generated",
        "revision_id": "c-a:gen:deadbeef",
        "placements": [
            {
                "room_id": "r1",
                "floor_id": "F1",
                "x": 0,
                "y": 0,
                "width": 4.0,
                "depth": 3.5,
                "area": 14.0,
            }
        ],
        "validation": {"valid": True, "hard_violations": [], "soft_violations": []},
    }
    base.update(overrides)
    return base


def _payload(candidate: dict | None = None) -> dict:
    return {
        "form": {},
        "program": {
            "rooms": [
                {"id": "r1", "name": "客厅", "category": "living", "target_area": 20}
            ]
        },
        "requirement_spec": {
            "floor_count": 2,
            "household": {"bedrooms": 3, "bathrooms": 2, "has_garage": True},
            "site": {"width": 11, "depth": 13},
            "spaces": [],
        },
        "candidates": [candidate or _candidate()],
        "selected_id": "c-a",
    }


def _png_size(data: bytes) -> tuple[int, int]:
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    return struct.unpack(">II", data[16:24])


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PLANSEED_DB", str(tmp_path / "exports-png.db"))
    return TestClient(create_app())


def _save(client: TestClient, payload: dict | None = None, name: str = "PngExport") -> str:
    r = client.post(
        "/api/projects",
        json={"name": name, "payload": payload or _payload()},
    )
    assert r.status_code == 200, r.text
    return r.json()["id"]


def test_png_export_final_revision(client: TestClient):
    pid = _save(client)
    r = client.post(
        "/api/exports/png",
        json={
            "project_id": pid,
            "candidate_id": "c-a",
            "revision_id": "c-a:gen:deadbeef",
            "scope": "floor",
            "floor_id": "F1",
            "size": 2048,
        },
    )
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("image/png")
    assert "2048" in r.headers.get("content-disposition", "")
    w, h = _png_size(r.content)
    assert max(w, h) == 2048
    assert w == int(r.headers.get("X-PlanSeed-Png-Width", "0"))
    assert h == int(r.headers.get("X-PlanSeed-Png-Height", "0"))


def test_png_export_wrong_revision_rejected(client: TestClient):
    pid = _save(client)
    r = client.post(
        "/api/exports/png",
        json={
            "project_id": pid,
            "candidate_id": "c-a",
            "revision_id": "wrong",
            "scope": "floor",
            "floor_id": "F1",
            "size": 2048,
        },
    )
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "revision_mismatch"


def test_png_export_dirty_candidate_rejected(client: TestClient):
    cand = _candidate(revision_status="dirty")
    pid = _save(client, _payload(cand))
    r = client.post(
        "/api/exports/png",
        json={
            "project_id": pid,
            "candidate_id": "c-a",
            "revision_id": "c-a:gen:deadbeef",
            "scope": "floor",
            "floor_id": "F1",
            "size": 2048,
        },
    )
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "candidate_requires_revalidation"


def test_png_export_size_4096(client: TestClient):
    pid = _save(client)
    r = client.post(
        "/api/exports/png",
        json={
            "project_id": pid,
            "candidate_id": "c-a",
            "revision_id": "c-a:gen:deadbeef",
            "scope": "snapshot",
            "size": 4096,
        },
    )
    assert r.status_code == 200, r.text
    w, h = _png_size(r.content)
    assert max(w, h) == 4096


def test_png_export_invalid_size_rejected(client: TestClient):
    pid = _save(client)
    r = client.post(
        "/api/exports/png",
        json={
            "project_id": pid,
            "candidate_id": "c-a",
            "revision_id": "c-a:gen:deadbeef",
            "scope": "floor",
            "floor_id": "F1",
            "size": 1024,
        },
    )
    assert r.status_code == 422


def test_png_export_white_background():
    import io

    from PIL import Image

    # 内容不铺满画布：角像素应为白底
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="80">'
        '<rect x="20" y="20" width="60" height="40" fill="#cccccc"/>'
        "</svg>"
    )
    png, w, h = rasterize_svg_to_png(svg, max_px=2048)
    assert max(w, h) == 2048
    im = Image.open(io.BytesIO(png)).convert("RGB")
    assert im.getpixel((0, 0)) == (255, 255, 255)
    assert im.getpixel((w - 1, h - 1)) == (255, 255, 255)
    png2, w2, h2 = rasterize_svg_to_png(svg, max_px=2048)
    assert (w, h) == (w2, h2)
    assert png == png2


def test_png_export_content_type_zip(client: TestClient):
    pid = _save(client)
    r = client.post(
        "/api/exports/png",
        json={
            "project_id": pid,
            "candidate_id": "c-a",
            "revision_id": "c-a:gen:deadbeef",
            "scope": "all_floors",
            "size": 2048,
        },
    )
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/zip"
    assert r.content[:2] == b"PK"


def test_fit_pixel_size_portrait():
    svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 20"></svg>'
    w, h = fit_pixel_size(svg, 2048)
    assert h == 2048
    assert w == 1024
