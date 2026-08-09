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
MaxRect product qualified   ❌ 直到 Suite v1（建议 n=32 与 n=64）通过人工门槛
```

门槛示例（可后续写成 gate 脚本，当前人工）：

1. 各 case `valid_rate` 不得系统性显著低于 Guillotine  
2. `mean_aspect_ratio_penalty` 不得再出现 ~5× 全局劣化  
3. locks cases（B11/B12）可复现且不崩溃  
4. 不得仅因 B03 好看就宣称合格  

Alpha 默认 generator **仍为 Guillotine only**（禁止自动 multi-gen 混入 MaxRect）。
