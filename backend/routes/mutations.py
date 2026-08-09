"""POST /api/mutations/preview|revalidate — Python Geometry Mutation Authority。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from packages.schema.layout import (
    PlacementRect,
    PlacementSource,
    RoomPlacement,
    ZonePlacement,
)
from packages.schema.locks import LayoutLocks
from packages.schema.mutation import GeometryMutation, MutationPreviewResult
from packages.schema.requirements import RequirementSpec
from pydantic import BaseModel, Field
from solver.mutation import preview_mutation, revalidate_candidate

from backend.schemas.api import (
    CandidatePayload,
    GenerateRequest,
    MutationRecordPayload,
    RoomPlacementPayload,
    ZonePlacementPayload,
)
from backend.services.generation import resolve_solve_input
from backend.services.serialization import make_revision_id, serialize_candidate

router = APIRouter(tags=["mutations"])


class MutationPreviewRequest(BaseModel):
    """与 generate 相同方式解析 DesignProgram；placements 为当前会话几何。"""

    use_benchmark: bool = False
    requirements: RequirementSpec | None = None
    placements: list[RoomPlacementPayload] = Field(default_factory=list)
    locks: LayoutLocks = Field(default_factory=LayoutLocks)
    mutation: GeometryMutation
    snap_module: float | None = Field(default=None, gt=0)


class MutationRevalidateRequest(BaseModel):
    """对 dirty draft 重算 openings / access / evaluation（不改用户几何）。"""

    use_benchmark: bool = False
    requirements: RequirementSpec | None = None
    placements: list[RoomPlacementPayload] = Field(default_factory=list)
    locks: LayoutLocks = Field(default_factory=LayoutLocks)
    zones: list[ZonePlacementPayload] = Field(default_factory=list)
    candidate_id: str = "revalidated"
    seed: int = 0
    label_index: int = Field(default=0, ge=0, le=25)
    variant_parent_id: str | None = None
    variant_generation: int = Field(default=0, ge=0)
    lock_snapshot_id: str | None = None
    mutations: list[MutationRecordPayload] = Field(default_factory=list)
    revision_parent_id: str | None = None


def _to_room_placements(rows: list[RoomPlacementPayload]) -> list[RoomPlacement]:
    out: list[RoomPlacement] = []
    for p in rows:
        source = (
            PlacementSource.GENERATED
            if p.room_id.startswith("stair-") or p.room_id.startswith("circ-")
            else PlacementSource.PROGRAM
        )
        out.append(
            RoomPlacement(
                room_id=p.room_id,
                floor_id=p.floor_id,
                rect=PlacementRect(
                    x=p.x,
                    y=p.y,
                    width=p.width,
                    depth=p.depth,
                ),
                source=source,
                name=p.room_id,
            )
        )
    return out


def _to_zone_placements(rows: list[ZonePlacementPayload]) -> list[ZonePlacement]:
    out: list[ZonePlacement] = []
    for z in rows:
        kind = z.kind or z.zone
        out.append(
            ZonePlacement(
                id=z.id,
                zone=z.zone,
                kind=kind,
                floor_id=z.floor_id,
                rect=PlacementRect(
                    x=z.x, y=z.y, width=z.width, depth=z.depth
                ),
                room_ids=list(z.room_ids),
            )
        )
    return out


@router.post("/api/mutations/preview", response_model=MutationPreviewResult)
def mutations_preview(body: MutationPreviewRequest) -> MutationPreviewResult:
    if not body.placements:
        raise HTTPException(status_code=400, detail="placements 不能为空")
    program = resolve_solve_input(
        GenerateRequest(
            use_benchmark=body.use_benchmark,
            requirements=body.requirements,
        )
    ).program
    return preview_mutation(
        program=program,
        placements=_to_room_placements(body.placements),
        locks=body.locks,
        mutation=body.mutation,
        snap_module=body.snap_module,
    )


@router.post("/api/mutations/revalidate", response_model=CandidatePayload)
def mutations_revalidate(body: MutationRevalidateRequest) -> CandidatePayload:
    if not body.placements:
        raise HTTPException(status_code=400, detail="placements 不能为空")
    program = resolve_solve_input(
        GenerateRequest(
            use_benchmark=body.use_benchmark,
            requirements=body.requirements,
        )
    ).program
    cand = revalidate_candidate(
        program=program,
        placements=_to_room_placements(body.placements),
        locks=body.locks,
        candidate_id=body.candidate_id,
        seed=body.seed,
        zones=_to_zone_placements(body.zones),
        variant_parent_id=body.variant_parent_id,
        variant_generation=body.variant_generation,
        lock_snapshot_id=body.lock_snapshot_id,
    )
    payload = serialize_candidate(program, cand, body.label_index)
    return payload.model_copy(
        update={
            "revision_status": "validated",
            "revision_id": make_revision_id(body.candidate_id, kind="val"),
            "revision_parent_id": body.revision_parent_id or body.candidate_id,
            "mutations": list(body.mutations),
        }
    )
