# PlanSeed 路线图

> **当前焦点：Phase 7 Deliverables / Export**  
> Phase 6 ✅ Strict Alpha Qualified（Blind v4 Gate PASS）  
> 详案：[phase-7-deliverables.md](phase-7-deliverables.md) · [phase-6.7.2-blind-requalification.md](phase-6.7.2-blind-requalification.md)  
> 契约：[api-contract.md](api-contract.md)

## 项目状态（阶段判断）

| 阶段 | 主题 | 状态 |
|------|------|------|
| **0–5.1.1** | **Design Kernel** | **✅** |
| **6.0–6.6** | **LLM Infrastructure** | **✅** |
| **6.7 / 6.7.1** | **Qualification · Parser Precision** | ✅ Engineering；Holdout 泄漏 |
| **6.7.2** | **Blind Requalification** | ✅ **Blind v4 PASS → Strict Alpha Qualified** |
| **7** | **Deliverables / Export** | **← 当前** |

```text
0–5.1.1   Design Kernel                ✅
6.0–6.6   LLM Infrastructure           ✅
6.7.1     Precision Pipeline           ✅
6.7.2     Blind Qualification          ✅ Blind v4 PASS → Strict Alpha Qualified
7         Deliverables / Export        ← 当前（DesignReport → HTML/JSON/Print）
```

```text
现在做：Phase 7.0 DesignReport model + /api/reports/build + HTML 预览/Print
不做：DXF/DWG/IFC · 手搓 PDF layout · 前端重算面积 · 继续抠 Phase 6 分数 · 云端 LLM
```

## 阶段总览（以代码为准）

| Phase | 主题 | 状态 |
|-------|------|------|
| 0–3 | Core / Solver / Evaluation | ✅ Design Kernel |
| **3.5** | **Core Consolidation** | **✅** |
| **3.6** | **Desktop Runtime Reliability** | **✅**（勿再扩 runtime 主线） |
| **4** | **Interactive Design Workbench** | **✅ 4.3 / 4.3.1** |
| **5** | **Project Persistence** | **✅ P0/P1** |
| **5.1** | **Revision Integrity & Mutation Single Source** | **✅ P0** |
| **5.1.1** | **Program Fidelity Gate** | **✅ P0** |
| **6.0–6.6** | **LLM Infrastructure** | **✅ Engineering Complete** |
| **6.7** | **Real Model Qualification & Runtime Hardening** | ✅ |
| **6.7.1** | **Parser Precision & Holdout** | ✅ Engineering（Holdout 泄漏 → 非严格独立） |
| **6.7.2** | **Blind Requalification** | ✅ Blind v4 PASS |
| **7** | **Deliverables / Export** | **← 当前** |
| **8+** | Advanced Site / Code Profiles / Interop… | **暂不正式规划**（避免失焦） |
| — | SVG Debug | ✅ 开发工具 |

**平台纪律：** Desktop Alpha **只交付 Windows 10/11 x64**；禁止并行搞 macOS/Linux packaging 拖慢主线。  
**禁止：** 因 UI 已出现就堆按钮；推倒四区工作台；runtime 与 solver **同时快速改**；在 6.7 未完成前扩 LLM 产品功能或回头大改 solver。

### Desktop Alpha v0.1 — 契约冻结（至少到 v0.1 发布）

Solver / Evaluation / API **短暂冻结**，避免 Phase 4 交互编辑时前端追 schema：

| 层 | 冻结内容 |
|----|----------|
| Solver schema | `LayoutCandidate` 主字段形状；不借机大改几何模型 |
| Evaluation | **七轴名称**（已冻）+ `DesignScore` / `DesignFinding` 字段契约 |
| API | `GenerateResponse` · `CandidatePayload` · `DesignScore` · `DesignFinding` · `solver_identity` / `CandidateProvenance` |
| Alias | `DesignEvaluation = DesignScore` **保持**；正式拆 Evaluation 延后 |

**允许：** bugfix、文档、CI 绿、runtime 小修、Workbench UI（只消费冻结契约）。  
**禁止：** 为「模型纯洁」拆 Evaluation；扩轴；改 ranking/compare 规则却不 bump `evaluation_version`；前端自创评分逻辑。  

书面契约：[api-contract.md](api-contract.md)

---

## Phase 3 — Architectural Evaluation（✅ MVP）

Evaluator 只评分，不改几何。用户层七轴：

| 用户轴 | 模块 | 要点 |
|--------|------|------|
| Program | `program_fit.py` + adjacency | 清单覆盖 / 面积份额 / 邻接 |
| Spatial | geometry + compactness | 比例 / 紧凑度（面积归 Program） |
| Circulation | `circulation.py` + `access.py` | realized 可达 / 深度 / 穿堂 |
| Privacy | `privacy.py` | entry→private 过渡；穿卧惩罚 |
| Environment | `orientation.py` | **Orientation MVP**：朝向 / 外墙；非日照·通风·景观 |
| Technical | `vertical.py` + entry/site | **Technical Logic**：楼梯 / 湿区 / 入口·场地；非结构·设备·消防·法规 |
| Robustness | repair metrics | ConnectionResolver / reslice 稳定性 |

`DesignScore`：七轴（**名称冻结至 Phase 4**，见 [scoring.md](scoring.md)）+ `findings[]`；`explanations` / `warnings` 由 findings 派生。  
`DesignEvaluation`：当前为 **temporary compatibility alias**（`= DesignScore`）；长期再拆成真正 Evaluation 模型（非 P0，见 [scoring.md](scoring.md)）。  
Finding = **design heuristic**（≠ code compliance；无 CodeProfile 前禁止合规语气）。  
版本签名：`solver=0.4` / `generator=guillotine-lock-v4` / `evaluation=residential-alpha-v1`（见 [scoring.md](scoring.md)）。  
**不做（本 Phase）**：daylight；LLM；房间拖拽编辑。

---

## Phase 3.5 — Core Consolidation & Local Desktop Runtime（✅）

详案：[phase-3.5-core-consolidation.md](phase-3.5-core-consolidation.md)

### 优先级

| 级 | 主题 | 状态 |
|----|------|------|
| **P0** | DesignEvaluation / Finding、Metric ownership、去重评、roadmap | ✅ |
| **P0** | **Tauri sidecar runtime**（本地独立工具能否成立） | ✅（见 3.6 Windows 装包验收） |
| **P1** | API layering | ✅ |
| **P1** | Inspector findings 人话 + **Candidate Compare** | ✅（房间/度量/平面高亮 + Compare） |
| **P2** | Rejected Candidates（为何被淘汰） | ✅ MVP（仅 hard-fail；≠ 未进 Top-K） |
| **P2** | Local LLM | **不做本阶段** |

### Desktop Alpha 里程碑（本阶段完成定义）

**平台写死：Windows 10/11 x64**（`build_backend_sidecar.ps1`）。macOS/Linux **Alpha 后**再开。

```text
双击 PlanSeed → 后台自动起引擎 → 输入需求 → Generate
→ Top 5 → 评分与设计解释 → A/B 比较
```

跑通即第一个真正可用 Desktop Alpha。  
解释必须 deterministic（findings / score 差分），禁止用 LLM 写优缺点。

### Candidate Compare（P1）

不只点击切换 A…E；支持 **Compare A vs B**：七轴对照表 + 双方优势列表（由 findings/分数差分生成）。

### Rejected Candidates（P2 MVP）

左侧「被淘汰」展示 **hard-fail** 样例：`seed` + hard violation 人话原因 + `violation_summary`。  
**`rejected` ≠ 有效但未进 Top-K**（后者本轮不做）。

---

## Phase 3.6 — Desktop Runtime Reliability & Evaluation Contract（✅）

详案：[phase-3.6-runtime-reliability.md](phase-3.6-runtime-reliability.md)

**已完成并冻结进 Phase 4。** 禁止再开「runtime 收口」轮次；仅允许 bugfix / 装包冒烟。不开 3.7+。

| 级 | 主题 | 状态 |
|----|------|------|
| **P0** | Engine Identity Probe 三态：PORT_FREE / PLANSEED_ENGINE / FOREIGN_SERVICE | ✅ |
| **P0** | health 契约含 api_version + engine_version；就绪非仅 TCP | ✅ |
| **P0** | **GitHub Actions CI**（pytest / ruff / mypy / pnpm build / cargo check） | ✅ workflow 已配；**是否绿以 Actions run 为准** |
| **P0** | **3.6.1** `engine-status` 唯一事实源；MANAGED / REUSED；reuse health；retry | ✅ |
| **P1** | evaluation 单一事实源 / 确定性契约测试 | ✅ 基线；后续只 bugfix，不扩规则 |
| **P2** | onedir 真装包冒烟 | ✅ 本机记录；sidecar 工作流手动/release |

---

## Phase 4 — Interactive Design Workbench（← 当前：4.3）

**围绕加深，禁止推倒重做。** UI = 观察/控制 solver 的窗口，不是功能堆场。

### Phase 4.0 — Select → Inspect → Edit area → Regenerate（✅）

- [x] 点击平面房间选中
- [x] Inspector：RoomSpec + RoomPlacement（`placements` additive）
- [x] 修改 target_area（session Program）
- [x] Regenerate（按当前 spaces 整案重生成）

### Phase 4.1 — Lock Room / Stair（✅ MVP）

- [x] Lock Room / Lock Stair（钉死当前候选几何）
- [x] `GenerateRequest.locks` → Guillotine 挖洞 + 合并锁定放置
- [x] Regenerate unlocked（未锁空间重排）

### Phase 4.1.1 — Lock Zone（✅ MVP）

- [x] Lock Zone（钉死功能区 envelope；区内仍可重排）
- [x] FunctionalZoneGroup（同 floor + kind 全部组件）

### Phase 4.1.2 — Lock Semantics Hardening（✅）

详案：[phase-4.1.2-lock-semantics.md](phase-4.1.2-lock-semantics.md)

| 级 | 主题 | 状态 |
|----|------|------|
| **P0** | floor-local lock free space | ✅ |
| **P0** | post-processing 不得移动 Room/Stair lock | ✅ |
| **P0** | final lock invariant checker | ✅ |
| **P1** | lock request validation（422） | ✅ |
| **P1** | Room > Zone > Free | ✅ |
| **P1** | zone identity（`id` / `kind`） | ✅ |
| **P1** | zone member 过程护栏（不得修出 envelope） | ✅ |
| **P2** | Variant locks 快照 · `lock_invariant_ok` · 补测 | ✅ |

**暂停：** 拖房间深化、拖墙、自由 resize。  
已有平移 MVP 可留；扩编辑必须等 **Geometry Mutation Authority**（见 4.3）。

**4.1.2 收口完成** → 下一产品步 **4.3**（有限编辑 + Mutation Authority）。

### Phase 4.2 — Create Variant + Compare（✅）

- [x] `GenerateRequest.base_seed`（additive）→ 新种子批次
- [x] Create Variant：同 program/locks，**追加**候选条带（不替换）
- [x] 自动设比较对象（旧选中 vs 新 Top）
- [x] 沿用 `POST /api/compare`（React 不自算分）

**产品方向（已确认）：** 保留 program + locks → `max(seed)+1` 起跑 8 取 Top3 → 追加 Strip → 自动对比。  
血缘树进 Phase 5。

### Phase 4.3 — Constraint-aware Direct Manipulation（← 当前）

详案：[phase-4.3-direct-manipulation.md](phase-4.3-direct-manipulation.md)

**不是**鼠标随便拖墙。流程必须是：

```text
拖动 → ProposedMutation → Constraint Preview
  → 合法？ Commit : 显示原因 / Snap Back
```

统一经 **Geometry Mutation Authority**：

```text
LockGuard → GeometryConstraintChecker → AccessImpactChecker → Commit → Revalidate
```

| 级 | 主题 | 状态 |
|----|------|------|
| **P0** | `GeometryMutation`（MOVE / RESIZE / LOCK / UNLOCK）+ Authority 唯一写入口 | ✅ MOVE/RESIZE；LOCK/UNLOCK kind 已建模 |
| **P0** | Move Room：迁入现有平移 MVP；非法 Snap Back | ✅ |
| **P0** | LockGuard（zone envelope；不与其它锁/房重叠；可建范围） | ✅ |
| **P1** | Resize Room（边/角；受 min width） | ✅ |
| **P2** | 拖动中 preview / 冲突高亮 / AccessImpact | ✅ |
| **4.3.1** | 有限共墙 `ADJUST_WALL`（恰好两房；拒 T 接） | ✅ |

**不做：** T 接多房推挤、无约束自由 resize、绕过 Authority 写 PlacementRect。

```text
┌ Requirements ┬──────── Floorplan ────────┬ Inspector ┐
│ Site         │     受控 Move / Resize    │ RoomSpec  │
│ Program      │        FLOOR PLAN         │ Placement │
│ Constraints  │                           │ Score…    │
│ Preferences  │                           │ Findings  │
└──────────────┴───────────────────────────┴───────────┘
│                   Candidate Strip（含 Compare）       │
└─────────────────────────────────────────────────────┘
```

---

## Phase 5 — Project Persistence（✅ P0/P1）

详案：[phase-5-persistence.md](phase-5-persistence.md)

- [x] 本地项目 / 候选快照（含 provenance + 血缘）  
- [x] 重开可解释：`evaluation_version_mismatch` 提示  
- [x] **Variant 血缘（设计过程树）** — additive；Strip 仍扁平列表 + 代数标签：
  - `variant_parent_id`：从哪个候选点的 Create Variant
  - `variant_generation`：相对根的代数（A → A·1 → A·2）
  - `lock_snapshot_id`：当时 locks 指纹
- [x] SQLite `~/.planseed/projects.db`（`PLANSEED_DB` 可覆盖）+ `/api/projects` CRUD

---

## Phase 5.1 — Revision Integrity & Mutation Single Source（✅ P0）

详案：[phase-5.1-revision-integrity.md](phase-5.1-revision-integrity.md)

在接 LLM 之前的短闸门：消除「两个 Geometry Mutation Authority」、脏 Candidate 假评分、保存时误 bump 版本。

- [x] `POST /api/mutations/preview` → `preview_mutation()`（Python 唯一裁决）
- [x] Desktop pointer-up 走 Mutation API；TS 仅 visual / 手柄
- [x] WorkingDraft + `revision_status`（DIRTY 不展示旧分当当前）
- [x] 项目快照保留 dirty / mutations；Save 不误升 `evaluation_version`
- [x] 测试覆盖 mutation API + version preserve
- [x] `POST /api/mutations/revalidate`（openings + evaluation；不经 Guillotine）

**Phase 5.1 P0 已收口。**

---

## Phase 5.1.1 — Program Fidelity Gate（✅ P0）

详案：[phase-5.1.1-program-fidelity.md](phase-5.1.1-program-fidelity.md)

LLM 前极短闸门：canonical `RequirementSpec` 往返 + revalidate 楼梯 metadata 推导。

- [x] `GenerateResponse.requirement_spec` + `ProjectPayload.requirement_spec`
- [x] Desktop 会话以 RequirementSpec 为事实源（禁止 ProgramSummary 反推）
- [x] hydrate 从 `stair-*` placements 填 `stair_x0…` / `core_placement`
- [x] 测试：spec 持久化往返；stair 对齐可测

**已收口；可进入 Phase 6。**

---

## Phase 6 — Local LLM Requirement Parsing（Infrastructure ✅ · Qualification ←）

详案：[phase-6-local-llm.md](phase-6-local-llm.md)

```text
Natural Language → (Ollama) → RequirementSpec → validate → normalize → Solver
```

**LLM NEVER GENERATES GEOMETRY。** 写出的 `RequirementSpec` 必须进入会话事实源并随项目保存。

**完成标准：**

```text
6.0–6.6  ✅ LLM Infrastructure（Engineering Complete）
6.7      ← Real Model Qualification & Runtime Hardening
Phase 6  ✅ Alpha Qualified  ← 仅当某本地模型过 Alpha Gate
然后     → Phase 7 Deliverables / Export
```

| 子阶段 | 主题 | 状态 |
|--------|------|------|
| **6.0** | LLM Boundary（契约 / Known·Assumed·Unknown） | ✅ |
| **6.1** | Ollama Provider（`LLMProvider` 抽象） | ✅ |
| **6.2** | Structured Requirement Parser | ✅ |
| **6.3** | Validation + Repair | ✅ |
| **6.4** | Assumption / Unknown UI | ✅ |
| **6.5** | NL → Generate | ✅ |
| **6.6** | Requirement Benchmark（oracle harness ≠ 真模型准确率） | ✅ |
| **6.7** | Real Model Qualification & Runtime Hardening | ← 当前 |

详案：[phase-6.0-llm-boundary.md](phase-6.0-llm-boundary.md) · [phase-6.1-ollama-provider.md](phase-6.1-ollama-provider.md) · [phase-6.2-structured-parser.md](phase-6.2-structured-parser.md) · [phase-6.3-validation-repair.md](phase-6.3-validation-repair.md) · [phase-6.4-assumption-unknown-ui.md](phase-6.4-assumption-unknown-ui.md) · [phase-6.5-nl-generate.md](phase-6.5-nl-generate.md) · [phase-6.6-requirement-benchmark.md](phase-6.6-requirement-benchmark.md) · [phase-6.7-real-model-qualification.md](phase-6.7-real-model-qualification.md) · [phase-6-local-llm.md](phase-6-local-llm.md)

### Phase 6.0 — LLM Boundary ✅

- [x] 禁几何扫描 + `LLMRequirementDraft` / Known·Assumed·Unknown
- [x] `LLMProvider` Protocol + `MockLLMProvider`
- [x] `RequirementSemanticValidator` + `ingest_llm_requirement`
- [x] Draft → `RequirementSpec`（可进 Normalizer）
- [x] 测试：`packages/llm/tests`

### Phase 6.1 — Ollama Provider ✅

- [x] `OllamaConfig` + env（`PLANSEED_OLLAMA_*`）
- [x] `OllamaProvider.complete_json` → `/api/chat`（`format=json`）
- [x] `create_llm_provider()` 工厂（`ollama` | `mock`）
- [x] MockTransport 测试；无云端 API
- [x] `httpx` 运行时依赖

### Phase 6.2 — Structured Parser ✅

- [x] `parse_requirement_text` / `StructuredRequirementParser`
- [x] `draft_json_schema()` + `create_requirement_llm_provider()`
- [x] 用户提示模板；经 ingest gate
- [x] 测试：MockProvider 路径

### Phase 6.3 — Validation + Repair ✅

- [x] 几何错误统一为 `LLMIngestError`（`req.geometry_forbidden`）
- [x] `parse_requirement_text_with_repair` / `LLMRepairExhaustedError`
- [x] `ParseResult.attempts` / `repair_notes`
- [x] 连接类错误不走 repair；测试覆盖成功与耗尽

### Phase 6.4 — Assumption / Unknown UI ✅

- [x] 左栏 `RequirementGapsPanel`（假设可改/清除，未知可「已知悉」）
- [x] 事实源 `requirementSpec`；镜像 `program`；空态明示
- [x] Generate 时把假设/未知写入会话 spec
- [x] 无 NL 入口（留给 6.5）

### Phase 6.5 — NL → Generate ✅

- [x] `POST /api/requirements/parse`（repair + Mock 可测）
- [x] Desktop：自然语言「解析」/「解析并生成」
- [x] 写入 `requirementSpec` + 简表回填；假设/未知走 6.4
- [x] 契约文档 additive 登记

### Phase 6.6 — Requirement Benchmark ✅

- [x] ≥50 条中文住宅用例（`packages/llm/benchmark/cases.py`）
- [x] 字段准确率 + must_unknown 反幻觉评分
- [x] CI oracle Mock：`field_accuracy` / `case_pass_rate` = 1.0（**仅 harness**）
- [x] 真模型可选：`run_benchmark(use_oracle=False, provider=…)`

**6.0–6.6 LLM Infrastructure Complete；可靠度不由 oracle 100% 代表。过 Alpha Gate 前不要写 Phase 6 ✅。**

### Phase 6.7 — Real Model Qualification & LLM Runtime Hardening

详案：[phase-6.7-real-model-qualification.md](phase-6.7-real-model-qualification.md)

**目标：证明本地 LLM 真正好用。** 不扩 LLM 产品功能；不回头重构 solver。

### Phase 6.7.1 — Parser Precision & Holdout ✅ Engineering

详案：[phase-6.7.1-parser-precision-holdout.md](phase-6.7.1-parser-precision-holdout.md)

**Holdout（30）+ Pipeline 已过门**，但 Holdout 在落地后继续驱动 enricher paraphrase，**独立性已泄漏** → 不作严格泛化证据。

| 指标（Holdout，工程） | 结果 |
|------|------|
| Field / Rel F1·P / Case pass | 96.2% / 82.4%·75% / 76.7% |
| Unknown P·R / Assumption P | 100%·89% / 100% |

### Phase 6.7.2 — Blind Requalification ✅ Strict Alpha Qualified

详案：[phase-6.7.2-blind-requalification.md](phase-6.7.2-blind-requalification.md) · 架构：[hybrid-semantic-parser.md](hybrid-semantic-parser.md)

```text
Blind v4 + qwen2.5:7b Pipeline：Alpha Gate PASS
parse 100% · field 96% · rel F1/P 91%/84% · repair 0% · case 89%
```

- [x] Blind v1–v3 FAIL 归档
- [x] Hybrid Parser · Relation Kind 分流 · Draft Coerce
- [x] Blind v4 Gate PASS → **Phase 6 ✅ Strict Alpha Qualified**
- [x] 解锁 Phase 7

---

## Phase 7 — Deliverables / Export ← 当前

详案：[phase-7-deliverables.md](phase-7-deliverables.md)

**产品闭环：** 用户已能理解需求 → 生成 → 比较 → 修改 → 评价 → 保存；下一步问「怎么把方案带走？」

**第一版价值最高的不是高级分析，而是 Export / Deliverable Layer：**

- Design Report（PDF 优先；或 HTML→打印）
- SVG / PNG 平面图
- JSON 项目快照
- DXF 后续

报告内容草案：项目需求 · 平面图 · 房间面积表 · 设计评分 · 主要 Findings · Assumptions · Unknowns · Candidate provenance。

**明确不塞进 Phase 7：** Advanced Site 分析 · Code Profiles · 跨平台 packaging · Interop · 交互编辑加深 · **LLM 性能专项**（量化/换模等）。这些若需要，以后单独开阶段，**现在不正式规划到 Phase 10**。  
NL 解析进度文案属最小 UX，见 [phase-7-deliverables.md](phase-7-deliverables.md)。

---

# 历史阶段（已完成，供查阅）

以下 Phase 0–2.x 已收口；**不要**当作当前开发焦点。

## Phase 1.5 — Solver Reliability（✅）

### P0 Correctness（✅ 已完成）

- [x] Hard adjacency checker
- [x] Soft area/width → `ConstraintEvaluationResult` 不丢弃
- [x] Missing / duplicate / wrong_floor / unknown room（`geometry.*`）
- [x] Duplicate room assignment detection
- [x] Floor assignment consistency
- [x] RequirementSpec assumption / unknown tracking（空 spaces ≠ benchmark）
- [x] Orientation evaluator 闭环
- [x] Exterior edges / wall length
- [x] LayoutSignature + buildable 归一化 similarity
- [x] `docs/constraint-coverage.md`
- [x] Quality regression 门槛 + demo 指标
- [x] SVG debug（room id / target·actual area）

### P1 Floor Assignment（✅）

```text
Rooms → FloorAssignmentSolver → floor.room_ids
```

Generator 不猜楼层。

**语义边界：** 住宅规则以 `RoomSpec.tags` 为准；`name` 是 UI 文本。  
中文 name 子串回退冻结在 `solver/semantics/roles.py`。  
自然语言 → tags 由 normalize / Phase 6 LLM 负责；Solver 不承担 NLP。

### P2 StairCore（✅；禁止缩小）

```text
1.6×整进深条带  →  StairCore ~1.8×4.2，N/S/E/W/center
放不下 → 换 orientation / placement → 仍不行 → geometry.core_unfit（不缩放）
```

### P3 Architectural Zones（✅ 初版）

```text
building envelope → StairCore → Zones (day / night / service) → Rooms
```

`ZonePlanner`：功能区与 `WetStack` 分离；MVP `max_wet_stacks=1`。

---

## 目标生成流水线（Phase 2 终态，✅）

```text
DesignProgram
      ↓
FloorAssignment
      ↓
Semantic RoomGraph
      ↓
AccessGraph
      ↓
ZonePlanner
      ↓
CorePlacement
      ↓
Graph-aware Room Ordering
      ↓
Guillotine
      ↓
ConnectionResolver
      ↓
DoorPlacement
      ↓
AccessibilityValidator
      ↓
Evaluator（→ LayoutCandidate.evaluation）
```

### Graph 反向驱动 Generator（已完成）

| 阶段 | 行为 |
|------|------|
| ~~纯 `rng.shuffle(rooms)`~~ | ❌ 已淘汰 |
| **2.0 ✅** | `TopologyPlan.pack_order_hint` + adjacency cluster 连续序 |
| **2.0.1 ✅** | `[Kitchen,Dining,Living]` 同一 slicing group |
| **2.1 ✅** | AccessGraph + ConnectionResolver 局部修补 |
| **2.1.2–2.1.3 ✅** | 跨区重切 / 绕核多 free-rect |
| **当前主线** | **Phase 7** Deliverables / Export（Phase 6 Strict Alpha Qualified） |

---

## Phase 2.0 — Topology-driven pack（✅ MVP）

```text
RoomGraph → TopologyPlan → Zone placement → Room placement
```

- `TopologyPlanner` 产出簇与 `pack_order_hint`
- Guillotine 区内序读 TopologyPlan；邻接簇为 slicing group

## Phase 2.1 — AccessGraph（✅）

```text
Room topology → AccessGraph → Required connections → Shared boundary → Door placement
```

- `ExteriorEntry`、`access.unreachable_room`、默认 soft AccessGraph
- ConnectionResolver：缝隙修补 → 局部重切 → 绕核多 free-rect
- **仍不**整层为连通重跑 Guillotine

## Phase 2.3 — Realized Circulation（✅）

```text
Adjacency / 共墙  ≠  Access Intent  ≠  Realized Access
```

- Reachability 只走 `RealizedAccessGraph`
- `RepairRecord` + repair budget；`layout_stability`

## Phase 2.2 — Door polish（✅；不回改房间）

- 净宽 soft、`swing_room_id`、铰链、SVG 门扇弧
- 无共边禁止凭空戳门
