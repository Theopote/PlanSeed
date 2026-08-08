"""
房间语义角色 — tags / semantic role 优先。

原则：
- `RoomSpec.name` 是 UI 文本，Solver 不承担 NLP
- 自然语言（「父母房」「西厨」…）→ tags 由 normalize / Phase 6 LLM 负责
- 中文 name 子串回退仅服务中文 MVP，**冻结集**：禁止为新房间类型继续加 `in name`

判定顺序：tags →（可选）MVP name 回退 → False
"""

from __future__ import annotations

from packages.schema.room import RoomSpec

# 约定语义标签（可扩展 tags；不要扩展中文 name）
TAG_KITCHEN = "kitchen"
TAG_DINING = "dining"
TAG_GARAGE = "garage"
TAG_LAUNDRY = "laundry"
TAG_BEDROOM = "bedroom"
TAG_MASTER = "master"
TAG_MASTER_BEDROOM = "master_bedroom"
TAG_MASTER_BATH = "master_bath"
TAG_MASTER_BATHROOM = "master_bathroom"
TAG_ENSUITE = "ensuite"
TAG_ELDERLY = "elderly"
TAG_ELDER = "elder"
TAG_ELDERLY_ACCESSIBLE = "elderly_accessible"
TAG_STUDY = "study"
TAG_STORAGE = "storage"
TAG_BATHROOM = "bathroom"
TAG_GUEST_BATH = "guest_bath"


def room_tags(room: RoomSpec) -> set[str]:
    return {t.lower().replace("-", "_") for t in room.tags}


def has_any_tag(room: RoomSpec, *candidates: str) -> bool:
    tags = room_tags(room)
    return any(c.lower().replace("-", "_") in tags for c in candidates)


def is_kitchen(room: RoomSpec, *, allow_name_fallback: bool = True) -> bool:
    if has_any_tag(room, TAG_KITCHEN):
        return True
    if not allow_name_fallback:
        return False
    # MVP 冻结
    name = room.name
    return "厨" in name or name in ("餐厅+厨房",)


def is_dining(room: RoomSpec, *, allow_name_fallback: bool = True) -> bool:
    if has_any_tag(room, TAG_DINING):
        return True
    if not allow_name_fallback:
        return False
    name = room.name
    return "餐厅" in name or ("餐" in name and "厨" not in name)


def is_garage(room: RoomSpec, *, allow_name_fallback: bool = True) -> bool:
    if has_any_tag(room, TAG_GARAGE):
        return True
    if not allow_name_fallback:
        return False
    return "车库" in room.name


def is_laundry(room: RoomSpec, *, allow_name_fallback: bool = True) -> bool:
    if has_any_tag(room, TAG_LAUNDRY):
        return True
    if not allow_name_fallback:
        return False
    return "洗衣" in room.name


def is_storage(room: RoomSpec, *, allow_name_fallback: bool = True) -> bool:
    if has_any_tag(room, TAG_STORAGE):
        return True
    if not allow_name_fallback:
        return False
    return "储藏" in room.name


def is_study(room: RoomSpec, *, allow_name_fallback: bool = True) -> bool:
    if has_any_tag(room, TAG_STUDY):
        return True
    if not allow_name_fallback:
        return False
    return "书房" in room.name


def is_elderly_bedroom(room: RoomSpec, *, allow_name_fallback: bool = True) -> bool:
    if has_any_tag(room, TAG_ELDERLY, TAG_ELDER, TAG_ELDERLY_ACCESSIBLE):
        return True
    if not allow_name_fallback:
        return False
    # MVP 冻结：「父母房」等必须靠 tags，勿在此加子串
    return "老人" in room.name or "长辈" in room.name


def is_master_bedroom(room: RoomSpec, *, allow_name_fallback: bool = True) -> bool:
    if has_any_tag(room, TAG_MASTER_BEDROOM):
        return True
    # 单独 master：排除浴相关
    if has_any_tag(room, TAG_MASTER) and not has_any_tag(
        room,
        TAG_MASTER_BATH,
        TAG_MASTER_BATHROOM,
        TAG_ENSUITE,
        TAG_BATHROOM,
        TAG_LAUNDRY,
    ):
        return True
    if has_any_tag(room, TAG_BEDROOM) and has_any_tag(room, TAG_MASTER):
        return True
    if not allow_name_fallback:
        return False
    return "主卧" in room.name


def is_master_bath(room: RoomSpec, *, allow_name_fallback: bool = True) -> bool:
    if has_any_tag(room, TAG_MASTER_BATH, TAG_MASTER_BATHROOM, TAG_ENSUITE):
        return True
    if not allow_name_fallback:
        return False
    return "主卫" in room.name


def is_guest_bath(room: RoomSpec, *, allow_name_fallback: bool = True) -> bool:
    """客卫 / 公卫等非主卫湿区（非厨非洗）。"""
    if is_kitchen(room, allow_name_fallback=allow_name_fallback):
        return False
    if is_master_bath(room, allow_name_fallback=allow_name_fallback):
        return False
    if is_laundry(room, allow_name_fallback=allow_name_fallback):
        return False
    if has_any_tag(room, TAG_GUEST_BATH, TAG_BATHROOM):
        return True
    if not allow_name_fallback:
        return False
    return "卫" in room.name
