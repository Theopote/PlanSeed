# Desktop Alpha v0.1 — API / Evaluation Contract Freeze

> **冻结至 Desktop Alpha v0.1 完成**（覆盖 Phase 3.6.1 收口与 Phase 4 Workbench 前期）。  
> 详路线：[roadmap.md](roadmap.md) · 评分：[scoring.md](scoring.md)

## 原则

| 允许 | 禁止 |
|------|------|
| **Additive** 字段（可选、有默认） | 无迁移的 **rename / remove** |
| bugfix、文档、CI | 前端自创 score / ranking / compare |
| bump `evaluation_version` 后改规则 | 静默改七轴语义却不 bump 版本 |

**单一事实源：** score / finding / ranking / comparison / recommendation → **Python**。React 只展示。

---

## 冻结表面

### Evaluation

| 符号 | 位置 | 说明 |
|------|------|------|
| `EvaluationAxis` | `packages/schema/scoring.py` | 七轴名冻结 |
| `DesignScore` | 同上 | 七轴分 + findings |
| `DesignFinding` | 同上 | severity / room_ids / metric… |
| `DesignEvaluation` | alias `= DesignScore` | **暂不拆** |

### HTTP API

| 符号 | 位置 |
|------|------|
| `GenerateResponse` | `backend/schemas/api.py` |
| `CandidatePayload` | 同上（含 `design_score`、`provenance`、`placements`） |
| `GenerateRequest` · `locks` | Phase 4.1：`LayoutLocks`（rooms + stair + zones）；生成前 `validate_layout_locks`，非法 → **422** |
| `GenerateRequest` · `base_seed` | Phase 4.2 additive：变体批次种子起点 |
| `CandidatePayload` · `zones` | Phase 4 Lock Zone：功能分区几何摘要（同 floor+kind 多块 = FunctionalZoneGroup） |
| `RoomPlacementPayload` | Phase 4.0 additive：点选房间用 |
| `CandidateProvenance` | solver / generator / evaluation_version |
| `solver_identity` | generate / health 响应 |
| `CompareRequest` / `CompareResponse` | `POST /api/compare` |

### SolverIdentity（算法契约，≠ engine_version）

```text
solver_version
generator_version
evaluation_version
```

定义：`packages/schema/identity.py`。

---

## CI 状态记录（勿混淆）

| 标签 | 含义 |
|------|------|
| **CI configured** | `.github/workflows/ci.yml` 含 pytest / ruff / mypy / pnpm build / **cargo check** |
| **CI verified green** | 某次 push/PR 的 GitHub Actions run **实际成功** |

仅「configured」时文档不得写「CI passed / verified green」。

---

## 变更流程

1. 需要破坏性改契约 → 先写迁移 / bump 版本 → 再改 Desktop 类型。  
2. 改评价规则 → bump `EVALUATION_VERSION`。  
3. Phase 4 交互编辑 **消费**本契约，不重新发明响应形状。
