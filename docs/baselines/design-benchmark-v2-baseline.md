# Design Benchmark v2 — Baseline

> **规格文档：** [../design-benchmark-v2.md](../design-benchmark-v2.md)（本文件仅存首跑摘要与复现，不重复规格）  
> **首跑：** 2026-08-26 · Guillotine · n=32 · seed=42  
> **自动指标：** [design_benchmark_v2_n32.json](design_benchmark_v2_n32.json)  
> **人工评级：** [design_benchmark_v2_grades_theopote.json](design_benchmark_v2_grades_theopote.json)（reviewer: Theopote）  
> **合并报告：** [design_benchmark_v2_n32_graded.json](design_benchmark_v2_n32_graded.json)

## 主指标：ab_rate（建筑师可接受率）

```text
ab_rate = (count_A + count_B) / 32
```

| Case | valid_rate | **ab_rate** | A | B | C | D(人工) | 解读 |
|------|------------|-------------|---|---|---|---------|------|
| B01 | 0.531 | **0.250** | 6 | 2 | 9 | — | 窄宅可用，最佳 case |
| B04 | 0.625 | **0.031** | 0 | 1 | 19 | — | 双车库几乎不可用 |
| B06 | 0.531 | **0.062** | 0 | 2 | 10 | 5 | 适老一层，动线问题严重 |
| B12 | 0.812 | **0.000** | 0 | 0 | 14 | 12 | valid 最高但无 A/B |

**Aggregate ab_rate: 0.086**（11/128）  
**Aggregate valid_rate: 0.625**（评审子集四 case）

### valid_rate vs ab_rate 落差

| 指标 | 值 | 含义 |
|------|-----|------|
| valid_rate | 62.5% | 硬约束通过率（solver 视角） |
| ab_rate | **8.6%** | 建筑师愿继续深化率（产品视角） |

**7 倍落差** — 证明 Design Benchmark v2 的必要性；自动分数不能代理设计可接受性。

## Failure Patterns（Theopote 首评归纳）

| 优先级 | 模式 | Cases | 建议归属 |
|--------|------|-------|----------|
| P0 | 入口-门厅-楼梯逻辑错误 | B04 | AccessGraph / circulation |
| P0 | 空间串联 / 房间无出口 | B06, B12 | RealizedAccessGraph |
| P0 | 客卫开向错误（面向主卧/厨房而非公区） | B12 | Privacy + door placement |
| P1 | 黑卫生间（无外墙） | B01 | Environment / 落位 |
| P1 | 走廊过多或缺失 | B01, B04, B06 | Circulation / topology |
| P1 | 车库布局浪费 | B04, B12 | Program + site |
| P2 | 门 SVG 图示错误 | B01, B04 | Renderer（非 solver） |

## 优先人工评审 cases（已完成）

B01, B04, B06, B12 — 80/80 valid 候选已评级。

## 自动重跑对照（2026-11-21）

> **不是**新的人工 ab_rate。旧 grades 绑定首跑几何，不可直接套到新候选。  
> 本地产物：`debug/design-benchmark-v2/auto_rerun_n32.json`（gitignore）。  
> 命令：`uv run python -m solver.benchmark --suite design-v2 --cases B01,B04,B06,B12 --count 32 --out debug/design-benchmark-v2/auto_rerun_n32.json`

| Case | 首跑 valid_rate | 重跑 valid_rate | Δ | 重跑 valid 中无 Gate blocker | 有 Gate blocker |
|------|----------------:|---------------:|--:|---------------------------:|----------------:|
| B01 | 0.531 | 0.531 | 0 | 17/17 | 0 |
| B04 | 0.625 | 0.469 | −0.156 | 15/15 | 0 |
| B06 | 0.531 | 0.531 | 0 | 17/17 | 0 |
| B12 | 0.812 | 0.812 | 0 | 20/26 | 6 |

四 case 合计 valid_rate：首跑评审子集 **0.625** → 重跑 **0.586**（B04 明显下降）。

**B04 −5 valid 复核（当前 HEAD）：** 再跑仍为 **20/32 = 0.625**；中间 0.469 为 ExteriorEntry/Gate 收紧窗口态。当前 12 个 invalid 主因：`geometry.missing_room`（bath2）+ 连带 `access.unreachable_room`、床/卫 `area-bound-*`、`vertical.wet_stack_alignment`、洗衣间 `room_aspect_ratio`、偶发车库面积过大——非 ExteriorWallSegment 回归。valid 中 Gate blocker / `private_through` 均为 0。

重跑常见 Gate **warning**（非 blocker）：B06 几乎全部 valid 带 `black_wet`；B01/B04/B12 亦见暗卫/深度访问类 findings。  
**下一步：** 导出 SVG 后按原标准重做 A/B/C/D，才能更新 ab_rate；在此之前不得宣称建筑师接受率已提升。

### 人工 ab_rate 重评门闩（AI Copilot 前）

旧 grades 绑定首跑几何，**不可**套到 ExteriorWallSegment / Gate / Intent 之后的新候选。

```bash
uv run python -m solver.benchmark --suite design-v2 --cases B01,B04,B06,B12 --count 32 \
  --export-svg debug/design-benchmark-v2/review-ab-rerate \
  --out debug/design-benchmark-v2/auto_rerun_for_ab.json
```

**已导出（2026-11-21）：** `review-ab-rerate/{B01,B04,B06,B12}` 各 32 SVG；自动报告 `auto_rerun_for_ab.json`；评级模板 `review-ab-rerate/grades-template.json`。  
当前自动 valid_rate：B01 0.531 · B04 0.625 · B06 0.531 · B12 0.812（聚合 **0.625**）。

人工按 [design-benchmark-v2.md](../design-benchmark-v2.md) 填模板后：

```bash
uv run python -m solver.benchmark.design_acceptance \
  --grades-only debug/design-benchmark-v2/review-ab-rerate/grades-template.json \
  --out docs/baselines/design_benchmark_v2_n32_graded.json
```

**产品 KPI = ab_rate**；Blind 字段准仅衡量需求解析，不替代建筑师接受率。

## 复现

`debug/design-benchmark-v2/` 为本地评审产物（已 gitignore），正式基线写入 `docs/baselines/`。

```bash
# 生成 + 导出（SVG/中间报告仅本地；勿直接覆盖入库 JSON，除非准备同步人工重评）
uv run python -m solver.benchmark --suite design-v2 --cases B01,B04,B06,B12 --count 32 \
  --export-svg debug/design-benchmark-v2/review \
  --out debug/design-benchmark-v2/auto_rerun_n32.json

# 人工评级合并（仅当 grades 对应当前几何）
uv run python -m solver.benchmark.design_acceptance \
  --grades-only docs/baselines/design_benchmark_v2_grades_theopote.json \
  --out docs/baselines/design_benchmark_v2_n32_graded.json
```
