"""DesignFinding 构造辅助 — Phase 3.5。"""

from __future__ import annotations

from packages.schema.scoring import DesignFinding, FindingSeverity


def finding(
    *,
    id: str,
    category: str,
    severity: FindingSeverity | str,
    title: str,
    message: str,
    room_ids: list[str] | None = None,
    metric: str | None = None,
    measured_value: float | None = None,
    recommended_action: str | None = None,
) -> DesignFinding:
    sev = (
        severity
        if isinstance(severity, FindingSeverity)
        else FindingSeverity(severity)
    )
    return DesignFinding(
        id=id,
        category=category,
        severity=sev,
        title=title,
        message=message,
        room_ids=list(room_ids or []),
        metric=metric,
        measured_value=measured_value,
        recommended_action=recommended_action,
    )


def findings_to_explanations(findings: list[DesignFinding]) -> list[str]:
    """兼容旧 explanations：优先 POSITIVE，再 WARNING/PROBLEM 标题。"""
    order = {
        FindingSeverity.POSITIVE: 0,
        FindingSeverity.PROBLEM: 1,
        FindingSeverity.WARNING: 2,
        FindingSeverity.INFO: 3,
    }
    sorted_f = sorted(findings, key=lambda f: (order.get(f.severity, 9), f.id))
    out: list[str] = []
    for f in sorted_f:
        prefix = {
            FindingSeverity.POSITIVE: "+",
            FindingSeverity.PROBLEM: "!",
            FindingSeverity.WARNING: "~",
            FindingSeverity.INFO: "·",
        }.get(f.severity, "·")
        out.append(f"{prefix} [{f.category}] {f.title}")
    return out


def findings_to_warnings(findings: list[DesignFinding]) -> list[str]:
    return [
        f.message
        for f in findings
        if f.severity in (FindingSeverity.WARNING, FindingSeverity.PROBLEM)
    ]
