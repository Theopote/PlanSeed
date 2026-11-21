"""隐私访问深度 — 跨层楼梯折叠。"""

from __future__ import annotations

from solver.evaluation.privacy import collapsed_access_depth


def test_collapse_consecutive_stairs() -> None:
    path = [
        "exterior-entry",
        "entry",
        "stair-F1",
        "stair-F2",
        "bed1",
    ]
    # 未折叠边数 4；折叠后 3
    assert len(path) - 1 == 4
    assert collapsed_access_depth(path) == 3


def test_collapse_keeps_corridor_hops() -> None:
    path = [
        "exterior-entry",
        "entry",
        "circ-F1-0",
        "stair-F1",
        "stair-F2",
        "circ-F2-0",
        "bed1",
    ]
    assert collapsed_access_depth(path) == 5


def test_empty_and_short() -> None:
    assert collapsed_access_depth([]) == 0
    assert collapsed_access_depth(["exterior-entry"]) == 0
    assert collapsed_access_depth(["exterior-entry", "living"]) == 1


def test_typical_two_floor_secondary_bed_depth() -> None:
    """门厅直连楼梯 + 一层走廊进次卧 → 折叠深度 4（不应触发 deep_access）。"""
    path = [
        "exterior-entry",
        "entry",
        "stair-F1",
        "stair-F2",
        "circ-F2-0",
        "bed2",
    ]
    assert collapsed_access_depth(path) == 4
