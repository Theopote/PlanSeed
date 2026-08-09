# Phase 6.7.2 — Blind Requalification

> **状态：✅ Blind v4 Gate PASS — Strict Alpha Qualified**  
> 前置：[phase-6.7.1-parser-precision-holdout.md](phase-6.7.1-parser-precision-holdout.md) · 架构：[hybrid-semantic-parser.md](hybrid-semantic-parser.md)  
> 下一：可开 [phase-7-deliverables.md](phase-7-deliverables.md)；Holdout / Blind v1–v3 仅作工程对照

## 为什么还要 6.7.2

6.7.1 的 Holdout（30 条）在工程上已过 Alpha Gate，但 **独立性已被破坏**：

1. `holdout_cases.py` 先落地  
2. 随后继续改 enricher / vocabulary，加入与 Holdout 重合的 paraphrase 规则  
   （如「最好挨着」「不要靠着」「老人最好住」「从 A 能进 B」「南向 / 偏北」等）

因此 Holdout 通过证明的是：

```text
Pipeline 对「已参与规则设计的 30 句」可过门
```

**不能**严格证明：

```text
系统对未见自然语言具备同等泛化能力
```

状态应理解为：

| 层 | 状态 |
|----|------|
| 6.7.1 Engineering / precision work | ✅ |
| Current 30-case Holdout | ✅ Passed（工程证据，非严格独立） |
| Blind v1 | ❌ FAIL（归档 `llm-alpha-baseline-blind-v1.json`） |
| Blind v2 | ❌ FAIL（归档 `llm-alpha-baseline-blind-v2.json`） |
| Blind v3 | ❌ FAIL（归档 `llm-alpha-baseline-blind-v3.json`） |
| Blind v4 | ✅ **PASS**（`llm-alpha-baseline.json` / `…-blind-v4.json`） |
| Phase 6 | ✅ **Strict Alpha Qualified** |
| Phase 7 | ▶ 可开 |

## 本阶段唯一目标

```text
Development 一般规律改进（不看 Blind 逐案）
        ↓
Freeze parser / enrich / semantic / prompts
        ↓
Create & human-review Blind Set vN（未见规则迭代）
        ↓
Run qwen2.5:7b Pipeline **一次**
        ↓
Record summary → PASS / FAIL
```

**失败时禁止：** 对着 Blind 逐案加 regex，再宣布 Blind 通过。  
失败后只允许：回到 Development 改一般规律 → **新建 Blind v(N+1)**（本集作废为调参集）。

## Blind Set 要求

- 路径：`packages/llm/benchmark/blind_cases_v2.py`（v1/v2 失败集归档；下一严格集为 v3）
- 规模：**40–60** 条中文住宅需求
- 语气：口语 / 叙事，避免「两层三卧，X，Y」测试句式堆砌
- 六类覆盖：
  1. Explicit Facts（层数 / 卧卫 / 车库 / 场地）
  2. Design Intent Paraphrase（如厨餐 near，勿抄 Holdout/v1 原句）
  3. Access vs Near（靠近 ≠ 能直接进屋）
  4. Weak Preference（现有 schema 内验证，不扩 strength）
  5. Negative Constraints（不要靠 / 别上二楼…）
  6. Ambiguous Requirements（宽敞一点 → Unknown，勿编造面积）

## 冻结范围（Blind 跑分期间）

禁止修改：

- `packages/llm/enrich.py`
- `packages/llm/vocabulary.py`
- `packages/llm/semantic.py`
- `packages/llm/parser.py` / `repair.py` 中的 prompt 模板
- Blind 语料本身（除发现 gold 标注错误的修正）

允许：跑分脚本、报告、文档状态。

## Gate

沿用 6.7.1 Alpha Gate；**以 Blind + Pipeline 为准**。

```powershell
.\scripts\run_llm_qualify.ps1 -CaseSet blind -Gate
```

产物：`docs/baselines/llm-alpha-baseline.json`（blind+pipeline）或  
`docs/baselines/llm-alpha-baseline-blind-pipeline.json`。

## 完成标准

- [x] Blind Set v1–v3 单次跑分 **FAIL**（已归档）
- [x] Development：口语标量 · 关系证据收紧 · Draft Coerce
- [x] Blind Set v4（44 条）`qwen2.5:7b` Pipeline **单次**入库 → Gate **PASS**
- [x] **Phase 6 ✅ Strict Alpha Qualified** → 可开 Phase 7

## Blind v1 单次结果（2026-08-09，`qwen2.5:7b` Pipeline）

| 指标 | 实际 | Gate | |
|------|------|------|--|
| Geometry | 0% | 0% | ✅ |
| Parse success | 96.2% | ≥95% | ✅ |
| Relation F1 / precision | **84.3% / 87.5%** | ≥80% / ≥75% | ✅ |
| Unknown precision / recall | 92.6% / 79.4% | ≥70% | ✅ |
| Assumption precision | 100% | ≥80% | ✅ |
| Repair exhausted | 3.8% | ≤5% | ✅ |
| **Scalar field accuracy** | **77.3%** | ≥90% | ❌ |
| **Case pass rate** | **30.2%** | ≥70% | ❌ |

分字段：site ≈17%；bathrooms ≈56%；garage ≈47%；floor_pref ≈17%。

## Blind v3 单次结果（2026-08-09，`qwen2.5:7b` Pipeline）

| 指标 | 实际 | Gate | |
|------|------|------|--|
| Geometry | 0% | 0% | ✅ |
| **Parse success** | **86.4%** | ≥95% | ❌ |
| Relation F1 / precision | **84.9% / 82.4%** | ≥80% / ≥75% | ✅ |
| Unknown precision / recall | 100% / 84.6% | ≥70% | ✅ |
| Assumption precision | 100% | ≥80% | ✅ |
| **Repair exhausted** | **13.6%** | ≤5% | ❌ |
| **Scalar field accuracy** | **86.6%** | ≥90% | ❌ |
| Case pass rate | 81.8% | ≥70% | ✅ |

## Blind v4 单次结果（2026-08-09，`qwen2.5:7b` Pipeline）— **PASS**

| 指标 | 实际 | Gate | |
|------|------|------|--|
| Geometry | 0% | 0% | ✅ |
| Parse success | **100%** | ≥95% | ✅ |
| Relation F1 / precision | **91.4% / 84.2%** | ≥80% / ≥75% | ✅ |
| Unknown precision / recall | 100% / 100% | ≥70% | ✅ |
| Assumption precision | 100% | ≥80% | ✅ |
| Repair exhausted | **0%** | ≤5% | ✅ |
| Scalar field accuracy | **96.2%** | ≥90% | ✅ |
| Case pass rate | **88.6%** | ≥70% | ✅ |

分字段：garage / south / 卧卫 / 层数 = 100%；site ≈77%（未拖垮总 field）。

**解读：** Draft Coerce 把 parse/repair 耗尽压到 0；关系 precision-first 仍过门（P 84% · R 100% · F1 91%）。  
**结论：** Phase 6 **Strict Alpha Qualified**；可进入 Phase 7 Deliverables。  
**延迟：** Holdout/Blind 量级十几秒～P90 约 35–40s，**不阻塞** Phase 7；Alpha 用进度反馈，性能后置（见 [hybrid-semantic-parser.md](hybrid-semantic-parser.md)）。  
**bathrooms：** Holdout 分字段 ≈87.5%（整体 field ≈96%）— **Phase 6 post-alpha known limitation**，不回头阻塞；见同文档 § 已知限制。
