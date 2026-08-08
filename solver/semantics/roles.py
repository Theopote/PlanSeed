"""
房间语义角色 — semantic_role → tags → category → legacy name。

原则：
- `RoomSpec.name` 是 UI 文本，Solver 不承担 NLP
- 自然语言 → semantic_role / tags 由 normalize / Phase 6 LLM 负责
- 中文 name 子串回退仅服务中文 MVP，**冻结集**
"""

from __future__ import annotations

from packages.schema.room import RoomSpec, SemanticRole

# 约定 tags（与 SemanticRole 对齐；可并存）
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
TAG_LIVING = "living"
TAG_FOYER = "foyer"
TAG_HALL = "hall"


def room_tags(room: RoomSpec) -> set[str]:
    tags = {t.lower().replace("-", "_") for t in room.tags}
    if room.semantic_role is not None:
        tags.add(room.semantic_role.value)
    return tags


def has_any_tag(room: RoomSpec, *candidates: str) -> bool:
    tags = room_tags(room)
    return any(c.lower().replace("-", "_") in tags for c in candidates)


def has_role(room: RoomSpec, *roles: SemanticRole) -> bool:
    if room.semantic_role is None:
        return False
    return room.semantic_role in roles


def is_kitchen(room: RoomSpec, *, allow_name_fallback: bool = True) -> bool:
    if has_role(room, SemanticRole.KITCHEN):
        return True
    if has_any_tag(room, TAG_KITCHEN):
        return True
    if not allow_name_fallback:
        return False
    name = room.name
    return "厨" in name or name in ("餐厅+厨房",)


def is_dining(room: RoomSpec, *, allow_name_fallback: bool = True) -> bool:
    if has_role(room, SemanticRole.DINING):
        return True
    if has_any_tag(room, TAG_DINING):
        return True
    if not allow_name_fallback:
        return False
    name = room.name
    return "餐厅" in name or ("餐" in name and "厨" not in name)


def is_living(room: RoomSpec, *, allow_name_fallback: bool = True) -> bool:
    if has_role(room, SemanticRole.LIVING):
        return True
    if has_any_tag(room, TAG_LIVING):
        return True
    if not allow_name_fallback:
        return False
    return "客厅" in room.name or "起居" in room.name


def is_foyer(room: RoomSpec, *, allow_name_fallback: bool = True) -> bool:
    if has_role(room, SemanticRole.FOYER):
        return True
    if has_any_tag(room, TAG_FOYER):
        return True
    if not allow_name_fallback:
        return False
    return "门厅" in room.name or "玄关" in room.name


def is_hall(room: RoomSpec, *, allow_name_fallback: bool = True) -> bool:
    if has_role(room, SemanticRole.HALL):
        return True
    if has_any_tag(room, TAG_HALL):
        return True
    if not allow_name_fallback:
        return False
    return "过厅" in room.name or room.name == "走廊"


def is_garage(room: RoomSpec, *, allow_name_fallback: bool = True) -> bool:
    if has_role(room, SemanticRole.GARAGE):
        return True
    if has_any_tag(room, TAG_GARAGE):
        return True
    if not allow_name_fallback:
        return False
    return "车库" in room.name


def is_laundry(room: RoomSpec, *, allow_name_fallback: bool = True) -> bool:
    if has_role(room, SemanticRole.LAUNDRY):
        return True
    if has_any_tag(room, TAG_LAUNDRY):
        return True
    if not allow_name_fallback:
        return False
    return "洗衣" in room.name


def is_storage(room: RoomSpec, *, allow_name_fallback: bool = True) -> bool:
    if has_role(room, SemanticRole.STORAGE):
        return True
    if has_any_tag(room, TAG_STORAGE):
        return True
    if not allow_name_fallback:
        return False
    return "储藏" in room.name


def is_study(room: RoomSpec, *, allow_name_fallback: bool = True) -> bool:
    if has_role(room, SemanticRole.STUDY):
        return True
    if has_any_tag(room, TAG_STUDY):
        return True
    if not allow_name_fallback:
        return False
    return "书房" in room.name


def is_elderly_bedroom(room: RoomSpec, *, allow_name_fallback: bool = True) -> bool:
    if has_role(room, SemanticRole.ELDERLY_BEDROOM):
        return True
    if has_any_tag(room, TAG_ELDERLY, TAG_ELDER, TAG_ELDERLY_ACCESSIBLE):
        return True
    if not allow_name_fallback:
        return False
    return "老人" in room.name or "长辈" in room.name


def is_master_bedroom(room: RoomSpec, *, allow_name_fallback: bool = True) -> bool:
    if has_role(room, SemanticRole.MASTER_BEDROOM):
        return True
    if has_any_tag(room, TAG_MASTER_BEDROOM):
        return True
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
    if has_role(room, SemanticRole.MASTER_BATHROOM):
        return True
    if has_any_tag(room, TAG_MASTER_BATH, TAG_MASTER_BATHROOM, TAG_ENSUITE):
        return True
    if not allow_name_fallback:
        return False
    return "主卫" in room.name


def is_guest_bath(room: RoomSpec, *, allow_name_fallback: bool = True) -> bool:
    if is_kitchen(room, allow_name_fallback=allow_name_fallback):
        return False
    if is_master_bath(room, allow_name_fallback=allow_name_fallback):
        return False
    if is_laundry(room, allow_name_fallback=allow_name_fallback):
        return False
    if has_role(room, SemanticRole.BATHROOM):
        return True
    if has_any_tag(room, TAG_GUEST_BATH, TAG_BATHROOM):
        return True
    if not allow_name_fallback:
        return False
    return "卫" in room.name
