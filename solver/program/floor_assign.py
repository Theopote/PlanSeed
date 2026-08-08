"""楼层归属 — 保证每个程序房间恰好属于一层。"""

from __future__ import annotations

from packages.schema.room import FloorSpec, RoomCategory, RoomSpec


class UnassignedRoomError(ValueError):
    """规范化后仍有房间未归属楼层。"""


def auto_assign_floor(
    room: RoomSpec,
    floor_count: int,
    *,
    floor_ids: list[str] | None = None,
) -> str:
    """
    住宅默认楼层归属（source=normalizer）。

    永不返回 None。多层时：
    - 公共 / 入口相关 / 车库 / 厨餐 → F1
    - 私密卧室 / 书房 / 卫浴 → F2（或最高层）
    """
    ids = floor_ids or [f"F{i + 1}" for i in range(floor_count)]
    if floor_count <= 1 or len(ids) == 1:
        return ids[0]

    ground = ids[0]
    upper = ids[min(1, len(ids) - 1)]

    tags = {t.lower() for t in room.tags}
    name = room.name

    if room.category == RoomCategory.PUBLIC:
        return ground
    if room.category == RoomCategory.SERVICE:
        return ground
    if room.category == RoomCategory.CIRCULATION:
        return ground

    if "garage" in tags or "车库" in name:
        return ground

    if room.category == RoomCategory.WET:
        if (
            "kitchen" in tags
            or "dining" in tags
            or "厨" in name
            or "餐厅" in name
            or "餐" in name
        ):
            return ground
        # 卫浴默认与私密层同层，便于主卫/公卫服务卧室
        return upper

    if room.category == RoomCategory.PRIVATE:
        return upper

    if room.category == RoomCategory.OTHER:
        # 书房等辅助空间默认上层；无法判断时也不丢弃
        return upper

    return ground


def ensure_floor_assignment(
    rooms: list[RoomSpec],
    floors: list[FloorSpec],
) -> list[tuple[str, str]]:
    """
    保证每个房间恰好归属一层。

    - 尊重已有 floor_id / floor.room_ids / floor_preference[0]
    - 未归属房间按住宅启发式自动分配，并写回 floor_id
    - 重建各层 room_ids，避免空层或幽灵房间

    返回 [(room_id, floor_id), ...] 中由本函数新分配的条目。
    """
    if not floors:
        raise UnassignedRoomError("DesignProgram 至少需要一层")

    floor_ids = [f.id for f in floors]
    floor_by_id = {f.id: f for f in floors}
    assigned: dict[str, str] = {}
    newly_assigned: list[tuple[str, str]] = []

    # 1) 已在 floor.room_ids 中的
    for fl in floors:
        for rid in fl.room_ids:
            if rid not in assigned:
                assigned[rid] = fl.id

    # 2) RoomSpec.floor_id / floor_preference
    for room in rooms:
        if room.id in assigned:
            continue
        if room.floor_id and room.floor_id in floor_by_id:
            assigned[room.id] = room.floor_id
            continue
        if room.floor_preference:
            for pref in room.floor_preference:
                if pref in floor_by_id:
                    assigned[room.id] = pref
                    break

    # 3) 仍未归属 → 自动分配（永不丢弃）
    for room in rooms:
        if room.id in assigned:
            continue
        floor_id = auto_assign_floor(room, len(floors), floor_ids=floor_ids)
        assigned[room.id] = floor_id
        newly_assigned.append((room.id, floor_id))

    # 4) 写回 RoomSpec.floor_id，并重建 floor.room_ids
    for room in rooms:
        floor_id = assigned[room.id]
        room.floor_id = floor_id

    for fl in floors:
        fl.room_ids = [r.id for r in rooms if assigned[r.id] == fl.id]

    # 5) 不变量：每个程序房间都能在某一层找到
    covered = {rid for fl in floors for rid in fl.room_ids}
    missing = [r.id for r in rooms if r.id not in covered]
    if missing:
        raise UnassignedRoomError(f"房间未归属任何楼层: {missing}")

    return newly_assigned


def assert_all_rooms_placed(program_rooms: list[RoomSpec], floors: list[FloorSpec]) -> None:
    """供 generator / pipeline 在入口做防御性检查。"""
    covered = {rid for fl in floors for rid in fl.room_ids}
    # 若 room_ids 全空，退化为 floor_id 检查
    if not any(fl.room_ids for fl in floors):
        missing = [r.id for r in program_rooms if not r.floor_id]
    else:
        missing = [r.id for r in program_rooms if r.id not in covered]
    if missing:
        raise UnassignedRoomError(f"程序房间未出现在任何楼层: {missing}")
