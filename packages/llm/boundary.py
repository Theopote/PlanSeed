"""LLM 边界：禁止几何；系统提示骨架（6.1 Provider 消费）。"""

from __future__ import annotations

from typing import Any

# 出现在 payload 任意层级即视为越界（LLM NEVER GENERATES GEOMETRY）
# 例外：site.width/depth、spaces[].target_area / min_width（需求量，非坐标）
FORBIDDEN_GEOMETRY_KEYS: frozenset[str] = frozenset(
    {
        "x",
        "y",
        "svg",
        "placements",
        "placement",
        "door_openings",
        "door",
        "doors",
        "wall",
        "walls",
        "wall_axis",
        "wall_coord",
        "rect",
        "rects",
        "coordinates",
        "coordinate",
        "layout_candidate",
        "layout",
        "geometry",
        "polygon",
        "polyline",
        "path_d",
        "transform",
        "hinge_x",
        "hinge_y",
        "stair_x0",
        "stair_y0",
        "stair_x1",
        "stair_y1",
        "snapped",
        "snapped_partner",
    }
)

# 仅在非 site / 非 space 尺寸上下文中禁止
_CONTEXTUAL_SIZE_KEYS: frozenset[str] = frozenset({"width", "depth", "area"})

SYSTEM_PROMPT_SKELETON = """你是 PlanSeed 住宅需求解析器。

只输出 JSON，形状必须符合 LLMRequirementDraft：
- known: 用户明确说出的事实
- assumptions: 你采用的显式默认（必须带 reason）；不确定则不要猜，放入 unknowns
- unknowns: 用户未提供且你未推断的信息

绝对禁止输出几何：x/y、墙坐标、门、SVG、placements、LayoutCandidate。
site.width/depth 与 spaces[].target_area 是需求量，允许。
不要生成完整 RoomSpec 表或求解器内部字段。
不要擅自补全卧室数、卫生间数、场地尺寸等关键未知；用 unknowns 或带 reason 的 assumptions。
"""


class GeometryForbiddenError(ValueError):
    """LLM 输出含几何或布局字段。"""

    def __init__(self, keys: list[str]) -> None:
        self.keys = keys
        super().__init__(f"LLM 输出禁止含几何字段: {', '.join(keys)}")


def _is_allowed_size_context(path: str, key: str) -> bool:
    """site 场地尺寸、spaces 需求面积/最小宽度允许。"""
    if key in {"width", "depth"} and path.endswith(".site"):
        return True
    if key == "target_area" and ".spaces[" in path:
        return True
    if key == "min_width" and ".spaces[" in path:
        return True
    return False


def assert_no_geometry_payload(payload: Any, *, path: str = "$") -> None:
    """递归扫描 dict/list；发现禁键则抛 GeometryForbiddenError。"""
    found: list[str] = []
    _scan(payload, path, found)
    if found:
        uniq = list(dict.fromkeys(found))
        raise GeometryForbiddenError(uniq)


def _scan(node: Any, path: str, found: list[str]) -> None:
    if isinstance(node, dict):
        for key, val in node.items():
            key_l = str(key)
            child = f"{path}.{key_l}"
            if key_l in FORBIDDEN_GEOMETRY_KEYS:
                found.append(child)
            elif key_l in _CONTEXTUAL_SIZE_KEYS and not _is_allowed_size_context(
                path, key_l
            ):
                found.append(child)
            elif key_l == "target_area" and ".spaces[" not in path:
                # target_area 仅允许在 spaces 下
                found.append(child)
            _scan(val, child, found)
    elif isinstance(node, list):
        for i, item in enumerate(node):
            _scan(item, f"{path}[{i}]", found)
