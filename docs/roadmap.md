# PlanSeed 路线图

> **当前焦点：Phase 4.3 — Constraint-aware Direct Manipulation（前置）**  
> **4.1.2 Lock Semantics ✅** · 暂停自由拖拽深化 · 详案：[phase-4.1.2-lock-semantics.md](phase-4.1.2-lock-semantics.md)  
> 3.6 runtime ✅ · 契约：[api-contract.md](api-contract.md)

## 阶段总览（以代码为准）

| Phase | 主题 | 状态 |
|-------|------|------|
| 0–3 | Core / Solver / Evaluation | ✅ Alpha foundation |
| **3.5** | **Core Consolidation** | **✅** |
| **3.6** | **Desktop Runtime Reliability** | **✅**（勿再扩 runtime 主线） |
| **4** | **Interactive Design Workbench** | **← 当前（4.1.2 ✅ → 4.3）** |
| **5** | **Project Persistence** | 未开始 |
| **6** | **Local LLM Requirement Parsing** | **未开始**（禁止插队） |
| **7+** | **Export / Advanced Analysis**（含 packaging 硬化、跨平台） | 未开始 |
| — | SVG Debug | ✅ 开发工具 |

**平台纪律：** Desktop Alpha **只交付 Windows 10/11 x64**；禁止并行搞 macOS/Linux packaging 拖慢主线。  
**禁止：** 因 UI 已出现就堆按钮；推倒四区工作台；把 LLM 插队到 Alpha 冻结之前；runtime 与 solver **同时快速改**。

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

## Phase 4 — Interactive Design Workbench（← 当前：4.3 前置）

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

### Phase 4.3 — Constraint-aware Direct Manipulation（未开始）

先建立统一几何变更权威，再做有限编辑（非自由 CAD）：

```text
MutationRequest → LockGuard → GeometryValidator → Apply → Revalidate
```

- [ ] Geometry Mutation Authority（所有改 placement 的唯一入口）
- [ ] 有限平移 / 有限改尺寸（受 lock + 约束）
- [ ] **不做**本阶段：拖墙、完全自由 resize、constraint solver 重写

```text
┌ Requirements ┬──────── Floorplan ────────┬ Inspector ┐
│ Site         │     点击房间选中          │ RoomSpec  │
│ Program      │        FLOOR PLAN         │ Placement │
│ Constraints  │                           │ Score…    │
│ Preferences  │                           │ Findings  │
└──────────────┴───────────────────────────┴───────────┘
│                   Candidate Strip（含 Compare）       │
└─────────────────────────────────────────────────────┘
```

---

## Phase 5 — Project Persistence（未开始）

- [ ] 本地项目 / 候选快照（含 provenance）  
- [ ] 重开可解释：布局变了 vs `evaluation_version` 变了
- [ ] **Variant 血缘（设计过程树）** — additive，当前会话 Strip 仍可用扁平列表：
  - `variant_parent_id`：从哪个候选点的 Create Variant
  - `variant_generation`：相对根的代数（A → A1 → A1.1）
  - `lock_snapshot_id`：当时 locks 指纹/快照，解释「同锁不同种子」

```text
A
 ├─ A1
 ├─ A2
 │   ├─ A2.1
 │   └─ A2.2
```

Packaging 硬化（CSP、签名、其后 macOS）并入 **7+**，**禁止**与 Alpha / Phase 4 并行跨平台。

---

## Phase 6 — Local LLM Requirement Parsing（未开始）

```text
Natural Language → (Ollama) → RequirementSpec → normalize → Solver
```

禁止 LLM 输出坐标 / SVG / DesignProgram。**晚于 Desktop Alpha 契约冻结与 Phase 4 壳深化。**

---

## Phase 7+ — Export / Advanced Analysis（未开始）

- Export（图纸 / 数据）  
- Advanced analysis  
- Packaging 硬化（Windows 签名、CSP；其后 macOS / Linux）  
- Interactive editing 加深（仍在中栏 Floorplan）

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
| **当前主线** | **Phase 4.3** Constraint-aware Direct Manipulation（4.1.2 Lock ✅） |

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
