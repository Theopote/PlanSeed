"""LLMRequirementDraft → Ollama / 结构化输出用的 JSON Schema。"""

from __future__ import annotations

from typing import Any

from packages.schema.llm_contract import LLMRequirementDraft


def draft_json_schema() -> dict[str, Any]:
    """
    供 Ollama `format=` 的 JSON Schema。

    形状对齐 LLMRequirementDraft（known / assumptions / unknowns）。
    """
    return LLMRequirementDraft.model_json_schema()
