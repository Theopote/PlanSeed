"""轻量布局签名 — diversity / similarity，不复制 DesignProgram。"""

from __future__ import annotations

from pydantic import BaseModel, Field

from packages.schema.layout import LayoutCandidate, PlacementSource


class NormalizedRoomRect(BaseModel):
    room_id: str
    floor_id: str
    x: float
    y: float
    width: float
    depth: float


class LayoutSignature(BaseModel):
    """
    Phase 1.5：归一化房间矩形 + core 区位。

    坐标相对 buildable：x/width ÷ W，y/depth ÷ D。
    """

    floor_count: int
    rooms: list[NormalizedRoomRect] = Field(default_factory=list)
    core_placement: str | None = None
    core_x: float | None = None
    core_y: float | None = None
    core_width: float | None = None
    core_depth: float | None = None


def build_layout_signature(
    candidate: LayoutCandidate,
    *,
    buildable_width: float,
    buildable_depth: float,
) -> LayoutSignature:
    bw = max(buildable_width, 1e-9)
    bd = max(buildable_depth, 1e-9)
    rooms: list[NormalizedRoomRect] = []
    core_placement: str | None = None
    core_x = core_y = core_w = core_d = None

    for fl in candidate.floors:
        if core_placement is None and fl.core_placement:
            core_placement = fl.core_placement
        if core_x is None and fl.stair_x0 is not None and fl.stair_x1 is not None:
            core_x = fl.stair_x0 / bw
            core_y = (fl.stair_y0 or 0.0) / bd
            core_w = (fl.stair_x1 - fl.stair_x0) / bw
            core_d = ((fl.stair_y1 or 0.0) - (fl.stair_y0 or 0.0)) / bd

        for p in fl.placements:
            if p.source != PlacementSource.PROGRAM:
                continue
            rooms.append(
                NormalizedRoomRect(
                    room_id=p.room_id,
                    floor_id=fl.floor_id,
                    x=p.rect.x / bw,
                    y=p.rect.y / bd,
                    width=p.rect.width / bw,
                    depth=p.rect.depth / bd,
                )
            )

    rooms.sort(key=lambda r: (r.floor_id, r.room_id))
    return LayoutSignature(
        floor_count=len(candidate.floors),
        rooms=rooms,
        core_placement=core_placement,
        core_x=core_x,
        core_y=core_y,
        core_width=core_w,
        core_depth=core_d,
    )


def signature_similarity(a: LayoutSignature, b: LayoutSignature) -> float:
    """两签名相似度 [0, 1]；基于归一化 L1。"""
    if a.floor_count != b.floor_count:
        return 0.0

    map_a = {(r.floor_id, r.room_id): r for r in a.rooms}
    map_b = {(r.floor_id, r.room_id): r for r in b.rooms}
    keys = set(map_a) | set(map_b)
    if not keys:
        return 1.0

    diffs: list[float] = []
    for key in keys:
        ra, rb = map_a.get(key), map_b.get(key)
        if ra is None or rb is None:
            diffs.append(1.0)
            continue
        diffs.append(
            abs(ra.x - rb.x)
            + abs(ra.y - rb.y)
            + abs(ra.width - rb.width)
            + abs(ra.depth - rb.depth)
        )

    if a.core_x is not None and b.core_x is not None:
        diffs.append(
            abs((a.core_x or 0) - (b.core_x or 0))
            + abs((a.core_y or 0) - (b.core_y or 0))
            + abs((a.core_width or 0) - (b.core_width or 0))
            + abs((a.core_depth or 0) - (b.core_depth or 0))
        )
    elif a.core_placement != b.core_placement:
        diffs.append(1.0)

    avg = sum(diffs) / len(diffs)
    return max(0.0, 1.0 - avg / 2.0)
