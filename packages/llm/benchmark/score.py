"""Requirement Benchmark 评分（字段准确率 + 反幻觉）。"""

from __future__ import annotations

from dataclasses import dataclass, field

from packages.llm.benchmark.cases import ExpectKnown, RequirementBenchmarkCase
from packages.schema.requirements import RequirementSpec

_FIELD_LABELS = (
    "floor_count",
    "bedrooms",
    "bathrooms",
    "site_width",
    "site_depth",
    "has_garage",
    "prefer_south_facing_living",
)


@dataclass
class FieldScore:
    name: str
    expected: object
    actual: object
    hit: bool


@dataclass
class CaseScore:
    case_id: str
    fields: list[FieldScore] = field(default_factory=list)
    hallucinations: list[str] = field(default_factory=list)
    geometry_fail: bool = False
    space_ok: bool = True
    notes: list[str] = field(default_factory=list)

    @property
    def field_hits(self) -> int:
        return sum(1 for f in self.fields if f.hit)

    @property
    def field_total(self) -> int:
        return len(self.fields)

    @property
    def passed(self) -> bool:
        if self.geometry_fail:
            return False
        if self.hallucinations:
            return False
        if not self.space_ok:
            return False
        return all(f.hit for f in self.fields)


def _actual_map(spec: RequirementSpec) -> dict[str, object | None]:
    return {
        "floor_count": spec.floor_count,
        "bedrooms": spec.household.bedrooms,
        "bathrooms": spec.household.bathrooms,
        "site_width": spec.site.width,
        "site_depth": spec.site.depth,
        "has_garage": spec.household.has_garage,
        "prefer_south_facing_living": spec.preferences.prefer_south_facing_living,
    }


def _expect_fields(expect: ExpectKnown) -> list[tuple[str, object]]:
    out: list[tuple[str, object]] = []
    mapping = {
        "floor_count": expect.floor_count,
        "bedrooms": expect.bedrooms,
        "bathrooms": expect.bathrooms,
        "site_width": expect.site_width,
        "site_depth": expect.site_depth,
        "has_garage": expect.has_garage,
        "prefer_south_facing_living": expect.prefer_south_facing_living,
    }
    for name, val in mapping.items():
        if val is not None:
            out.append((name, val))
    return out


def _values_equal(expected: object, actual: object) -> bool:
    if expected is None:
        return True
    if actual is None:
        return False
    if isinstance(expected, float) or isinstance(actual, float):
        try:
            return abs(float(expected) - float(actual)) < 1e-6
        except (TypeError, ValueError):
            return False
    return expected == actual


_UNKNOWN_TO_FIELD = {
    "site.width": "site_width",
    "site.depth": "site_depth",
    "household.bedrooms": "bedrooms",
    "household.bathrooms": "bathrooms",
    "household.has_garage": "has_garage",
    "floor_count": "floor_count",
}


def score_requirement_case(
    case: RequirementBenchmarkCase,
    spec: RequirementSpec,
    *,
    geometry_fail: bool = False,
) -> CaseScore:
    """对照 gold expect 打分。"""
    score = CaseScore(case_id=case.id, geometry_fail=geometry_fail)
    actual = _actual_map(spec)

    for name, expected in _expect_fields(case.expect):
        got = actual.get(name)
        hit = _values_equal(expected, got)
        score.fields.append(
            FieldScore(name=name, expected=expected, actual=got, hit=hit)
        )

    for key in case.must_unknown:
        field = _UNKNOWN_TO_FIELD.get(key, key)
        got = actual.get(field)
        if got is not None:
            score.hallucinations.append(key)

    # spaces 软约束
    names = {s.name for s in spec.spaces}
    for need in case.expect.space_names_contains:
        if need not in names:
            score.space_ok = False
            score.notes.append(f"缺少空间名 {need!r}")
    if case.expect.min_spaces is not None:
        if len(spec.spaces) < case.expect.min_spaces:
            score.space_ok = False
            score.notes.append(
                f"spaces<{case.expect.min_spaces}（实际 {len(spec.spaces)}）"
            )

    return score
