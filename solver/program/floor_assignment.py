"""
FloorAssignmentSolver — 楼层归属独立求解。

流水线：
  Requirement / Project rooms
        ↓
  explicit floor constraints / floor_id / room_ids / preference
        ↓
  implicit residential rules（基于 tags / category，非 NLP）
        ↓
  FloorAssignment
        ↓
  floor.room_ids

Generator 不得自行猜测楼层。
住宅规则以 semantic tags 为准；中文 name 回退见 solver.semantics.roles（冻结 MVP）。
"""

from __future__ import annotations

from packages.schema.constraints import Constraint, FloorConstraint, ConstraintKind
from packages.schema.floor_assignment import (
    FloorAssignment,
    FloorAssignmentSource,
    RoomFloorDecision,
)
from packages.schema.room import FloorSpec, RoomCategory, RoomSpec
from solver.semantics.roles import (
    is_dining,
    is_elderly_bedroom,
    is_garage,
    is_kitchen,
    is_master_bath,
    is_master_bedroom,
)

class UnassignedRoomError(ValueError):
    """规范化后仍有房间未归属楼层。"""


class DuplicateRoomAssignmentError(ValueError):
    """同一房间被声明到多个楼层，或显式来源互相冲突。"""


class FloorAssignmentSolver:
    """
    第一版：规则驱动，非优化算法。

    优先级（高 → 低）：
    1. FloorConstraint（显式硬约束）
    2. FloorSpec.room_ids（已声明归属）
    3. RoomSpec.floor_id
    4. RoomSpec.floor_preference[0]
    5. 住宅默认规则（可解释 rule_id）
    6. fallback → 地面层（永不丢弃）
    """

    def solve(
        self,
        rooms: list[RoomSpec],
        floors: list[FloorSpec],
        constraints: list[Constraint] | None = None,
    ) -> FloorAssignment:
        if not floors:
            raise UnassignedRoomError("至少需要一层")
        if not rooms:
            return FloorAssignment(decisions=[])

        floor_ids = [f.id for f in floors]
        floor_set = set(floor_ids)
        ground = floor_ids[0]
        upper = floor_ids[min(1, len(floor_ids) - 1)]
        constraints = constraints or []
        room_id_set = {r.id for r in rooms}

        # 输入侧：同一房间出现在多个 floor.room_ids
        seen_in_room_ids: dict[str, str] = {}
        for fl in floors:
            for rid in fl.room_ids:
                if rid in seen_in_room_ids and seen_in_room_ids[rid] != fl.id:
                    raise DuplicateRoomAssignmentError(
                        f"房间 {rid} 同时出现在 {seen_in_room_ids[rid]} 与 {fl.id} 的 room_ids"
                    )
                seen_in_room_ids[rid] = fl.id

        decided: dict[str, RoomFloorDecision] = {}

        def accept(decision: RoomFloorDecision, *, allow_override: bool = False) -> None:
            if decision.floor_id not in floor_set:
                return
            if decision.room_id in room_id_set or decision.room_id in seen_in_room_ids:
                pass  # 允许尚未在 rooms 列表的显式 id 时仍记录；最终 apply 以 rooms 为准
            existing = decided.get(decision.room_id)
            if existing is not None:
                if existing.floor_id == decision.floor_id:
                    return
                # 显式来源冲突不可静默覆盖
                explicit = {
                    FloorAssignmentSource.EXPLICIT_CONSTRAINT,
                    FloorAssignmentSource.EXPLICIT_ROOM_IDS,
                    FloorAssignmentSource.EXPLICIT_FLOOR_ID,
                }
                if existing.source in explicit and decision.source in explicit:
                    raise DuplicateRoomAssignmentError(
                        f"房间 {decision.room_id} 楼层冲突："
                        f"{existing.floor_id} ({existing.source.value}) vs "
                        f"{decision.floor_id} ({decision.source.value})"
                    )
                if not allow_override:
                    return
            decided[decision.room_id] = decision

        # --- 1. Explicit FloorConstraint ---
        for c in constraints:
            if c.kind != ConstraintKind.FLOOR or not isinstance(c, FloorConstraint):
                continue
            accept(
                RoomFloorDecision(
                    room_id=c.room_id,
                    floor_id=c.floor_id,
                    source=FloorAssignmentSource.EXPLICIT_CONSTRAINT,
                    source_key=f"constraints.{c.id}",
                    rule_id="explicit.floor_constraint",
                    reason=c.description or f"FloorConstraint → {c.floor_id}",
                )
            )

        # --- 2. Explicit FloorSpec.room_ids ---
        for fl in floors:
            for rid in fl.room_ids:
                accept(
                    RoomFloorDecision(
                        room_id=rid,
                        floor_id=fl.id,
                        source=FloorAssignmentSource.EXPLICIT_ROOM_IDS,
                        source_key=f"floors.{fl.id}.room_ids",
                        rule_id="explicit.room_ids",
                        reason=f"已在 {fl.id}.room_ids 中声明",
                    )
                )

        # --- 3. RoomSpec.floor_id ---
        for room in rooms:
            if room.floor_id and room.floor_id in floor_set:
                accept(
                    RoomFloorDecision(
                        room_id=room.id,
                        floor_id=room.floor_id,
                        source=FloorAssignmentSource.EXPLICIT_FLOOR_ID,
                        source_key=f"rooms.{room.id}.floor_id",
                        rule_id="explicit.floor_id",
                        reason=f"RoomSpec.floor_id={room.floor_id}",
                    )
                )

        # --- 4. floor_preference ---
        for room in rooms:
            for pref in room.floor_preference:
                if pref in floor_set:
                    accept(
                        RoomFloorDecision(
                            room_id=room.id,
                            floor_id=pref,
                            source=FloorAssignmentSource.FLOOR_PREFERENCE,
                            source_key=f"rooms.{room.id}.floor_preference",
                            rule_id="explicit.floor_preference",
                            reason=f"floor_preference 首选 {pref}",
                        )
                    )
                    break

        # --- 5a. Residential rules: non-bath wet & non-wet ---
        for room in rooms:
            if room.id in decided:
                continue
            rule = self._match_residential_rule(room, ground=ground, upper=upper)
            if rule is not None:
                floor_id, rule_id, reason = rule
                accept(
                    RoomFloorDecision(
                        room_id=room.id,
                        floor_id=floor_id,
                        source=FloorAssignmentSource.RESIDENTIAL_RULE,
                        source_key=f"residential_rules.{rule_id}",
                        rule_id=rule_id,
                        reason=reason,
                    )
                )

        # --- 5b. Wet bathrooms: affiliation + wet stacking ---
        for room in rooms:
            if room.id in decided:
                continue
            if room.category != RoomCategory.WET:
                continue
            floor_id, rule_id, reason = self._assign_wet_bathroom(
                room, rooms, decided, ground=ground, upper=upper, floor_ids=floor_ids
            )
            accept(
                RoomFloorDecision(
                    room_id=room.id,
                    floor_id=floor_id,
                    source=FloorAssignmentSource.RESIDENTIAL_RULE,
                    source_key=f"residential_rules.{rule_id}",
                    rule_id=rule_id,
                    reason=reason,
                )
            )

        # --- 6. Fallback: never drop ---
        for room in rooms:
            if room.id in decided:
                continue
            accept(
                RoomFloorDecision(
                    room_id=room.id,
                    floor_id=ground,
                    source=FloorAssignmentSource.FALLBACK,
                    source_key="residential_rules.fallback_ground",
                    rule_id="fallback.ground",
                    reason="无匹配规则，兜底归属地面层",
                )
            )

        missing = [r.id for r in rooms if r.id not in decided]
        if missing:
            raise UnassignedRoomError(f"FloorAssignmentSolver 未能归属: {missing}")

        return FloorAssignment(decisions=list(decided.values()))

    def _match_residential_rule(
        self,
        room: RoomSpec,
        *,
        ground: str,
        upper: str,
    ) -> tuple[str, str, str] | None:
        """返回 (floor_id, rule_id, reason)；浴室留给湿区第二遍。"""
        if room.category == RoomCategory.PUBLIC:
            return ground, "public.ground", "公共空间优先地面层"

        if room.category == RoomCategory.SERVICE:
            return ground, "service.ground", "服务空间优先地面层"

        if room.category == RoomCategory.CIRCULATION:
            return ground, "circulation.ground", "交通空间默认地面层入口侧"

        if is_garage(room):
            return ground, "garage.ground", "车库必须地面层"

        if is_kitchen(room):
            return ground, "kitchen.ground", "厨房优先地面层"

        if is_dining(room):
            return ground, "dining.ground", "餐厅优先地面层"

        if is_elderly_bedroom(room):
            return ground, "elderly_bedroom.ground", "老人房优先地面层"

        if is_master_bedroom(room):
            return upper, "master_bedroom.upper", "主卧优先上层"

        if room.category == RoomCategory.PRIVATE:
            return upper, "private.upper", "私密卧室优先上层"

        if room.category == RoomCategory.WET and (is_kitchen(room) or is_dining(room)):
            return ground, "wet_kitchen_dining.ground", "厨餐湿区优先地面层"

        if room.category == RoomCategory.WET:
            # 卫浴：第二遍处理
            return None

        if room.category == RoomCategory.OTHER:
            return upper, "other.upper", "辅助空间（书房等）默认上层"

        return None

    def _assign_wet_bathroom(
        self,
        room: RoomSpec,
        all_rooms: list[RoomSpec],
        decided: dict[str, RoomFloorDecision],
        *,
        ground: str,
        upper: str,
        floor_ids: list[str],
    ) -> tuple[str, str, str]:
        # 主卫 → 跟随主卧
        if is_master_bath(room):
            master = next((r for r in all_rooms if is_master_bedroom(r)), None)
            if master and master.id in decided:
                return (
                    decided[master.id].floor_id,
                    "wet.master_bath_follows_master",
                    f"主卫跟随主卧所在层 {decided[master.id].floor_id}",
                )
            return upper, "wet.master_bath_upper", "主卫默认上层"

        # wet stacking：优先已有湿区的层（非厨餐亦可）
        wet_floors = [
            decided[r.id].floor_id
            for r in all_rooms
            if r.id in decided and r.category == RoomCategory.WET
        ]
        if wet_floors:
            preferred = upper if upper in wet_floors else wet_floors[0]
            return preferred, "wet.stacking", f"湿区叠置到已有湿区层 {preferred}"

        private_floors = [
            decided[r.id].floor_id
            for r in all_rooms
            if r.id in decided and r.category == RoomCategory.PRIVATE
        ]
        if private_floors:
            return (
                private_floors[0],
                "wet.follows_private",
                f"卫浴跟随私密区 {private_floors[0]}",
            )

        return upper, "wet.bathroom_upper", "卫浴默认上层"


def ensure_floor_assignment(
    rooms: list[RoomSpec],
    floors: list[FloorSpec],
    constraints: list[Constraint] | None = None,
) -> FloorAssignment:
    """运行 FloorAssignmentSolver 并写回 rooms / floors。"""
    assignment = FloorAssignmentSolver().solve(rooms, floors, constraints)
    assignment.apply(rooms, floors)

    covered = {rid for fl in floors for rid in fl.room_ids}
    missing = [r.id for r in rooms if r.id not in covered]
    if missing:
        raise UnassignedRoomError(f"房间未归属任何楼层: {missing}")

    # 输出侧不变量：每个房间恰好出现一次
    counts: dict[str, int] = {}
    for fl in floors:
        for rid in fl.room_ids:
            counts[rid] = counts.get(rid, 0) + 1
    dupes = [rid for rid, n in counts.items() if n > 1]
    if dupes:
        raise DuplicateRoomAssignmentError(f"输出 room_ids 出现重复归属: {dupes}")

    return assignment


def assert_all_rooms_placed(program_rooms: list[RoomSpec], floors: list[FloorSpec]) -> None:
    """Generator / pipeline 入口防御检查。"""
    covered = {rid for fl in floors for rid in fl.room_ids}
    if not any(fl.room_ids for fl in floors):
        missing = [r.id for r in program_rooms if not r.floor_id]
    else:
        missing = [r.id for r in program_rooms if r.id not in covered]
    if missing:
        raise UnassignedRoomError(f"程序房间未出现在任何楼层: {missing}")


# 兼容旧 import 名
def auto_assign_floor(room: RoomSpec, floor_count: int, *, floor_ids: list[str] | None = None) -> str:
    """仅用于单规则探测的兼容包装；正式流程请用 FloorAssignmentSolver。"""
    ids = floor_ids or [f"F{i + 1}" for i in range(max(1, floor_count))]
    floors = [FloorSpec(id=fid, label=fid, room_ids=[]) for fid in ids]
    assignment = FloorAssignmentSolver().solve([room], floors, [])
    floor_id = assignment.floor_id_for(room.id)
    if floor_id is None:
        raise UnassignedRoomError(room.id)
    return floor_id
