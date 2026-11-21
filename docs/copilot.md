# AI Design Copilot — 数据闭环

> **状态：** 框架已落地 · 真实工作流硬化中（2026-11-21）  
> **总览：** [v0.2-architect-workflow.md](v0.2-architect-workflow.md) · 需求事实源：[adr/003-requirementspec-canonical-source.md](adr/003-requirementspec-canonical-source.md)  
> **原则：** AI understands intent · Solver proves geometry · Architect remains in control

## 能力面（代码入口）

| 能力 | 入口 | 说明 |
|------|------|------|
| NL → IntentPatch | `packages/llm/intent_parser.py` · `POST /api/copilot/intent/parse` | 确定性规则优先；正式入口暂未强制 LLM 草稿 |
| 预览 / 应用 | `solver/intent/apply.py` · `/api/copilot/intent/preview\|apply` | 推导 `RegenerationScope` + 局部 regen |
| Spec 写回 | `solver/intent/spec_sync.py` | IntentPatch 变更镜像到 `RequirementSpec` |
| 拓扑策略 | `solver/topology/strategy.py` · `/api/copilot/strategies` | 内置 3 策略 → RoomGraph（权重进 Solver 仍待加深） |
| 审查 | `solver/critique/critic.py` · `POST /api/copilot/critique` | Gate / `evaluation.findings` / metrics |
| 受控优化 | `solver/optimization/session.py` · `POST /api/copilot/optimize` | 有限轮次；仅 `improved` 时回传 best |
| 对话 | `packages/schema/design_conversation.py` | 进程内会话 + 项目快照持久化 |
| Desktop | `desktop/src/components/CopilotPanel.tsx` | 工作台面板 |

**尚未等同于成熟 LLM 自主建筑设计。** 意图解析当前以确定性规则为主；Ollama 住宅需求解析仍走既有 `/api/requirements/parse`。

## 候选传输契约（P0）

桌面 `CandidatePayload` 与 Solver `LayoutCandidate` **形状不同**：

| 字段语义 | CandidatePayload（API/桌面） | LayoutCandidate（Solver） |
|----------|------------------------------|---------------------------|
| 房间几何 | 扁平 `placements[]` | `floors[].placements` |
| 评价 | `design_score` | `evaluation` |

Copilot 的 critique / optimize **不得**直接 `LayoutCandidate.model_validate(payload)`（会静默得到空 `floors`）。

权威重建：`backend/services/candidate_rebuild.py` → `layout_candidate_from_copilot_payload`。

- 有 `placements` → 按 `floor_id` 重建楼层  
- `design_score` → `evaluation`  
- 无有效几何 → **422**（禁止 Pydantic 默认空列表悄悄通过）

改 FastAPI / Pydantic 后须同步 OpenAPI：

```bash
uv run python scripts/export_openapi.py
pnpm --dir desktop generate:api
```

## IntentPatch → RequirementSpec（P0）

`apply_intent_patch` 会改 `DesignProgram`（如主卧 `target_area`），但 **RequirementSpec 才是需求事实源**（ADR-003）。

`POST /api/copilot/intent/apply` 必须：

1. 对 Program 应用补丁并局部 regen  
2. 经 `sync_requirement_spec_after_intent` 写回 Spec（面积 / 朝向 / relation / 走廊偏好）  
3. 在 `GenerateResponse.requirement_spec` 返回更新后的 Spec  

Desktop `onMergeGenerate` 会把该 Spec 写入会话；下次整栋生成不得回退到旧面积。

## DesignConversation 持久化（P0）

| 层 | 行为 |
|----|------|
| 进程内 | `_CONVERSATIONS`（`/api/copilot/conversation/*`） |
| 项目快照 | `ProjectPayload.design_conversation` |
| 未保存项目 | 会话键 `draft`；首次 Save 一并写入并回灌到真实 `project_id` |

关闭 / 重启 / 重新打开后，对话须能从 payload 恢复。

## 优化与 Critic 纪律

- Critic 读 `candidate.evaluation.findings`（不是不存在的 `candidate.findings`）  
- 排序与「是否改善」共用 `candidate_quality_key`：**Gate 优先** → `private_through` → `-score`  
- `optimize` 响应含 `improved`；仅真正出现新候选几何时返回 `best`，前端才追加  

## 验收场景（推荐）

```text
NL「两层、四卧、客厅朝南」→ 生成 A → 选中 A
→ Copilot「保持客厅和厨房，主卧增大」→ 预览锁定范围
→ 确认局部 regen → A1 → 审查 → 受控优化
→ 保存 → 重启 → 打开
→ 校验：RequirementSpec、对话、方案血缘、几何、评价一致
```

测试须覆盖桌面实际发送的 `CandidatePayload`，不能只手工构造完整 `LayoutCandidate`。

## 关系意图编译（P0）

`RequirementSpec.relation_intents` 经 `solver/program/relation_compiler.py` 在 normalize 时编译为：

| kind | 编译目标 |
|------|----------|
| adjacency / near | `AdjacencyConstraint` |
| separation | `SeparationConstraint` |
| access | `AccessGraph` + `SpaceConnection(DOOR)` |
| open_connection | `AccessGraph` + `SpaceConnection(OPEN)` |

保存后再次 Generate，邻接/分离/通行不得静默丢失。

## 候选需求版本（P0）

`CandidatePayload.requirement_revision_id` = `requirement_revision_id(RequirementSpec)` 短指纹。  
比较面板在两侧指纹不同时提示「分数不可直接当作同一基准比较」。

## 策略权重（P1）

`apply_topology_strategy` 将 `objective_weights` / `corridor_penalty` 写入 `SolverConfig`；  
`run_pipeline` 经 `evaluator_for_program` 使用调整后的 `ScoreWeights`。

## layout_snapshot（可信几何）

`serialize_candidate` 写入 `CandidatePayload.layout_snapshot`（floors / doors / entry / wet_stacks / …）。  
`layout_candidate_from_copilot_payload` 重建优先级：顶层 `floors` → `layout_snapshot` → 扁平 `placements`（有损回退）。

`POST /api/copilot/optimize` 可传 `project_id` + `candidate_id` 从项目快照取候选（找不到则回退请求体）。

## 走廊面积目标

`circulation_area_ratio` 写入 metrics；`corridor_penalty>1` 且交通面积比 >12% 时，circulation 轴额外扣分。

## 已知缺口（勿标完成）

- 意图解析正式入口尚未完整接入 Ollama 草稿  
- Design Benchmark v2 人工 ab_rate 待几何改动后重评  
