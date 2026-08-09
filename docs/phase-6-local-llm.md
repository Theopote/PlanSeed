# Phase 6 — Local LLM Requirement Parsing

> **状态：✅ Phase 6 Strict Alpha Qualified（Blind v4 + qwen2.5:7b）**  
> 总览：[roadmap.md](roadmap.md) · 下一：[phase-7-deliverables.md](phase-7-deliverables.md)  
> 架构：[hybrid-semantic-parser.md](hybrid-semantic-parser.md) · 资格：[phase-6.7.2-blind-requalification.md](phase-6.7.2-blind-requalification.md)

## 完成标准

```text
0–5.1.1  ✅ Design Kernel
6.0–6.6  ✅ LLM Infrastructure
6.7–6.7.2 ✅ Blind v4 Gate PASS
Phase 6  ✅ Strict Alpha Qualified
Phase 7  ← Deliverables / Export
```

## 最高原则

```text
LLM NEVER GENERATES GEOMETRY
```

Requirement 解析层正式定为 **Hybrid Semantic Parser**（非纯 LLM parser），详见 [hybrid-semantic-parser.md](hybrid-semantic-parser.md)：

```text
NL → Local LLM → Deterministic Extraction → Vocabulary
  → Semantic Gate → Repair → RequirementSpec
```

LLM 只参与草稿；确定性抽取与 Gate 负责精度。完整链路：

```text
NL → Hybrid Semantic Parser → RequirementSpec
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
| **6.6** | Requirement Benchmark | 语料 + oracle harness（≠ 真模型准确率） | ✅ |
| **6.7** | Real Model Qualification & Runtime Hardening | Alpha Gate · 真模型跑分 · 过门后 Phase 7 Export | ← 当前 |

详案：[phase-6.0-llm-boundary.md](phase-6.0-llm-boundary.md) · [phase-6.1-ollama-provider.md](phase-6.1-ollama-provider.md) · [phase-6.2-structured-parser.md](phase-6.2-structured-parser.md) · [phase-6.3-validation-repair.md](phase-6.3-validation-repair.md) · [phase-6.4-assumption-unknown-ui.md](phase-6.4-assumption-unknown-ui.md) · [phase-6.5-nl-generate.md](phase-6.5-nl-generate.md) · [phase-6.6-requirement-benchmark.md](phase-6.6-requirement-benchmark.md) · [phase-6.7-real-model-qualification.md](phase-6.7-real-model-qualification.md)

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

## 改进纪律

Prompt 保持短。准确率靠 **Benchmark → 失败模式 → Schema/语义/Normalizer**，禁止靠堆 few-shot / 长指令冒充可靠。详案见 [phase-6.7](phase-6.7-real-model-qualification.md)。

## Definition of Done（整 Phase）

1. NL → RequirementSpec 稳定、可验证 ✅（6.0–6.6 LLM Infrastructure）  
2. 输出永不含几何 ✅  
3. 某本地模型过 [Alpha Gate](phase-6.7-real-model-qualification.md) → **Phase 6 ✅ Alpha Qualified**  
4. 然后进入 [Phase 7 Deliverables / Export](phase-7-deliverables.md)（不是高级分析大杂烩）
