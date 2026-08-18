# Layout Benchmark Suite v1

> **用途：** 判定 generator strategy（尤其 MaxRect）是否可进入 Alpha candidate pool。  
> **不是：** 单 case `benchmark_11x13_2floors` 的同义重复。

实现入口：

- Cases：`solver/fixtures/layout_suite_v1.py`
- Runner：`solver/benchmark/layout_generation.py`
- CLI：`uv run python -m solver.benchmark --suite v1`

## 案例目录

| ID | 覆盖 |
|----|------|
| B01 | 8×10 单层紧凑 |
| B02 | 10×12 单层 3卧 |
| B03 | 11×13 两层（原单 case） |
| B04 | 12×16 两层 + garage |
| B05 | 9×18 窄长 |
| B06 | 16×10 宽浅 |
| B07 | 三层 |
| B08 | 高 privacy（分离/朝向软约束） |
| B09 | open living/dining |
| B10 | 多 wet spaces |
| B11 | room locks |
| B12 | zone locks |

## 推荐跑法

```bash
# 资格判定（建议）
uv run python -m solver.benchmark --suite v1 --count 32 \
  --out docs/baselines/layout_benchmark_suite_v1_n32.json

uv run python -m solver.benchmark --suite v1 --count 64 \
  --out docs/baselines/layout_benchmark_suite_v1_n64.json

# 子集调试
uv run python -m solver.benchmark --suite v1 --cases B01,B03,B05 --count 8

# 列表
uv run python -m solver.benchmark --list-cases
```

## 比较指标

每 case × 每 strategy：

| 指标 | 说明 |
|------|------|
| valid_rate | 硬约束通过率 |
| mean_score / top_score | 总分 |
| area_fit | mean `area_accuracy` |
| mean_aspect_ratio_penalty / aspect_ratio_quality | 长宽比 |
| circulation / privacy / environment | 轴分均值 |
| orientation | 朝向满足 |
| mean_repair_count | mean `connection_repairs` |
| diversity | 几何指纹去重率 |
| runtime_s | 墙钟 |

报告另含 `aggregate`（跨 case 无权重均值）供总览；**不得**只看 aggregate 忽略单 case 劣化。

## 资格结论（纪律）

```text
MaxRect implementation      ✅
MaxRect product qualified   ❌  Suite v1 gate FAILED（solver 0.6 · n=32/n=64 · 2026-08-18）
```

**自动化 gate：** `solver/benchmark/maxrect_qualification.py`  
CLI：`uv run python -m solver.benchmark --suite v1 --count 32 --qualify`

```powershell
.\scripts\run_maxrect_qualify.ps1
.\scripts\run_maxrect_qualify.ps1 -Count 64
.\scripts\run_maxrect_qualify.ps1 -QualifyOnly docs\baselines\layout_benchmark_suite_v1_n32.json
```

### valid_rate 解读（2026-08-18 调查）

**不是 8.4.1 几何回归。** `test_rect_benchmark_regression_unchanged` 确认矩形路径生成指纹不变；ADR-011 走廊修补后 `benchmark_program` valid 仍为 **23/64 ≈ 0.359**。

| 现象 | 解释 |
|------|------|
| 遗留 JSON `valid_rate=1.0` | **过时快照**（2026-08-09，硬约束未进 checker） |
| 当前 `benchmark_program` n=64 | **0.359**（`quality_baselines.py` / ADR-011 已记录） |
| Suite B03 n=64 Guillotine | **0.172**（11/64）；与遗留单 case **不可比**（无车库 vs 含车库） |
| Suite aggregate ~0.17 | 多 case（B04–B12）在当前 solver 下 **双策略均接近 0 valid** |

**B03 主要 hard 失败（Guillotine，n=64）：**

| constraint_id | 无效 seed 数（首要失败） |
|---------------|-------------------------|
| `geometry.layout_coverage` | 41 |
| `geometry.room_aspect_ratio` | 12 |
| `vertical.wet_stack_alignment` | （次位） |
| `area-bound-*` | 若干 |

**`benchmark_program` 主要 hard 失败：** `area-bound-r4`（车库面积界，17）、`geometry.*`（长宽比/覆盖率，24）。

硬约束上线时间线（见 `quality_baselines.py`）：

- 2026-08-09 前：benchmark 报告 `valid_rate=1.0`（软评分，硬 violation 未剔除）
- 2026-08-15 起：area-bound + 长宽比硬约束 → plain **≈0.36**
- 2026-08-18：ADR-011 走廊修补 → valid **不变**

**对 gate 的含义：** aggregate `valid_rate` 反映「硬约束下可解比例」，不是 MaxRect 独有劣化；MaxRect 仍因 `valid_rate` 系统性低于 Guillotine + `top_score` 比值 0.17 而 **FAILED**。

### Suite v1 快照（solver 0.6 · 2026-08-18）

| 指标（aggregate 均值） | n=32 Guillotine | n=32 MaxRect | n=64 Guillotine | n=64 MaxRect |
|------------------------|-----------------|--------------|-----------------|--------------|
| valid_rate | 0.167 | **0.013** | 0.169 | **0.014** |
| area_fit | 0.425 | 0.064 | 0.426 | 0.064 |
| top_score | 45.6 | 7.8 | 45.6 | 7.8 |
| mean_score | 45.2 | 7.7 | 45.2 | 7.7 |

Gate：`PASSED=False`（n=32/n=64 `aggregate_top_score_ratio≈0.17` · 多 case MaxRect `valid_rate=0`）  
n=32 与 n=64 aggregate 一致 → 统计稳定，非采样噪声。

产物：`layout_benchmark_suite_v1_n32.json` · `layout_benchmark_suite_v1_n64.json`（及对应 `_qualification.json`）

**B03（标准两层，无车库）** — 与遗留单 case（`benchmark_program` 含车库）不可直接对比：

| | Guillotine (n=32/64) | MaxRect (n=32/64) |
|--|----------------------|-------------------|
| valid_rate | 0.188 / 0.172 | **0.000** |
| top_score | 91.5 | 0.0 |

```bash
uv run python -m solver.benchmark --count 64 \
  --out docs/baselines/layout_generation_guillotine_vs_maxrect.json
```

**遗留单 case**（`layout_generation_guillotine_vs_maxrect.json` · solver 0.6 · n=64）：

| | Guillotine | MaxRect |
|--|------------|---------|
| valid_rate | 0.359 | **0.094** |
| top_score | 92.8 | 93.9 |
| distinct_valid | 23 | 6 |

硬约束前归档（aspect penalty ≈5.8× 证据仍有效）：`layout_generation_guillotine_vs_maxrect_2026-08-09_pre-hard-constraint.json`

门槛示例（gate v1 已实现）：

1. 各 case `valid_rate` 不得系统性显著低于 Guillotine  
2. `mean_aspect_ratio_penalty` 不得再出现 ~5× 全局劣化  
3. locks cases（B11/B12）可复现且不崩溃  
4. 不得仅因 B03 好看就宣称合格  

Alpha 默认 generator **仍为 Guillotine only**（禁止自动 multi-gen 混入 MaxRect）。
