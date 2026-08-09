"""RequirementSpec / Draft 语义校验（第二层 Gate）。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from packages.schema.llm_contract import LLMRequirementDraft
from packages.schema.requirements import RequirementSpec

_FLOOR_ID_RE = re.compile(r"^F([1-3])$")


@dataclass(frozen=True)
class SemanticIssue:
    code: str
    message: str
    hard: bool = True


@dataclass
class SemanticValidationResult:
    issues: list[SemanticIssue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any(i.hard for i in self.issues)

    @property
    def hard_issues(self) -> list[SemanticIssue]:
        return [i for i in self.issues if i.hard]


class RequirementSemanticValidator:
    """建筑语义：楼层 id、场地、空间 id 重复等。"""

    def validate_draft(self, draft: LLMRequirementDraft) -> SemanticValidationResult:
        return self.validate_spec(draft.to_requirement_spec())

    def validate_spec(self, spec: RequirementSpec) -> SemanticValidationResult:
        out = SemanticValidationResult()
        floor_count = spec.floor_count

        if floor_count is not None and floor_count not in (1, 2, 3):
            out.issues.append(
                SemanticIssue(
                    code="req.floor_count",
                    message=f"floor_count 必须为 1–3，收到 {floor_count}",
                )
            )

        allowed_floors: set[str] | None = None
        if floor_count is not None:
            allowed_floors = {f"F{i}" for i in range(1, floor_count + 1)}

        seen_ids: set[str] = set()
        for sp in spec.spaces:
            if not (sp.name and sp.name.strip()):
                out.issues.append(
                    SemanticIssue(
                        code="req.space_name",
                        message="spaces 项 name 不能为空",
                    )
                )
            if sp.id:
                if sp.id in seen_ids:
                    out.issues.append(
                        SemanticIssue(
                            code="req.space_id_dup",
                            message=f"重复 space id：{sp.id}",
                        )
                    )
                seen_ids.add(sp.id)
            for pref in sp.floor_preference:
                m = _FLOOR_ID_RE.match(pref)
                if not m:
                    out.issues.append(
                        SemanticIssue(
                            code="req.floor_preference",
                            message=f"非法楼层偏好 {pref!r}（须 F1/F2/F3）",
                        )
                    )
                    continue
                if allowed_floors is not None and pref not in allowed_floors:
                    out.issues.append(
                        SemanticIssue(
                            code="req.floor_preference_range",
                            message=(
                                f"楼层偏好 {pref} 超出 floor_count={floor_count}"
                            ),
                        )
                    )

        if spec.site.width is not None and not (6 <= spec.site.width <= 60):
            out.issues.append(
                SemanticIssue(
                    code="req.site_width",
                    message=f"site.width 超出范围：{spec.site.width}",
                )
            )
        if spec.site.depth is not None and not (6 <= spec.site.depth <= 60):
            out.issues.append(
                SemanticIssue(
                    code="req.site_depth",
                    message=f"site.depth 超出范围：{spec.site.depth}",
                )
            )

        # relation 端点分别 soft 校验（一端幻觉不可被另一端掩盖）
        # enrich 后应用别名：入口≈门厅≈玄关
        names = {s.name for s in spec.spaces} | {
            s.id for s in spec.spaces if s.id
        }
        for rel in spec.relation_intents:
            if not names:
                continue
            if not _endpoint_resolves(rel.a, names):
                out.issues.append(
                    SemanticIssue(
                        code="req.relation_a_unknown",
                        message=f"关系意图端点 a={rel.a!r} 未匹配任何 space",
                        hard=False,
                    )
                )
            if not _endpoint_resolves(rel.b, names):
                out.issues.append(
                    SemanticIssue(
                        code="req.relation_b_unknown",
                        message=f"关系意图端点 b={rel.b!r} 未匹配任何 space",
                        hard=False,
                    )
                )

        return out


_ENDPOINT_ALIASES: dict[str, frozenset[str]] = {
    "入口": frozenset({"入口", "门厅", "玄关"}),
    "门厅": frozenset({"入口", "门厅", "玄关"}),
    "玄关": frozenset({"入口", "门厅", "玄关"}),
}


def _endpoint_resolves(endpoint: str, names: set[str]) -> bool:
    ep = (endpoint or "").strip()
    if not ep:
        return False
    if ep in names:
        return True
    aliases = _ENDPOINT_ALIASES.get(ep)
    if aliases and aliases & names:
        return True
    return False
