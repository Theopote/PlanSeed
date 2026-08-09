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
    ├─ 1b. Draft Coerce           字符串数字 / kind 别名等 schema 缓冲（packages/llm/coerce.py）
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
| Draft Coerce | 可恢复的形状归一（降 repair 耗尽） | 臆造业务事实 |
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

## Relation：precision-first + Kind 分流（已对齐 Solver 原则）

Solver 侧早已成立：

```text
Adjacency ≠ Access Intent
邻接 ≠ 通行（见 solver/topology/derive_access.py）
```

**Requirement / Hybrid Parser 输入端现已同一原则**，不得再把口语里的靠近 / 连通 / 进入全部压成 `adjacency`。

| RelationKind | 口语线索（例） | 语义 |
|--------------|----------------|------|
| `near` | 靠近、挨着、邻近 | 靠近，**不必**连通或通行 |
| `separation` | 远离、不要靠、避免噪声 | 分离 / 私密 |
| `open_connection` | 连通、开敞连通 | 开敞空间连通（如客餐厅） |
| `access` | 相连、连着、从 A 进 B | **可通行** / 内部相连 |
| `visual_connection` | 望向、视野（预留） | 视线，非几何 |
| `adjacency` | （遗留） | 仅共享边界级；**禁止**当万能桶 |

纪律：

```text
宁可少关系，不可乱关系
precision ↓ 时，禁止为抬 recall 无限补 relation_intents
```

证据策略：仅高置信二元模板 / 显式通行句 / 复合词（客餐厅·餐厨）；**两端共现 + 全文任意「近」不够**。  
Normalizer 再把已支持的 kind 映射到 solver intents；RequirementSpec 须保留用户原意。

健康方向（相对早期「Recall 100% / Precision ~18%」）：

```text
Recall 高但可控 · Precision 过门 · F1 健康
→ 假阳性约束不再廉价灌进 DesignProgram
```

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

## 延迟与产品体验（不阻塞 Phase 7）

真模型量级（Holdout / Blind，`qwen2.5:7b`，约）：

```text
average ≈ 15–20s · P50 ≈ 14–15s · P90 ≈ 35–40s · max ≈ 45s
```

对最终桌面产品仍偏慢，但 **不作为卡住 Phase 7 的理由**。

判断：

| 点 | 结论 |
|----|------|
| 操作类型 | NL 解析 **不是** 60fps 交互；完整需求提交后等十几秒，Alpha 可接受 |
| 真正痛点 | 界面无状态 → 像死机；不是「必须先砍到 2s」 |
| Alpha UX | 进度文案：正在理解需求… / 正在检查设计条件… / 正在整理未确定信息… |
| 性能优化 | 后置（量化、缓存、更小模型、流式…）；**另开**，不挡 Export |

```text
先交付可带走的方案（Phase 7）
再优化等待体感与绝对耗时
```

## Phase 6 post-alpha 已知限制

Strict Alpha Qualified **之后**仍承认、但**不**据此回头卡 Phase 7 / 堆 Blind 规则：

| 项 | 现状（约） | 处理 |
|----|------------|------|
| **Latency** | avg ~15–20s · P90 ~35–40s | 进度文案；性能另阶段 |
| **bathrooms 分字段** | Holdout ≈ **87.5%**（弱于卧/层/场地/车库/朝南） | 已知限制；整体 field ≈96% 已过门 |

Holdout 分字段对照（工程回归，非 Blind）：

```text
floor_count ≈ 96.6% · bedrooms ≈ 95.8% · bathrooms ≈ 87.5%
site w/d ≈ 100% · garage ≈ 100% · south ≈ 100%
```

卫浴口语变体多（卫 / 卫生间 / 洗手间 / 卫浴 / 「先按 N 个算」等）；后续若修，只收 **一般语言规律**，禁止 Holdout/Blind 逐案 regex。

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
| `packages/llm/coerce.py` | Draft schema 缓冲 |
| `packages/llm/repair.py` | Repair |
