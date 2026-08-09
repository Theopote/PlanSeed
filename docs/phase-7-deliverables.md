# Phase 7 — Deliverables / Export

> **状态：▶ 7.2.3 DesignReport JSON ← 下一 · 7.2.1/7.2.2 ✅ · 7.1.1 Print smoke 人手待勾**
> **详案：** 本页 · [phase-7.1.1-accuracy-print-smoke.md](phase-7.1.1-accuracy-print-smoke.md) · [phase-7.1-print-smoke.md](phase-7.1-print-smoke.md)
> **前置：** Phase 6 **彻底冻结**（Blind 工程 PASS；`qualify --gate` 拒 dirty worktree；不开抠分）  
> 总览：[roadmap.md](roadmap.md) · 架构原则：[hybrid-semantic-parser.md](hybrid-semantic-parser.md)

## 产品闭环

完整链已是：

```text
NL → RequirementSpec → Generate → Evaluate → Compare
  → Edit → Revalidate → Save → Deliver
```

Phase 7 = **Deliverable Layer**（可靠地把真实 design revision 变成不会误导用户的交付物），  
不是高级分析、再扩 LLM，也不是 Interoperability Platform。  
**产品问题已变为：** 生成的东西能不能离开 PlanSeed？

## 子阶段优先级

| 子阶段 | 主题 | 状态 |
|--------|------|------|
| **7.0** | Deliverable Model | ✅ |
| **7.0.1** | Report Integrity | ✅（含 score 事实源 · `validation.valid` gate） |
| **7.1** | Report Presentation | ✅ Engineering（收口见 7.1.1） |
| **7.1.1** | Presentation Accuracy & Smoke | Engineering ✅；Print smoke ☐ |
| **7.2** | Export Formats | **← 当前**（下一 7.2.3 JSON） |
| **7.5** | Alpha Engineering Hardening | 7.2 完成后 |
| **8.0** | Solver Diversity / Solver 2.0 | 后续 |

**不做（本 Phase）：** DXF / DWG / IFC / Revit / BIM · ReportLab / WeasyPrint / Chromium headless / PDF canvas · ZIP Export Package · ExportManifest · Phase 6 抠分 · 新评价轴 · 新 LLM · solver refactor · Canva 式品牌模板 · 把审计优化建议塞进 7.2 · **继续美化 7.1 报告视觉**。

## 第一刀：Export Design Report

格式优先级：

1. **HTML → WebView → Print / PDF**（Alpha 正确路径）  
2. SVG / PNG 平面图  
3. JSON（`DesignReportPayload` 快照）  
4. DXF — **later**，不挡主线

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
DesignReport → HTML Renderer（→ Print / PDF）
DesignReport → JSON export
DesignReport → SVG / PNG（7.2）
# 不做：专业 PDF 引擎 · DXF/DWG/IFC
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

## PDF 策略：HTML → Print，不引入专业 PDF 引擎

Phase 7 **正确路径**：

```text
DesignReport → HTML → Tauri WebView → Print / PDF
```

**除非** HTML Print 出现解决不了的问题，否则**不**引入：ReportLab · WeasyPrint · Chromium headless service · PDF canvas engine。

优势：排版快、中文易、SVG 原生、预览即所得。

## 报告要可解释，不是「漂亮」

首页建议结构：

```text
PlanSeed 设计报告
项目 · 求解器生成 | 用户编辑 · 已验证 · 方案 A.2 · Score 84
（用户编辑 · 评价过期 禁止正式报告）

设计要点（Key Intent）：
  两层住宅
  3 间卧室
  客厅朝南
  厨房靠近餐厅
  …

假设 …
待决问题 …

（再）分层平面 · 空间面积表 · 设计评价 · 关键发现
```

文案由 `ReportLocale` 集中管理（**Alpha 默认 `zh-CN`**；`en` 仅预留，文档示例以中文为准），禁止散落硬编码。  
关系 intent 经 `present_relation_intent`：`near` →「厨房靠近餐厅」（`intent.relation.near`），禁止输出 enum 名。  
上列 Key Intent 为 **`report_i18n.format_key_intents` 当前 zh-CN 真实输出**（`intent.two_story` / `intent.bedrooms` / `intent.south_living` / `intent.relation.near`）。  
**禁止**再写过时英文示例：`Two-story residence` / `3 bedrooms` / `Kitchen near dining`。

### 必须声明 AI / Solver 边界（页脚或 Provenance）

准确写法示例（`zh-CN`；`en-US` 见 `report_i18n`）：

```text
需求解释：本地 LLM + 确定性语义流水线
几何：PlanSeed 确定性求解器
评价：PlanSeed 住宅启发式评价器

AI 解释设计意图；确定性求解器生成并评价几何。
```

**禁止**写：「AI designed this house.」

## 明确不做（本阶段）

- Advanced Site / Environmental Analysis  
- Code Profiles / Jurisdiction  
- **BIM / IFC / Revit / DWG**（≠ Interop Platform）  
- **DXF**（7.x 不做）  
- **ReportLab / WeasyPrint / Chromium headless / 手搓 PDF canvas**  
- 跨平台 packaging 硬化  
- 交互编辑加深  
- solver 重构 · LLM 扩功能 · 性能专项（量化/换模）  
- **Phase 6.7.3+ Blind 抠分**（仅可选：干净 commit 复跑资格认证）

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


## Definition of Done（7.0.1）— ✅ 关闭

1. [x] `DesignReport.status` / `evaluation_fresh` / `source_revision_id`  
2. [x] Dirty → `409 candidate_requires_revalidation`（默认）  
3. [x] Desktop dirty 拦截 + 文案  
4. [x] HTML 对 stale 打醒目标记（仅 allow_stale 路径）  
5. [x] Preview（payload）vs Final（`project_id` + `candidate_id` + `revision_id`）  
6. [x] `sanitize_report_svg` 纵深防御（print / srcDoc）  
7. [x] `revision_id` / `source_revision_id` 溯源；mismatch → 409  
8. [x] Report 层成体系测试：`backend/tests/test_report_layer.py`（含 dirty / area / score / findings / sanitize / escape）  
9. [x] 报告 Header 总分 **只取** `DesignScore.total_score`（`candidate.score` 仅为 ranking cache，不得覆盖）  
10. [x] `validation` 存在且 `valid=false` → `INVALID_CANDIDATE`（正式报告拒绝；不依赖「正常 pipeline 不会出现」）

原则：**Report renderer ≠ Evaluator** — Finding 直接消费 `DesignFinding.title/message/severity`，不重算分。

实现落点：`packages/schema/report.py` · `backend/services/report_builder.py` · `backend/services/report_html.py` · `backend/routes/reports.py` · Desktop「报告」按钮。

→ **进入 7.1 Report Presentation**（不重开 Phase 6）。

## 已知 P2（不挡 7.1）

- **`ProjectMetadata.generated_at` 命名不准**：实际是**报告构建时间**，不是 Candidate 生成时间。后续宜改为 `report_generated_at`，并另留 `candidate_created_at` / `revision_created_at`（需 schema / HTML / API 一并改）。

## 7.1 — Report Presentation（✅ Engineering）

目标：报告成为建筑师愿意给客户 / 同事 / 自己归档的**设计成果**，不是开发面板导出。

**不再补 backend Integrity 主线**（7.0.1 已关）。视觉已够 Alpha — **不做** logo / 品牌色 / 复杂封面 / 主题商城。

短收口见 **[7.1.1](phase-7.1.1-accuracy-print-smoke.md)**（北针 · TS fidelity · Print smoke）。

### A. 信息层级

```text
Cover / Executive Summary
  项目 · Candidate · Score · 关键意图 · 一句话摘要
01 Design Brief
02 Floor Plans
03 Space Schedule
04 Design Evaluation
05 Key Findings
06 Assumptions & Open Questions
07 Provenance
```

第一眼不是技术数据流。

### B. Floor Plan = 视觉核心

每层独立页 · 楼层标题 · **真实北向** · 尺度说明 · 图例 · 留白 · 打印分页。  
接近建筑方案报告，避免 Web UI 截图感。  
（房间标签 / 面积标注仍消费既有 SVG；本阶段不切 SVG DOM。）

**北向（P0）：** `FloorPlanBlock.north_angle_deg` ← `SiteCoordinateSystem` / `requirement.site.north_angle`  
（或 assumption）。HTML 用 `rotate(-north_angle)` 指向世界北。  
**未知 → 显示「北向未定义」，禁止默认 ↑N。** Renderer 不重新解释坐标系。

**尺度文案：** 保持「单位：米 · 图示为方案示意…」即可。  
**禁止**冒充 `1:100` / `1:50`，除非 7.2.4 真正做了打印物理尺度校准。

### C. Space Schedule 建筑化

主表列：房间 · 楼层 · 目标面积 · 实际面积 · 差值 · 宽 × 深。  
`room_id` 留在 JSON / Provenance，不进主表首列。

### D. Evaluation Presenter

```text
DesignScore + DesignFinding
  → ReportEvaluationPresenter（确定性）
  → 七轴分数 + 档位（良好/尚可/可改善）
  → Top 3 strengths / Top 3 concerns
```

**禁止** LLM 重写优缺点。

### E. 阅读顺序

Assumptions / Unknowns **后置**（06），不抢平面之前的主视觉。  
仅 **blocking** unknown 在 Cover 醒目标出。

**事实链：** Desktop `RequirementSpecPayload` / `ProgramSummary` 须携带
`unknown.priority` 与 `assumption.source`（与 Phase 6 schema 一致）；
编辑假设时不得丢弃 `source`。报告 Cover 的 blocking banner 依赖完整 priority。  
详见 [phase-5.1.1-program-fidelity.md](phase-5.1.1-program-fidelity.md)「TS Fidelity Audit」。

### Definition of Done（7.1）

工程项 1–7 已完成。收口见 **7.1.1**（仅四条）：

1. [x] 北向真实绑定项目坐标  
2. [x] RequirementSpec TS fidelity audit  
3. [ ] Windows WebView2 打印 smoke（P01–P08）  
4. [x] 文档同步（Key Intent 示例 = zh-CN 真实输出）  

第 3 条填完 → **关闭 7.1**，开工 7.2。**不要继续美化报告视觉。**

## 7.1.1 — Accuracy + Print Smoke（极短收口）

详案：[phase-7.1.1-accuracy-print-smoke.md](phase-7.1.1-accuracy-print-smoke.md)

| 级 | 项 | 状态 |
|----|-----|------|
| P0 | 北向真实绑定项目坐标 | ✅ |
| P1 | RequirementSpec TS fidelity audit | ✅ |
| P1 | Windows WebView2 打印 smoke | ☐ 人手 |
| P2 | 文档同步（zh-CN Key Intent 示例） | ✅ |

四条齐 → **关闭 7.1** → **7.2.1**。不要继续美化。

## 7.2 — Export Formats（← 主线）

用户闭环：Generate → Compare → Edit → Revalidate → Save → **Export**。  
完成后视为 **PlanSeed Alpha Product Loop Complete**。

**禁止：** DXF/DWG/IFC/BIM · ReportLab/WeasyPrint/Chromium PDF · ZIP Export Package（先单格式）· ExportManifest（稳定后再议）· 继续美化 7.1。

| 子阶段 | 主题 | 状态 |
|--------|------|------|
| **7.2.1** | SVG Export | ✅ |
| **7.2.2** | PNG Export | ✅ |
| **7.2.3** | DesignReport JSON | **← 下一** |
| **7.2.4** | Print / PDF Polish | CSS print only；非 PDF 引擎 |
| **7.2.5** | Export UX Consolidation | Export Dialog；防按钮爆炸 |

### 7.2.1 — SVG Export ✅

**导什么（三分）：**

| scope | 来源 | 文件名后缀 |
|-------|------|------------|
| `floor` | `candidate.floor_svgs[floor_id]` | `_F1.svg` |
| `all_floors` | 各层 SVG → zip | `_floors.svg.zip` |
| `snapshot` | `candidate.svg` | `_ALL.svg` |

**信任边界：**

```text
project_id + candidate_id + revision_id (+ floor_id)
  → ProjectStore → canonical floor_svgs / svg
  → sanitize → file response
```

**禁止：** React DOM `querySelector("svg").outerHTML`。

**API：** `POST /api/exports/svg`（不塞进 `/api/reports/build`）  
**实现：** `backend/services/export/svg_exporter.py` · `final_gate.py` · `backend/routes/exports.py`

### 7.2.2 — PNG Export ✅

```text
Canonical Floor SVG → sanitize → resvg → PNG（白底）
```

| 项 | 约定 |
|----|------|
| 分辨率 | 最长边 **2048 / 4096** px（保持比例） |
| 背景 | `#ffffff` |
| 引擎 | `resvg-py`（本地 wheel；**非** Chromium / HTML 截图） |
| API | `POST /api/exports/png`（同 SVG 的 scope + `size`） |
| 实现 | `backend/services/export/png_exporter.py` |

**禁止：** HTML/Workbench 截图 · Chromium 服务 · 透明/暗色/水印/品牌模板（Alpha）  
**依赖：** `resvg-py` · `pillow`（测试/像素校验；光栅主路径为 resvg）

### 7.2.3 — DesignReport JSON（← 下一）

| | Project Snapshot | DesignReport JSON |
|--|------------------|-------------------|
| 用途 | 继续编辑 / 恢复 | 交付 / 归档 / 审计 |
| 内容 | 工作台 payload | `DesignReport` + `report_schema_version` |

含：schema_version · project · source_revision_id · requirement · assumptions/unknowns · candidate · floor meta · schedule · evaluation · findings · provenance。  
Alpha 可内嵌 SVG；禁止 `candidate.model_dump()` 冒充。

### 7.2.4 — Print / PDF Polish

继续 `HTML → WebView2 → Print → PDF`。  
只做 `@page` / break / orphans / widows / 表头 / 封面。  
**禁止**冒充 `1:100`（未做物理校准前）。

### 7.2.5 — Export UX Consolidation

单一 **Export Dialog**（报告预览/打印/JSON · 平面 SVG/PNG），避免按钮爆炸。

### Definition of Done（7.2）

用户可导出：**Design Report · PDF(Print) · SVG · PNG · JSON**，且均走 Final Export trust boundary → **Alpha Product Loop Complete**。
