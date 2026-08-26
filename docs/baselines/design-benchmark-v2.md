# Design Benchmark v2 — Baseline

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

## 复现

```bash
# 生成 + 导出
uv run python -m solver.benchmark --suite design-v2 --cases B01,B04,B06,B12 --count 32 \
  --export-svg debug/design-benchmark-v2/review \
  --out debug/design-benchmark-v2/review/report.json

# 合并人工评级
uv run python -m solver.benchmark.design_acceptance \
  --grades-only docs/baselines/design_benchmark_v2_grades_theopote.json \
  --out docs/baselines/design_benchmark_v2_n32_graded.json
```
