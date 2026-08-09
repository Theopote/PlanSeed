# Phase 7 — Deliverables / Export

> **状态：▶ 进行中（7.0 落地；当前 P0 = 7.0.1 Report Integrity Gate）**  
> **前置：** [phase-6.7.2-blind-requalification.md](phase-6.7.2-blind-requalification.md) — Blind v4 Gate **工程 PASS**；严格可复现资格 ⚠（见该文）  
> 总览：[roadmap.md](roadmap.md) · 架构原则：[hybrid-semantic-parser.md](hybrid-semantic-parser.md)

## 产品闭环

完整链已是：

```text
NL → RequirementSpec → Generate → Evaluate → Compare
  → Edit → Revalidate → Save
```

下一步自然是 **Deliver**。Phase 7 = Deliverable Layer，不是高级分析或再扩 LLM。

## 第一刀：Export Design Report

格式优先级（**不要**被建筑软件惯性拖进 DWG / IFC / Revit）：

1. **HTML → Print / PDF**（Alpha 首选，见下）  
2. SVG / PNG 平面图  
3. JSON（`DesignReportPayload` 快照）  
4. DXF — **later**，不挡 7.0

## 7.0 先建 Deliverable Model

**禁止**「React 截图 → PDF」各写一套。先建立权威文档模型，再挂 Renderer：

```text
DesignReport
├ status / evaluation_fresh / source_revision_id   # 7.0.1 Integrity
├ ProjectMetadata
├ RequirementSummary          # Key Intent（层数 / 卧卫 / 朝南 / 关系…）
├ Assumptions
├ Unknowns
├ CandidateSummary            # 如 Candidate A.2 · Score 84
├ FloorPlans[]                # 优先 floor_svgs（F1/F2…）；否则 Candidate 整图 snapshot
├ RoomSchedule                # 面积表 ← placements / report builder
├ EvaluationSummary           # DesignScore 七轴 + evaluation_fresh
├ Findings                    # DesignFinding[]
└ Provenance                  # seed / generator / versions / 边界声明
```

之后：

```text
DesignReport → HTML Renderer
DesignReport → JSON export
DesignReport →（未来）专业 PDF / DXF
```

同一事实源，多 renderer。

## 权威数据必须来自 Backend

继续：**frontend does not reinterpret design data**。

交付物原则：**不能生成错误报告** — 缺权威数据时 fail loudly，禁止 best-effort 半成品报告。

| 内容 | 来源 | 失败时 |
|------|------|--------|
| Room area | placements.**area** | 400 `placement_area_missing`（禁止 width×depth） |
| Evaluation / Findings | `DesignScore` | 400 `design_score_missing` / `design_score_invalid` |
| Key Intent / Assumptions / Unknowns | `RequirementSpec` | 400 `requirement_spec_missing` |
| Floor plan SVG | 已保存候选的 `floor_svgs` / `svg`（经 sanitize） | 400 `floor_plan_svg_missing` / `svg_sanitize_failed` |
| Dirty evaluation | revision_status | 409 `candidate_requires_revalidation` |
| Broken candidate | 缺 id / placements | 409 `invalid_candidate` |
| Wrong candidate id | 查找 | 404 `candidate_not_found` |

| 内容 | 禁止 |
|------|------|
| Room area | React / builder 自算 `width × depth` |
| Evaluation | exporter 另发明一套分 |
| Findings | 报告层重写启发式 |
| Assumptions / Unknowns | 前端臆造 |

## 平面图：Candidate snapshot + per-floor SVG

`floor_plans: list[FloorPlanBlock]` 报告层**只消费**已渲染 SVG，禁止切 DOM。

| 来源 | 含义 |
|------|------|
| `candidate.floor_svgs` | serializer 用 `render_floor_svg` 产出的 F1/F2/…（**优先**） |
| `candidate.svg` | 整候选纵向堆叠 snapshot（Workbench / 无 floor_svgs 时退回 `floor_id=all`） |

```text
render_floor_svg(candidate, floor_id)
  → CandidatePayload.floor_svgs
  → DesignReport.floor_plans[]
  → HTML
```

旧项目快照若无 `floor_svgs`，报告仍可用整图 snapshot（可接受）。

## 7.0.1 — Report Integrity Gate（P0）

Dirty 候选不得导出「正式评价报告」（否则会把过期 Score / Findings 写进交付物）。

```text
Generated / Validated  → 可正式导出（status=valid）
Dirty                  → HTTP 409 candidate_requires_revalidation
                         （可选 allow_stale_evaluation=true 仅调试；报告标 stale）
```

`ReportStatus`：`valid` | `stale_evaluation` | `invalid_candidate`  
`GeometryOrigin`：`solver_generated` | `user_edited_validated` | `user_edited_stale`  
`ReportLocale`：Alpha 默认 `zh-CN`（`packages/schema/report_i18n.py`）；预留 `en-US`。  
Desktop：dirty 时拦截并提示「请先重新验证」。  
几何-only 导出（不含评分）可后置，本刀默认拒绝正式评价报告。

## Export API（additive）

两种模式：

```text
Preview
  mode=preview
  in:  { payload } 或 { project_id }  + optional candidate_id
  → 开发 / 工作台预览；可带 client 几何快照

Final Export
  mode=final
  in:  { project_id, candidate_id, revision_id }
  → 必须从 ProjectStore 读取；禁止 client payload
  → revision_id 须与 store 候选一致（否则 409 revision_mismatch）
```

Desktop「报告」= Final：先 Save，再 `project_id + candidate_id + revision_id`。  
`CandidatePayload.revision_id` 在 generate / revalidate 时由 serializer 写入；旧快照缺省回退 `candidate.id`。

HTML 内嵌平面图另经 `sanitize_report_svg`（拒绝 script / foreignObject / 外链等）。

Desktop：

```text
Report Preview（HTML，即所得）
  → Print / Save PDF（系统打印）
```

契约写入 [api-contract.md](api-contract.md)（additive）。

## PDF 策略：HTML → Print，不手搓 PDF layout

Phase 7 Alpha **不建议**在 Python 里排版 PDF。

```text
DesignReport
  → HTML template（CSS + 中文字体 + 内嵌 SVG）
  → Tauri WebView 预览
  → Print / PDF
```

优势：排版快、中文易、SVG 原生、预览即所得。专业排版以后再升级。

## 报告要可解释，不是「漂亮」

首页建议结构：

```text
PlanSeed Design Report
Project · 求解器生成 | 用户编辑 · 已验证 · Candidate A.2 · Score 84
（用户编辑 · 评价过期 禁止正式报告）

文案由 `ReportLocale` 集中管理（Alpha 默认 `zh-CN`；预留 `en-US`），禁止散落硬编码。  
关系 intent 经 `present_relation_intent`（RelationPresenter）：`near` →「厨房靠近餐厅」，禁止输出 enum 名。

Key Intent
  - Two-story residence
  - 3 bedrooms
  - Living room south-oriented
  - Kitchen near dining
  …

Assumptions …
Unresolved (Unknowns) …

（再）Floor plans · Room schedule · Evaluation · Findings
```

### 必须声明 AI / Solver 边界（页脚或 Provenance）

准确写法示例：

```text
Requirement interpretation: Local LLM + deterministic semantic pipeline
Geometry: PlanSeed deterministic solver
Evaluation: PlanSeed residential heuristic evaluator

AI interpreted design intent; deterministic solver generated and evaluated geometry.
```

**禁止**写：「AI designed this house.」

## 明确不做（本阶段）

- Advanced Site / Environmental Analysis  
- Code Profiles / Jurisdiction  
- BIM / IFC / Revit / DWG  
- DXF（7.0 不做）  
- 跨平台 packaging 硬化  
- 交互编辑加深  
- solver 重构 · LLM 扩功能 · 性能专项（量化/换模）
- **不为 Blind 证据链停下来重开 Phase 6 抠分**（可选日后冻结 commit 复跑；见 6.7.2）

NL 解析进度文案属最小 UX（「正在理解需求…」），见下；**不**把 P90 压到数秒当 Phase 7 门槛。

## Blind Gate 与开工条件（状态）

严格顺序曾为：

```text
冻结 parser → Blind 单次跑分 → Gate → Phase 7
```

**当前：** Blind v4（44 案，`qwen2.5:7b` Pipeline）**数字过门**入库  
（`docs/baselines/llm-alpha-baseline.json` / `…-blind-v4.json`）。

| 门槛 | Blind v4 |
|------|----------|
| Field ≥90% | ✅ 96.2% |
| Rel F1 ≥80% / P ≥75% | ✅ 91.4% / 84.2% |
| Unknown P ≥70% | ✅ 100% |
| Case pass ≥70% | ✅ 88.6% |
| Geometry = 0 | ✅ |

→ **工程上可继续 Phase 7；不因 provenance 缺口重开 Phase 6。**  
→ Blind v4 **不等于**「冻结 commit 严格可复现资格」（meta.git_commit 与 blind-v4 落地 commit 不一致；见 6.7.2）。  
post-alpha 已知限制（latency、Holdout bathrooms ≈87.5%）见 [hybrid-semantic-parser.md](hybrid-semantic-parser.md)，不挡 Export。

## NL 解析进度（最小 UX）

```text
正在理解需求…
正在检查设计条件…
正在整理未确定信息…
```

## Definition of Done（7.0）

1. [x] Backend 可 `POST /api/reports/build` → `DesignReportPayload`（JSON）  
2. [x] Desktop 可预览 HTML 报告并 Print/PDF  
3. [x] 报告含：Key Intent · Assumptions · Unknowns · 平面（`floor_svgs` 或整图 snapshot）· Room schedule · Score · Findings · Provenance  
4. [x] 面积 / 评分 / Finding **不**由前端重算  
5. [x] 不引入云端渲染 / 云端 LLM / DXF  
6. [x] per-floor：`render_floor_svg` → `CandidatePayload.floor_svgs` → 报告只消费（禁止 builder 切 DOM）  


## Definition of Done（7.0.1）

1. [x] `DesignReport.status` / `evaluation_fresh` / `source_revision_id`  
2. [x] Dirty → `409 candidate_requires_revalidation`（默认）  
3. [x] Desktop dirty 拦截 + 文案  
4. [x] HTML 对 stale 打醒目标记（仅 allow_stale 路径）  
5. [x] Preview（payload）vs Final（`project_id` + `candidate_id` + `revision_id`）  
6. [x] `sanitize_report_svg` 纵深防御（print / srcDoc）  
7. [x] `revision_id` / `source_revision_id` 溯源；mismatch → 409  
8. [x] Report 层成体系测试：`backend/tests/test_report_layer.py`（含 dirty / area / score / findings / sanitize / escape）

原则：**Report renderer ≠ Evaluator** — Finding 直接消费 `DesignFinding.title/message/severity`，不重算分。

实现落点：`packages/schema/report.py` · `backend/services/report_builder.py` · `backend/services/report_html.py` · `backend/routes/reports.py` · Desktop「报告」按钮。
