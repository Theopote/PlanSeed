# Desktop Alpha v0.1 — API / Evaluation Contract Freeze

> **冻结至 Desktop Alpha v0.1 完成**（Phase 3.6 ✅ 已冻结；覆盖 Phase 4 Workbench）。  
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
| `CandidatePayload` | 同上（含 `design_score`、`provenance`、`placements`、`svg` 整图、`floor_svgs` 分层） |
| `CandidatePayload` · 血缘 | Phase 5 additive：`variant_parent_id` / `variant_generation` / `lock_snapshot_id` |
| `GenerateRequest` · `locks` | Phase 4.1：`LayoutLocks`（rooms + stair + zones）；生成前 `validate_layout_locks`，非法 → **422** |
| `GenerateRequest` · `base_seed` | Phase 4.2 additive：变体批次种子起点 |
| `CandidatePayload` · `zones` | Phase 4：`id` + `kind` + `zone`（兼容）；同 floor+kind 多块 = FunctionalZoneGroup |
| `RoomPlacementPayload` | Phase 4.0 additive：点选房间用 |
| `CandidateProvenance` | solver / generator / evaluation_version |
| `solver_identity` | generate / health 响应 |
| `CompareRequest` / `CompareResponse` | `POST /api/compare` |
| Projects CRUD | Phase 5 / 5.1.1：`GET/POST /api/projects`；payload 含 `requirement_spec`；详见 [phase-5.1.1-program-fidelity.md](phase-5.1.1-program-fidelity.md) |
| Mutation preview / revalidate | Phase 5.1：`POST /api/mutations/preview`、`POST /api/mutations/revalidate`；详见 [phase-5.1-revision-integrity.md](phase-5.1-revision-integrity.md) |
| `POST /api/requirements/parse` | Phase 6.5 additive：NL → `RequirementSpec`（含 repair）；详见 [phase-6.5-nl-generate.md](phase-6.5-nl-generate.md) |
| `POST /api/reports/build` | Phase 7：`mode=preview` 可 payload；`mode=final` 须 `project_id`+`candidate_id`+`revision_id`（只读 store，禁止 payload）；SVG sanitize；详见 [phase-7-deliverables.md](phase-7-deliverables.md) |
| `POST /api/exports/svg` | Phase 7.2.1：`project_id`+`candidate_id`+`revision_id`+`scope`（`floor`/`snapshot`/`all_floors`）；`scope=floor` 须 `floor_id`；只读 store → sanitize → 文件；禁止 DOM outerHTML |
| `POST /api/exports/png` | Phase 7.2.2：同上 + `size`∈{2048,4096}；Canonical SVG → `resvg` 白底 PNG；禁止 HTML 截图 |
| `POST /api/exports/report-json` | Phase 7.2.3：`DesignReport` + `report_schema_version` 文件下载；≠ Project Snapshot；禁止 candidate dump |

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
