"""LLMProvider 抽象 — 业务层不依赖具体后端。"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class LLMProvider(Protocol):
    """
    结构化完成接口。

    实现须返回可 JSON 序列化的 dict（LLMRequirementDraft 形状）。
    禁止在实现内直接调用 solver / 写几何。
    """

    def complete_json(
        self,
        *,
        system: str,
        user: str,
    ) -> dict[str, Any]:
        """给定 system/user 提示，返回 JSON 对象。"""
        ...
