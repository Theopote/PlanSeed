# ADR-009 — Rect engine remains default; Shapely for irregular sites only

## Status

Accepted（Phase 8.4）

## Context

不规则场地 / 庭院 / 非矩形 footprint 需要多边形运算，但全量迁移 Rect engine 会破坏 Guillotine/MaxRect、locks 与大量确定性测试。

## Decision

1. **默认**仍为 `Rect2D` + `solver.geometry.rect` / `free_rects`  
2. Shapely 仅用于 **opt-in** 不规则场地工具：`solver.geometry.irregular`  
3. 正交多边形可分解为 free rects，供现有 packing **消费**，不改写 packing 内核  
4. `SiteSpec.site_polygon` / `buildable_polygon` 可选；为空则行为与 Phase 8 之前一致  

```bash
uv sync --group research   # shapely + ortools
```

## Consequences

- 禁止「因为有 Shapely 就重写整个求解器」  
- 斜边多边形可表示，但 `orthogonal_free_rects` 会拒绝（Alpha 明确边界）  
- 各向不等退线暂用 max-edge 均匀 inset 近似
