"""语义角色：tags 优先，中文 name 冻结回退。"""

from __future__ import annotations

from packages.schema.room import RoomCategory, RoomSpec
from solver.semantics.roles import (
    is_elderly_bedroom,
    is_kitchen,
    is_master_bath,
    is_master_bedroom,
)


class TestSemanticRoles:
    def test_tags_without_chinese_name(self):
        kitchen = RoomSpec(
            id="k", name="西厨", category=RoomCategory.WET, target_area=8, tags=["kitchen"]
        )
        parents = RoomSpec(
            id="p",
            name="父母房",
            category=RoomCategory.PRIVATE,
            target_area=14,
            tags=["bedroom", "elderly_accessible"],
        )
        suite = RoomSpec(
            id="s",
            name="套房",
            category=RoomCategory.PRIVATE,
            target_area=20,
            tags=["bedroom", "master"],
        )
        bath = RoomSpec(
            id="b",
            name="套房卫浴",
            category=RoomCategory.WET,
            target_area=5,
            tags=["ensuite"],
        )
        assert is_kitchen(kitchen, allow_name_fallback=False)
        assert is_elderly_bedroom(parents, allow_name_fallback=False)
        assert is_master_bedroom(suite, allow_name_fallback=False)
        assert is_master_bath(bath, allow_name_fallback=False)

    def test_name_fallback_frozen_not_parents(self):
        parents = RoomSpec(
            id="p", name="父母房", category=RoomCategory.PRIVATE, target_area=14
        )
        elder = RoomSpec(
            id="e", name="老人房", category=RoomCategory.PRIVATE, target_area=14
        )
        assert not is_elderly_bedroom(parents)
        assert is_elderly_bedroom(elder)  # MVP 冻结集内
