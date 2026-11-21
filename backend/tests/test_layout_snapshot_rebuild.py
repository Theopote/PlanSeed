"""layout_snapshot 优先重建，保留 GENERATED 走廊 source。"""

from __future__ import annotations

from backend.main import create_app
from backend.services.candidate_rebuild import layout_candidate_from_copilot_payload
from fastapi.testclient import TestClient
from packages.schema.layout import PlacementSource


def test_generate_embeds_layout_snapshot_and_rebuild_preserves_source():
    client = TestClient(create_app())
    gen = client.post(
        "/api/generate",
        json={"use_benchmark": True, "candidate_count": 4, "return_top_k": 1},
    )
    assert gen.status_code == 200, gen.text
    cand = gen.json()["candidates"][0]
    snap = cand.get("layout_snapshot")
    assert isinstance(snap, dict)
    assert snap.get("floors")

    # 去掉扁平 floors 顶层，强制走 snapshot
    raw = {k: v for k, v in cand.items() if k != "floors"}
    rebuilt = layout_candidate_from_copilot_payload(raw)
    assert rebuilt.floors
    sources = {
        p.source
        for fl in rebuilt.floors
        for p in fl.placements
        if str(p.room_id).startswith("circ-")
    }
    assert PlacementSource.GENERATED in sources or not sources
    # 有走廊时须保留 GENERATED；无走廊也允许（布局碰巧无 circ）
    if any(
        str(p.room_id).startswith("circ-")
        for fl in rebuilt.floors
        for p in fl.placements
    ):
        assert PlacementSource.GENERATED in sources
