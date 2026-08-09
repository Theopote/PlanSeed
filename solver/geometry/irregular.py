"""Phase 8.4 — 不规则场地几何（Shapely opt-in）。

默认 Alpha 仍走轴对齐 Rect2D / free_rects。
本模块仅在提供 site_polygon / buildable_polygon 时使用：

- 均匀退线（buffer inset）
- 轴对齐矩形是否落在可建面内
- **正交多边形** → 极大矩形分解（供现有 packing 消费）

禁止：用 Shapely 替换整个 Rect engine / Guillotine。
"""

from __future__ import annotations

from packages.schema.site import Point2D, Polygon2D, Rect2D, SetbackSpec
from solver.geometry.rect import Rect


class ShapelyUnavailableError(RuntimeError):
    """未安装 shapely（``uv sync --group research``）。"""


class IrregularGeometryError(ValueError):
    """不规则场地输入不合法或超出 Alpha 支持范围。"""


def _require_shapely():
    try:
        import shapely  # noqa: F401
        from shapely.geometry import Polygon
    except ImportError as exc:
        raise ShapelyUnavailableError(
            "shapely 未安装。研究路径：uv sync --group research"
        ) from exc
    return Polygon


def polygon_to_shapely(poly: Polygon2D):
    Polygon = _require_shapely()
    exterior = [(p.x, p.y) for p in poly.exterior]
    if exterior[0] != exterior[-1]:
        exterior = exterior + [exterior[0]]
    holes = []
    for hole in poly.holes:
        ring = [(p.x, p.y) for p in hole]
        if ring and ring[0] != ring[-1]:
            ring = ring + [ring[0]]
        if len(ring) >= 4:
            holes.append(ring)
    geom = Polygon(exterior, holes)
    if not geom.is_valid or geom.is_empty:
        raise IrregularGeometryError("Polygon2D 无效或为空")
    return geom


def shapely_to_polygon(geom) -> Polygon2D:
    if geom.is_empty:
        raise IrregularGeometryError("空几何无法转为 Polygon2D")
    # MultiPolygon：取面积最大块
    if geom.geom_type == "MultiPolygon":
        geom = max(geom.geoms, key=lambda g: g.area)
    if geom.geom_type != "Polygon":
        raise IrregularGeometryError(f"不支持的几何类型: {geom.geom_type}")
    exterior = [Point2D(x=float(x), y=float(y)) for x, y in geom.exterior.coords[:-1]]
    holes: list[list[Point2D]] = []
    for ring in geom.interiors:
        holes.append([Point2D(x=float(x), y=float(y)) for x, y in ring.coords[:-1]])
    return Polygon2D(exterior=exterior, holes=holes)


def rect_to_polygon(rect: Rect2D | Rect) -> Polygon2D:
    x = float(rect.x)
    y = float(rect.y)
    w = float(rect.width)
    d = float(rect.depth)
    return Polygon2D(
        exterior=[
            Point2D(x=x, y=y),
            Point2D(x=x + w, y=y),
            Point2D(x=x + w, y=y + d),
            Point2D(x=x, y=y + d),
        ]
    )


def is_orthogonal_polygon(poly: Polygon2D, *, eps: float = 1e-6) -> bool:
    """外环与洞是否均为轴对齐边。"""
    rings = [poly.exterior, *poly.holes]
    for ring in rings:
        n = len(ring)
        for i in range(n):
            a = ring[i]
            b = ring[(i + 1) % n]
            dx = abs(a.x - b.x)
            dy = abs(a.y - b.y)
            if dx > eps and dy > eps:
                return False
    return True


def uniform_inset(poly: Polygon2D, distance: float) -> Polygon2D:
    """均匀内缩（米）。distance<=0 返回原样拷贝语义的多边形。"""
    if distance <= 0:
        return poly.model_copy(deep=True)
    geom = polygon_to_shapely(poly)
    inset = geom.buffer(-float(distance), join_style=2)  # mitre
    if inset.is_empty:
        raise IrregularGeometryError(f"退线 {distance}m 后可建面为空")
    return shapely_to_polygon(inset)


def inset_with_setbacks(poly: Polygon2D, setbacks: SetbackSpec) -> Polygon2D:
    """
    退线近似：取四边最大值做均匀 inset。

    各向不等退线的精确偏移留给后续；Alpha 文档标明此近似。
    """
    dist = max(setbacks.north, setbacks.south, setbacks.east, setbacks.west)
    return uniform_inset(poly, dist)


def contains_axis_aligned_rect(
    buildable: Polygon2D,
    *,
    x: float,
    y: float,
    width: float,
    depth: float,
    eps: float = 1e-6,
) -> bool:
    """轴对齐矩形是否完全落在可建多边形内。"""
    from shapely.geometry import box

    geom = polygon_to_shapely(buildable)
    rect = box(x + eps, y + eps, x + width - eps, y + depth - eps)
    if rect.is_empty or rect.area <= 0:
        return False
    return bool(geom.covers(rect))


def orthogonal_free_rects(buildable: Polygon2D, *, eps: float = 1e-9) -> list[Rect]:
    """
    将**正交**可建多边形分解为互不重叠的轴对齐矩形覆盖。

    算法：坐标网格 → 标记内部格 → 贪心合并为极大矩形。
    非正交输入 → IrregularGeometryError。
    """
    if not is_orthogonal_polygon(buildable, eps=eps):
        raise IrregularGeometryError(
            "orthogonal_free_rects 仅支持正交边多边形（L 形 / 矩形洞庭院）"
        )

    geom = polygon_to_shapely(buildable)
    xs: set[float] = set()
    ys: set[float] = set()
    for x, y in geom.exterior.coords:
        xs.add(round(float(x), 9))
        ys.add(round(float(y), 9))
    for ring in geom.interiors:
        for x, y in ring.coords:
            xs.add(round(float(x), 9))
            ys.add(round(float(y), 9))
    x_list = sorted(xs)
    y_list = sorted(ys)
    if len(x_list) < 2 or len(y_list) < 2:
        return []

    from shapely.geometry import Point

    # cell[i][j] covers [x_i, x_{i+1}] x [y_j, y_{j+1}]
    nx = len(x_list) - 1
    ny = len(y_list) - 1
    inside = [[False] * ny for _ in range(nx)]
    for i in range(nx):
        for j in range(ny):
            cx = 0.5 * (x_list[i] + x_list[i + 1])
            cy = 0.5 * (y_list[j] + y_list[j + 1])
            inside[i][j] = bool(geom.contains(Point(cx, cy)) or geom.touches(Point(cx, cy)))

    used = [[False] * ny for _ in range(nx)]
    rects: list[Rect] = []

    for i0 in range(nx):
        for j0 in range(ny):
            if used[i0][j0] or not inside[i0][j0]:
                continue
            # 向右扩展最大宽度
            i1 = i0
            while i1 + 1 < nx and inside[i1 + 1][j0] and not used[i1 + 1][j0]:
                i1 += 1
            # 向上扩展，保持宽度 [i0,i1]
            j1 = j0
            while j1 + 1 < ny:
                if all(inside[i][j1 + 1] and not used[i][j1 + 1] for i in range(i0, i1 + 1)):
                    j1 += 1
                else:
                    break
            for i in range(i0, i1 + 1):
                for j in range(j0, j1 + 1):
                    used[i][j] = True
            w = x_list[i1 + 1] - x_list[i0]
            d = y_list[j1 + 1] - y_list[j0]
            if w > eps and d > eps:
                rects.append(Rect(x=x_list[i0], y=y_list[j0], width=w, depth=d))

    rects.sort(key=lambda r: (-r.area, r.x, r.y))
    return rects


def prepare_buildable_rects(
    *,
    site_polygon: Polygon2D | None = None,
    buildable_polygon: Polygon2D | None = None,
    setbacks: SetbackSpec | None = None,
    fallback_rect: Rect2D | None = None,
) -> list[Rect]:
    """
    得到可供 packing 使用的 free rect 列表。

    优先 buildable_polygon；否则 site_polygon + setbacks；
    再否则 fallback 矩形（兼容默认路径）。
    """
    poly = buildable_polygon
    if poly is None and site_polygon is not None:
        poly = inset_with_setbacks(site_polygon, setbacks or SetbackSpec())
    if poly is not None:
        return orthogonal_free_rects(poly)
    if fallback_rect is not None:
        return [
            Rect(
                x=fallback_rect.x,
                y=fallback_rect.y,
                width=fallback_rect.width,
                depth=fallback_rect.depth,
            )
        ]
    raise IrregularGeometryError("无多边形或 fallback 矩形可构建可建面")
