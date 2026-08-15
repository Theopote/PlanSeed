# Vertical Systems — 竖向空洞统一提案

> **状态**：设计存档 + 部分已落地（见 §6）。  
> **关联 ADR**：[ADR-010 — Vertical Voids](../adr/010-vertical-voids.md)（**Proposed**，未 Accept）。  
> **不代表排期承诺**；已落地部分以代码与测试为准。

---

## 1. 问题

独栋住宅平面生成里，三类竖向约束长期被混为一谈或缺失：

| 类型 | 用户语义 | 旧版行为 |
|------|----------|----------|
| **楼梯核** | 每层可达的竖向交通 | 唯一一等公民：`StairCore` 预扣除 + `stair-*` placement |
| **天井 / 采光井** | 合法留白、上下贯通 | **不存在**；任何未铺满面积一律判 `layout_coverage` 缺陷 |
| **湿区立管** | 卫生间/厨房跨层叠置 | 有 `WetStack` 技术锚 + 软评分，但 IoU 门槛 ≈ 0，几乎不拒绝 |

`RoomSpec.daylight_required` 只影响 Environment 轴评分，**不会**在几何上开洞——语义与实现脱节。

本提案用统一的 **`VerticalVoidSpec`** 描述输入意图，但在 **solver 内部分两条几何路径**（预扣除 vs 事后对齐），避免强行一套算法套三种物理含义。

---

## 2. 概念模型

```
Requirement / ProjectSpec
    vertical_voids: list[VerticalVoidSpec]
            │
            ▼ normalize ──► DesignProgram.vertical_voids
            │
            ├─ STAIR / ATRIUM ──► build_prededuction_plan()
            │                      holes_by_floor → zone 裁剪 → void-* placement
            │
            └─ WET_RISER ───────► Step A: checker 硬约束 (IoU≥0.6)
                                   Step B: 锚层先行 + 上层湿区预放置
            │
            ▼
    LayoutCandidate
        floors[].placements      (含 stair-* / void-* / program 房间)
        vertical_void_placements (ATRIUM 几何快照，可追溯)
        wet_stacks               (技术锚，≠ 功能分区)
```

### 2.1 三者不可混用

| `void_type` | 几何策略 | 输出形态 |
|-------------|----------|----------|
| `stair` | **预扣除** | 每层 `stair-{floor_id}`；`floor_span` **必须**覆盖全部楼层 |
| `atrium` | **预扣除** | 每层 `void-{id}`；`floor_span` 为连续 ≥2 层区间 |
| `wet_riser` | **不预扣除** | 无 `void-*`；靠湿区房间 footprint 跨层对齐 |

**关键原则**：`VerticalVoidSpec` 统一的是**数据模型与跨层位置约束概念**，不是 placement 函数。STAIR/ATRIUM 用 `solver/vertical/prededuction.py`；WET_RISER 用 `solver/generators/wet_anchor.py` + `solver/evaluation/vertical.py`。

---

## 3. Schema

### 3.1 输入：`VerticalVoidSpec`

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
    alignment_tolerance: float = 0.3       # 仅 WET_RISER（米）；映射 IoU 下限见 min_iou_for_wet_riser_tolerance()
```

校验：`validate_vertical_voids_for_floors()` — STAIR 全覆盖、ATRIUM/WET_RISER ≥2 层、id 唯一。

### 3.2 输出：`VerticalVoidPlacement`

```python
class VerticalVoidPlacement(BaseModel):
    void_id: str
    void_type: VerticalVoidType
    floor_id: str
    rect: PlacementRect
    skylight_required: bool = False
```

挂接于 `LayoutCandidate.vertical_void_placements`。同层另有 `void-{id}` 的 `RoomPlacement`（`source=generated`），用于满铺覆盖率与 fill/grow。

### 3.3 隐式 STAIR

`vertical_voids` **为空**时，solver 行为与旧版一致：隐式 `StairCoreSpec` + `place_stair_core_resolving`，**不**写入 `vertical_voids` 列表。显式声明 STAIR void 时，尺寸/区位偏好以 void 为准（`resolve_stair_core_spec_for_program`）。

---

## 4. 算法路径

### 4.1 预扣除（STAIR / ATRIUM）

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

### 4.2 湿区立管（WET_RISER）— Step A

**模块**：`solver/evaluation/vertical.py` → `wet_stack_alignment_violations()`

- 相邻楼层湿区按 `wet_stack_pairing_key()`（`semantic_role` / `tags`）配对
- 仅当**两层均有同 key 湿区**时检查（单层独有厨房/主卫不强制）
- 逐对 IoU ≥ 阈值（默认 **0.6**；有 `WET_RISER` 时按 `alignment_tolerance` 映射），否则 `vertical.wet_stack_alignment` **hard**

**Checker**：`solver/constraints/checker_impl.py::_check_wet_stack_alignment`

### 4.3 湿区立管 — Step B

**模块**：`solver/generators/wet_anchor.py`

1. **锚层**：湿区目标面积最大的楼层（benchmark 为 F1）先正常 zone 打包
2. **收集锚**：`collect_wet_anchor_rects()` → `pairing key → Rect`
3. **上层预放置**：`preplace_wet_anchored_rooms()` 将同 key 湿区对齐到锚矩形
4. Zone 裁剪 + 打包后裁剪，避免与楼梯/天井重叠

**benchmark 实测**（`candidate_count=32`）：

| 阶段 | valid 率 | 说明 |
|------|----------|------|
| 仅 Step A | ~28% (9/32) | 硬筛有效但候选不足 |
| Step A + B | ~81% (26/32) | 生成器主动对齐，Top-K 仍全 valid |

---

## 5. 满铺覆盖率 vs 合法留白

近期修复要求 footprint 被 placements **完全铺满**（`geometry.layout_coverage`）。天井与非法 gap 几何上相同，必须区分：

| 空白来源 | 判定 |
|----------|------|
| `void-{atrium_id}` placement 覆盖 | **合法**（计入已放置面积） |
| 无对应 `VerticalVoidSpec` 的剩余区域 | **非法** → `layout_coverage` hard |

当前实现：天井作为 `generated` placement 参与满铺，**无需**在 `layout_coverage_violations` 单独豁免。`vertical_void_placements` 提供 ADR 可追溯性；export / SVG 可读取 `skylight_required`。

---

## 6. 落地状态（2026-08-15）

| 能力 | 状态 | 主要路径 |
|------|------|----------|
| `VerticalVoidSpec` schema | ✅ | `packages/schema/vertical_void.py` |
| `ProjectSpec` / `DesignProgram` 字段 | ✅ | `project.py`, `program.py` |
| STAIR 预扣除（隐式 + 显式 void） | ✅ | `prededuction.py`, `guillotine.py` |
| ATRIUM 预扣除 + 跨层对齐 | ✅ | 同上 |
| 固定区裁剪 / 重叠检测 | ✅ | `coverage.py`, `checker_impl.py` |
| 湿区 Step A 硬约束 | ✅ | `vertical.py`, `checker_impl.py` |
| 湿区 Step B 锚层预放置 | ✅ | `wet_anchor.py`, `guillotine.py` |
| `VerticalVoidPlacement` 输出 | ✅ | `layout.py` / `vertical_void.py` |
| 回归测试 | ✅ | `test_vertical_void*.py`, `test_wet_stack_alignment.py`, `test_wet_anchor.py` |
| `WET_RISER` 写入 normalizer / LLM | ☐ | 需从 `wet_stack_preference` 等推导 |
| `alignment_tolerance` → IoU 联动 | ✅ | `min_iou_for_wet_riser_tolerance()`；checker 按楼对读取 WET_RISER |
| `daylight_required` → 自动 ATRIUM | ☐ | 仅评分轴 |
| SVG / DesignReport 天井标注 | ✅ | `svg.py` ATRIUM 叠加 + 顶层天窗符号 |
| DesignFinding 免责声明 | ☐ | 「heuristic-only，非规范符合性」 |
| ADR-010 Accept | ☐ | 待 v0.1.x 观察窗口 |

---

## 7. 输入示例

### 7.1 贯通两层天井（benchmark 改造）

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

### 7.2 显式楼梯 void

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

### 7.3 湿区立管（声明式，solver 侧 Step A/B 已生效）

```python
VerticalVoidSpec(
    id="wet-riser-1",
    void_type=VerticalVoidType.WET_RISER,
    floor_span=("F1", "F2"),
    alignment_tolerance=0.3,
)
```

当前：**schema 可校验**，但 benchmark 未挂此 void 时，湿区对齐仍由 implicit WetStack + Step A/B 保证。Normalizer 尚未自动注入。

---

## 8. 测试与回归

| 测试文件 | 覆盖点 |
|----------|--------|
| `packages/schema/tests/test_vertical_void.py` | schema 校验、normalize 透传 |
| `solver/tests/test_vertical_void_prededuction.py` | 预扣除、满铺、无重叠、向后兼容 |
| `solver/tests/test_wet_stack_alignment.py` | Step A 硬约束 + pipeline 批量 seed |
| `solver/tests/test_wet_anchor.py` | Step B r3↔r9 对齐 |
| `solver/tests/test_layout_coverage.py` | 与 atrium 交叉：满铺仍成立 |

批量门槛见 `solver/tests/quality_baselines.py`（湿区 Step A/B 后 valid ≈ 81%）。

---

## 9. 后续工作（建议优先级）

1. **Normalizer**：`preferences.wet_stack_preference` / 多层湿区 → 注入 `WET_RISER` void；`daylight_required` + 多层 → 可选 `ATRIUM` 草案（须用户确认，非自动法规结论）
2. **`alignment_tolerance`**：✅ `min_iou_for_wet_riser_tolerance()`（反比：0.3 m → 0.6 IoU）
3. **SVG 叠加层**：✅ `void-*` / `skylight_required` 标注（`solver/visualize/svg.py`）
4. **DesignFinding**：湿区对齐 / 天井仅「几何可能性」声明，非给排水施工图深度
5. **ADR-010 Accept**：Alpha 观察窗结束后，结合桌面 smoke 与 blind 案例复评

---

## 10. 非目标（与 ADR-009 一致）

- 管径、坡度、检修口、通气帽出屋面位置
- Shapely 非矩形竖井轮廓
- 云端规范合规引擎

本系统只回答：**在当前矩形 footprint 假设下，房间几何是否为竖向贯通留出可能**——heuristic-only。

---

## 11. 相关文件索引

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
