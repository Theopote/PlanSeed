"""IntentPatch LLM 草稿 — 短 Prompt + 几何 Gate；失败则由调用方回退确定性解析。"""

from __future__ import annotations

from typing import Any

from packages.llm.boundary import GeometryForbiddenError, assert_no_geometry_payload
from packages.llm.provider import LLMProvider
from packages.schema.intent_patch import IntentChangeAction, IntentPatchDraft

# 故意保持短：准确率靠确定性抽取 + Gate，不堆 few-shot
INTENT_SYSTEM_PROMPT = """你是 PlanSeed 设计意图草稿器。
只输出 JSON：{"preserve":[角色名], "changes":[{"action","target","partner","value","priority"}], "regeneration":"partial"|"full"}
action 仅限：increase_target_area|decrease_target_area|set_orientation_preference|avoid_private_through|require_adjacency|avoid_adjacency|reduce_corridor_preference
角色用英文：living|kitchen|dining|master_bedroom|secondary_bedroom|bedroom|study|garage
禁止坐标、placements、SVG、墙门几何。只根据用户原文，勿臆造未提及的房间。
"""

_ALLOWED_ACTIONS = {a.value for a in IntentChangeAction}


def gate_intent_draft(payload: dict[str, Any]) -> dict[str, Any]:
    """几何禁令 + action 白名单；返回可并入 parse_intent_patch 的 dict。"""
    assert_no_geometry_payload(payload)
    draft = IntentPatchDraft.model_validate(
        {
            "preserve": payload.get("preserve") or [],
            "changes": payload.get("changes") or [],
            "regeneration": payload.get("regeneration") or "partial",
            "notes": payload.get("notes"),
        }
    )
    clean_changes: list[dict[str, Any]] = []
    for raw in draft.changes:
        if not isinstance(raw, dict):
            continue
        action = str(raw.get("action") or "").strip()
        if action not in _ALLOWED_ACTIONS:
            continue
        clean_changes.append(
            {
                "action": action,
                "target": raw.get("target"),
                "partner": raw.get("partner"),
                "value": raw.get("value"),
                "priority": raw.get("priority") or "preferred",
            }
        )
    return {
        "preserve": [str(p) for p in draft.preserve if str(p).strip()],
        "changes": clean_changes,
        "regeneration": draft.regeneration,
    }


def fetch_intent_llm_draft(
    text: str,
    provider: LLMProvider,
) -> dict[str, Any] | None:
    """
    向 Provider 要 IntentPatchDraft；任一步失败返回 None（调用方用确定性结果）。
    """
    cleaned = (text or "").strip()
    if not cleaned:
        return None
    try:
        raw = provider.complete_json(system=INTENT_SYSTEM_PROMPT, user=cleaned)
    except Exception:  # noqa: BLE001 — Copilot 入口软降级
        return None
    if not isinstance(raw, dict):
        return None
    try:
        return gate_intent_draft(raw)
    except (GeometryForbiddenError, ValueError, TypeError):
        return None
