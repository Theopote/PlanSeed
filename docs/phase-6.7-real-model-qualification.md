# Phase 6.7 — Real Model Qualification

> **状态：🚧 In Progress（框架落地；真模型 Alpha Baseline 待本机跑数）**  
> 总览：[phase-6-local-llm.md](phase-6-local-llm.md) · [roadmap.md](roadmap.md)  
> 前置：[phase-6.6-requirement-benchmark.md](phase-6.6-requirement-benchmark.md)

## 为什么要有 6.7

Phase 6.0–6.6 证明的是：

```text
Provider Boundary + Schema Gate + Semantic Gate + Benchmark Harness
```

在 **oracle Mock（永远给正确答案）** 下，`field_accuracy` / `case_pass_rate` = 1.0。

这 **不是** 本地模型准确率。

```text
Harness Oracle Pass  ≠  Real Model Accuracy
Phase 6 框架完成    ≠  LLM 已可靠
```

6.7 的目标：用 **真实** `qwen2.5:7b`（或当前 `PLANSEED_OLLAMA_MODEL`）跑语料，得到可引用的 **LLM Alpha Baseline**。

## 目标

1. **文档纠偏**：明确 oracle 100% 只验证 harness  
2. **真模型跑分**：`use_oracle=False` + repair，产出 latency / repair / parse failure 等  
3. **Benchmark v2（设计意图）**：评分 `relations` / `floor_preferences` / `orientations`  
4. **Known / Assumption / Unknown 严格化**：Detection Recall、Unknown FPR、Assumption Precision（缺 reason 不算命中）  
5. **P0**：relation 端点分别 soft 校验（一端幻觉不可被掩盖）  
6. **CI 不变**：默认 pytest 仍走 oracle；真模型不挡 merge

## 指标（Alpha Baseline）

| 指标 | 含义 |
|------|------|
| `field_accuracy` | 标量 known 命中率 |
| `case_pass_rate` | 整案通过率（含设计意图期望） |
| `hallucination_rate` | 违反 `must_unknown` |
| `geometry_fail_rate` | 含禁几何输出 |
| `repair_rate` / `average_attempts` | repair 使用情况 |
| `parse_failure_rate` | ingest / repair 耗尽失败 |
| `average_latency_s` | 单案平均耗时 |
| `relation_precision` / `relation_recall` | 关系意图 |
| `floor_preference_accuracy` | 楼层偏好 |
| `orientation_accuracy` | 空间朝向 |
| `unknown_detection_recall` | `must_unknown` 被显式列入 `unknowns` 的比例 |
| `unknown_false_positive_rate` | 列入 `unknowns` 但不在 `must_unknown` 的比例 |
| `assumption_precision` / `assumption_recall` | 显式假设命中；缺 reason 不算命中 |
| `unknown_precision` | unknowns 列表精确率（与 FPR 互补） |

## 运行

本机 Ollama（默认 `127.0.0.1:11434`，模型 `qwen2.5:7b`，timeout 120s）：

```bash
uv run python -m packages.llm.benchmark.qualify
# 冒烟：只跑前 N 条
uv run python -m packages.llm.benchmark.qualify --limit 3
```

结果写入：`docs/baselines/llm-alpha-baseline.json`。

CI：

```bash
uv run pytest packages/llm/tests/test_requirement_benchmark.py -q
# 仍为 oracle → 期望 100% harness 通过
```

## Definition of Done

1. relation 端点分别 soft 告警 + 单测  
2. Benchmark 含设计意图用例与评分；oracle 仍 100%  
3. `qualify` CLI 可跑真模型并写出 baseline JSON  
4. roadmap / Phase 6 文档标明：**框架 ✅；可靠度 = Alpha Baseline（真模型数字）**  
5. （可选）把一次完整 `qwen2.5:7b` 跑分检入 `docs/baselines/`

## 不做

调参竞赛 · 云端 API · CAD/BIM · 几何生成 · 把真模型 100% 设为 CI 门槛
