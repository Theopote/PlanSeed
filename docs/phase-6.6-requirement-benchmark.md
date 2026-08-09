# Phase 6.6 — Requirement Benchmark

> **状态：✅ Done（harness / oracle）** · 真模型见 [phase-6.7-real-model-qualification.md](phase-6.7-real-model-qualification.md)  
> 总览：[phase-6-local-llm.md](phase-6-local-llm.md) · [roadmap.md](roadmap.md)  
> 前置：[phase-6.5-nl-generate.md](phase-6.5-nl-generate.md)

## 目标

用**可量化准确率**衡量 NL→RequirementSpec，而非「看起来聪明」：

1. ≥50 条中文住宅需求用例（`text` + `expect` + `must_unknown`）  
2. 字段级打分：楼层 / 卧室 / 场地 / 朝南偏好等  
3. **反幻觉**：未说清的关键项不得装进 known（应在 unknowns 或不出现）  
4. CI：`MockLLMProvider` oracle（按用例期望回草稿）→ 基线 100%（**只验证 harness**）  
5. 可选：真 Ollama 跑分（Phase 6.7 `qualify`，不进默认 CI）

## 重要澄清

```text
CI oracle field_accuracy / case_pass_rate = 1.0
  → 证明：评分器 + Schema/Semantic Gate + 解析流水线在「模型永远正确」时工作正常
  ≠ 证明：qwen2.5:7b 对语料达到 100%
```

真模型数字以 6.7 Alpha Baseline 为准。

## 不做

调参竞赛 · 云端 API · 几何正确性（仍禁止几何）。

## 包布局

```text
packages/llm/benchmark/
  cases.py     # ≥50 用例（含 6.7 设计意图子集）
  score.py     # 标量 / 关系 / 楼层偏好 / 朝向 / 幻觉
  runner.py    # run_benchmark / oracle mock
  report.py    # BenchmarkReport
  qualify.py   # 真模型 qualification CLI（6.7）
```

## 指标

| 指标 | 含义 |
|------|------|
| `field_accuracy` | 期望 known 字段命中率 |
| `case_pass_rate` | 整案全中且无幻觉 |
| `hallucination_rate` | 违反 must_unknown 的比例 |
| `geometry_fail` | 含几何的输出数（应为 0） |

## Definition of Done

1. 用例数 ≥ 50  
2. 评分器单测覆盖命中 / 漏检 / 幻觉  
3. 默认 pytest：oracle mock 全案通过  
4. 详案 / roadmap 勾选；**框架**收口（可靠度见 6.7）
