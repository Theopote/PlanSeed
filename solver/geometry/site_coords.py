"""
场地坐标系 — model edge ↔ world orientation（azimuth）。

Model（绘图/求解坐标，与 SVG 一致）：
  y=0 为 model north 边；y 增大向 model south
  x=0 为 model west 边；x 增大向 model east

World：
  azimuth 0° = 正北，顺时针；90°=东，180°=南，270°=西

SiteSpec.north_angle：
  正北相对 model -Y 轴（model north 外向）的顺时针角（度）。
  north_angle=0 → model north 边朝向世界正北
  north_angle=90 → model north 边朝向世界正东
"""

from __future__ import annotations

from dataclasses import dataclass

from packages.schema.site import CardinalEdge, CardinalOrientation


_EDGE_BASE_AZIMUTH: dict[str, float] = {
    CardinalEdge.NORTH.value: 0.0,
    CardinalEdge.EAST.value: 90.0,
    CardinalEdge.SOUTH.value: 180.0,
    CardinalEdge.WEST.value: 270.0,
}


def normalize_azimuth(degrees: float) -> float:
    """归一化到 [0, 360)。"""
    return degrees % 360.0


def azimuth_to_cardinal(azimuth: float) -> CardinalOrientation:
    """将方位角映射到最近的 cardinal（±45° 扇区）。"""
    az = normalize_azimuth(azimuth)
    if az >= 315.0 or az < 45.0:
        return CardinalOrientation.NORTH
    if az < 135.0:
        return CardinalOrientation.EAST
    if az < 225.0:
        return CardinalOrientation.SOUTH
    return CardinalOrientation.WEST


@dataclass(frozen=True)
class SiteCoordinateSystem:
    """场地坐标：连接 model edge 与 world orientation。"""

    north_angle: float = 0.0

    @classmethod
    def from_site(cls, site) -> SiteCoordinateSystem:
        angle = float(getattr(site, "north_angle", 0.0) or 0.0)
        return cls(north_angle=normalize_azimuth(angle))

    def edge_azimuth(self, edge: CardinalEdge | str) -> float:
        """
        model 边外向法线的世界方位角。

        model north → north_angle
        model east  → north_angle + 90
        model south → north_angle + 180
        model west  → north_angle + 270
        """
        key = edge.value if isinstance(edge, CardinalEdge) else str(edge).lower()
        if key not in _EDGE_BASE_AZIMUTH:
            raise ValueError(f"unknown model edge: {edge}")
        return normalize_azimuth(self.north_angle + _EDGE_BASE_AZIMUTH[key])

    def world_orientation_for_edge(self, edge: CardinalEdge | str) -> CardinalOrientation:
        """model 边朝向的世界 cardinal。"""
        return azimuth_to_cardinal(self.edge_azimuth(edge))

    def model_edges_facing(self, world: CardinalOrientation | str) -> set[str]:
        """哪些 model 边朝向给定的世界方位。"""
        target = (
            world.value if isinstance(world, CardinalOrientation) else str(world).lower()
        )
        return {
            edge
            for edge in _EDGE_BASE_AZIMUTH
            if self.world_orientation_for_edge(edge).value == target
        }
