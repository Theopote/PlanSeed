# Phase 6 — Local LLM Requirement Parsing

> **状态：✅ Phase 6 收口（6.0–6.6 Done）**  
> 总览：[roadmap.md](roadmap.md)  
> 前置：[phase-6.0-llm-boundary.md](phase-6.0-llm-boundary.md)

## 最高原则

```text
LLM NEVER GENERATES GEOMETRY
```

LLM 只做：

```text
Natural Language → RequirementSpec
```

然后退出核心链。完整链路：

```text
NL → Local LLM → RequirementSpec
  → Pydantic validate → Semantic validate
  → Normalizer → DesignProgram
  → Deterministic Solver → Candidates → Evaluator
```

**禁止 LLM：** 坐标 / 墙 / 门 / SVG / DoorOpening / LayoutCandidate / 直接 RoomSpec 完整表。

## 分期

| 子阶段 | 主题 | 要点 | 状态 |
|--------|------|------|------|
| **6.0** | LLM Boundary | 契约、Known/Assumed/Unknown、不进几何 | ✅ |
| **6.1** | Ollama Provider | `LLMProvider` 抽象；仅 Ollama 实现 | ✅ |
| **6.2** | Structured Parser | Text → JSON → RequirementSpec | ✅ |
| **6.3** | Validation + Repair | schema + semantic gate；非法拒收/修 JSON | ✅ |
| **6.4** | Assumption / Unknown UI | 显式假设与未知；禁止偷偷补全 | ✅ |
| **6.5** | NL → Generate | Workbench 接入口 | ✅ |
| **6.6** | Requirement Benchmark | ~50 条住宅需求；准确率而非「聪明感」 | ✅ |

详案：[phase-6.0-llm-boundary.md](phase-6.0-llm-boundary.md) · [phase-6.1-ollama-provider.md](phase-6.1-ollama-provider.md) · [phase-6.2-structured-parser.md](phase-6.2-structured-parser.md) · [phase-6.3-validation-repair.md](phase-6.3-validation-repair.md) · [phase-6.4-assumption-unknown-ui.md](phase-6.4-assumption-unknown-ui.md) · [phase-6.5-nl-generate.md](phase-6.5-nl-generate.md) · [phase-6.6-requirement-benchmark.md](phase-6.6-requirement-benchmark.md)

## 第一版不做

Agent / tool calling / multi-agent / RAG / memory / planner / reflection / 自然语言改几何。

## LLM 输出三层

沿用现有 `assumptions` / `unknowns`：

```text
known      → 用户明确说的
assumptions → 显式默认（必须可展示、可改）
unknowns    → 未提供且未推断
```

第一版**不要**让 LLM 擅自补全卧室数/面积等关键未知。

## 两次 Schema Gate

```text
raw JSON → RequirementSpec.model_validate()
         → RequirementSemanticValidator
         → Normalizer
```

## Provider 抽象

```python
class LLMProvider(Protocol):
    def complete_json(self, *, system: str, user: str) -> dict: ...
```

实现：`OllamaProvider`（`packages/llm/ollama.py`）；工厂：`create_llm_provider()`。业务层不散落 Ollama URL。

## Definition of Done（整 Phase）

1. NL → RequirementSpec 稳定、可验证 ✅  
2. 输出永不含几何 ✅  
3. Assumption / Unknown 可解释 ✅  
4. Requirement Benchmark 有基线（≥50 + 字段准确率） ✅  
5. Desktop 仍以 RequirementSpec 为事实源（5.1.1） ✅
