"""桌面简表 → 完整 RequirementSpec（显式 spaces + assumptions）。

不进入 solver.normalize：未给 spaces 时仍由 normalizer 记 unknown。
此处仅服务 API / Desktop 表单路径，把卧室等计数展开为可求解的空间清单。
"""

from __future__ import annotations

from packages.schema.requirements import (
    Assumption,
    RequirementSpec,
    SpaceRequirement,
)
from packages.schema.site import CardinalOrientation


def ensure_spaces_for_solve(req: RequirementSpec) -> RequirementSpec:
    """若已有 spaces 则原样返回；否则按 household 展开（带可追踪 assumption）。"""
    if req.spaces:
        return req

    bedrooms = req.household.bedrooms
    if bedrooms is None:
        return req

    bathrooms = req.household.bathrooms if req.household.bathrooms is not None else max(1, min(bedrooms, 2))
    has_garage = req.household.has_garage
    floor_count = req.floor_count if req.floor_count is not None else (2 if bedrooms >= 2 else 1)
    prefer_south = req.preferences.prefer_south_facing_living

    spaces: list[SpaceRequirement] = []
    n = 0

    def add(
        name: str,
        category: str,
        area: float,
        *,
        floor: str,
        tags: list[str] | None = None,
        orientation: CardinalOrientation | None = None,
    ) -> None:
        nonlocal n
        n += 1
        kwargs: dict = {
            "id": f"r{n}",
            "name": name,
            "category": category,
            "target_area": area,
            "floor_preference": [floor],
            "tags": tags or [],
        }
        if orientation is not None:
            kwargs["preferred_orientation"] = orientation
        spaces.append(SpaceRequirement(**kwargs))

    # 一层公共区
    living_orient = CardinalOrientation.SOUTH if prefer_south else None
    add("客厅", "public", 24.0, floor="F1", orientation=living_orient)
    add("餐厅+厨房", "wet", 16.0, floor="F1", tags=["kitchen"])
    add("卫生间", "wet", 4.0, floor="F1")
    if has_garage is True:
        add("车库/储藏", "other", 15.0, floor="F1", tags=["garage"])

    # 卧室与卫浴
    private_floor = "F2" if floor_count >= 2 else "F1"
    add("主卧", "private", 18.0, floor=private_floor)
    baths_placed = 1  # 一层卫已计
    if bathrooms >= 2:
        add(
            "主卫",
            "wet",
            5.0,
            floor=private_floor,
            tags=["ensuite", "master_bath"],
        )
        baths_placed += 1

    for i in range(2, bedrooms + 1):
        add(f"次卧{i - 1}", "private", 12.0, floor=private_floor)

    while baths_placed < bathrooms:
        add("公共卫生间", "wet", 4.0, floor=private_floor)
        baths_placed += 1

    if floor_count >= 2 and bedrooms >= 3:
        add("书房", "other", 9.0, floor=private_floor)

    assumption = Assumption(
        key="spaces.program.from_household",
        value=f"bedrooms={bedrooms},bathrooms={bathrooms},garage={has_garage}",
        reason="桌面简表未给空间清单，按户型计数展开住宅程序（非 benchmark 静默套用）",
    )
    return req.model_copy(
        update={
            "spaces": spaces,
            "floor_count": floor_count,
            "assumptions": [*req.assumptions, assumption],
        }
    )
