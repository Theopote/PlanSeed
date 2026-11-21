"""从桌面 CandidatePayload 重建 LayoutCandidate（Copilot 契约）。"""

from __future__ import annotations

from typing import Any

from packages.schema.layout import (
    CandidateValidation,
    FloorLayout,
    LayoutCandidate,
    PlacementRect,
    PlacementSource,
    RoomPlacement,
    ZonePlacement,
)
from packages.schema.provenance import SolverProvenance
from packages.schema.scoring import DesignScore
from pydantic import ValidationError

from backend.schemas.api import CandidatePayload, RoomPlacementPayload


class CandidateRebuildError(ValueError):
    """候选无法重建为完整几何。"""


def _placements_by_floor(
    placements: list[RoomPlacementPayload],
) -> list[FloorLayout]:
    by_floor: dict[str, list[RoomPlacement]] = {}
    for p in placements:
        by_floor.setdefault(p.floor_id, []).append(
            RoomPlacement(
                room_id=p.room_id,
                floor_id=p.floor_id,
                rect=PlacementRect(
                    x=p.x,
                    y=p.y,
                    width=p.width,
                    depth=p.depth,
                ),
                source=PlacementSource.PROGRAM,
            )
        )
    return [
        FloorLayout(floor_id=fid, placements=rooms)
        for fid, rooms in sorted(by_floor.items())
    ]


def _zones_from_payload(payload: CandidatePayload) -> list[ZonePlacement]:
    return [
        ZonePlacement(
            id=z.id,
            zone=z.zone,
            kind=z.kind,
            floor_id=z.floor_id,
            rect=PlacementRect(
                x=z.x,
                y=z.y,
                width=z.width,
                depth=z.depth,
            ),
            room_ids=list(z.room_ids),
        )
        for z in payload.zones
    ]


def _validation_from_payload(raw: dict[str, Any] | None) -> CandidateValidation | None:
    if not raw:
        return None
    try:
        return CandidateValidation.model_validate(raw)
    except ValidationError:
        return None


def layout_candidate_from_copilot_payload(raw: dict[str, Any]) -> LayoutCandidate:
    """
    接受桌面 CandidatePayload 或完整 LayoutCandidate JSON。

    桌面侧房间在扁平 placements，评价在 design_score；
    Solver 需要 floors[].placements 与 evaluation。
    几何缺失时显式失败，禁止靠 Pydantic 默认空列表悄悄通过。
    """
    if not isinstance(raw, dict):
        raise CandidateRebuildError("candidate 必须是对象")

    floors_raw = raw.get("floors")
    if isinstance(floors_raw, list) and floors_raw:
        data = dict(raw)
        if data.get("evaluation") is None and data.get("design_score") is not None:
            data["evaluation"] = data["design_score"]
        try:
            cand = LayoutCandidate.model_validate(data)
        except ValidationError as exc:
            raise CandidateRebuildError(f"LayoutCandidate 无效：{exc}") from exc
    else:
        try:
            payload = CandidatePayload.model_validate(raw)
        except ValidationError as exc:
            raise CandidateRebuildError(f"CandidatePayload 无效：{exc}") from exc
        if not payload.placements:
            raise CandidateRebuildError(
                "candidate 缺少 placements，无法重建楼层几何"
            )
        evaluation: DesignScore | None = payload.design_score
        score = payload.score
        if score is None and evaluation is not None:
            score = evaluation.total_score
        provenance = None
        if payload.provenance is not None:
            provenance = SolverProvenance.model_validate(
                payload.provenance.model_dump()
            )
        metrics = dict(payload.metrics or {})
        if payload.requirement_revision_id:
            metrics.setdefault(
                "requirement_revision_id", payload.requirement_revision_id
            )
        cand = LayoutCandidate(
            id=payload.id,
            seed=payload.seed,
            floors=_placements_by_floor(payload.placements),
            zone_placements=_zones_from_payload(payload),
            evaluation=evaluation,
            score=score,
            provenance=provenance,
            variant_parent_id=payload.variant_parent_id,
            variant_generation=payload.variant_generation,
            lock_snapshot_id=payload.lock_snapshot_id,
            metrics=metrics,
            validation=_validation_from_payload(payload.validation),
        )

    if not cand.floors or not any(fl.placements for fl in cand.floors):
        raise CandidateRebuildError("candidate 无有效楼层/房间几何")
    return cand
