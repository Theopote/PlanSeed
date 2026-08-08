"""候选方案确定性比较 — 由 evaluation / findings 差分，不用 LLM。"""

from __future__ import annotations

from dataclasses import dataclass, field

from packages.schema.scoring import DesignEvaluation, DesignFinding

# 轴分差 >= 此值才记为「优势」
AXIS_MARGIN = 3.0

AXIS_SPECS: tuple[tuple[str, str, str], ...] = (
    ("total_score", "Total", "综合得分更高"),
    ("program_score", "Program", "空间清单 / 面积 / 邻接更贴合"),
    ("spatial_score", "Spatial", "比例与紧凑度更好"),
    ("circulation_score", "Circulation", "交通更直接 / 可达更好"),
    ("privacy_score", "Privacy", "私密过渡更好"),
    ("environment_score", "Environment", "朝向 / 外墙更优"),
    ("technical_score", "Technical", "楼梯 / 湿区 / 入口更稳"),
    ("robustness_score", "Robustness", "更少 repair、布局更稳"),
)


@dataclass
class AxisCompareRow:
    key: str
    label: str
    score_a: float
    score_b: float


@dataclass
class CandidateComparison:
    label_a: str
    label_b: str
    rows: list[AxisCompareRow] = field(default_factory=list)
    advantages_a: list[str] = field(default_factory=list)
    advantages_b: list[str] = field(default_factory=list)


def _axis_value(ev: DesignEvaluation, key: str) -> float:
    return float(getattr(ev, key, 0.0) or 0.0)


def _finding_bullet(f: DesignFinding) -> str:
    text = (f.title or f.message or f.id).strip()
    return text


def compare_evaluations(
    eval_a: DesignEvaluation,
    eval_b: DesignEvaluation,
    *,
    label_a: str = "A",
    label_b: str = "B",
    axis_margin: float = AXIS_MARGIN,
) -> CandidateComparison:
    """比较两套 DesignEvaluation，产出对照表与双方优势。"""
    rows: list[AxisCompareRow] = []
    adv_a: list[str] = []
    adv_b: list[str] = []

    for key, label, reason in AXIS_SPECS:
        sa = _axis_value(eval_a, key)
        sb = _axis_value(eval_b, key)
        rows.append(AxisCompareRow(key=key, label=label, score_a=sa, score_b=sb))
        if key == "total_score":
            continue
        delta = sa - sb
        if delta >= axis_margin:
            adv_a.append(f"{reason}（{label} {sa:.0f} vs {sb:.0f}）")
        elif delta <= -axis_margin:
            adv_b.append(f"{reason}（{label} {sb:.0f} vs {sa:.0f}）")

    pos_a = {
        f.id: _finding_bullet(f)
        for f in eval_a.findings
        if f.severity.value == "positive" or str(f.severity) == "positive"
    }
    pos_b = {
        f.id: _finding_bullet(f)
        for f in eval_b.findings
        if f.severity.value == "positive" or str(f.severity) == "positive"
    }
    for fid, text in pos_a.items():
        if fid not in pos_b and text:
            adv_a.append(text)
    for fid, text in pos_b.items():
        if fid not in pos_a and text:
            adv_b.append(text)

    # 对方独有 problem → 己方相对优势（简短）
    prob_a = {f.id for f in eval_a.findings if str(f.severity) == "problem"}
    prob_b = {f.id for f in eval_b.findings if str(f.severity) == "problem"}
    for f in eval_b.findings:
        if str(f.severity) == "problem" and f.id not in prob_a:
            title = _finding_bullet(f)
            if title:
                adv_a.append(f"避免：{title}")
    for f in eval_a.findings:
        if str(f.severity) == "problem" and f.id not in prob_b:
            title = _finding_bullet(f)
            if title:
                adv_b.append(f"避免：{title}")

    # 去重保序
    def _uniq(items: list[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for x in items:
            if x in seen:
                continue
            seen.add(x)
            out.append(x)
        return out[:8]

    return CandidateComparison(
        label_a=label_a,
        label_b=label_b,
        rows=rows,
        advantages_a=_uniq(adv_a),
        advantages_b=_uniq(adv_b),
    )
