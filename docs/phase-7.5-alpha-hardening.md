# Phase 7.5 — Alpha Engineering Hardening

> **状态：▶ 7.5-C persistence migrations ← 当前 · 7.5-B ✅ · 7.5-A ✅ · 7.2 ✅ · 不改建筑设计行为**  
> 总览：[roadmap.md](roadmap.md) · 契约：[api-contract.md](api-contract.md)

## 原则

- **不改变** solver / parser / 评价 / 生成几何行为  
- **不增加**设计向用户功能（`.planseed` 是交付包装，允许，但不抢 A）  
- **禁止**：全仓 `mypy --strict` · Alembic · Zustand 先行 · pydantic-ai / instructor / 外部规则引擎  
- 发现问题记 backlog，**禁止**因债新开 Phase  

## 顺序

```text
7.5-A OpenAPI → TS
  → 7.5-B mypy Round 1–3
  → 7.5-C persistence migrations
  → 7.5-D .planseed package
  → 7.5-E App hooks
  → 7.5-F enrich stages
  → 7.5-G Hypothesis
  → 7.5-H coverage reporting
  → 7.5-I privacy / limits / audit
```

| 项 | 主题 | 状态 |
|----|------|------|
| **7.5-A** | OpenAPI → TypeScript + CI drift | ✅ |
| **7.5-B** | 渐进 mypy（三轮） | ✅ |
| **7.5-C** | `PRAGMA user_version` migrations | **← 当前** |
| **7.5-D** | `.planseed` ZIP 项目包 | |
| **7.5-E** | `App.tsx` → hooks 拆分 | |
| **7.5-F** | LLM Enricher stage 化 | |
| **7.5-G** | Hypothesis 不变量 | |
| **7.5-H** | pytest-cov 报告（暂不门槛） | |
| **7.5-I** | Ollama local 守卫 · RuntimeLimits · audit | |

## 7.5-A — OpenAPI → TypeScript

```text
FastAPI create_app().openapi()
  → scripts/export_openapi.py → desktop/openapi.json
  → openapi-typescript → desktop/src/api/generated.ts
  → client.ts：fetch + error + domain helper（不再手维核心 DTO）
  → CI：regenerate + git diff --exit-code
```

### 本地命令

```bash
# 从仓库根目录
uv run python scripts/export_openapi.py
pnpm --dir desktop generate:api
```

改 FastAPI / Pydantic 请求响应后：**必须**重跑并提交 `openapi.json` + `generated.ts`。

### CI

`contract` job：export → generate → `git diff --exit-code -- desktop/openapi.json desktop/src/api/generated.ts`

### 保留在 client（非 OpenAPI）

`EngineLifecycle` · Tauri invoke · `RequirementForm` UI · form/spec sync helpers · `downloadBlob` · locks clone 等。

## 7.5-B — 渐进 mypy（三轮）

全局仍 `disable_error_code` 较重项；**禁止**一次删光 / `--strict`。

| Round | 范围 | 恢复的检查 |
|-------|------|------------|
| 1 | `packages/schema` · `solver/geometry` · `solver/constraints` | `return-value` / `arg-type` / `assignment` |
| 2 | `solver/evaluation` · `backend/services` | 同上 |
| 3 | `backend/routes` · `packages/llm`（tests ignore） | 同上 |

配置：`pyproject.toml` → `[[tool.mypy.overrides]]` + `enable_error_code`。

## 后续批次（摘要）

- **C**：不上 Alembic；`migrations/v001_…` + `migrate(conn, …)`  
- **D**：ZIP = `manifest.json` + `project.json` + `assets/` + `previews/`  
- **E**：hooks 七件套；不上 Zustand 除非 prop drilling 仍严重  
- **F**：拆 `packages/llm/enrich.py`；行为不变；stage provenance  
- **G/H**：Hypothesis 核心不变量；coverage 先观察  
- **I**：非 loopback Ollama 警告/可拦；集中 Limits；`pip-audit` + `cargo audit`

## Definition of Done（7.5）

- [x] OpenAPI → generated TypeScript + CI drift  
- [x] mypy 第一轮收紧（含 Round 1–3 目录 overrides）  
- [ ] persistence migration  
- [ ] `.planseed` project package  
- [ ] App orchestration 拆分  
- [ ] Enricher stage 化  
- [ ] Hypothesis 核心 property tests  
- [ ] coverage reporting  
- [ ] local LLM privacy guard  
- [ ] dependency audit  

完成后：功能型 Alpha → **工程上较可靠的 Alpha**。
