"""Requirement Benchmark 评分（标量字段 + 设计意图 + 反幻觉）。"""

from __future__ import annotations

from dataclasses import dataclass, field

from packages.llm.benchmark.cases import (
    ExpectFloorPreference,
    ExpectKnown,
    ExpectOrientation,
    ExpectRelation,
    RequirementBenchmarkCase,
)
from packages.schema.requirements import RelationIntent, RequirementSpec


@dataclass
class FieldScore:
    name: str
    expected: object
    actual: object
    hit: bool


@dataclass
class RelationHit:
    expected: ExpectRelation
    hit: bool


@dataclass
class CaseScore:
    case_id: str
    fields: list[FieldScore] = field(default_factory=list)
    hallucinations: list[str] = field(default_factory=list)
    geometry_fail: bool = False
    space_ok: bool = True
    notes: list[str] = field(default_factory=list)
    # Phase 6.7 — 设计意图
    relations: list[RelationHit] = field(default_factory=list)
    relation_predicted: int = 0
    floor_prefs: list[FieldScore] = field(default_factory=list)
    orientations: list[FieldScore] = field(default_factory=list)
    unknown_expected: list[str] = field(default_factory=list)
    unknown_predicted: list[str] = field(default_factory=list)
    # 真模型 qualification 元数据
    attempts: int = 1
    parse_failed: bool = False
    latency_s: float = 0.0

    @property
    def field_hits(self) -> int:
        return sum(1 for f in self.fields if f.hit)

    @property
    def field_total(self) -> int:
        return len(self.fields)

    @property
    def relation_hits(self) -> int:
        return sum(1 for r in self.relations if r.hit)

    @property
    def relation_total(self) -> int:
        return len(self.relations)

    @property
    def repaired(self) -> bool:
        return self.attempts > 1

    @property
    def unknown_tp(self) -> int:
        exp = set(self.unknown_expected)
        pred = set(self.unknown_predicted)
        return len(exp & pred)

    @property
    def passed(self) -> bool:
        if self.geometry_fail or self.parse_failed:
            return False
        if self.hallucinations:
            return False
        if not self.space_ok:
            return False
        if not all(f.hit for f in self.fields):
            return False
        if not all(r.hit for r in self.relations):
            return False
        if not all(f.hit for f in self.floor_prefs):
            return False
        if not all(f.hit for f in self.orientations):
            return False
        return True


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


def _relation_matches(expected: ExpectRelation, actual: RelationIntent) -> bool:
    ends_e = {expected.a.strip(), expected.b.strip()}
    ends_a = {actual.a.strip(), actual.b.strip()}
    if ends_e != ends_a:
        return False
    if expected.kind is not None and actual.kind != expected.kind:
        return False
    return True


def _score_relations(
    expected: list[ExpectRelation],
    actual: list[RelationIntent],
) -> list[RelationHit]:
    remaining = list(actual)
    hits: list[RelationHit] = []
    for exp in expected:
        matched_i: int | None = None
        for i, act in enumerate(remaining):
            if _relation_matches(exp, act):
                matched_i = i
                break
        if matched_i is not None:
            remaining.pop(matched_i)
            hits.append(RelationHit(expected=exp, hit=True))
        else:
            hits.append(RelationHit(expected=exp, hit=False))
    return hits


def _space_by_name(spec: RequirementSpec, name: str):
    for sp in spec.spaces:
        if sp.name == name or sp.id == name:
            return sp
    return None


def _score_floor_prefs(
    expected: list[ExpectFloorPreference],
    spec: RequirementSpec,
) -> list[FieldScore]:
    out: list[FieldScore] = []
    for exp in expected:
        sp = _space_by_name(spec, exp.space_name)
        actual = list(sp.floor_preference) if sp else None
        hit = actual is not None and all(f in actual for f in exp.floors)
        out.append(
            FieldScore(
                name=f"floor_pref:{exp.space_name}",
                expected=list(exp.floors),
                actual=actual,
                hit=hit,
            )
        )
    return out


def _score_orientations(
    expected: list[ExpectOrientation],
    spec: RequirementSpec,
) -> list[FieldScore]:
    out: list[FieldScore] = []
    for exp in expected:
        sp = _space_by_name(spec, exp.space_name)
        actual = sp.preferred_orientation if sp else None
        actual_v = str(actual) if actual is not None else None
        expected_v = str(exp.orientation)
        hit = actual_v == expected_v
        out.append(
            FieldScore(
                name=f"orientation:{exp.space_name}",
                expected=expected_v,
                actual=actual_v,
                hit=hit,
            )
        )
    return out


def score_requirement_case(
    case: RequirementBenchmarkCase,
    spec: RequirementSpec,
    *,
    geometry_fail: bool = False,
    attempts: int = 1,
    parse_failed: bool = False,
    latency_s: float = 0.0,
) -> CaseScore:
    """对照 gold expect 打分。"""
    score = CaseScore(
        case_id=case.id,
        geometry_fail=geometry_fail,
        attempts=attempts,
        parse_failed=parse_failed,
        latency_s=latency_s,
        unknown_expected=list(case.must_unknown),
        unknown_predicted=[u.key for u in spec.unknowns],
    )
    actual = _actual_map(spec)

    for name, expected in _expect_fields(case.expect):
        got = actual.get(name)
        hit = _values_equal(expected, got)
        score.fields.append(
            FieldScore(name=name, expected=expected, actual=got, hit=hit)
        )

    for key in case.must_unknown:
        field_key = _UNKNOWN_TO_FIELD.get(key, key)
        got = actual.get(field_key)
        if got is not None:
            score.hallucinations.append(key)

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

    actual_rels = list(spec.relation_intents)
    score.relation_predicted = len(actual_rels)
    score.relations = _score_relations(case.expect.relations, actual_rels)
    score.floor_prefs = _score_floor_prefs(case.expect.floor_preferences, spec)
    score.orientations = _score_orientations(case.expect.orientations, spec)

    return score
