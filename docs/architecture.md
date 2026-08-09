# PlanSeed 架构文档

> Phase 0 基线 — 以 Architecture Foundation & MVP v2 为准。  
> **Desktop Alpha v0.1：** Solver schema / 七轴 / API 契约短暂冻结（见 [roadmap.md](roadmap.md)）；runtime 与 solver **不要同时快速改**。

## 1. 产品定位

PlanSeed 是 **local-first、本地运行** 的独栋住宅生成式设计工具。

核心流程：

```text
Natural Language / Manual Input
→ RequirementSpec（后续）
→ ProjectSpec
→ DesignProgram（normalize）
→ FloorAssignment
→ Semantic RoomGraph + TopologyPlan（打包序 / slicing group）
→ AccessIntentGraph（SpaceConnection）
→ ZonePlanner + CorePlacement
→ Graph-aware Room Ordering → Guillotine
→ ConnectionResolver → DoorOpening / RealizedAccessGraph
→ AccessibilityValidator（仅 realized）→ Evaluator → Ranking
→ Interactive Floorplan（SVG）
```

**LLM 不单独充当 parser，也不生成几何。**  
自然语言需求由 **Hybrid Semantic Parser** 解析为 `RequirementSpec`（详见 [hybrid-semantic-parser.md](hybrid-semantic-parser.md)）：

```text
Local LLM + Deterministic Extraction + Vocabulary
  + Semantic Gate + Repair
→ RequirementSpec
→ normalize → DesignProgram → Solver
```

LLM **不得**输出坐标、SVG、DesignProgram 或最终平面。

Phase 2 终态流水线见 [roadmap.md](roadmap.md)。

## 2. 领域术语（已定）

```text
RequirementSpec → normalize → DesignProgram → generate → LayoutCandidate
```

| 模型 | 语义 |
|------|------|
| RequirementSpec | 用户 / LLM 表达的需求 |
| DesignProgram | Normalizer 规范化后的建筑任务 |
| LayoutCandidate | Solver 输出几何 |

`ProjectSpec` 保留为内部过渡模型，不暴露给 LLM 直接输出。

LLM Phase 6 目标：`Natural Language → Hybrid Semantic Parser → RequirementSpec → normalize → Solver`

## 3. 已拍板决策

- **Python 环境**：3.12 + uv；所有命令 `uv run`
- **Implicit constraints**：有限规则集，必须带 `source` / `source_key`
- **Circulation**：系统生成（`source=generated`），用户可约束
- **Setbacks 默认 0**：表示未提供规划信息，非法规结论
- **Finding = design heuristic**：与 **code compliance** 严格分开；无 CodeProfile / Jurisdiction / Rule source 时，禁止「符合规范 / 合法 / 满足消防 / 无障碍」等合规语气
- **版本签名**：`solver_version` / `generator_version` / `evaluation_version`（`packages/schema/identity.py`）；解释历史分数与 regression，≠ `engine_version`
- **静态检查**：ruff clean → mypy 核心 → 逐目录收紧；**不做**全仓 `mypy --strict`
- **CI**：`.github/workflows/ci.yml`（pytest / ruff / mypy / pnpm build / cargo check）；sidecar 打包不进每次 commit
- **FastAPI + Tauri**：四区 Workbench；**当前 Phase 4.3**（受控 Move/Resize + Mutation Authority）
- **路线图**：见 [roadmap.md](roadmap.md) · [phase-4.3-direct-manipulation.md](phase-4.3-direct-manipulation.md)
- **UI 纪律**：不因壳已出现就堆按钮；加深 `Evaluation → Finding → Inspector → Compare`
- **引擎复用**：仅当 `GET /api/health` 返回 `service=planseed` 时 reuse 端口

```text
UI (Tauri + React)
↓
Requirement Parsing (Hybrid：Ollama + enrich + vocab + gate + repair)
↓
Design Program (packages/schema + solver/program)
↓
Constraint System (packages/schema/constraints + solver/constraints)
↓
Topology (packages/schema/topology + solver/topology)
↓
Geometry Solver (solver/geometry)
↓
Candidate Generator (solver/generators)
↓
Evaluator (solver/evaluation)
↓
Ranker (solver/optimization)
↓
Renderer (desktop SVG — 后续)
```

**越层禁止**：Renderer 不修复布局；LLM 不决定坐标；Evaluator 不修改房间；Solver 不读 React state。

## 3. 技术栈（锁定）

| 组件 | 技术 |
|------|------|
| Backend | Python + FastAPI |
| Solver | 纯 Python domain modules |
| Schema | Pydantic v2 |
| LLM | Ollama（structured output） |
| Desktop | Tauri v2 + React + TypeScript |
| Rendering | SVG |
| Persistence | SQLite |
| Python 包管理 | uv |
| 前端包管理 | pnpm |

禁止擅自替换为 Electron、Three.js、Canvas 平面图库、云端 DB、云端 LLM API。

## 4. Local-first 与 Sidecar 打包

### 开发入口（用户不可见 Python / 端口）

```text
pnpm dev                  # 仓库根：自动拉起 backend + Vite UI
pnpm --dir desktop tauri:dev   # Tauri：Rust setup 内 spawn uv run python -m backend
```

等价引擎入口：`uv run python -m backend`（`PLANSEED_HOST` / `PLANSEED_PORT` 可覆写，默认 `127.0.0.1:8787`）。

### Release（锁定：resources + managed process，不回退 externalBin）

```text
scripts/build_backend_sidecar.*  →  PyInstaller --onedir
desktop/src-tauri/resources/planseed-backend/  →  bundle.resources map → planseed-backend/
canonical: {resource_dir}/planseed-backend/planseed-backend(.exe)
  （Windows: resource_dir = exe 所在目录；必须用 map，勿用列表保留 resources/ 前缀）
Tauri Command::new 启动；退出时 kill 子进程
setup 不阻塞；就绪后 emit **engine-status**（health 身份探针；已废弃 engine-ready）
```

验收标准：最终用户路径中不出现 `uvicorn` / `pip` / 手动端口说明；UI 只显示「引擎就绪 / 启动中 / 未就绪」。

**Desktop Alpha 门禁（Phase 3.6 ✅ 已满足）：**  
平台 = **Windows 10/11 x64**；双击启动 → 自动引擎 → Generate → Top5 → 解释 → A/B Compare；用户路径无 uvicorn。  
**不做并行 macOS/Linux packaging。** 当前开发主线：**Phase 4** Workbench。

**Packaging 硬化（Phase 5，Alpha 后）：**

- [ ] Windows 签名 / 分发
- [ ] **收紧 `app.security.csp`**（开发期 `null` 可接受）
- [ ] macOS（再后 Linux）— **仅在 Windows Alpha 跑通后**

本机需 Rust 工具链才能 `tauri:build`；主线脚本：`scripts/build_backend_sidecar.ps1`。

## 5. 目录结构

```text
PlanSeed/
├── packages/schema/       # Schema v2 Pydantic 模型
├── solver/                # 纯 Python 求解引擎
├── backend/               # FastAPI（routes / schemas / services）
├── desktop/               # Tauri v2 + React
│   └── src-tauri/resources/planseed-backend  # onedir sidecar
├── scripts/               # dev-desktop / build_backend_sidecar
├── reference/             # floorplan-generator.html 参考原型
└── docs/                  # 架构文档
```

## 6. 候选流水线（Phase 1 实现）

```text
ProjectSpec
→ normalize()           # solver/program/normalize.py
→ build_constraints()   # implicit + explicit
→ build_room_graph()    # solver/program/normalize.py
→ generate_candidates() # GuillotineGenerator × N seeds
→ validate_candidate()  # ConstraintChecker
→ evaluate_candidate()  # Evaluator
→ rank_candidates()     # solver/optimization/rank.py
→ Top K LayoutCandidate
```

默认参数：

- `candidate_count = 32`
- `return_top_k = 5`

## 7. 确定性与 Seed

所有随机过程必须使用明确 `seed`。相同 `(ProjectSpec, Generator, seed)` 必须产生相同结果。

## 8. LLM 架构（Phase 4 实现）

```text
Natural Language → Ollama → RequirementSpec/ProjectSpec
→ Pydantic model_validate_json()
→ normalize() → Solver
```

- JSON Schema 由 `ProjectSpec.model_json_schema()` 生成，不维护第二份手写 schema
- `temperature = 0`, `stream = false`
- 校验失败最多 3 次 correction retry
- 未知信息保持 `unknown`，不强迫 LLM 猜测（confidence 系统后续实现）

## 9. UI 原则（Desktop Workbench — 结构锁定）

四区工作台是产品基本形态：**加深，不重设计。**

```text
┌ Requirements ┬──────── Floorplan ────────┬ Inspector ┐
│ Site         │                           │ Score     │
│ Program      │        FLOOR PLAN         │ Findings  │
│ Constraints  │                           │ Metrics   │
│ Preferences  │                           │ Rooms     │
└──────────────┴───────────────────────────┴───────────┘
│                   Candidate Strip                    │
└─────────────────────────────────────────────────────┘
```

- 左：需求与 Program（可编辑；含未来 Constraints / Preferences）
- 中：平面图（SVG；交互编辑属 Phase 4 Workbench，仍在中栏）
- 右：评价（七轴 / Findings / Metrics / Rooms）
- 下：候选条（A / B / C…）

启动见仓库根 `pnpm dev`。AI 推断的需求必须可编辑；禁止 black box 直接出图（LLM → Phase 6）。下一产品闭环见 Phase 7 Deliverables / Export。

## 10. 与旧版开发手册的冲突

| 主题 | 旧手册 | v2 架构（本基线） |
|------|--------|-------------------|
| Schema | `Room(id, name, area, type)` | `RoomSpec` + `SiteSpec` + `Constraint` 等 v2 模型 |
| Solver 结构 | `solver/layout.py` + `scoring.py` 单体 | 分层：generators / constraints / evaluation / rank |
| 输出 | 房间带 `rect` 字段 | `RoomSpec` 与 `RoomPlacement` 分离 |
| 方案数 | 单一布局 | 多 candidate + Top K |
| Phase 0 | Step 1 立即移植完整 solver | Phase 0 仅架构 + schema + 接口，solver 在 Phase 1 |

**以 v2 Prompt 为准**；旧手册 Step 1 的测试基准仍作为 Phase 1 GuillotineGenerator 的验收标准。

## 11. RequirementSpec 与 Confidence（后续）

未来 RequirementSpec 字段应区分：

- `explicit` — 用户明确提供
- `inferred` — LLM 推断
- `unknown` — 未提供且不猜测

Phase 0 仅在文档记录，不实现完整 confidence 系统。
