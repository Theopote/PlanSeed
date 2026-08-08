# Phase 6.5 — NL → Generate

> **状态：✅ Done**  
> 总览：[phase-6-local-llm.md](phase-6-local-llm.md) · [roadmap.md](roadmap.md)  
> 前置：[phase-6.4-assumption-unknown-ui.md](phase-6.4-assumption-unknown-ui.md)

## 目标

Workbench 自然语言入口：

```text
NL → POST /api/requirements/parse → RequirementSpec（会话事实源）
   →（可选）POST /api/generate → Candidates
```

1. 后端 `parse`：调用 6.2/6.3 `parse_requirement_text_with_repair`  
2. Provider 仅经 `create_requirement_llm_provider`（可 mock）  
3. Desktop：左栏 NL 文本框 +「解析」/「解析并生成」  
4. 解析结果写入 `requirementSpec`；假设/未知走 6.4 面板  
5. **仍禁止** LLM 出几何

## 不做

Benchmark 集（6.6）· Agent/RAG · 云端 API。

## API

```http
POST /api/requirements/parse
{ "text": "两层三卧客厅朝南", "max_repairs": 2 }
→
{
  "requirement_spec": { ... },
  "attempts": 1,
  "repair_notes": [],
  "provider": "ollama" | "mock"
}
```

失败：`400`（校验/repair 耗尽）或 `503`（Ollama 不可达）。

## Definition of Done

1. MockProvider 下 parse API 测试绿  
2. Desktop 可 NL 解析进会话；可一键生成  
3. 表单字段在有 known 时同步（宽深/层数/卧室等）  
4. roadmap / 本详案勾选
