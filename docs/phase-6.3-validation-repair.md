# Phase 6.3 — Validation + Repair

> **状态：✅ Done**  
> 总览：[phase-6-local-llm.md](phase-6-local-llm.md) · [roadmap.md](roadmap.md)  
> 前置：[phase-6.2-structured-parser.md](phase-6.2-structured-parser.md)

## 目标

在 6.2 单次解析之上：

1. **硬拒收**：几何 / Draft schema / semantic 失败有明确错误码与消息  
2. **有限 repair**：把错误反馈给同一 Provider，要求重出完整 Draft JSON  
3. **耗尽则失败**：不静默降级、不偷偷删字段凑合通过  
4. 连接类错误（Ollama down）**不**走 repair

```text
attempt 0: parse
  → fail (geometry|schema|semantic|bad JSON text)
→ repair prompt（含错误 + 上次输出）→ attempt 1…N
→ 成功 IngestResult | LLMRepairExhaustedError
```

默认 `max_repairs=2`（最多 3 次模型调用）。

## 不做

Assumption UI（6.4）· HTTP/Desktop（6.5）· 自动 strip 几何键「伪通过」· Agent。

## 包布局

```text
packages/llm/
  repair.py    # build_repair_prompt / parse_with_repair
  gate.py      # 几何错误统一为 LLMIngestError
```

## Definition of Done

1. 首次非法 → 可在后续 attempt 修成合法 RequirementSpec  
2. 耗尽抛 `LLMRepairExhaustedError`（含历次错误）  
3. `ParseResult.attempts` / `repair_notes` 可观测  
4. MockProvider 多响应队列测通；无本机 Ollama 依赖
