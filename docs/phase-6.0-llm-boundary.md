# Phase 6.0 — LLM Boundary

> **状态：✅ Done**  
> 总览：[phase-6-local-llm.md](phase-6-local-llm.md) · [roadmap.md](roadmap.md)

## 目标

在接 Ollama（6.1）之前，冻结边界与契约：

1. **LLM NEVER GENERATES GEOMETRY** — 代码可拒收  
2. 结构化输出 = `LLMRequirementDraft`（Known / Assumed / Unknown）  
3. `LLMProvider` Protocol + `MockLLMProvider`（无真实模型）  
4. 双 Gate：Pydantic + `RequirementSemanticValidator`  
5. Draft → `RequirementSpec`（进入 5.1.1 事实源）

## 不做（本子阶段）

Ollama / HTTP 路由 / Desktop NL UI / Agent / RAG / JSON repair 循环。

## 包布局

```text
packages/schema/llm_contract.py   # Draft 契约（可跨前后端）
packages/llm/
  boundary.py                     # 禁几何键、系统提示骨架
  provider.py                     # Protocol
  mock.py                         # MockLLMProvider
  semantic.py                     # RequirementSemanticValidator
  gate.py                         # ingest_llm_requirement()
```

## Definition of Done

1. 含坐标/墙/门/SVG 等几何字段的 JSON 被硬拒  
2. Draft 校验通过后可得到 RequirementSpec  
3. Semantic 拒绝非法楼层偏好等  
4. MockProvider 可测、业务不依赖 Ollama  
5. 测试覆盖边界与 gate
