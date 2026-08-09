"""DesignScore + DesignFinding → 报告层可读评价（确定性 Presenter）。

禁止 LLM 重写优缺点；只消费已有 DesignFinding / 七轴分数。
"""

from __future__ import annotations

from dataclasses import dataclass

from packages.schema.report_i18n import ReportLocale, normalize_report_locale, tr
from packages.schema.scoring import DesignFinding, DesignScore, FindingSeverity


@dataclass(frozen=True)
class AxisPresentation:
    axis_key: str
    label: str
    score: float
    band_key: str
    band_label: str


@dataclass(frozen=True)
class EvaluationPresentation:
    axes: list[AxisPresentation]
    strengths: list[DesignFinding]
    concerns: list[DesignFinding]
    executive_summary: str


_AXIS_FIELDS: tuple[tuple[str, str], ...] = (
    ("axis.program", "program_score"),
    ("axis.spatial", "spatial_score"),
    ("axis.circulation", "circulation_score"),
    ("axis.privacy", "privacy_score"),
    ("axis.environment", "environment_score"),
    ("axis.technical", "technical_score"),
    ("axis.robustness", "robustness_score"),
)


def score_band_key(score: float) -> str:
    """分数 → 档位 key（良好 / 尚可 / 可改善）。"""
    if score >= 80:
        return "band.good"
    if score >= 70:
        return "band.fair"
    return "band.improve"


def present_evaluation(
    *,
    locale: ReportLocale | str,
    design_score: DesignScore,
    findings: list[DesignFinding],
    key_intents: list[str],
    candidate_label: str,
) -> EvaluationPresentation:
    loc = normalize_report_locale(locale)
    axes: list[AxisPresentation] = []
    for axis_key, field in _AXIS_FIELDS:
        val = float(getattr(design_score, field))
        band = score_band_key(val)
        axes.append(
            AxisPresentation(
                axis_key=axis_key,
                label=tr(loc, axis_key),
                score=val,
                band_key=band,
                band_label=tr(loc, band),
            )
        )

    strengths = _pick_findings(
        findings,
        preferred=(FindingSeverity.POSITIVE, FindingSeverity.INFO),
        limit=3,
    )
    concerns = _pick_findings(
        findings,
        preferred=(FindingSeverity.PROBLEM, FindingSeverity.WARNING),
        limit=3,
    )

    total = float(design_score.total_score)
    summary = _executive_summary(
        loc,
        total=total,
        key_intents=key_intents,
        candidate_label=candidate_label,
        strengths=strengths,
        concerns=concerns,
    )
    return EvaluationPresentation(
        axes=axes,
        strengths=strengths,
        concerns=concerns,
        executive_summary=summary,
    )


def _pick_findings(
    findings: list[DesignFinding],
    *,
    preferred: tuple[FindingSeverity, ...],
    limit: int,
) -> list[DesignFinding]:
    ranked: list[DesignFinding] = []
    for sev in preferred:
        ranked.extend(f for f in findings if f.severity == sev)
    return ranked[:limit]


def _executive_summary(
    locale: ReportLocale,
    *,
    total: float,
    key_intents: list[str],
    candidate_label: str,
    strengths: list[DesignFinding],
    concerns: list[DesignFinding],
) -> str:
    band = tr(locale, score_band_key(total))
    intent_hint = "、".join(key_intents[:3]) if key_intents else ""
    if concerns:
        concern_hint = concerns[0].title
        if intent_hint:
            return tr(
                locale,
                "summary.with_concern",
                label=candidate_label,
                score=f"{total:.0f}",
                band=band,
                intents=intent_hint,
                concern=concern_hint,
            )
        return tr(
            locale,
            "summary.with_concern_no_intent",
            label=candidate_label,
            score=f"{total:.0f}",
            band=band,
            concern=concern_hint,
        )
    if strengths and intent_hint:
        return tr(
            locale,
            "summary.with_strength",
            label=candidate_label,
            score=f"{total:.0f}",
            band=band,
            intents=intent_hint,
            strength=strengths[0].title,
        )
    if intent_hint:
        return tr(
            locale,
            "summary.basic",
            label=candidate_label,
            score=f"{total:.0f}",
            band=band,
            intents=intent_hint,
        )
    return tr(
        locale,
        "summary.minimal",
        label=candidate_label,
        score=f"{total:.0f}",
        band=band,
    )
