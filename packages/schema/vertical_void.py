"""ADR-010 — 竖向空洞规格：楼梯核 / 天井 / 湿区立管。"""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field, model_validator

from packages.schema.core import CorePlacement
from packages.schema.layout import PlacementRect

if TYPE_CHECKING:
    from packages.schema.room import FloorSpec

# WET_RISER：footprint 偏移容差（米）；经 min_iou_for_wet_riser_tolerance 映射 IoU 下限。
DEFAULT_WET_RISER_ALIGNMENT_TOLERANCE = 0.3
# 与 solver.evaluation.vertical.DEFAULT_WET_STACK_MIN_IOU 保持同步。
DEFAULT_WET_STACK_MIN_IOU = 0.6


def min_iou_for_wet_riser_tolerance(
    alignment_tolerance: float,
    *,
    ref_tolerance: float = DEFAULT_WET_RISER_ALIGNMENT_TOLERANCE,
    ref_min_iou: float = DEFAULT_WET_STACK_MIN_IOU,
) -> float:
    """
    将 WET_RISER ``alignment_tolerance``（米）映射为湿区配对 IoU 下限。

    反比：默认 0.3 m → 0.6 IoU；容差越大，要求 IoU 越低。
    """
    if alignment_tolerance <= 0:
        return 1.0
    iou = ref_min_iou * ref_tolerance / alignment_tolerance
    return max(0.0, min(1.0, iou))


class VerticalVoidType(StrEnum):
    """竖向空洞类型。"""

    STAIR = "stair"
    ATRIUM = "atrium"
    WET_RISER = "wet_riser"


class VerticalVoidSpec(BaseModel):
    """
    跨层竖向空洞 / 对齐约束的统一输入模型。

    - STAIR / ATRIUM：生成前从 free space 预扣除（同几何路径）
    - WET_RISER：不预扣除；由 checker + 生成器锚点对齐（ADR-010 Step A/B）
    """

    id: str = Field(min_length=1, description="稳定标识，如 stair-core / atrium-1 / wet-riser-1")
    void_type: VerticalVoidType
    floor_span: tuple[str, str] = Field(
        description="(起始 FloorSpec.id, 终止 FloorSpec.id)；按 floors 声明顺序取连续区间",
    )
    width: float | None = Field(
        default=None,
        gt=0,
        description="STAIR 缺省由 StairCoreSpec 默认；ATRIUM 必填",
    )
    depth: float | None = Field(
        default=None,
        gt=0,
        description="STAIR 缺省由 StairCoreSpec 默认；ATRIUM 必填",
    )
    preferred_placement: CorePlacement | None = Field(
        default=None,
        description="STAIR / ATRIUM 区位偏好；WET_RISER 不适用",
    )
    skylight_required: bool = Field(
        default=False,
        description="仅 ATRIUM：顶层是否需天窗（evaluation / export 标注）",
    )
    alignment_tolerance: float = Field(
        default=DEFAULT_WET_RISER_ALIGNMENT_TOLERANCE,
        ge=0.0,
        description="仅 WET_RISER：允许的 footprint 偏移容差（米）",
    )

    @model_validator(mode="after")
    def _type_specific_fields(self) -> VerticalVoidSpec:
        if self.void_type == VerticalVoidType.ATRIUM:
            if self.width is None or self.depth is None:
                raise ValueError("ATRIUM 须显式提供 width 与 depth")
        if self.void_type == VerticalVoidType.WET_RISER:
            if self.width is not None or self.depth is not None:
                raise ValueError("WET_RISER 不走预扣除路径，不得设置 width / depth")
            if self.preferred_placement is not None:
                raise ValueError("WET_RISER 不适用 preferred_placement")
            if self.skylight_required:
                raise ValueError("skylight_required 仅适用于 ATRIUM")
        if self.void_type == VerticalVoidType.STAIR and self.skylight_required:
            raise ValueError("skylight_required 仅适用于 ATRIUM")
        if self.floor_span[0] == self.floor_span[1] and self.void_type != VerticalVoidType.STAIR:
            raise ValueError(f"{self.void_type.value} 的 floor_span 须覆盖至少两层")
        return self

    def is_prededuction(self) -> bool:
        """是否走「生成前从 free space 扣除」路径。"""
        return self.void_type in (VerticalVoidType.STAIR, VerticalVoidType.ATRIUM)


class VerticalVoidPlacement(BaseModel):
    """Solver 产出的竖向空洞几何（STAIR / ATRIUM 预扣除结果）。"""

    void_id: str = Field(description="对应 VerticalVoidSpec.id")
    void_type: VerticalVoidType
    floor_id: str
    rect: PlacementRect
    skylight_required: bool = Field(
        default=False,
        description="仅 ATRIUM：顶层天窗需求标注",
    )


def floor_ids_in_span(floor_ids: list[str], span: tuple[str, str]) -> list[str]:
    """按 floors 声明顺序解析 floor_span 连续区间（含端点）。"""
    if not floor_ids:
        raise ValueError("floor_ids 为空，无法解析 floor_span")
    start, end = span
    if start not in floor_ids or end not in floor_ids:
        missing = {start, end} - set(floor_ids)
        raise ValueError(f"floor_span 引用未知楼层: {sorted(missing)}")
    i0 = floor_ids.index(start)
    i1 = floor_ids.index(end)
    if i0 > i1:
        i0, i1 = i1, i0
    return floor_ids[i0 : i1 + 1]


def void_covers_floor(
    spec: VerticalVoidSpec,
    floor_id: str,
    *,
    floor_ids: list[str],
) -> bool:
    """当前楼层是否落在 void 的 floor_span 内。"""
    return floor_id in floor_ids_in_span(floor_ids, spec.floor_span)


def validate_vertical_voids_for_floors(
    voids: list[VerticalVoidSpec],
    floors: list[FloorSpec],
) -> None:
    """
    校验 void 列表与楼层表的一致性。

    在 ProjectSpec / DesignProgram 层调用；单条 VerticalVoidSpec 无法独立完成。
    """
    floor_ids = [f.id for f in floors]
    if not floor_ids:
        raise ValueError("floors 为空")

    seen: set[str] = set()
    stair_count = 0
    for spec in voids:
        if spec.id in seen:
            raise ValueError(f"vertical_voids 含重复 id: {spec.id}")
        seen.add(spec.id)

        span_ids = floor_ids_in_span(floor_ids, spec.floor_span)

        if spec.void_type == VerticalVoidType.STAIR:
            stair_count += 1
            if span_ids != floor_ids:
                raise ValueError(
                    "STAIR 的 floor_span 必须覆盖全部楼层"
                    f"（期望 {floor_ids[0]}–{floor_ids[-1]}，实际 {spec.floor_span}）"
                )
        elif spec.void_type == VerticalVoidType.ATRIUM:
            if len(span_ids) < 2:
                raise ValueError(f"ATRIUM {spec.id} 的 floor_span 须覆盖至少两层")
        elif spec.void_type == VerticalVoidType.WET_RISER:
            if len(span_ids) < 2:
                raise ValueError(f"WET_RISER {spec.id} 的 floor_span 须覆盖至少两层")

    if stair_count > 1:
        raise ValueError("vertical_voids 至多声明一个 STAIR void")


def default_stair_void(floor_ids: list[str]) -> VerticalVoidSpec:
    """合成覆盖全部楼层的 STAIR void（solver 迁移 / 缺省回填用）。"""
    if not floor_ids:
        raise ValueError("floor_ids 为空")
    return VerticalVoidSpec(
        id="stair-core",
        void_type=VerticalVoidType.STAIR,
        floor_span=(floor_ids[0], floor_ids[-1]),
    )
