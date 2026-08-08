# PlanSeed 架构文档

> Phase 0 基线 — 以 Architecture Foundation & MVP v2 为准。

## 1. 产品定位

PlanSeed 是 **local-first、本地运行** 的独栋住宅生成式设计工具。

核心流程：

```text
Natural Language / Manual Input
→ RequirementSpec（后续）
→ ProjectSpec
→ DesignProgram（normalize）
→ ConstraintGraph + RoomGraph
→ TopologyPlan（生成前；影响打包序）
→ Candidate Generation
→ Constraint Validation
→ Multi-objective Evaluation
→ Ranking
→ Interactive Floorplan（SVG）
```

**LLM 只负责理解自然语言**，不得生成坐标、SVG 或最终平面。

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

LLM Phase 4 目标：`Natural Language → RequirementSpec → normalize → Solver`

## 3. 已拍板决策

- **Python 环境**：3.12 + uv；所有命令 `uv run`
- **Implicit constraints**：有限规则集，必须带 `source` / `source_key`
- **Circulation**：系统生成（`source=generated`），用户可约束
- **Setbacks 默认 0**：表示未提供规划信息，非法规结论
- **FastAPI + Tauri**：延后至 Phase 5/7；当前焦点 Phase 1.5 Solver Reliability
- **路线图**：见 [roadmap.md](roadmap.md)

```text
UI (Tauri + React)
↓
Requirement Parsing (FastAPI + Ollama)
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

MVP 开发阶段：

```text
uv run uvicorn backend.main:app
```

Release 架构预留：

```text
FastAPI backend → self-contained executable → Tauri sidecar
```

最终用户不应需要手动 `pip install` / `uvicorn` / Python 环境。Phase 0 不实现打包，仅在此文档记录意图。

## 5. 目录结构

```text
PlanSeed/
├── packages/schema/       # Schema v2 Pydantic 模型
├── solver/                # 纯 Python 求解引擎
├── backend/               # FastAPI（Phase 2+）
├── desktop/               # Tauri + React（Phase 3+）
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

## 9. UI 原则（Phase 3+）

```text
Left: Requirements / Program
Center: Floorplan
Right: Inspector / Evaluation
Bottom: Candidate Strip (A 91, B 89, ...)
```

AI 推断的 ProjectSpec 必须可编辑；禁止 black box 直接出图。

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
