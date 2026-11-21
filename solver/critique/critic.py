"""DesignCritic — 只读评价证据，产出可执行 IntentPatch 建议。"""

from __future__ import annotations

from packages.schema.intent_patch import (
    DesignIntentPatch,
    IntentChange,
    IntentChangeAction,
    IntentPriority,
    IntentRegenerationMode,
)
from packages.schema.layout import LayoutCandidate
from packages.schema.program import DesignProgram


def critique_candidate(
    program: DesignProgram,
    candidate: LayoutCandidate,
) -> dict:
    """
    返回严重度分组 + 建议补丁列表（不执行）。

    证据来源：metrics / findings / Gate；不另造评分体系。
    """
    must_fix: list[dict] = []
    should_improve: list[dict] = []
    preference: list[dict] = []
    suggested_patches: list[DesignIntentPatch] = []

    gate_pass = bool(candidate.metrics.get("architectural_gate_pass", True))
    blockers = int(candidate.metrics.get("architectural_gate_blocker_count") or 0)
    priv = int(candidate.metrics.get("private_through_count") or 0)

    if not gate_pass or blockers > 0:
        must_fix.append(
            {
                "code": "architectural_gate",
                "message": f"Architectural Gate 未通过（blockers={blockers}）",
                "evidence": {
                    "architectural_gate_pass": gate_pass,
                    "architectural_gate_blocker_count": blockers,
                },
            }
        )

    if priv > 0:
        must_fix.append(
            {
                "code": "private_through",
                "message": f"存在 {priv} 条穿卧室通行路径",
                "evidence": {"private_through_count": priv},
            }
        )
        suggested_patches.append(
            DesignIntentPatch(
                target_candidate=candidate.id,
                preserve=[],
                changes=[
                    IntentChange(
                        action=IntentChangeAction.AVOID_PRIVATE_THROUGH,
                        priority=IntentPriority.REQUIRED,
                    )
                ],
                regeneration=IntentRegenerationMode.PARTIAL,
                source="critic",
                confidence=0.85,
                raw_utterance_ref=f"critic:{candidate.id}:private_through",
            )
        )

    evaluation = getattr(candidate, "evaluation", None)
    findings = list(getattr(evaluation, "findings", None) or []) if evaluation else []
    for f in findings:
        sev = str(getattr(f, "severity", "") or "").lower()
        item = {
            "code": getattr(f, "id", "finding"),
            "message": getattr(f, "message", "") or getattr(f, "title", ""),
            "room_ids": list(getattr(f, "room_ids", None) or []),
        }
        if sev in ("error", "blocker", "critical"):
            must_fix.append(item)
        elif sev in ("warning",):
            should_improve.append(item)
        else:
            preference.append(item)

    if candidate.validation and not candidate.validation.valid:
        for v in candidate.validation.hard_violations or []:
            must_fix.append(
                {
                    "code": getattr(v, "constraint_id", "hard"),
                    "message": getattr(v, "message", "硬约束失败"),
                    "room_ids": list(getattr(v, "room_ids", None) or []),
                }
            )

    orient = float(candidate.metrics.get("orientation_satisfaction") or 1.0)
    if orient < 0.99 and program.constraints:
        should_improve.append(
            {
                "code": "orientation",
                "message": f"朝向满足度 {orient:.2f}",
                "evidence": {"orientation_satisfaction": orient},
            }
        )

    _ = program
    return {
        "candidate_id": candidate.id,
        "must_fix": must_fix,
        "should_improve": should_improve,
        "preference": preference,
        "suggested_patches": [p.model_dump() for p in suggested_patches],
    }
