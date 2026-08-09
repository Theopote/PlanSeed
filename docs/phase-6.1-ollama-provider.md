# Phase 6.1 — Ollama Provider

> **状态：✅ Done**  
> 总览：[phase-6-local-llm.md](phase-6-local-llm.md) · [roadmap.md](roadmap.md)  
> 前置：[phase-6.0-llm-boundary.md](phase-6.0-llm-boundary.md)

## 目标

业务层只依赖 `LLMProvider.complete_json`；本地推理唯一实现为 `OllamaProvider`（HTTP → Ollama `/api/chat`）。

1. `OllamaConfig`（base_url / model / timeout；环境变量可读）  
2. `OllamaProvider`：`format=json`（可选 JSON Schema）  
3. 工厂 `create_llm_provider()`：`mock` | `ollama`  
4. 错误可区分：连接失败 / HTTP / 非 JSON  
5. 单元测试 **不** 依赖本机 Ollama（httpx MockTransport）

## 不做（本子阶段）

NL HTTP 路由 · Desktop 输入框 · JSON repair 循环 · Agent / RAG · 云端 LLM API。

## 环境变量

| 变量 | 默认 | 含义 |
|------|------|------|
| `PLANSEED_LLM_PROVIDER` | `ollama` | `ollama` / `mock` |
| `PLANSEED_OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | Ollama 根 URL |
| `PLANSEED_OLLAMA_MODEL` | `qwen2.5:7b` | 聊天模型名 |
| `PLANSEED_OLLAMA_TIMEOUT` | `120` | 秒 |

## 包布局

```text
packages/llm/
  ollama.py      # OllamaConfig / OllamaProvider / OllamaError*
  factory.py     # create_llm_provider / load_ollama_config
  runtime.py     # 进程内共享 Requirement Provider（复用 httpx）
```

生产 NL 解析经 `get_shared_requirement_provider()`（backend `get_nl_provider`），**不要**每次 `create_requirement_llm_provider()` 后丢弃不 close。

## Definition of Done

1. `OllamaProvider` 实现 `LLMProvider`  
2. 业务代码无直接 `ollama.chat` / 散落 URL  
3. MockTransport 测试覆盖成功路径与失败路径  
4. `httpx` 为运行时依赖  
5. roadmap / 本详案勾选
