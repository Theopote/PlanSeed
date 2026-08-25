# Design Benchmark v2 — Baseline

> **首跑：** 2026-08-26 · Guillotine · n=32 · seed=42  
> **数据：** [design_benchmark_v2_n32.json](design_benchmark_v2_n32.json)

## 汇总（valid_rate）

| Case | Tier | valid_rate | valid_n/32 | top_score | 备注 |
|------|------|------------|------------|-----------|------|
| B01 | core | 0.531 | 17 | 96.5 | 可用 |
| B02 | core | 0.438 | 14 | 90.1 | 可用 |
| B03 | core | **0.000** | 0 | — | 南向退界 4m 压缩过强 |
| B04 | core | 0.625 | 20 | 88.7 | 可用 |
| B05 | core | **0.000** | 0 | — | 三代同堂程序过满 |
| B06 | core | 0.531 | 17 | 94.7 | 可用 |
| B07 | core | **0.000** | 0 | — | 四卧二层 + 11×14 过紧 |
| B08 | site | **0.000** | 0 | — | 9×20 窄面宽极限 |
| B09 | site | 0.438 | 14 | 89.7 | L 型 irregular |
| B10 | site | 0.531 | 17 | 90.7 | 转角地块 |
| B11 | site | 0.344 | 11 | 93.1 | 阶梯形 irregular |
| B12 | site | 0.812 | 26 | 89.8 | 高退界但用地较大 |

**Aggregate valid_rate:** 0.354

## 解读

1. **Benchmark 正在起作用** — 暴露的是真实程序/场地张力，不是分数微调空间。
2. **0% valid cases（B03/B05/B07/B08）** 应优先调查：是 case 程序过满，还是 solver 硬约束过严。
3. **ab_rate 待人工评级** — 使用 [design-benchmark-v2-grades-template.json](design-benchmark-v2-grades-template.json)，对 valid candidate 评 A/B/C/D 后：

```bash
uv run python -m solver.benchmark --suite design-v2 \
  --merge-grades path/to/grades.json \
  --out docs/baselines/design_benchmark_v2_n32.json
```

4. **优先人工评审 cases：** B01, B04, B06, B12（valid_rate 最高，有 A/B 候选可评）

## 复现

```bash
uv run python -m solver.benchmark --suite design-v2 --count 32 \
  --out docs/baselines/design_benchmark_v2_n32.json
```
