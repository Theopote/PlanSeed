# Vertical Systems — 竖向空洞统一提案

> **状态**：设计存档 + **大部分已落地**（见 §7）。  
> **关联 ADR**：[ADR-010 — Vertical Voids](../adr/010-vertical-voids.md)（**Proposed**，未 Accept）。  
> 已落地部分以代码与测试为准；未勾选项不代表排期承诺。

---

## 1. 问题背景

三条独立线索，在最近一轮平面质量检查里合并到了一起：

1. **面积与 footprint 不匹配**：房间目标面积和用地面积经常对不上（尤其上层楼面积需求 < footprint）。修复面积失控 bug 之后，多余面积被强行摊给某个房间（撞到 `DEFAULT_MAX_AREA_FACTOR` 上限），本质是「多余空间该去哪」被回避而非解决。
2. **湿区跨层对齐形同虚设**：旧版按每层湿区 AABB 整体 IoU 评分，checker 门槛 ≈ 0 且 `hard=False`（见 ADR-010 Context）。管线贯通性并未被真正保证。
3. **天井/采光井缺失于 schema**：`daylight_required` 只影响 Environment 轴评分，**不会**在几何上开洞。

三条线索指向同一方向：**把「竖向占位、跨层锁定位置」做成统一、显式的一等公民**，而不是让「多余空间」和「对不齐的湿区」成为生成算法的副产品。

### 1.1 三类竖向约束（对照表）

| 类型 | 用户语义 | 旧版行为 |
|------|----------|----------|
| **楼梯核** | 每层可达的竖向交通 | 唯一一等公民：`StairCore` 预扣除 + `stair-*` placement |
| **天井 / 采光井** | 合法留白、上下贯通 | **不存在**；任何未铺满面积一律判 `layout_coverage` 缺陷 |
| **湿区立管** | 卫生间/厨房跨层叠置 | 有 `WetStack` 技术锚 + 软评分，但 IoU 门槛 ≈ 0，几乎不拒绝 |

本提案用统一的 **`VerticalVoidSpec`** 描述输入意图，但在 **solver 内部分两条几何路径**（预扣除 vs 事后对齐），避免强行一套算法套三种物理含义。

---

## 2. 天井方案对比（产品决策，算法不替你选）

| | 方案 A 全贯通 | 方案 B 顶部两层 | 方案 C 底部两层 |
|---|---|---|---|
| `floor_span` 示例（3 层） | `(F1, F3)` | `(F2, F3)` | `(F1, F2)` |
| 结构影响 | 每层楼板都要绕洞，梁转换多 | 仅顶层楼板开洞 | 仅二层楼板开洞（两层住宅则无中间楼板影响） |
| 防水节点 | 单一顶部采光顶，渗漏影响全楼 | 单一顶部天窗，影响范围小 | 玻璃顶同顶部；露天则需考虑排水 |
| 采光/通风 | 最优 | 楼梯间采光，效果集中在楼梯周边 | 底层厅厨采光，类似合院天井 |
| 私密性 | 各层可能互视，需栏杆/视线设计 | 影响小（多为楼梯间） | 影响小（多为公共空间） |
| 独栋性价比 | 偏低，适合层数多、预算宽裕 | **高，推荐默认** | 高，适合内庭院感 |

`VerticalVoidSpec.floor_span` 三种取值分别对应上表——**算法层面完全对称支持**，选哪种是产品/用户决策，不是本提案要下的结论。

---

## 3. 概念模型

```
Requirement / ProjectSpec
    vertical_voids: list[VerticalVoidSpec]
            │
            ▼ normalize ──► DesignProgram.vertical_voids
            │
            ├─ STAIR / ATRIUM ──► build_prededuction_plan()
            │                      holes_by_floor → zone 裁剪 → void-* placement
            │
            └─ WET_RISER ───────► Step A: checker 硬约束 (IoU 阈值)
                                   Step B: 锚层先行 + 上层湿区预放置
            │
            ▼
    LayoutCandidate
        floors[].placements      (含 stair-* / void-* / program 房间)
        vertical_void_placements (ATRIUM 几何快照，可追溯)
        wet_stacks               (技术锚，≠ 功能分区)
```

### 3.1 三者不可混用

| `void_type` | 几何策略 | 输出形态 |
|-------------|----------|----------|
| `stair` | **预扣除** | 每层 `stair-{floor_id}`；`floor_span` **必须**覆盖全部楼层 |
| `atrium` | **预扣除** | 每层 `void-{id}`；`floor_span` 为连续 ≥2 层区间 |
| `wet_riser` | **不预扣除** | 无 `void-*`；靠湿区房间 footprint 跨层对齐 |

**关键原则**：`VerticalVoidSpec` 统一的是**数据模型与跨层位置约束概念**，不是 placement 函数。STAIR/ATRIUM 用 `solver/vertical/prededuction.py`；WET_RISER 用 `solver/generators/wet_anchor.py` + `solver/evaluation/vertical.py`。

---

## 4. Schema

### 4.1 输入：`VerticalVoidSpec`

定义于 `packages/schema/vertical_void.py`，挂接点：

- `ProjectSpec.vertical_voids`（用户 / LLM 可填）
- `DesignProgram.vertical_voids`（`from_project` / `normalize` 透传）

```python
class VerticalVoidType(StrEnum):
    STAIR = "stair"
    ATRIUM = "atrium"
    WET_RISER = "wet_riser"

class VerticalVoidSpec(BaseModel):
    id: str
    void_type: VerticalVoidType
    floor_span: tuple[str, str]   # 按 floors 声明顺序的闭区间端点
    width: float | None = None     # ATRIUM 必填；STAIR 可空 → SiteSpec / 默认 1.8×4.2
    depth: float | None = None
    preferred_placement: CorePlacement | None = None
    skylight_required: bool = False      # 仅 ATRIUM
    alignment_tolerance: float = 0.3       # 仅 WET_RISER（米）；映射 IoU 见 min_iou_for_wet_riser_tolerance()
```

校验：`validate_vertical_voids_for_floors()` — STAIR 全覆盖、ATRIUM/WET_RISER ≥2 层、id 唯一；`floor_span` 端点须存在于 `floors`（顺序无关，内部按 floors 声明顺序解析连续区间）。

**WET_RISER IoU 映射**：`min_iou = clamp(0.6 × 0.3 / alignment_tolerance)`；无覆盖楼对的 WET_RISER 时 checker 仍用默认 0.6。

### 4.2 输出：`VerticalVoidPlacement`

```python
class VerticalVoidPlacement(BaseModel):
    void_id: str
    void_type: VerticalVoidType
    floor_id: str
    rect: PlacementRect
    skylight_required: bool = False
```

挂接于 `LayoutCandidate.vertical_void_placements`。同层另有 `void-{id}` 的 `RoomPlacement`（`source=generated`），用于满铺覆盖率与 fill/grow。

### 4.3 隐式 STAIR（向后兼容）

`vertical_voids` **为空**时，solver 行为与旧版一致：隐式 `StairCoreSpec` + `place_stair_core_resolving`，**不**写入 `vertical_voids` 列表。显式声明 STAIR void 时，尺寸/区位偏好以 void 为准（`resolve_stair_core_spec_for_program`）。

---

## 5. 算法路径

### 5.1 预扣除（STAIR / ATRIUM）

**模块**：`solver/vertical/prededuction.py` → `build_prededuction_plan()`

1. 放置楼梯核（锁定位 / seed 解析 / `CorePlacement` 尝试顺序）
2. 对每个 ATRIUM：在剩余 footprint 内放置矩形，**避开**已放置的 stair/atrium
3. 产出 `holes_by_floor[floor_id] = [stair_rect, …atrium_rects_on_floor]`

**Guillotine 接入**（`solver/generators/guillotine.py`）：

- `_free_on_floor`：按层扣除 `holes_by_floor`
- WetStack 跨层锚仍只扣楼梯（天井按层处理，不污染他层 zone 规划）
- Zone 打包前：`prededuction_obstacles` 裁剪 zone 矩形
- 打包后：`clip_placement_away_from_obstacles` 防止 program 房间侵入固定区
- 每层写入 `stair-*` + `void-*` placement

**固定区保护**（`solver/geometry/coverage.py`）：

- `is_fixed_void_placement()`：`stair-*` / `void-*` 不参与 grow/fill donor
- `placement_overlap_violations()`：checker 硬拒绝侵入

### 5.2 湿区立管（WET_RISER）— Step A

**模块**：`solver/evaluation/vertical.py` → `wet_stack_alignment_violations()`

- 相邻楼层湿区按 `wet_stack_pairing_key()`（`semantic_role` / `tags`）配对
- 仅当**两层均有同 key 湿区**时检查（单层独有厨房/主卫不强制）
- 逐对 IoU ≥ 阈值（默认 **0.6**；有 `WET_RISER` 时按 `alignment_tolerance` 映射），否则 `vertical.wet_stack_alignment` **hard**

**Checker**：`solver/constraints/checker_impl.py::_check_wet_stack_alignment`

### 5.3 湿区立管 — Step B

**模块**：`solver/generators/wet_anchor.py`

1. **锚层**：湿区目标面积最大的楼层（benchmark 为 F1）先正常 zone 打包
2. **收集锚**：`collect_wet_anchor_rects()` → `pairing key → Rect`
3. **上层预放置**：`preplace_wet_anchored_rooms()` 将同 key 湿区对齐到锚矩形
4. Zone 裁剪 + 打包后裁剪，避免与楼梯/天井重叠

**benchmark 实测**（历史 `candidate_count=32`；默认已提至 **64**）：

| 阶段 | valid 率（n=32） | 说明 |
|------|------------------|------|
| 仅 Step A | ~28% (9/32) | 硬筛有效但候选不足 |
| Step A + B | ~81% (26/32) | 生成器主动对齐，Top-K 仍全 valid |

默认 `SolverConfig.candidate_count=64`（ADR-010 Step A 后扩大候选池）。

---

## 6. 满铺覆盖率 vs 合法留白

近期修复要求 footprint 被 placements **完全铺满**（`geometry.layout_coverage`）。天井与非法 gap 几何上相同，必须区分：

| 空白来源 | 判定 |
|----------|------|
| `void-{atrium_id}` placement 覆盖 | **合法**（计入已放置面积） |
| 无对应 placement 的剩余区域 | **非法** → `layout_coverage` hard |

当前实现：天井作为 `generated` placement 参与满铺，**无需**在 `layout_coverage_violations` 单独豁免。`vertical_void_placements` 提供 ADR 可追溯性；SVG 可读取 `skylight_required`（`solver/visualize/svg.py`）。

---

## 7. 落地状态（2026-08-15）

| 能力 | 状态 | 主要路径 |
|------|------|----------|
| `VerticalVoidSpec` schema | ✅ | `packages/schema/vertical_void.py` |
| `ProjectSpec` / `DesignProgram` 字段 | ✅ | `project.py`, `program.py` |
| STAIR 预扣除（隐式 + 显式 void） | ✅ | `prededuction.py`, `guillotine.py` |
| ATRIUM 预扣除 + 跨层对齐 | ✅ | 同上 |
| 固定区裁剪 / 重叠检测 | ✅ | `coverage.py`, `checker_impl.py` |
| 合法 ATRIUM 空白 vs 非法 gap | ✅ | `void-*` placement 计入满铺 |
| 湿区 Step A 硬约束 | ✅ | `vertical.py`, `checker_impl.py` |
| 湿区 Step B 锚层预放置 | ✅ | `wet_anchor.py`, `guillotine.py` |
| `VerticalVoidPlacement` 输出 | ✅ | `layout.py` / `vertical_void.py` |
| `alignment_tolerance` → IoU 联动 | ✅ | `min_iou_for_wet_riser_tolerance()` |
| SVG 天井 / 天窗标注 | ✅ | `solver/visualize/svg.py` |
| 默认 `candidate_count=64` | ✅ | `packages/schema/program.py` |
| 房间长宽比硬约束（`geometry.room_aspect_ratio`） | ✅ | `geometry.py`, `checker_impl.py`；阈值 2.2 |
| 生成器长宽比启发式 + 重叠消解 | ✅ | `guillotine.py`, `coverage.py`（`clamp` / `resolve_placement_overlaps`） |
| 回归测试 | ✅ | 见 §9 |
| `WET_RISER` 写入 normalizer / LLM | ☐ | 需从 `wet_stack_preference` 等推导 |
| `daylight_required` → 自动 ATRIUM | ☐ | 仅评分轴；须用户确认 |
| DesignFinding 免责声明 | ☐ | 「heuristic-only，非规范符合性」 |
| ADR-010 Accept | ☐ | 待 v0.1.x 观察窗口 |

---

## 8. 输入示例

### 8.1 贯通两层天井（benchmark 改造）

```python
VerticalVoidSpec(
    id="atrium-1",
    void_type=VerticalVoidType.ATRIUM,
    floor_span=("F1", "F2"),
    width=3.0,
    depth=3.0,
    preferred_placement=CorePlacement.CENTER,
    skylight_required=True,
)
```

挂到 `benchmark_program().vertical_voids` 后：`GuillotineGenerator` 在 F1/F2 同位扣除 3×3 m，产出 `void-atrium-1` 与 `vertical_void_placements`。

### 8.2 显式楼梯 void

```python
VerticalVoidSpec(
    id="stair-core",
    void_type=VerticalVoidType.STAIR,
    floor_span=("F1", "F2"),  # 必须等于全部楼层
    width=2.0,
    depth=4.5,
    preferred_placement=CorePlacement.WEST,
)
```

等价于 `default_stair_void(floor_ids)`，但覆盖默认 1.8×4.2。

### 8.3 湿区立管（声明式）

```python
VerticalVoidSpec(
    id="wet-riser-1",
    void_type=VerticalVoidType.WET_RISER,
    floor_span=("F1", "F2"),
    alignment_tolerance=0.3,
)
```

benchmark 未挂此 void 时，湿区对齐仍由 implicit WetStack + Step A/B 保证（默认 IoU 0.6）。声明 WET_RISER 后，覆盖楼对按 `alignment_tolerance` 映射阈值。

---

## 9. 测试与回归

| 测试文件 | 覆盖点 |
|----------|--------|
| `packages/schema/tests/test_vertical_void.py` | schema 校验、normalize 透传、IoU 映射 |
| `solver/tests/test_vertical_void_prededuction.py` | 预扣除、满铺、无重叠、向后兼容 |
| `solver/tests/test_wet_stack_alignment.py` | Step A 硬约束 + WET_RISER 容差 + pipeline 批量 seed |
| `solver/tests/test_wet_anchor.py` | Step B r3↔r9 对齐 |
| `solver/tests/test_layout_coverage.py` | 满铺仍成立 |
| `solver/tests/test_aspect_ratio_constraint.py` | 长宽比硬约束 + fill/clamp 不引入重叠 |
| `solver/tests/test_visualize.py` | ATRIUM / skylight SVG 叠加 |

批量门槛见 `solver/tests/quality_baselines.py`（`candidate_count=64`）。

---

## 10. 后续工作

1. **Normalizer**：`preferences.wet_stack_preference` / 多层湿区 → 注入 `WET_RISER` void；`daylight_required` + 多层 → 可选 `ATRIUM` 草案（须用户确认，非自动法规结论）
2. **DesignFinding**：湿区对齐 / 天井仅「几何可能性」声明，非给排水施工图深度
3. **ADR-010 Accept**：Alpha 观察窗结束后，结合桌面 smoke 与 blind 案例复评

---

## 11. 非目标

- 真实管径、坡度、检修口、通气帽出屋面位置（`alignment_tolerance` 只是几何 footprint 近似容差）
- 用户在 UI 上拖拽天井位置（本提案只做数据模型与 solver；desktop 暴露为独立提案）
- 因本提案顺带改不规则用地 / Shapely（与 ADR-009 独立）
- Shapely 非矩形竖井轮廓、云端规范合规引擎

本系统只回答：**在当前矩形 footprint 假设下，房间几何是否为竖向贯通留出可能**——heuristic-only。

---

## 12. 相关文件索引

| 层级 | 路径 |
|------|------|
| ADR | `docs/adr/010-vertical-voids.md` |
| Schema | `packages/schema/vertical_void.py` |
| 预扣除 | `solver/vertical/prededuction.py` |
| 湿区锚 | `solver/generators/wet_anchor.py` |
| 湿区评价 | `solver/evaluation/vertical.py` |
| 生成器 | `solver/generators/guillotine.py` |
| 覆盖率 | `solver/geometry/coverage.py` |
| Checker | `solver/constraints/checker_impl.py` |
| SVG | `solver/visualize/svg.py` |

---

## 附录 A · 历史实施 Prompt（已完成，仅供归档）

> 原 Downloads 版「决定开工后按顺序丢给 Cursor」的三步 Prompt。当前代码已按此方向落地，路径与初稿略有差异（如 `solver/vertical/prededuction.py` 而非 `solver/circulation/vertical_void.py`）。**勿再重复执行。**

<details>
<summary>Step 1 · Schema + 向后兼容（✅）</summary>

- `VerticalVoidSpec` / `validate_vertical_voids_for_floors`
- `ProjectSpec` / `DesignProgram.vertical_voids`
- 空列表行为与旧版一致

</details>

<details>
<summary>Step 2 · ATRIUM 预扣除（✅）</summary>

- `build_prededuction_plan()` + `guillotine.py` 按层扣洞
- `void-*` placement 计入满铺；`test_vertical_void_prededuction.py`

</details>

<details>
<summary>Step 3 · WET_RISER Step A + B（✅）</summary>

- Step A：`wet_stack_alignment_violations()` hard + IoU 配对
- Step B：`wet_anchor.py` 锚层预放置
- `alignment_tolerance` 映射、`candidate_count` 提至 64

</details>
