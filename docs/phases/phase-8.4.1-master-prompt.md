# Phase 8.4.1 — Irregular Site Pipeline Integration（Master Prompt）

> **用途**：粘贴到 Cursor Agent，按顺序执行。  
> **目标**：端到端跑通 `site_polygon → buildable → free rects → Guillotine → Checker → Evaluation → SVG/Report`，**不重写 Guillotine**。  
> **边界**：正交多边形 only；斜边 → `IrregularGeometryError`；Alpha Stable（无 polygon）行为 **bit-identical** 回归。

---

## 0. 背景（只读，勿改 scope）

当前已落地（Phase 8.4 Foundation）：

| 层 | 位置 | 状态 |
|----|------|------|
| Schema | `packages/schema/site.py` — `site_polygon` / `buildable_polygon` | ✅ |
| 几何工具 | `solver/geometry/irregular.py` — `prepare_buildable_rects` · `orthogonal_free_rects` · `contains_axis_aligned_rect` | ✅ |
| 测试 | `solver/tests/test_irregular_site.py` — 单元级 decomposition | ✅ |
| ADR | `docs/adr/009-rect-default-shapely-irregular.md` | ✅ |

**断点（必须修）**：

```text
prepare_buildable_rects()  ──✗──►  normalize / DesignProgram
DesignProgram.buildable     ──►  始终 Rect2D envelope（width×depth 或 site 矩形退线）
GuillotineGenerator         ──►  floor_rect = Rect(0,0,w,d)  单矩形
DefaultConstraintChecker    ──►  program_local_buildable() 单矩形 boundary
layout_coverage_violations  ──►  footprint = buildable.width × depth（L 形会算错）
geometry_backend_for        ──►  恒 `rect`（即使输入带 site_polygon）
SVG                         ──►  不绘制 polygon 轮廓
```

**禁止**：

- 重写 Guillotine / MaxRect 为 Shapely solver
- 改 Alpha Stable 默认（Guillotine + axis + heuristic + rect）
- 开 Phase 9 / 新评分轴 / CP-SAT geometry
- 因本任务把 MaxRect 混入 Alpha 默认池

---

## 1. 目标架构

```text
RequirementSpec / ProjectSpec
      ↓
normalize() / DesignProgram.from_project()
      ↓
resolve_buildable_geometry(site)     ← 新 helper
      ├─ buildable: Rect2D             bounding box（坐标系 / rank / SVG 尺寸）
      ├─ buildable_free_rects: list[Rect2D]   prepare_buildable_rects 输出
      └─ buildable_polygon: Polygon2D | None  校验 & 评价用（可建 union）
      ↓
GuillotineGenerator.generate()
      pack_rects = buildable_free_rects or [local_buildable(w,d)]
      shared_free = subtract_rects(pack_rects, [stair_rect])
      free_rects_by_floor = subtract_rects(pack_rects, holes…)
      ↓
ConstraintChecker + layout_coverage（按 pack_rects 面积 union，非 bbox）
      ↓
Evaluation（site metrics 用 polygon contains）
      ↓
provenance.geometry_backend = "shapely-orthogonal"（仅 irregular 路径）
      ↓
SVG debug 层绘制 buildable 轮廓（可选 customer 淡线）
```

**坐标约定**：保持现有 placement frame — origin = buildable bounding box 西北角；free rects 已在 polygon 顶点坐标系内（与 L 形测试一致，起始于 0,0）。

---

## 2. Schema 变更

### 2.1 `packages/schema/program.py`

在 `DesignProgram` 增加（默认值保证旧序列化兼容）：

```python
buildable_free_rects: list[Rect2D] = Field(
    default_factory=list,
    description="可建 free rect 分解；空列表表示退化为单一 buildable 矩形",
)
buildable_polygon: Polygon2D | None = Field(
    default=None,
    description="resolved 可建多边形；irregular 路径用于 boundary / site 评价",
)
```

- `buildable: Rect2D` **保留** — 作为 bounding envelope，不改为 Polygon。
- `from_project()` 仍设 `buildable=envelope`，但 normalize 随后可能覆盖 bbox + 填充 free rects。

### 2.2 版本

- bump `SOLVER_VERSION`：`0.5` → `0.6`（geometry pipeline 接入）
- **不** bump `EVALUATION_VERSION` / `SELECTION_VERSION`（除非七轴权重或 Top-K 规则变了）

### 2.3 Shapely 依赖

- 将 `shapely>=2.0` 从 `[project.optional-dependencies] research` **移到主 `dependencies`**
- irregular site 是产品能力，不能要求用户 `uv sync --group research`
- `ortools` 仍留 research 组

---

## 3. 新模块 `solver/geometry/buildable.py`

实现（命名可微调，职责不变）：

```python
@dataclass(frozen=True)
class BuildableGeometry:
    buildable: Rect2D           # bbox
    free_rects: list[Rect]      # solver.geometry.rect.Rect
    polygon: Polygon2D | None     # resolved buildable polygon
    uses_irregular: bool

def site_has_irregular_input(site: SiteSpec) -> bool:
    return site.buildable_polygon is not None or site.site_polygon is not None

def resolve_buildable_geometry(site: SiteSpec) -> BuildableGeometry:
    """
    - 无 polygon → single rect = site.buildable_envelope，uses_irregular=False
    - 有 polygon → prepare_buildable_rects(..., setbacks=site.setbacks,
                    fallback_rect=site.buildable_envelope)
      bbox = union(free_rects) 的 axis-aligned bounds
      polygon = buildable_polygon or inset(site_polygon, setbacks)
    - free_rects 为空 / 面积≈0 → IrregularGeometryError
    """
```

辅助：

```python
def program_pack_rects(program: DesignProgram) -> list[Rect]:
    if program.buildable_free_rects:
        return [Rect(r.x, r.y, r.width, r.depth) for r in program.buildable_free_rects]
    return [program_local_buildable(program)]

def program_footprint_area(program: DesignProgram) -> float:
    return sum(r.area for r in program_pack_rects(program))
```

放在 `solver/geometry/rect.py` 亦可，但 prefer 独立 `buildable.py` 避免 rect 模块膨胀。

---

## 4. Normalize 接入

### 4.1 `solver/program/normalize.py`

在 `normalize()` 内 `DesignProgram.from_project` 之后：

```python
from solver.geometry.buildable import apply_buildable_geometry  # 或 inline

def apply_buildable_geometry(program: DesignProgram) -> None:
    geom = resolve_buildable_geometry(program.site)
    program.buildable = geom.buildable
    program.buildable_free_rects = [Rect2D(...) for r in geom.free_rects]
    program.buildable_polygon = geom.polygon
```

更新 `_footprint_area()` → 调用 `program_footprint_area(program)`。

### 4.2 `SiteSpec`（可选小改）

当 `site_polygon` 存在且 `buildable_envelope` 为推导矩形时，文档注明 envelope 只是 fallback；**normalize 后** `program.buildable` 以 polygon bbox 为准。  
不必改 `derive_rectangles`  validator 逻辑（避免破坏现有 schema 测试），在 normalize 层覆盖即可。

---

## 5. Generator 接入（Guillotine — 最小 diff）

文件：`solver/generators/guillotine.py`

在 `generate()` 中，替换单矩形假设：

```python
# BEFORE
w, d = buildable.width, buildable.depth
floor_rect = Rect(x=0, y=0, width=w, depth=d)
shared_free = subtract_rects([floor_rect], [stair_rect])

# AFTER
pack_rects = program_pack_rects(program)
w = program.buildable.width   # bbox — rank / prededuction / zone 尺寸仍用
d = program.buildable.depth
shared_free = subtract_rects(pack_rects, [stair_rect])
```

`_free_on_floor()` 同样从 `pack_rects` 出发 subtract holes，**不要**从 `floor_rect` 出发。

`_layout_floor_with_zones()` 里：

```python
# BEFORE
footprint = Rect(x=0, y=0, width=floor_width, depth=floor_depth)
placements = fill_floor_coverage_gaps(footprint, ...)

# AFTER — 见 §6
placements = fill_floor_coverage_gaps_multi(pack_rects, ...)
# 或 fill_floor_coverage_gaps(..., pack_rects=pack_rects)
```

`build_prededuction_plan(..., floor_width=w, floor_depth=d)` — 楼梯放置仍在 bbox 内搜索；需确认 `core_fits` 也检查落在 **union(pack_rects)** 内（见 §7）。

`build_solver_provenance(..., program=program)` — 接入后 `geometry_backend_for` 应返回 `shapely-orthogonal`。

MaxRect 继承 Guillotine `generate()`，无需单独改 unless leaf pack 仍假设单 footprint。

---

## 6. Coverage / Gap fill（关键正确性）

文件：`solver/geometry/coverage.py`

**问题**：L 形 bbox 含不可建角落；对 full bbox 做 `fill_floor_coverage_gaps` 会把 cut-out 填成 circulation → boundary 假阳性或非法满铺。

**改法**（二选一，推荐 A）：

**A. 扩展 API**

```python
def fill_floor_coverage_gaps(
    footprint: Rect | list[Rect],  # 接受 pack_rects
    ...
):
    base = [footprint] if isinstance(footprint, Rect) else footprint
    gaps = subtract_rects(base, placed)
```

**B. 新增** `fill_pack_coverage_gaps(pack_rects, placements, ...)` wrapper。

同步修改：

- `layout_coverage_violations()` — `footprint = program_footprint_area(program)` 或 `pack_coverage_gap(program_pack_rects(...), placed)`
- `assign_residual_gaps_as_circulation()` — 只在 pack_rects union 内分配
- `grow_rooms_to_min_area` / `clamp_program_room_aspect_ratios` — 传入 pack_rects 或 bbox（按现有实现检查是否越界）

---

## 7. Constraint Checker

文件：`solver/constraints/checker_impl.py`

### `_check_boundary`

```python
if program.buildable_polygon is not None:
    for p in placements:
        if not contains_axis_aligned_rect(program.buildable_polygon, x=..., y=..., width=..., depth=...):
            violations.append(geometry.boundary)
else:
    # 现有 contains(buildable_rect, r)
```

可 lazy-import shapely 路径；polygon 已在 normalize 解析。

### `_check_layout_coverage`

已委托 `layout_coverage_violations` — 按 §6 修 footprint 语义即可。

---

## 8. Evaluation / Site metrics

文件：`solver/evaluation/site.py`

`rooms_inside_buildable`：irregular 时用 `contains_axis_aligned_rect(buildable_polygon, ...)` 计数，不用 bbox `contains`。

---

## 9. Provenance

文件：`packages/schema/provenance.py`

```python
def geometry_backend_for(program) -> str:
    if program.buildable_free_rects and (
        program.buildable_polygon is not None
        or site_has_irregular_input(program.site)
    ):
        return GEOMETRY_BACKEND_SHAPELY_ORTHOGONAL
    return GEOMETRY_BACKEND_RECT
```

更新 `solver/tests/test_solver_provenance.py`：

- 无 polygon → 仍 `rect`
- 有 polygon + normalize 后 → `shapely-orthogonal`
- **仅** 在 `site_polygon` 但未 normalize → 仍 `rect`（输入意图 ≠ runtime）

---

## 10. SVG / Report（最小可视化）

文件：`solver/visualize/svg.py`

- debug 模式：若 `site.buildable_polygon` 或 `program.buildable_polygon`，绘制 polygon 外轮廓（虚线，`_MUTED`）
- 各层 stack 尺寸仍用 `program.buildable.width/depth`（bbox）
- 不绘制 site_polygon 与 buildable 差异 unless buildable_polygon resolved

Report provenance 已有 `geometry_backend` 字段 — 无需改 schema。

---

## 11. Pipeline / Rank

文件：`solver/pipeline.py`

`rank_candidates(..., buildable_width=..., buildable_depth=...)` — 保持 bbox 尺寸（diversity 几何比较仍合理）。

---

## 12. 楼梯 / Prededuction

文件：`solver/circulation/stair_core.py` · `solver/vertical/prededuction.py`

确保 `core_fits` / `_place_rect_avoiding_obstacles` 验证 stair rect ⊆ **union(pack_rects)**，而非仅 ⊆ bbox。

实现：在 `build_prededuction_plan` 传入 `pack_rects: list[Rect]`，footprint 检查改为：

```python
def rect_inside_pack(rect: Rect, pack: list[Rect]) -> bool:
    # 保守：rect 四角都在 union 内 — 用 contains_axis_aligned_rect(polygon) 或
    # rect 被 pack 中某 rect contains，或 split rect 逐块检查
```

优先复用 `contains_axis_aligned_rect(buildable_polygon, ...)` 当 polygon 可用。

---

## 13. 测试（必须新增 / 更新）

### 13.1 新文件 `solver/tests/test_irregular_site_e2e.py`

Fixtures：

```python
def l_shape_site_program() -> DesignProgram:
    # L 形 10×10 缺 NE 5×5，可建面积 75㎡
    # 房间总面积 < 75，单层或多层简化
    site = SiteSpec(width=10, depth=10, site_polygon=_l_shape(), ...)
    return normalize(project_spec)
```

Cases：

| 测试 | 断言 |
|------|------|
| `test_normalize_populates_free_rects` | `len(buildable_free_rects) >= 2`，`program_footprint_area ≈ 75` |
| `test_guillotine_l_shape_valid_candidate` | 某 seed 下 `validation.valid` |
| `test_no_placement_in_cutout` | 所有 placement 满足 `contains_axis_aligned_rect` |
| `test_layout_coverage_uses_union_area` | gap ≤ tolerance（非 100㎡） |
| `test_pipeline_irregular_provenance` | top candidate `geometry_backend == shapely-orthogonal` |
| `test_rect_benchmark_regression_unchanged` | `benchmark_program()` seed=0..3 fingerprint 与 main 一致 |

### 13.2 更新现有

- `test_irregular_site.py` — 可加 `prepare_buildable_rects` integration with normalize
- `test_solver_provenance.py` — §9
- `test_layout_coverage.py` — 矩形 regression 不变；可加 irregular skip 或 separate file
- `test_checker.py` — boundary rejects room in L cut-out（手工构造越界 placement）

### 13.3 回归命令

```bash
uv sync
uv run pytest solver/tests/test_irregular_site.py solver/tests/test_irregular_site_e2e.py -q
uv run pytest solver/tests/test_layout_coverage.py solver/tests/test_solver_provenance.py -q
uv run pytest solver/tests/test_quality_regression.py solver/tests/test_pipeline.py -q
uv run pytest -q   # 全量
```

---

## 14. 文档勾选（实现完成后）

- [x] `docs/phases/phase-8-solver-2.0.md` — 8.4.1 ☐ → ✅
- [x] `docs/phases/phase-8.5-alpha-stabilization.md` — 8.4.1 ☐ → ✅
- [x] `docs/solver.md` — Pipeline Integration ✅
- [x] `docs/adr/009-rect-default-shapely-irregular.md` — 注明 8.4.1 已接入
- [ ] `docs/alpha-v0.1-release-notes.md` Known limitations — irregular 仍为 experimental **直到** product qualify 决策（本任务 = engineering complete，是否改 release notes 由人决定）

---

## 15. Definition of Done（8.4.1）

- [x] `normalize()` 对 `site_polygon` / `buildable_polygon` 调用 `prepare_buildable_rects` 并写入 `DesignProgram`
- [x] Guillotine（+ MaxRect 继承链）消费 `buildable_free_rects`，矩形输入零行为变化
- [x] Checker boundary + layout_coverage 对 irregular 正确（cut-out 不可放置、不可被 gap-fill）
- [x] `geometry_backend` 仅在实际 irregular pipeline 时为 `shapely-orthogonal`
- [x] E2E：`run_pipeline` → valid candidate → evaluation → SVG 不 crash
- [x] 全量 pytest 绿；矩形 benchmark seed 回归无 drift
- [x] `SOLVER_VERSION` bump + provenance 测试更新

---

## 16. 执行顺序（Agent checklist）

1. 读 ADR-009 · phase-8-solver-2.0 §8.4.1 · 本 prompt
2. Schema + `buildable.py` + shapely 主依赖
3. `normalize` 接入 + unit test
4. `program_pack_rects` / `program_footprint_area` 全库替换 footprint 语义（generator → coverage → checker → evaluation）
5. Guillotine `generate()` pack_rects 接线
6. Prededuction stair ⊆ pack union
7. Provenance + tests
8. SVG debug outline
9. 全量 pytest + 修 drift
10. 文档勾选

**每步完成后运行相关 pytest，不要一次改完再测。**

---

## 17. 参考代码位置（快速跳转）

| 符号 | 文件 |
|------|------|
| `prepare_buildable_rects` | `solver/geometry/irregular.py:210` |
| `DesignProgram.buildable` | `packages/schema/program.py:91` |
| `from_project` | `packages/schema/program.py:167` |
| `normalize` | `solver/program/normalize.py:20` |
| `GuillotineGenerator.generate` | `solver/generators/guillotine.py:405` |
| `floor_rect` / `shared_free` | `solver/generators/guillotine.py:460-468` |
| `fill_floor_coverage_gaps` | `solver/geometry/coverage.py:940` |
| `layout_coverage_violations` | `solver/geometry/coverage.py:317` |
| `_check_boundary` | `solver/constraints/checker_impl.py:131` |
| `geometry_backend_for` | `packages/schema/provenance.py:83` |
| `program_local_buildable` | `solver/geometry/rect.py:56` |
