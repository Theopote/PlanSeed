"""ADR-011 — 私密房间走廊邻接修补单元测试。"""

from __future__ import annotations

from packages.schema.layout import PlacementRect, PlacementSource, RoomPlacement
from solver.evaluation.weights import DEFAULT_WEIGHTS
from solver.geometry.coverage import (
    _has_direct_circulation_neighbor,
    improve_private_room_corridor_access,
)
from solver.geometry.rect import Rect
from solver.topology.doors import shared_boundary_between


def _placement(
    room_id: str,
    *,
    x: float,
    y: float,
    w: float,
    d: float,
    cat: str,
    floor_id: str = "F1",
) -> RoomPlacement:
    return RoomPlacement(
        room_id=room_id,
        floor_id=floor_id,
        rect=PlacementRect(x=x, y=y, width=w, depth=d),
        source=PlacementSource.PROGRAM,
        name=room_id,
        category=cat,
    )


def _footprint(w: float = 10.0, d: float = 10.0) -> Rect:
    return Rect(x=0, y=0, width=w, depth=d)


def _base_layout() -> list[RoomPlacement]:
    """
    circ 贴 B 左侧；A 在 B 下方偏右（不直接贴 circ）。
    走廊条沿 B 整面底边切出，左端与 circ 相接。
    """
    circ = _placement("circ-F1-0", x=0, y=0, w=2, d=8.1, cat="circulation")
    circ = circ.model_copy(update={"source": PlacementSource.GENERATED})
    neighbor = _placement("B", x=2, y=0, w=6, d=8, cat="other")
    private = _placement("A", x=3, y=8, w=5, d=2, cat="private")
    return [circ, neighbor, private]


class TestImprovePrivateRoomCorridorAccess:
    def test_borrows_strip_when_neighbor_has_spare_area(self) -> None:
        placements = _base_layout()
        min_area = {"B": 6.0 * 8.0 - 8.0}  # 可借出 0.9×6 面积

        out = improve_private_room_corridor_access(
            _footprint(),
            placements,
            "F1",
            min_area_by_room_id=min_area,
        )

        priv = next(p for p in out if p.room_id == "A")
        assert _has_direct_circulation_neighbor(priv, out, frozenset())
        b = next(p for p in out if p.room_id == "B")
        assert b.rect.area >= min_area["B"] - 1e-6
        new_circ = [
            p for p in out if p.room_id.startswith("circ-F1-") and p.room_id != "circ-F1-0"
        ]
        assert len(new_circ) == 1
        assert shared_boundary_between(priv, new_circ[0], min_length=0.05) is not None

    def test_skips_when_neighbor_would_drop_below_min_area(self) -> None:
        placements = _base_layout()
        min_area = {"B": 6.0 * 8.0}

        out = improve_private_room_corridor_access(
            _footprint(),
            placements,
            "F1",
            min_area_by_room_id=min_area,
        )

        priv = next(p for p in out if p.room_id == "A")
        assert not _has_direct_circulation_neighbor(priv, out, frozenset())
        assert len(out) == len(placements)

    def test_skips_when_neighbor_aspect_ratio_would_exceed_threshold(self) -> None:
        thr = DEFAULT_WEIGHTS.aspect_ratio_threshold
        circ = _placement("circ-F1-0", x=0, y=0, w=2, d=8.1, cat="circulation")
        circ = circ.model_copy(update={"source": PlacementSource.GENERATED})
        neighbor = _placement("B", x=2, y=0, w=6, d=thr * 0.9 + 0.05, cat="other")
        private = _placement("A", x=3, y=neighbor.rect.depth, w=5, d=2, cat="private")
        placements = [circ, neighbor, private]
        min_area = {"B": 1.0}

        out = improve_private_room_corridor_access(
            _footprint(10, 12),
            placements,
            "F1",
            min_area_by_room_id=min_area,
        )

        priv = next(p for p in out if p.room_id == "A")
        assert not _has_direct_circulation_neighbor(priv, out, frozenset())
        assert len(out) == len(placements)

    def test_skips_when_new_corridor_cannot_reach_circulation_network(self) -> None:
        """B 与 circ 无邻接，切出的走廊条够不到循环网络。"""
        neighbor = _placement("B", x=3, y=0, w=6, d=4, cat="other")
        private = _placement("A", x=3, y=4, w=6, d=2, cat="private")
        circ = _placement("circ-F1-0", x=0, y=0, w=2, d=3, cat="circulation")
        circ = circ.model_copy(update={"source": PlacementSource.GENERATED})
        placements = [neighbor, private, circ]
        min_area = {"B": 1.0}

        out = improve_private_room_corridor_access(
            _footprint(10, 8),
            placements,
            "F1",
            min_area_by_room_id=min_area,
        )

        priv = next(p for p in out if p.room_id == "A")
        assert not _has_direct_circulation_neighbor(priv, out, frozenset())
        assert len([p for p in out if p.room_id.startswith("circ-F1-")]) == 1

    def test_does_not_borrow_from_stair_core(self) -> None:
        """楼梯核不得作为 donor，避免 resolve 挤压楼梯尺寸。"""
        stair = _placement("stair-F1", x=0, y=0, w=1.8, d=4.2, cat="circulation")
        stair = stair.model_copy(update={"source": PlacementSource.GENERATED})
        wet = _placement("r6", x=1.8, y=0, w=4, d=4, cat="wet")
        private = _placement("r5", x=1.8, y=4, w=4, d=2, cat="private")
        placements = [stair, wet, private]
        min_area = {"r6": 1.0}

        out = improve_private_room_corridor_access(
            _footprint(8, 8),
            placements,
            "F1",
            min_area_by_room_id=min_area,
        )

        stair_out = next(p for p in out if p.room_id == "stair-F1")
        assert stair_out.rect.depth == 4.2
        priv = next(p for p in out if p.room_id == "r5")
        assert _has_direct_circulation_neighbor(priv, out, frozenset())
