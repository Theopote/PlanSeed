# Phase 6.4 — Assumption / Unknown UI

> **状态：✅ Done**  
> 总览：[phase-6-local-llm.md](phase-6-local-llm.md) · [roadmap.md](roadmap.md)  
> 前置：[phase-6.3-validation-repair.md](phase-6.3-validation-repair.md)

## 目标

会话里 **assumptions / unknowns 必须可见、可改**，禁止「系统默默补全用户看不见」。

1. 左栏以 **`requirementSpec` 为事实源**（无则回退 `program`）  
2. 假设：展示 key / value / reason；可改 value·reason；可清除  
3. 未知：展示 key / description；可「已知悉」移除（不偷偷填值）  
4. 编辑写入 `requirementSpec`，并镜像 `program` 列表；保存项目带走  
5. 空态说明（生成后无假设/未知时明示）

## 不做

NL 输入框 / Ollama 调用（→ **6.5**）· Benchmark（6.6）· 自动把 unknown 填成 known。

## 布局

```text
RequirementsPanel
  └─ RequirementGapsPanel   # 假设 / 未知
App.tsx                     # 编辑回调 → setRequirementSpec + setProgram
```

## Definition of Done

1. Generate 后假设/未知可见（中文标签）  
2. 清除假设 / 编辑假设 / 关闭未知 立即反映在会话 spec  
3. 保存/重开项目仍保留用户改过的列表  
4. 无 NL parse 入口（留给 6.5）
