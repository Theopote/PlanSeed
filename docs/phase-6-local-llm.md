# Phase 6 — Local LLM Requirement Parsing

> **状态：进行中（6.0 ✅ → 下一 6.1 Ollama）**  
> 总览：[roadmap.md](roadmap.md)  
> 前置：[phase-5.1.1-program-fidelity.md](phase-5.1.1-program-fidelity.md)

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
| **6.1** | Ollama Provider | `LLMProvider` 抽象；仅 Ollama 实现 | **← 下一** |
| **6.2** | Structured Parser | Text → JSON → RequirementSpec | 未开始 |
| **6.3** | Validation + Repair | schema + semantic gate；非法拒收/修 JSON | 未开始 |
| **6.4** | Assumption / Unknown UI | 显式假设与未知；禁止偷偷补全 | 未开始 |
| **6.5** | NL → Generate | Workbench 接入口 | 未开始 |
| **6.6** | Requirement Benchmark | ~50 条住宅需求；准确率而非「聪明感」 | 未开始 |

详案 6.0：[phase-6.0-llm-boundary.md](phase-6.0-llm-boundary.md)

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
    def generate_structured(self, prompt: str, schema: type[T]) -> T: ...
```

实现：`OllamaProvider`；业务层不散落 `ollama.chat`。

## 工程门禁

进入 6.1 实现前：最新 `master` CI green（pytest / ruff / mypy / pnpm build / cargo check）— 人为确认。

## Definition of Done（整 Phase）

1. NL → RequirementSpec 稳定、可验证  
2. 输出永不含几何  
3. Assumption / Unknown 可解释  
4. Requirement Benchmark 有基线  
5. Desktop 仍以 RequirementSpec 为事实源（5.1.1）
