"""DesignConversation — 多轮设计协作上下文（持久化）。"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class ConversationRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ConversationMessage(BaseModel):
    id: str
    role: ConversationRole
    content: str
    created_at: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )
    meta: dict[str, Any] = Field(default_factory=dict)


class DesignConversationState(BaseModel):
    """跨轮保留：选中候选、策略、补丁与确认事项。"""

    project_id: str
    messages: list[ConversationMessage] = Field(default_factory=list)
    selected_candidate_id: str | None = None
    active_strategy_id: str | None = None
    applied_patch_ids: list[str] = Field(default_factory=list)
    confirmed_facts: list[str] = Field(default_factory=list)
    locked_room_ids: list[str] = Field(default_factory=list)
    updated_at: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )
