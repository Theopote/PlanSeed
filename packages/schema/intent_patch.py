"""Design Intent Patch — 针对当前方案的结构化修改意图（非整栋重写 RequirementSpec）。"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field


class IntentChangeAction(StrEnum):
    INCREASE_TARGET_AREA = "increase_target_area"
    DECREASE_TARGET_AREA = "decrease_target_area"
    SET_ORIENTATION_PREFERENCE = "set_orientation_preference"
    AVOID_PRIVATE_THROUGH = "avoid_private_through"
    REQUIRE_ADJACENCY = "require_adjacency"
    AVOID_ADJACENCY = "avoid_adjacency"
    REDUCE_CORRIDOR_PREFERENCE = "reduce_corridor_preference"


class IntentPriority(StrEnum):
    REQUIRED = "required"
    PREFERRED = "preferred"


class IntentRegenerationMode(StrEnum):
    PARTIAL = "partial"
    FULL = "full"


class IntentChange(BaseModel):
    """单条可执行修改；禁止自由文本 action。"""

    action: IntentChangeAction
    target: str | None = Field(
        default=None,
        description="room_id 或语义角色（living/master_bedroom/…）",
    )
    partner: str | None = Field(
        default=None,
        description="邻接类动作的另一端 room_id / 角色",
    )
    value: str | float | None = Field(
        default=None,
        description="如朝向 south、面积增量比例 0.15",
    )
    priority: IntentPriority = IntentPriority.PREFERRED


class DesignIntentPatch(BaseModel):
    """自然语言 → 结构化补丁；LLM 不得直接输出坐标。"""

    target_candidate: str = Field(
        default="selected",
        description="'selected' 或具体 candidate id",
    )
    preserve: list[str] = Field(
        default_factory=list,
        description="须锁定的 room_id / 角色",
    )
    changes: list[IntentChange] = Field(default_factory=list)
    regeneration: IntentRegenerationMode = IntentRegenerationMode.PARTIAL
    source: str = Field(default="user", description="user | critic | copilot")
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    raw_utterance_ref: str | None = Field(
        default=None,
        description="原始话语引用 / 哈希，可追溯",
    )


class IntentPatchPreview(BaseModel):
    """补丁应用预览（确认前展示）。"""

    patch: DesignIntentPatch
    locked_rooms: list[str] = Field(default_factory=list)
    mutable_rooms: list[str] = Field(default_factory=list)
    program_deltas: list[str] = Field(
        default_factory=list,
        description="人类可读的 program/constraint 变更摘要",
    )
    warnings: list[str] = Field(default_factory=list)
    ok: bool = True


class IntentPatchDraft(BaseModel):
    """LLM 草稿；经 Gate 后升格为 DesignIntentPatch。"""

    preserve: list[str] = Field(default_factory=list)
    changes: list[dict[str, Any]] = Field(default_factory=list)
    regeneration: Literal["partial", "full"] = "partial"
    notes: str | None = None
