"""会话级几何变更 — Phase 4.3；不进 RequirementSpec。"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from packages.schema.layout import PlacementRect


class MutationKind(StrEnum):
    MOVE = "move"
    RESIZE = "resize"
    LOCK = "lock"
    UNLOCK = "unlock"


class MutationSource(StrEnum):
    POINTER = "pointer"
    INSPECTOR = "inspector"
    SYSTEM = "system"


class GeometryMutation(BaseModel):
    """Proposed 或已提交的几何变更。"""

    kind: MutationKind
    room_id: str | None = None
    floor_id: str
    before: PlacementRect | None = None
    proposed: PlacementRect | None = None
    source: MutationSource = MutationSource.POINTER


class MutationReject(BaseModel):
    code: str
    message: str


class MutationPreviewResult(BaseModel):
    """Authority 预览结果；ok 才可 Commit。warnings 为 soft（不阻挡 Commit）。"""

    ok: bool
    reasons: list[MutationReject] = Field(default_factory=list)
    warnings: list[MutationReject] = Field(default_factory=list)
    snapped: PlacementRect | None = None
    conflict_room_ids: list[str] = Field(default_factory=list)
