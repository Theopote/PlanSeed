# ADR-009 — Rect engine remains default; Shapely for irregular foundation only

## Status

Accepted（Phase **8.4 Irregular Geometry Foundation**）  
**未**宣称端到端 irregular site（见 8.4.1 ☐）

## Context

不规则场地 / 庭院 / 非矩形 footprint 需要多边形运算，但全量迁移 Rect engine 会破坏 Guillotine/MaxRect、locks 与大量确定性测试。

## Decision

1. **默认**仍为 `Rect2D` + `solver.geometry.rect` / `free_rects`  
2. Shapely 仅用于 **opt-in foundation 工具**：`solver.geometry.irregular`  
3. 正交多边形可分解为 free rects，**供未来 packing 消费**；当前 **未**接入标准 pipeline  
4. `DesignProgram.buildable` 仍为 `Rect2D`（`from_project` → `buildable_envelope`）  
5. `SiteSpec.site_polygon` / `buildable_polygon` 可选；为空则行为与 Phase 8 之前一致  
6. 各向不等退线暂用 **max-edge 均匀 inset**（conservative approximation），**不是**完整 Advanced Site  

```bash
uv sync --group research   # shapely + ortools
```

## Consequences

- 禁止「因为有 Shapely / polygon 字段就宣称 irregular site supported」  
- 禁止「因为有 Shapely 就重写整个求解器」  
- 斜边多边形可表示，但 `orthogonal_free_rects` 会拒绝（Alpha 明确边界）  
- 端到端接入另开 **8.4.1 Irregular Site Pipeline Integration**
