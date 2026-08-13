"""为 Desktop 手测 Gate（B1 / A / C）准备 .planseed 样本与 Print 对照包。

用法（引擎已启动）::

    uv run python scripts/prepare_desktop_hand_gate.py

输出::
    debug/desktop-hand-gate/alpha-v0.1-hand-gate.planseed
    debug/desktop-hand-gate/README.txt
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from packages.schema.identity import (
    EVALUATION_VERSION,
    GENERATOR_VERSION,
    SELECTION_VERSION,
    SOLVER_VERSION,
)

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "debug" / "desktop-hand-gate"
PACKAGE_NAME = "alpha-v0.1-hand-gate.planseed"


def _base() -> str:
    host = os.environ.get("PLANSEED_HOST", "127.0.0.1")
    port = os.environ.get("PLANSEED_PORT", "8787")
    return f"http://{host}:{port}"


def _req(
    method: str,
    path: str,
    *,
    body: dict[str, Any] | None = None,
) -> tuple[int, bytes]:
    data = None
    headers: dict[str, str] = {}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(
        f"{_base()}{path}",
        data=data,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def _program_from_summary(summary: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(summary, dict):
        return None
    rooms = summary.get("rooms") or []
    return {
        "project_id": summary.get("project_id"),
        "site_width": summary.get("site_width"),
        "site_depth": summary.get("site_depth"),
        "rooms": [
            {
                "id": r.get("id"),
                "name": r.get("name"),
                "category": r.get("category"),
                "target_area": r.get("target_area"),
            }
            for r in rooms
            if isinstance(r, dict)
        ],
    }


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / PACKAGE_NAME

    print(f"== prepare desktop hand gate @ {_base()} ==")

    status, raw = _req("GET", "/api/health")
    if status != 200:
        raise SystemExit(f"health failed: {status}")
    health = json.loads(raw)
    if health.get("service") != "planseed":
        raise SystemExit("engine not planseed")

    status, raw = _req(
        "POST",
        "/api/generate",
        body={"use_benchmark": True, "candidate_count": 8, "return_top_k": 3},
    )
    if status != 200:
        raise SystemExit(f"generate failed: {status} {raw[:300]!r}")
    gen = json.loads(raw)
    cands = gen.get("candidates") or []
    if not cands:
        raise SystemExit("no candidates")
    c0 = cands[0]
    prov = c0.get("provenance") or {}
    req_spec = gen.get("requirement_spec") or {}
    program_summary = gen.get("program_summary")

    # 模拟 Gate C：锁 + mutation 元数据（与 API fidelity 单测对齐）
    living_id = "living"
    rooms = (program_summary or {}).get("rooms") or []
    if rooms and isinstance(rooms[0], dict):
        living_id = rooms[0].get("id") or living_id

    payload: dict[str, Any] = {
        "form": {"width": 11, "depth": 13, "floors": 2},
        "requirement_spec": req_spec,
        "program": _program_from_summary(program_summary),
        "locks": {
            "rooms": [
                {
                    "room_id": living_id,
                    "floor_id": "F1",
                    "x": 1.0,
                    "y": 1.0,
                    "width": 4.0,
                    "depth": 5.0,
                }
            ],
            "stair": None,
            "zones": [],
        },
        "candidates": [
            {
                **{k: c0[k] for k in c0 if k != "placements"},
                "placements": c0.get("placements") or [],
                "revision_status": "validated",
                "revision_id": f"{c0.get('id', 'c')}:val:handgate",
                "lock_snapshot_id": "lock-snap-handgate",
                "mutations": [
                    {
                        "id": "m-handgate-1",
                        "kind": "nudge_room",
                        "source": "user",
                        "room_id": living_id,
                        "dx": 0.3,
                        "dy": 0.0,
                    }
                ],
                "svg": c0.get("svg")
                or (
                    '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="80">'
                    '<rect width="100" height="80" fill="#eee"/></svg>'
                ),
                "floor_svgs": c0.get("floor_svgs") or {},
            }
        ],
        "selected_id": c0.get("id"),
        "compare_id": cands[1].get("id") if len(cands) > 1 else None,
        "schema_versions": {
            "solver_version": prov.get("solver_version") or SOLVER_VERSION,
            "generator_strategy": prov.get("generator_strategy") or "guillotine",
            "generator_version": prov.get("generator_version") or GENERATOR_VERSION,
            "selection_strategy": prov.get("selection_strategy") or "axis-diverse",
            "selection_version": prov.get("selection_version") or SELECTION_VERSION,
            "evaluation_version": prov.get("evaluation_version") or EVALUATION_VERSION,
            "assignment_strategy": prov.get("assignment_strategy") or "heuristic",
            "geometry_backend": prov.get("geometry_backend") or "rect",
        },
    }

    status, raw = _req(
        "POST",
        "/api/projects",
        body={
            "name": "Alpha手测-GateC",
            "payload": payload,
        },
    )
    if status != 200:
        raise SystemExit(f"save project failed: {status} {raw[:300]!r}")
    project = json.loads(raw)
    pid = project["id"]

    status, pkg = _req("GET", f"/api/projects/{pid}/package")
    if status != 200:
        raise SystemExit(f"export package failed: {status}")
    out_path.write_bytes(pkg)
    print(f"OK: wrote {out_path.relative_to(ROOT)} ({len(pkg)} bytes)")

    _req("DELETE", f"/api/projects/{pid}")

    readme = OUT_DIR / "README.txt"
    readme.write_text(
        "\n".join(
            [
                "Alpha v0.1 Desktop Hand Gate",
                "===========================",
                "",
                f"Package: {PACKAGE_NAME}",
                "",
                "Gate C (Desktop):",
                "  1) Install PlanSeed from NSIS setup (see docs)",
                "  2) Click [导入包] and select this .planseed file",
                "  3) Verify: RequirementSpec, Program, candidates, locks, mutations, provenance",
                "  4) Export -> report preview / SVG / PNG",
                "",
                "Gate A (Print):",
                "  debug/print-smoke/index.html (Edge reference)",
                "  Desktop: Export -> [报告预览 / 打印 PDF]",
                "",
                "Installer:",
                "  desktop/src-tauri/target/release/bundle/nsis/PlanSeed_0.1.0_x64-setup.exe",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(f"OK: wrote {readme.relative_to(ROOT)}")
    print("== done ==")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
