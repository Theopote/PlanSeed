"""RequirementSpec assumptions / unknowns 可解释性。"""

from __future__ import annotations

import pytest

from packages.schema.requirements import RequirementSpec, SiteRequirements, SpaceRequirement
from solver.fixtures.benchmark import benchmark_requirement_spec
from solver.program.requirements_normalize import (
    IncompleteRequirementsError,
    normalize_requirements,
    normalize_requirements_to_program,
)


class TestAssumptionsAndUnknowns:
    def test_household_defaults_recorded_as_assumptions(self):
        req = RequirementSpec(
            site=SiteRequirements(width=11, depth=13),
            floor_count=2,
            spaces=[SpaceRequirement(name="客厅", category="public", target_area=24)],
        )
        result = normalize_requirements(req)
        assert result.can_solve
        keys = {a.key for a in result.assumptions}
        assert "household.bedrooms" in keys
        assert "household.occupants" in keys
        assert "household.bathrooms" in keys
        assert "household.has_garage" in keys
        bedrooms = next(a for a in result.assumptions if a.key == "household.bedrooms")
        assert bedrooms.value == 3
        assert "默认" in bedrooms.reason

    def test_missing_site_becomes_unknown_not_default(self):
        req = RequirementSpec(floor_count=2)
        result = normalize_requirements(req)
        assert result.can_solve is False
        assert result.program is None
        unknown_keys = {u.key for u in result.unknowns}
        assert "site.width" in unknown_keys
        assert "site.depth" in unknown_keys
        assert not any(a.key == "site.width" for a in result.assumptions)

    def test_partial_site_width_only(self):
        req = RequirementSpec(site=SiteRequirements(width=12), floor_count=1)
        result = normalize_requirements(req)
        assert result.can_solve is False
        assert any(u.key == "site.depth" for u in result.unknowns)
        assert not any(u.key == "site.width" for u in result.unknowns)

    def test_incomplete_raises_when_forcing_program(self):
        req = RequirementSpec()
        with pytest.raises(IncompleteRequirementsError) as exc:
            normalize_requirements_to_program(req)
        assert any(u.key.startswith("site.") for u in exc.value.unknowns)

    def test_explicit_household_not_assumed(self):
        req = RequirementSpec(
            site=SiteRequirements(width=11, depth=13),
            floor_count=2,
            household={"occupants": 5, "bedrooms": 4, "bathrooms": 3, "has_garage": False},
            spaces=[SpaceRequirement(name="客厅", category="public", target_area=24)],
        )
        result = normalize_requirements(req)
        keys = {a.key for a in result.assumptions}
        assert "household.bedrooms" not in keys
        assert "household.occupants" not in keys
        assert result.program is not None
        assert result.program.assumptions == result.assumptions

    def test_space_area_default_is_assumption(self):
        req = RequirementSpec(
            site=SiteRequirements(width=11, depth=13),
            floor_count=2,
            spaces=[
                SpaceRequirement(name="客厅", category="public"),
                SpaceRequirement(name="主卧", category="private", target_area=18),
            ],
        )
        result = normalize_requirements(req)
        area_assumptions = [a for a in result.assumptions if a.key.endswith(".target_area")]
        assert len(area_assumptions) == 1
        assert "客厅" in area_assumptions[0].reason

    def test_empty_spaces_is_unknown_not_benchmark(self):
        req = RequirementSpec(site=SiteRequirements(width=11, depth=13), floor_count=2)
        result = normalize_requirements(req)
        assert result.can_solve is False
        assert result.program is None
        assert any(u.key == "spaces.program" for u in result.unknowns)
        assert not any(a.key == "spaces.program" for a in result.assumptions)

    def test_empty_spaces_raises_when_forcing_program(self):
        req = RequirementSpec(site=SiteRequirements(width=11, depth=13), floor_count=2)
        with pytest.raises(IncompleteRequirementsError) as exc:
            normalize_requirements_to_program(req)
        assert any(u.key == "spaces.program" for u in exc.value.unknowns)

    def test_benchmark_fixture_solves(self):
        result = normalize_requirements(benchmark_requirement_spec())
        assert result.can_solve
        assert result.program is not None
        assert len(result.program.rooms) == 10

    def test_enriched_requirements_preserve_trace(self):
        req = RequirementSpec(
            site=SiteRequirements(width=11, depth=13),
            spaces=[SpaceRequirement(name="客厅", category="public", target_area=24)],
        )
        result = normalize_requirements(req)
        assert result.requirements.assumptions
        assert any(a.key == "floor_count" for a in result.requirements.assumptions)
        assert result.requirements.floor_count == 2
