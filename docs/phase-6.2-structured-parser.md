# Phase 6.2 — Structured Requirement Parser

> **状态：✅ Done**  
> 总览：[phase-6-local-llm.md](phase-6-local-llm.md) · [roadmap.md](roadmap.md)  
> 前置：[phase-6.1-ollama-provider.md](phase-6.1-ollama-provider.md)

## 目标

编排 **NL → Provider → Draft JSON → Gate → RequirementSpec**，业务只调一处入口：

```text
parse_requirement_text(text, provider) → ParseResult(spec, draft, raw)
```

1. 用户提示模板（中文住宅需求）  
2. `LLMRequirementDraft` JSON Schema（可选交给 Ollama `format=`）  
3. `StructuredRequirementParser` / `parse_requirement_text`  
4. `create_requirement_llm_provider()`：Ollama + Draft schema  
5. 仍经 6.0 `ingest_llm_requirement`（禁几何 + Pydantic + semantic）

## 不做（本子阶段）

JSON repair 重试（→ **6.3**）· Assumption UI（6.4）· HTTP / Desktop NL（6.5）· Benchmark（6.6）。

## 包布局

```text
packages/llm/
  draft_schema.py   # draft_json_schema()
  parser.py         # StructuredRequirementParser / parse_requirement_text
```

## Definition of Done

1. 给定 NL + MockProvider → 得到 `RequirementSpec`  
2. Provider 失败 / 非法 Draft 向上抛清晰错误（不静默吞）  
3. Ollama 路径可带 Draft JSON Schema  
4. 测试不依赖本机 Ollama  
5. 不调用 solver / 不写几何
