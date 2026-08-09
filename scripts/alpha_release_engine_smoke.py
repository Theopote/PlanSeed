"""Alpha v0.1 — 对运行中引擎做 Generate / PNG / SVG / .planseed 冒烟。

用法（桌面端或 sidecar 已听端口）::

    uv run python scripts/alpha_release_engine_smoke.py

环境变量：PLANSEED_HOST（默认 127.0.0.1）· PLANSEED_PORT（默认 8787）
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any


def _base() -> str:
    host = os.environ.get("PLANSEED_HOST", "127.0.0.1")
    port = os.environ.get("PLANSEED_PORT", "8787")
    return f"http://{host}:{port}"


def _req(
    method: str,
    path: str,
    *,
    body: dict[str, Any] | None = None,
    raw: bytes | None = None,
    content_type: str | None = None,
) -> tuple[int, dict[str, str], bytes]:
    headers: dict[str, str] = {}
    data: bytes | None = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    elif raw is not None:
        data = raw
        headers["Content-Type"] = content_type or "application/octet-stream"
    request = urllib.request.Request(
        f"{_base()}{path}",
        data=data,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as resp:
            return resp.status, {k.lower(): v for k, v in resp.headers.items()}, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, {k.lower(): v for k, v in e.headers.items()}, e.read()


def _ok(cond: bool, msg: str) -> None:
    if not cond:
        raise SystemExit(f"FAIL: {msg}")
    print(f"OK: {msg}")


def main() -> int:
    print(f"== Alpha release engine smoke @ {_base()} ==")

    status, _, raw = _req("GET", "/api/health")
    _ok(status == 200, "health HTTP 200")
    health = json.loads(raw)
    _ok(health.get("ok") is True, "health.ok")
    _ok(health.get("service") == "planseed", "health.service")

    status, _, raw = _req(
        "POST",
        "/api/generate",
        body={"use_benchmark": True, "candidate_count": 8, "return_top_k": 2},
    )
    _ok(status == 200, f"generate HTTP 200 (got {status})")
    gen = json.loads(raw)
    cands = gen.get("candidates") or []
    _ok(len(cands) >= 1, "generate has candidates")
    c0 = cands[0]
    prov = c0.get("provenance") or {}
    _ok(prov.get("generator_strategy") == "guillotine", "default generator=guillotine")
    _ok(
        prov.get("selection_strategy") in ("axis-diverse", "axis"),
        f"default selection axis-ish (got {prov.get('selection_strategy')!r})",
    )
    _ok(prov.get("geometry_backend") in (None, "rect"), "geometry rect/default")

    # 落库以便走 Final Export gate
    payload = {
        "form": {"width": 11, "depth": 13},
        "program": gen.get("program"),
        "candidates": [
            {
                **{k: c0[k] for k in c0 if k != "placements"},
                "placements": c0.get("placements") or [],
                "revision_status": c0.get("revision_status") or "generated",
                "revision_id": c0.get("revision_id")
                or f"{c0.get('id', 'c')}:gen:smoke",
                "svg": c0.get("svg")
                or (
                    '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="80">'
                    '<rect width="100" height="80" fill="#eee"/></svg>'
                ),
                "floor_svgs": c0.get("floor_svgs")
                or {
                    "F1": (
                        '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="80">'
                        '<rect width="100" height="80" fill="#ddd"/></svg>'
                    )
                },
            }
        ],
        "selected_id": c0.get("id"),
        "schema_versions": {
            "solver_version": prov.get("solver_version"),
            "generator_strategy": prov.get("generator_strategy"),
            "generator_version": prov.get("generator_version"),
            "selection_strategy": prov.get("selection_strategy"),
            "selection_version": prov.get("selection_version"),
            "evaluation_version": prov.get("evaluation_version"),
            "assignment_strategy": prov.get("assignment_strategy"),
            "geometry_backend": prov.get("geometry_backend") or "rect",
        },
    }
    # 确保 revision 字段齐全
    cand = payload["candidates"][0]
    if not cand.get("revision_id"):
        cand["revision_id"] = f"{cand['id']}:gen:smoke"
    if not cand.get("revision_status"):
        cand["revision_status"] = "generated"

    status, _, raw = _req(
        "POST",
        "/api/projects",
        body={"name": "alpha-smoke", "payload": payload},
    )
    _ok(status == 200, f"save project (got {status}: {raw[:200]!r})")
    project = json.loads(raw)
    pid = project["id"]
    cand = project["payload"]["candidates"][0]
    cid = cand["id"]
    rid = cand["revision_id"]
    floor_id = next(iter((cand.get("floor_svgs") or {"F1": None}).keys()), "F1")

    status, headers, raw = _req(
        "POST",
        "/api/exports/png",
        body={
            "project_id": pid,
            "candidate_id": cid,
            "revision_id": rid,
            "scope": "floor",
            "floor_id": floor_id,
            "size": 2048,
        },
    )
    _ok(status == 200, f"png export (got {status}: {raw[:200]!r})")
    _ok(raw[:8] == b"\x89PNG\r\n\x1a\n", "png magic")
    _ok(
        headers.get("content-type", "").startswith("image/png"),
        "png content-type",
    )

    status, headers, raw = _req(
        "POST",
        "/api/exports/svg",
        body={
            "project_id": pid,
            "candidate_id": cid,
            "revision_id": rid,
            "scope": "floor",
            "floor_id": floor_id,
        },
    )
    _ok(status == 200, f"svg export (got {status})")
    _ok(b"<svg" in raw[:200].lower() or b"<?xml" in raw[:80], "svg body")

    status, _, pkg = _req("GET", f"/api/projects/{pid}/package")
    _ok(status == 200, "export .planseed")
    _ok(pkg[:2] == b"PK", "planseed is zip")

    status, _, raw = _req("DELETE", f"/api/projects/{pid}")
    _ok(status == 200, "delete project")

    status, _, raw = _req(
        "POST",
        "/api/projects/import",
        raw=pkg,
        content_type="application/zip",
    )
    _ok(status == 200, f"import .planseed (got {status})")
    imported = json.loads(raw)
    _ok(imported["id"] == pid, "import keeps id")
    _ok(imported["payload"]["selected_id"] == cid, "import keeps selected_id")
    iprov = imported["payload"]["candidates"][0].get("provenance") or {}
    _ok(
        iprov.get("generator_strategy") == "guillotine",
        "import keeps generator_strategy",
    )

    print("== alpha release engine smoke passed ==")
    return 0


if __name__ == "__main__":
    sys.exit(main())
