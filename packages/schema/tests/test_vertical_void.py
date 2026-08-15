"""ADR-010 VerticalVoidSpec schema 测试。"""

from __future__ import annotations

import pytest
from packages.schema.core import CorePlacement
from packages.schema.project import ProjectSpec
from packages.schema.room import FloorSpec, RoomCategory, RoomSpec
from packages.schema.site import SiteSpec
from packages.schema.vertical_void import (
    VerticalVoidSpec,
    VerticalVoidType,
    default_stair_void,
    floor_ids_in_span,
    validate_vertical_voids_for_floors,
    void_covers_floor,
)
from pydantic import ValidationError
from solver.program.normalize import normalize


def _two_floor_ids() -> list[FloorSpec]:
    return [
        FloorSpec(id="F1", label="一层", room_ids=["r1"]),
        FloorSpec(id="F2", label="二层", room_ids=["r2"]),
    ]


class TestVerticalVoidSpec:
    def test_atrium_requires_dimensions(self) -> None:
        with pytest.raises(ValidationError, match="width 与 depth"):
            VerticalVoidSpec(
                id="atrium-1",
                void_type=VerticalVoidType.ATRIUM,
                floor_span=("F1", "F2"),
            )

    def test_wet_riser_rejects_prededuction_fields(self) -> None:
        with pytest.raises(ValidationError, match="width / depth"):
            VerticalVoidSpec(
                id="wr-1",
                void_type=VerticalVoidType.WET_RISER,
                floor_span=("F1", "F2"),
                width=2.0,
            )

    def test_stair_void_accepts_partial_dimensions(self) -> None:
        spec = VerticalVoidSpec(
            id="stair",
            void_type=VerticalVoidType.STAIR,
            floor_span=("F1", "F2"),
            preferred_placement=CorePlacement.WEST,
        )
        assert spec.is_prededuction()
        assert not spec.skylight_required

    def test_atrium_with_skylight(self) -> None:
        spec = VerticalVoidSpec(
            id="atrium-1",
            void_type=VerticalVoidType.ATRIUM,
            floor_span=("F1", "F2"),
            width=3.0,
            depth=3.0,
            skylight_required=True,
        )
        assert spec.is_prededuction()
        assert spec.skylight_required


class TestVerticalVoidHelpers:
    def test_floor_ids_in_span_reversed_endpoints(self) -> None:
        assert floor_ids_in_span(["F1", "F2", "F3"], ("F3", "F1")) == ["F1", "F2", "F3"]

    def test_void_covers_floor(self) -> None:
        spec = VerticalVoidSpec(
            id="atrium-1",
            void_type=VerticalVoidType.ATRIUM,
            floor_span=("F1", "F2"),
            width=2.0,
            depth=2.0,
        )
        assert void_covers_floor(spec, "F1", floor_ids=["F1", "F2", "F3"])
        assert void_covers_floor(spec, "F2", floor_ids=["F1", "F2", "F3"])
        assert not void_covers_floor(spec, "F3", floor_ids=["F1", "F2", "F3"])

    def test_default_stair_void_spans_all_floors(self) -> None:
        spec = default_stair_void(["F1", "F2"])
        validate_vertical_voids_for_floors([spec], _two_floor_ids())


class TestValidateVerticalVoidsForFloors:
    def test_stair_must_span_all_floors(self) -> None:
        stair = VerticalVoidSpec(
            id="stair",
            void_type=VerticalVoidType.STAIR,
            floor_span=("F1", "F1"),
        )
        with pytest.raises(ValueError, match="全部楼层"):
            validate_vertical_voids_for_floors([stair], _two_floor_ids())

    def test_atrium_needs_two_floors(self) -> None:
        with pytest.raises(ValidationError, match="至少两层"):
            VerticalVoidSpec(
                id="atrium-1",
                void_type=VerticalVoidType.ATRIUM,
                floor_span=("F1", "F1"),
                width=2.0,
                depth=2.0,
            )

    def test_duplicate_void_ids_rejected(self) -> None:
        a = VerticalVoidSpec(
            id="atrium-1",
            void_type=VerticalVoidType.ATRIUM,
            floor_span=("F1", "F2"),
            width=2.0,
            depth=2.0,
        )
        b = a.model_copy()
        with pytest.raises(ValueError, match="重复 id"):
            validate_vertical_voids_for_floors([a, b], _two_floor_ids())


class TestProjectSpecVerticalVoids:
    def _base_project(self, **kwargs) -> ProjectSpec:
        return ProjectSpec(
            site=SiteSpec(width=11, depth=13),
            floors=[
                FloorSpec(id="F1", label="一层", room_ids=["r1"]),
                FloorSpec(id="F2", label="二层", room_ids=["r2"]),
            ],
            rooms=[
                RoomSpec(id="r1", name="客厅", category=RoomCategory.PUBLIC, target_area=20),
                RoomSpec(id="r2", name="主卧", category=RoomCategory.PRIVATE, target_area=18),
            ],
            **kwargs,
        )

    def test_project_accepts_valid_atrium(self) -> None:
        spec = self._base_project(
            vertical_voids=[
                VerticalVoidSpec(
                    id="atrium-1",
                    void_type=VerticalVoidType.ATRIUM,
                    floor_span=("F1", "F2"),
                    width=3.0,
                    depth=3.0,
                )
            ]
        )
        assert len(spec.vertical_voids) == 1

    def test_normalize_passes_vertical_voids(self) -> None:
        spec = self._base_project(
            vertical_voids=[
                VerticalVoidSpec(
                    id="wet-riser-1",
                    void_type=VerticalVoidType.WET_RISER,
                    floor_span=("F1", "F2"),
                )
            ]
        )
        program = normalize(spec)
        assert len(program.vertical_voids) == 1
        assert program.vertical_voids[0].void_type == VerticalVoidType.WET_RISER

    def test_json_roundtrip(self) -> None:
        spec = self._base_project(
            vertical_voids=[default_stair_void(["F1", "F2"])]
        )
        restored = ProjectSpec.model_validate_json(spec.model_dump_json())
        assert restored.vertical_voids[0].void_type == VerticalVoidType.STAIR
