"""桌面简表展开 spaces 的契约。"""

from __future__ import annotations

from backend.services.form_requirements import ensure_spaces_for_solve
from packages.schema.requirements import (
    HouseholdRequirements,
    RequirementSpec,
    SiteRequirements,
    SpaceRequirement,
)
from solver.program.requirements_normalize import normalize_requirements_to_program


def test_ensure_spaces_noop_when_spaces_present():
    req = RequirementSpec(
        site=SiteRequirements(width=11, depth=13),
        spaces=[SpaceRequirement(name="客厅", category="public", target_area=24)],
    )
    out = ensure_spaces_for_solve(req)
    assert out is req or out.spaces == req.spaces


def test_ensure_spaces_noop_without_bedrooms():
    req = RequirementSpec(site=SiteRequirements(width=11, depth=13))
    out = ensure_spaces_for_solve(req)
    assert out.spaces == []


def test_household_form_expands_and_solves():
    req = RequirementSpec(
        site=SiteRequirements(width=11, depth=13),
        floor_count=2,
        household=HouseholdRequirements(bedrooms=3, bathrooms=2, has_garage=True),
    )
    expanded = ensure_spaces_for_solve(req)
    assert len(expanded.spaces) >= 6
    assert any(a.key == "spaces.program.from_household" for a in expanded.assumptions)
    program = normalize_requirements_to_program(expanded)
    assert len(program.rooms) >= 6
    assert program.site.width == 11
