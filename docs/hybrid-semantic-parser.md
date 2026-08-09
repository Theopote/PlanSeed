# PlanSeed — Hybrid Semantic Parser

> **正式定性：** Requirement 解析层是 **Hybrid Semantic Parser**，不是「纯 LLM parser」。  
> 相关代码：`packages/llm/` · 边界：[phase-6.0-llm-boundary.md](phase-6.0-llm-boundary.md)

## 一句话

```text
Local LLM 提出草稿 + 确定性抽取 / 词表归一 / Semantic Gate / Repair 把关
→ RequirementSpec
→（之后）normalize → Solver
```

这比「把一切押在 prompt / few-shot」更可靠；**确定性层变厚是预期，不是走偏。**

## 流水线（五段）

```text
Natural Language
    │
    ├─ 1. Local LLM（Ollama）     结构化草稿 LLMRequirementDraft
    ├─ 2. Deterministic Extraction  enrich：显式标量 / 关系 / 空间（高置信）
    ├─ 3. Vocabulary Normalization  vocabulary：别名 → 规范名
    ├─ 4. Semantic Gate             semantic + ingest gate
    └─ 5. Repair                    schema/语义失败时有限次修复
         ↓
    RequirementSpec
```

| 段 | 职责 | 不做 |
|----|------|------|
| Local LLM | 口语 → 草稿 JSON | 坐标 / DesignProgram / 几何 |
| Deterministic Extraction | 原文**显式**事实补全与假阳性剔除 | 臆造设计意图；单案 regex |
| Vocabulary | 表面形式归一 | 扩房间种类冒充产品功能 |
| Semantic Gate | 硬约束 / 一致性 | 用 Gate「猜」用户没说的 |
| Repair | 可恢复格式/语义错误 | 无限重试；用 repair 补业务知识 |

## 与「规则 NLP」的关系

`enrich.py` 里出现大量中文表面形式（靠近 / 挨着 / 连通 / 朝南 / …）**是 Hybrid 的合法组成部分**。

承认三点：

1. **LLM 不是唯一解析器** — 它是草稿生成器。  
2. **准确率主要靠 Schema · Vocabulary · Enrich · Gate · Benchmark**，不是堆 prompt。  
3. **假阳性比漏报更贵**（尤其 `relation_intents`）— precision-first 仍成立。

## Regex / 模板增长纪律（硬约束）

允许：

- 覆盖**一般语言规律**的模板与量词（中文数字、宽×深、N 卧 / N 卫…）
- 失败模式来自 **Development** 语料或产品真实口述，再抽象成规律
- Blind FAIL 后改一般规律，再开 **新** Blind 集

禁止：

- 对着 Blind / Holdout **逐案**加表面形式后宣称过门
- 无限扩 regex 冒充泛化（「再加一句就过」）
- 用超长 prompt / few-shot 替代 Schema / Enrich / Gate
- 为单个 benchmark id 硬编码句式

**经验阈值：** 若新增规则只能解释 1–2 条已知失败句、且无法用一句话说明「一般规律」，就不该合并。

## 产品边界（不变）

```text
LLM NEVER GENERATES GEOMETRY
```

Hybrid Parser 只产出 `RequirementSpec`（及 unknowns / assumptions）。  
Solver / Evaluator / Renderer 仍严格分层、确定性。

## 文档索引

| 文档 | 内容 |
|------|------|
| [architecture.md](architecture.md) | 全仓架构；本文件补 NL→Spec 段 |
| [phase-6.7.1-parser-precision-holdout.md](phase-6.7.1-parser-precision-holdout.md) | precision-first 工程 |
| [phase-6.7.2-blind-requalification.md](phase-6.7.2-blind-requalification.md) | 严格独立资格 |
| `packages/llm/enrich.py` | Deterministic Extraction |
| `packages/llm/vocabulary.py` | Vocabulary Normalization |
| `packages/llm/semantic.py` + `gate.py` | Semantic Gate |
| `packages/llm/repair.py` | Repair |
