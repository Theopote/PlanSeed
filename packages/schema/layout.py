"""Solver 输出几何模型 — 与 RoomSpec 严格分离。"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field

from packages.schema.entry import ExteriorEntryPlacement
from packages.schema.provenance import SolverProvenance
from packages.schema.topology import RealizedConnection

# 兼容旧名：与 SolverProvenance 同构
CandidateProvenance = SolverProvenance


class PlacementSource(StrEnum):
    PROGRAM = "program"
    GENERATED = "generated"


class PlacementRect(BaseModel):
    x: float = Field(ge=0)
    y: float = Field(ge=0)
    width: float = Field(gt=0)
    depth: float = Field(gt=0)

    @property
    def area(self) -> float:
        return self.width * self.depth

    @property
    def aspect_ratio(self) -> float:
        short = min(self.width, self.depth)
        long = max(self.width, self.depth)
        return long / max(short, 0.01)

    @property
    def right(self) -> float:
        return self.x + self.width

    @property
    def bottom(self) -> float:
        return self.y + self.depth


class ZonePlacement(BaseModel):
    """
    Solver 产出的功能分区容器（≠ RoomPlacement；供 Lock Zone / Inspector）。

    id 稳定标识单块组件（如 F1-day-0）；kind 为功能类。
    zone 与 kind 同义，保留兼容旧客户端。
    """

    id: str | None = Field(
        default=None,
        description="分区组件 id，如 F1-day-0；旧候选可空",
    )
    zone: str = Field(description="day | night | service | circulation（= kind）")
    kind: str | None = Field(
        default=None,
        description="功能类；空则回退 zone",
    )
    floor_id: str
    rect: PlacementRect
    room_ids: list[str] = Field(default_factory=list)

    def resolved_kind(self) -> str:
        return self.kind or self.zone



class RoomPlacement(BaseModel):
    """Solver 将房间放置在何处。"""

    room_id: str
    floor_id: str
    rect: PlacementRect
    source: PlacementSource = PlacementSource.PROGRAM
    name: str | None = None
    category: str | None = None

    @property
    def area(self) -> float:
        return self.rect.area

    @property
    def aspect_ratio(self) -> float:
        return self.rect.aspect_ratio


class FloorLayout(BaseModel):
    floor_id: str
    placements: list[RoomPlacement] = Field(default_factory=list)
    # 兼容镜像：由 LayoutCandidate.wet_stacks 主锚回填；新代码请用 wet_stacks
    wet_zone_x0: float | None = Field(
        default=None,
        description="[deprecated] 主 WetStack 锚左界；请用 LayoutCandidate.wet_stacks",
    )
    wet_zone_x1: float | None = None
    wet_zone_y0: float | None = None
    wet_zone_y1: float | None = None
    stair_x0: float | None = None
    stair_y0: float | None = None
    stair_x1: float | None = None
    stair_y1: float | None = None
    core_placement: str | None = Field(
        default=None,
        description="楼梯核区位 north/south/east/west/center",
    )


class WetStack(BaseModel):
    """
    竖向服务对齐单元（vertical service alignment）。

    MVP：max_wet_stacks=1 → 通常仅 WS1；未来可并存 WS2。
    """

    id: str = Field(default="WS1", description="叠组 id，如 WS1 / WS2")
    anchor_rect: PlacementRect = Field(description="跨层共享的技术锚矩形")
    floor_ids: list[str] = Field(default_factory=list, description="参与该叠组的楼层")
    member_room_ids: list[str] = Field(
        default_factory=list,
        description="归属该叠组的房间（各层合计）",
    )


class Violation(BaseModel):
    constraint_id: str
    room_ids: list[str] = Field(default_factory=list)
    message: str
    measured_value: float | None = None
    required_value: float | None = None
    hard: bool = True
    source: str | None = None


class CandidateValidation(BaseModel):
    valid: bool
    hard_violations: list[Violation] = Field(default_factory=list)
    soft_violations: list[Violation] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class DoorOpening(BaseModel):
    """
    门洞 / 开口标注 — Phase 2A 几何 + Phase 2.2 polish。

    只写在已有 shared boundary 上，**不修改** RoomPlacement 几何。
    """

    id: str
    connection_id: str | None = None
    room_a_id: str
    room_b_id: str
    floor_id: str
    x: float = Field(description="开口中心 x（模型坐标）")
    y: float = Field(description="开口中心 y（模型坐标）")
    width: float = Field(gt=0, description="门扇/洞口沿墙宽度（米）")
    axis: Literal["x", "y"] = Field(
        description="墙走向：x=水平墙（南北向分隔），y=竖向墙（东西向分隔）"
    )
    connection_type: str = Field(default="door", description="对应 SpaceConnectionType")
    clear_width: float = Field(
        default=0.9,
        gt=0,
        description="通行净宽（米）；单扇门通常等于 width",
    )
    swing_room_id: str | None = Field(
        default=None,
        description="门扇开启所入房间；OPEN 类型可为空",
    )
    hinge_side: Literal["left", "right"] | None = Field(
        default=None,
        description="在 swing 房间内面对门洞时的铰链侧",
    )
    hinge_x: float | None = Field(default=None, description="铰链点 x")
    hinge_y: float | None = Field(default=None, description="铰链点 y")


class RepairRecord(BaseModel):
    """ConnectionResolver 局部修改台账（Phase 2.3）。"""

    type: str = Field(description="gap_close | edge_lengthen | reslice")
    connection_id: str | None = None
    room_ids: list[str] = Field(default_factory=list)
    before_rects: dict[str, PlacementRect] = Field(default_factory=dict)
    after_rects: dict[str, PlacementRect] = Field(default_factory=dict)
    area_delta: float = 0.0
    max_displacement: float = 0.0
    reason: str = ""


# scoring 依赖 Violation；此处延迟导入避免循环。
from packages.schema.scoring import DesignEvaluation  # noqa: E402


class LayoutCandidate(BaseModel):
    id: str
    seed: int
    floors: list[FloorLayout] = Field(default_factory=list)
    wet_stacks: list[WetStack] = Field(
        default_factory=list,
        description="技术湿区叠组；MVP 通常 0～1 个",
    )
    zone_placements: list[ZonePlacement] = Field(
        default_factory=list,
        description="功能分区几何快照；Phase 4 Lock Zone",
    )
    door_openings: list[DoorOpening] = Field(
        default_factory=list,
        description="在共边上标注开口；不回改房间几何（除 Resolver 台账外）",
    )
    exterior_entry: ExteriorEntryPlacement | None = Field(
        default=None,
        description="对外主入口放置（≠ 楼梯）；AccessGraph 交通起点",
    )
    repair_records: list[RepairRecord] = Field(
        default_factory=list,
        description="ConnectionResolver 修改记录",
    )
    realized_connections: list[RealizedConnection] = Field(
        default_factory=list,
        description="RealizedAccessGraph 边快照",
    )
    validation: CandidateValidation | None = None
    evaluation: DesignEvaluation | None = Field(
        default=None,
        description="完整评价结果；由 pipeline 写入，API 不得重评",
    )
    score: float | None = Field(
        default=None,
        description="[compat] 与 evaluation.total_score 同步，供 rank/demo",
    )
    provenance: CandidateProvenance | None = Field(
        default=None,
        description="solver / generator / evaluation 版本；解释历史分数",
    )
    # Phase 5 — Variant 血缘（additive；会话 Create Variant 写入）
    variant_parent_id: str | None = Field(
        default=None,
        description="Create Variant 时的父候选 id；根为 None",
    )
    variant_generation: int = Field(
        default=0,
        ge=0,
        description="相对根的代数：0=根，1=A1，2=A1.1…",
    )
    lock_snapshot_id: str | None = Field(
        default=None,
        description="生成时 LayoutLocks 指纹；解释同锁不同种子",
    )
    metrics: dict[str, float | int | str | bool] = Field(default_factory=dict)
