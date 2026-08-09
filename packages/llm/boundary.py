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

只输出 JSON（LLMRequirementDraft）：
- known: 用户明确事实
- assumptions: 显式默认（须 reason）；不确定勿猜
- unknowns: 未提供且未推断的项

禁止几何（x/y、墙、门、SVG、placements）。
site.width/depth、spaces[].target_area 可为需求量。
勿编造卧卫/场地；relation_intents 仅限原文有二元谓词（靠近/连通/相连/远离等）。
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
