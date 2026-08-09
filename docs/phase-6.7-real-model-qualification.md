# Phase 6.7 — Real Model Qualification & LLM Runtime Hardening

> **状态：🚧 In Progress（工程项多已落地；缺本机真模型全量跑分）**  
> 总览：[phase-6-local-llm.md](phase-6-local-llm.md) · [roadmap.md](roadmap.md)  
> 前置：[phase-6.6-requirement-benchmark.md](phase-6.6-requirement-benchmark.md)  
> 下一：[phase-7-deliverables.md](phase-7-deliverables.md)

## 完成标准（比代码更重要）

```text
0–5.1.1    ✅ Design Kernel
6.0–6.6    ✅ LLM Infrastructure
6.7        ← Real Model Qualification & Runtime Hardening
Phase 6    ✅ Alpha Qualified   ← 仅当某本地模型过门
Phase 7    Deliverables / Export ← 其后
```

Harness oracle 100% **只证明工程闭环**，不证明 LLM 可靠。  
**禁止**在未过 Alpha Gate 时写「Phase 6 ✅」。  
**本阶段不做：** 扩 LLM 产品功能 · 回头重构 solver · 提前开工 Phase 7。

## 为什么要有 6.7

Phase 6.0–6.6 证明的是：

```text
Provider Boundary + Schema Gate + Semantic Gate + Benchmark Harness
```

在 **oracle Mock（永远给正确答案）** 下，`field_accuracy` / `case_pass_rate` = 1.0。

这 **不是** 本地模型准确率。

```text
Harness Oracle Pass  ≠  Real Model Accuracy
LLM Infrastructure   ≠  Alpha Qualified
```

6.7 的目标：用真实本地模型跑语料，对照 **Alpha Gate**；可选对比多个候选，判断 **7B 是否已够用**；硬化 Ollama 生命周期与 UI 状态。过门后进入 **Phase 7 Export**，而不是继续扩 LLM。

## Alpha Gate（PlanSeed 内部门槛）

这些数字**不是**行业标准，而是 Alpha 务实门槛。  
**唯一应接近绝对要求**的是 Geometry violation = 0（架构边界）。

| 指标 | Alpha Gate | 对应 summary / gate 键 |
|------|------------|------------------------|
| Geometry violation | **0%** | `geometry_violation_rate` |
| Parse success | ≥ 95% | `parse_success_rate` |
| Scalar field accuracy | ≥ 90% | `field_accuracy` |
| Relation F1 | ≥ 80% | `relation_f1` |
| Unknown hallucination | ≤ 5% | `hallucination_rate` |
| Repair exhausted | ≤ 5% | `repair_exhausted_rate` |
| Case pass rate | ≥ 70% | `case_pass_rate` |

实现：`packages/llm/benchmark/gates.py` · `evaluate_alpha_gates()`。

全部通过 → 可把该模型记为 **Alpha Qualified**，并在路线图写 `Phase 6 ✅ Alpha Qualified`。

## 多模型对比（非排行榜）

默认候选：`qwen2.5:7b`。Provider 已抽象，6.7 **应**快速对比其他本地模型，回答：

> 7B 规模是否已经够 PlanSeed 的需求解析？

若 7B 能过 Alpha Gate，**不要**为了几百分点精度强迫用户装巨大模型——这是 local-first 产品决策。

```bash
# 单模型（默认 PLANSEED_OLLAMA_MODEL）
uv run python -m packages.llm.benchmark.qualify
uv run python -m packages.llm.benchmark.qualify --gate   # 未过门则 exit 1

# 多模型对比
uv run python -m packages.llm.benchmark.qualify --models qwen2.5:7b,qwen2.5:14b
```

输出：

- 单模型 → `docs/baselines/llm-alpha-baseline.json`（含 `alpha_gate`）
- 多模型 → 每模型一份 `llm-alpha-baseline-<name>.json` + `llm-alpha-compare.json`

## 目标

1. **文档纠偏**：oracle 100% 只验证 harness；完成标准见上文  
2. **真模型跑分** + **Alpha Gate** 判定  
3. **Benchmark v2（设计意图）**：`relations` / `floor_preferences` / `orientations`  
4. **Known / Assumption / Unknown 严格化**  
5. **失败归因**：schema / semantic / geometry / JSON / repair  
6. **多模型对比**：判断最小够用规模  
7. **CI 不变**：pytest 仍走 oracle；真模型不挡 merge

## 指标（跑分报告）

| 指标 | 含义 |
|------|------|
| `field_accuracy` | 标量 known 命中率 |
| `case_pass_rate` | 整案通过率 |
| `hallucination_rate` | 违反 `must_unknown` |
| `geometry_violation_rate` | 禁几何输出占比（Gate：须为 0） |
| `parse_success_rate` | `1 - parse_failure_rate` |
| `relation_f1` | 关系意图 F1 |
| `repair_exhausted_rate` | repair 耗尽占比 |
| `schema_fail` / `semantic_fail` / `geometry_violation` / `json_parse_fail` | 失败归因计数 |
| `repair_success` / `repair_exhausted` | repair 结局计数 |
| `average_latency_s` | 单案平均耗时 |
| … | 其余见 `BenchmarkReport.summary()` |

## 改进回路（禁止 Prompt 堆砌）

```text
Benchmark / Alpha Gate
  → 归类失败模式（幻觉 / 漏列 unknown / 关系错 / schema / …）
  → 修 Schema · Semantic Gate · Normalizer · Repair · 评分契约
  → 仅当契约无法表达时，才做最小 Prompt 改动
```

Prompt 是边界说明，不是知识库。

## 运行

本机 Ollama（默认 `127.0.0.1:11434`，模型 `qwen2.5:7b`）：

```bash
uv run python -m packages.llm.benchmark.qualify
uv run python -m packages.llm.benchmark.qualify --limit 3
uv run python -m packages.llm.benchmark.qualify --model qwen2.5:7b --gate
uv run python -m packages.llm.benchmark.qualify --models qwen2.5:7b,<候选>
```

CI：

```bash
uv run pytest packages/llm/tests/test_requirement_benchmark.py packages/llm/tests/test_alpha_gates.py -q
# oracle → harness 100%；Alpha Gate 结构可测；真模型不挡 merge
```

## Definition of Done

1. Alpha Gate 规格文档化 + `evaluate_alpha_gates` 可测 ✅  
2. `qualify` 支持 `--gate` / `--model` / `--models` ✅  
3. Runtime：共享 Provider / close；server+model 两级健康；UI 状态 ✅  
4. Benchmark 设计意图 + 失败归因；oracle 仍 100%（≠ 模型质量）✅  
5. **本机** `qwen2.5:7b` 全量跑分检入 `docs/baselines/`；过门 → Phase 6 ✅ Alpha Qualified  
6. 然后进入 [Phase 7 Deliverables](phase-7-deliverables.md)——**不是**高级分析大杂烩

## 不做

调参竞赛 · 云端 API · CAD/BIM · 几何生成 · 把真模型设为默认 CI 门槛 · 模型排行榜产品化 · 扩 LLM feature · 重构 solver · 提前做 Export 以外的「7+」杂项
