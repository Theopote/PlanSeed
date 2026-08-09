"""Phase 5 — locks 指纹与血缘标签。"""

from __future__ import annotations

from packages.schema.lineage import lineage_label, locks_fingerprint
from packages.schema.locks import LayoutLocks, LockedRoomRect


def test_locks_fingerprint_stable_empty():
    a = locks_fingerprint(LayoutLocks())
    b = locks_fingerprint(None)
    c = locks_fingerprint({"rooms": [], "stair": None, "zones": []})
    assert a == b == c
    assert len(a) == 16


def test_locks_fingerprint_changes_with_room():
    empty = locks_fingerprint(LayoutLocks())
    locked = locks_fingerprint(
        LayoutLocks(
            rooms=[
                LockedRoomRect(
                    room_id="r1",
                    floor_id="F1",
                    x=0,
                    y=0,
                    width=3,
                    depth=3,
                )
            ]
        )
    )
    assert empty != locked


def test_locks_fingerprint_rooms_list_order_independent():
    a = LockedRoomRect(room_id="a", floor_id="F1", x=1, y=2, width=3, depth=4)
    b = LockedRoomRect(room_id="b", floor_id="F1", x=5, y=6, width=2, depth=2)
    assert locks_fingerprint(LayoutLocks(rooms=[a, b])) == locks_fingerprint(
        LayoutLocks(rooms=[b, a])
    )


def test_locks_fingerprint_order_independent_for_dict_keys():
    # model_dump + sort_keys；同内容同指纹
    locks = LayoutLocks(
        rooms=[
            LockedRoomRect(
                room_id="a",
                floor_id="F1",
                x=1,
                y=2,
                width=3,
                depth=4,
            )
        ]
    )
    assert locks_fingerprint(locks) == locks_fingerprint(locks.model_dump(mode="json"))


def test_lineage_label():
    assert lineage_label("A", 0) == "A"
    assert lineage_label("A", 1) == "A·1"
    assert lineage_label("B", 2) == "B·2"
