"""Hybrid Intent Patch 解析 — NL → DesignIntentPatch（确定性优先）。"""

from __future__ import annotations

import hashlib
import re
from typing import Any

from packages.schema.intent_patch import (
    DesignIntentPatch,
    IntentChange,
    IntentChangeAction,
    IntentPriority,
    IntentRegenerationMode,
)

# 一般语言规律（非逐案 Blind 扩 regex）
_PRESERVE_AND = re.compile(
    r"(?:保持|锁定|保留)\s*(.+?)(?:不变|位置)",
)
_LIKE_KEEP = re.compile(
    r"(?:喜欢|满意).{0,6}(?:现在的|当前的)?(.+?)[，,]?\s*(?:保持|锁定|保留)",
)
_ROOM_TOKEN = re.compile(r"客厅|起居室|厨房|餐厅|主卧(?:室)?|次卧|卧室|书房|车库")
_PRONOUN_KEEP = re.compile(r"(?:保持|锁定|保留)\s*(?:它们|它们的位置|现状|以上)")
_BIGGER = re.compile(
    r"(主卧(?:室)?|次卧|卧室|客厅|起居室|厨房|餐厅|书房|车库).{0,6}(?:大一点|更大|加大|增加面积)"
)
_SMALLER = re.compile(
    r"(主卧(?:室)?|次卧|卧室|客厅|起居室|厨房|餐厅|书房|车库).{0,6}(?:小一点|更小|缩小|减少面积)"
)
_NO_THROUGH = re.compile(
    r"(?:不要|别|避免).{0,8}(?:穿过|穿|通过).{0,8}(?:卧室|主卧|私人)",
)
_SOUTH = re.compile(r"(.+?)(?:朝南|向南|南向)")
_SHORT_CORRIDOR = re.compile(r"(?:缩短|减少|少).{0,6}走廊")

_ALIASES = {
    "客厅": "living",
    "起居室": "living",
    "厨房": "kitchen",
    "餐厅": "dining",
    "主卧": "master_bedroom",
    "主卧室": "master_bedroom",
    "次卧": "bedroom",
    "卧室": "bedroom",
    "书房": "study",
    "车库": "garage",
}


def _clean_token(raw: str) -> str:
    t = raw.strip(" 、，。；;的了和与把将希望比较")
    return _ALIASES.get(t, t)


def _tokens_from_chunk(chunk: str) -> list[str]:
    found = [_ALIASES[m.group(0)] for m in _ROOM_TOKEN.finditer(chunk)]
    if found:
        return found
    tok = _clean_token(chunk)
    return [tok] if tok and tok not in ("它们", "现状", "以上", "位置") else []


def parse_intent_patch_deterministic(
    text: str,
    *,
    target_candidate: str = "selected",
) -> DesignIntentPatch:
    """确定性抽取；无 LLM 时也可得到可用补丁。"""
    cleaned = text.strip()
    preserve: list[str] = []
    changes: list[IntentChange] = []

    # 「喜欢现在的客厅和厨房，保持它们不变」→ 从前文收房间名
    m_like = _LIKE_KEEP.search(cleaned)
    if m_like:
        preserve.extend(_tokens_from_chunk(m_like.group(1)))
    if _PRONOUN_KEEP.search(cleaned) and not preserve:
        # 回退：全文已点名的房间作 preserve
        preserve.extend(_tokens_from_chunk(cleaned.split("保持")[0]))

    m = _PRESERVE_AND.search(cleaned)
    if m:
        chunk = m.group(1)
        if chunk.strip() not in ("它们", "它们的位置", "现状", "以上"):
            for part in re.split(r"[和与、,/]", chunk):
                preserve.extend(_tokens_from_chunk(part))

    for m in _BIGGER.finditer(cleaned):
        tok = _clean_token(m.group(1))
        if tok:
            changes.append(
                IntentChange(
                    action=IntentChangeAction.INCREASE_TARGET_AREA,
                    target=tok,
                    value=0.15,
                    priority=IntentPriority.PREFERRED,
                )
            )

    for m in _SMALLER.finditer(cleaned):
        tok = _clean_token(m.group(1))
        if tok:
            changes.append(
                IntentChange(
                    action=IntentChangeAction.DECREASE_TARGET_AREA,
                    target=tok,
                    value=0.15,
                    priority=IntentPriority.PREFERRED,
                )
            )

    if _NO_THROUGH.search(cleaned):
        changes.append(
            IntentChange(
                action=IntentChangeAction.AVOID_PRIVATE_THROUGH,
                priority=IntentPriority.REQUIRED,
            )
        )

    for m in _SOUTH.finditer(cleaned):
        tok = _clean_token(m.group(1).split("希望")[-1].split("尽量")[-1])
        if tok:
            changes.append(
                IntentChange(
                    action=IntentChangeAction.SET_ORIENTATION_PREFERENCE,
                    target=tok,
                    value="south",
                    priority=IntentPriority.PREFERRED,
                )
            )

    if _SHORT_CORRIDOR.search(cleaned):
        changes.append(
            IntentChange(
                action=IntentChangeAction.REDUCE_CORRIDOR_PREFERENCE,
                priority=IntentPriority.PREFERRED,
            )
        )

    # 去重 preserve
    seen: set[str] = set()
    preserve_u: list[str] = []
    for p in preserve:
        if p not in seen:
            seen.add(p)
            preserve_u.append(p)

    ref = hashlib.sha1(cleaned.encode("utf-8")).hexdigest()[:12]
    return DesignIntentPatch(
        target_candidate=target_candidate,
        preserve=preserve_u,
        changes=changes,
        regeneration=IntentRegenerationMode.PARTIAL,
        source="user",
        confidence=0.75 if changes or preserve_u else 0.4,
        raw_utterance_ref=ref,
    )


def parse_intent_patch(
    text: str,
    *,
    target_candidate: str = "selected",
    llm_draft: dict[str, Any] | None = None,
) -> DesignIntentPatch:
    """
    Hybrid：确定性抽取为主；若提供 llm_draft 则合并（draft 不得含坐标）。
    """
    base = parse_intent_patch_deterministic(text, target_candidate=target_candidate)
    if not llm_draft:
        return base

    preserve = list(base.preserve)
    for p in llm_draft.get("preserve") or []:
        tok = _clean_token(str(p))
        if tok and tok not in preserve:
            preserve.append(tok)

    changes = list(base.changes)
    for raw in llm_draft.get("changes") or []:
        if not isinstance(raw, dict):
            continue
        action = raw.get("action")
        try:
            act = IntentChangeAction(str(action))
        except ValueError:
            continue
        changes.append(
            IntentChange(
                action=act,
                target=raw.get("target"),
                partner=raw.get("partner"),
                value=raw.get("value"),
                priority=IntentPriority(
                    str(raw.get("priority") or IntentPriority.PREFERRED.value)
                ),
            )
        )

    regen = str(llm_draft.get("regeneration") or base.regeneration.value)
    try:
        mode = IntentRegenerationMode(regen)
    except ValueError:
        mode = base.regeneration

    return base.model_copy(
        update={
            "preserve": preserve,
            "changes": changes,
            "regeneration": mode,
            "confidence": min(0.95, base.confidence + 0.1),
        }
    )
