# Create PlanSeed v0.2 GitHub Issues
#
# Prerequisites:
#   gh auth refresh -h github.com
#   gh auth status
#
# Usage:
#   .\scripts\create_v02_issues.ps1
#   .\scripts\create_v02_issues.ps1 -DryRun
#
# Creates milestone "v0.2 - Architect Workflow" and 18 tracking issues.

param(
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$MilestoneTitle = "v0.2 - Architect Workflow"

function Invoke-GhCommand {
    param([string[]]$GhArgs)
    if ($DryRun) {
        Write-Host "[dry-run] gh $($GhArgs -join ' ')" -ForegroundColor DarkGray
        return $null
    }
    $output = & gh @GhArgs 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "gh failed (exit $LASTEXITCODE): $($GhArgs -join ' ') :: $output"
    }
    return $output
}

function Ensure-Label {
    param([string]$Name, [string]$Color, [string]$Description)
    $labels = gh label list --json name --jq ".[].name" 2>$null
    if ($labels -notcontains $Name) {
        Invoke-GhCommand @("label", "create", $Name, "--color", $Color, "--description", $Description) | Out-Null
        Write-Host "Created label: $Name"
    }
}

function Ensure-Milestone {
    param([string]$Title, [string]$Description)
    $json = gh api "repos/{owner}/{repo}/milestones" 2>$null | ConvertFrom-Json
    $found = $json | Where-Object { $_.title -eq $Title } | Select-Object -First 1
    if ($found) {
        Write-Host "Milestone exists: $Title (#$($found.number))"
        return [int]$found.number
    }
    $result = gh api "repos/{owner}/{repo}/milestones" -f title=$Title -f description=$Description -f state=open --jq .number
    Write-Host "Created milestone: $Title (#$result)"
    return [int]$result
}

function New-Issue {
    param(
        [string]$Title,
        [string]$Body,
        [string[]]$Labels,
        [int]$MilestoneNumber
    )
    $titles = gh issue list --milestone $MilestoneTitle --state all --json title --jq ".[].title" 2>$null
    if ($titles -contains $Title) {
        Write-Host "Skip (exists): $Title" -ForegroundColor Yellow
        return
    }
    $bodyFile = New-TemporaryFile
    try {
        Set-Content -Path $bodyFile -Value $Body -Encoding UTF8
        $ghArgs = @("issue", "create", "--title", $Title, "--body-file", $bodyFile.FullName, "--milestone", $MilestoneTitle)
        foreach ($l in $Labels) { $ghArgs += @("--label", $l) }
        $result = Invoke-GhCommand $ghArgs
        Write-Host "Created: $result" -ForegroundColor Green
    }
    finally {
        Remove-Item -Force $bodyFile -ErrorAction SilentlyContinue
    }
}

Write-Host "=== PlanSeed v0.2 Issue Bootstrap ===" -ForegroundColor Cyan

if (-not $DryRun) {
    gh auth status 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Error "gh not authenticated. Run: gh auth refresh -h github.com"
    }
}

# Labels
Ensure-Label "v0.2" "1D76DB" "PlanSeed v0.2 Architect Workflow"
Ensure-Label "P0" "B60205" "Must-have for v0.2"
Ensure-Label "P1" "D93F0B" "Important, after P0"
Ensure-Label "P2" "FBCA04" "Later in v0.2"
Ensure-Label "benchmark" "0E8A16" "Design Benchmark v2"
Ensure-Label "product" "5319E7" "Product / UX capability"

$milestoneNum = Ensure-Milestone $MilestoneTitle @"
PlanSeed v0.2 - Architect Workflow

目标：从生成器升级为建筑师可持续参与的设计工作台。

执行顺序：
0.2-A Benchmark → 0.2-B Partial Regen → 0.2-C Topology → 0.2-E Revision → 0.2-F Intent → 0.2-G Copilot → 0.2-H CAD

文档：docs/v0.2-architect-workflow.md
"@

$issues = @(
    @{
        Title = "v0.2-A: Design Benchmark v2 - Specification & Case Catalog"
        Labels = @("v0.2", "P0", "benchmark")
        Body = @"
## Summary
Design Benchmark v2 规格与 B01–B20 案例定义。

## Deliverables
- [x] ``docs/design-benchmark-v2.md`` - 20 cases、11 评价维度、A/B/C/D rubric
- [ ] 评审者 D 级 checklist 首跑校准

## Acceptance
- 20 cases 均有 site/program/constraints/design intent/D-grade 定义
- 与 Suite v1 关系明确（qual vs acceptance）
- 主指标 ``ab_rate`` 定义清晰

## Docs
- [design-benchmark-v2.md](https://github.com/Theopote/PlanSeed/blob/main/docs/design-benchmark-v2.md)
- [v0.2-architect-workflow.md](https://github.com/Theopote/PlanSeed/blob/main/docs/v0.2-architect-workflow.md)

## Blocks
无（可立即开始 harness）

## Blocked by
无
"@
    }
    @{
        Title = "v0.2-A: Design Benchmark v2 - Harness & Grade Collection"
        Labels = @("v0.2", "P0", "benchmark")
        Body = @"
## Summary
实现 ``--suite design-v2`` benchmark harness 与人工评级汇总。

## Deliverables
- [ ] ``solver/fixtures/design_suite_v2.py`` - B01–B20 builders（Wave 1: Core B01–B07）
- [ ] ``solver/benchmark/design_acceptance.py`` - ``ab_rate`` 计算
- [ ] CLI: ``--suite design-v2 --export-svg`` / ``--merge-grades``
- [ ] ``grades.json`` 格式与首跑 baseline

## Acceptance
- ``uv run python -m solver.benchmark --suite design-v2 --cases B01 --count 8`` 可运行
- 输出 SVG + DesignScore + findings 摘要
- ``--merge-grades`` 产出 per-case ``ab_rate``

## Blocks
v0.2-B Partial Regen 基线测量

## Blocked by
#1 Specification（已完成 spec 文档）
"@
    }
    @{
        Title = "v0.2-A: Real User Testing Protocol"
        Labels = @("v0.2", "P0", "product")
        Body = @"
## Summary
建立真实建筑师用户测试协议，驱动 benchmark 校准与产品优先级。

## Deliverables
- [ ] 测试脚本（任务场景 × 5–8 个）
- [ ] 观察记录模板（ friction / failure pattern / quote）
- [ ] 与 Design Benchmark v2 评级流程对齐

## Acceptance
- ≥1 轮真实用户测试完成
- 发现录入 GitHub issues
- 至少 3 条 failure pattern 反馈到 benchmark case 或 solver

## Blocks
无（可与 harness 并行）

## Blocked by
无
"@
    }
    @{
        Title = "v0.2-A: Constraint / Intent Inspector Enhancement"
        Labels = @("v0.2", "P0", "product")
        Body = @"
## Summary
让建筑师理解「为什么这样生成」— 增强 Inspector 对约束来源与 DesignFinding 的解释。

## Deliverables
- [ ] Inspector 显示 constraint ``source`` / ``source_key``
- [ ] Finding → recommended action 可点击触发（预留 partial regen 入口）
- [ ] Topology / adjacency intent 可视化（只读先行）

## Acceptance
- 选中房间可看到影响它的 constraints 与 findings
- 不新增评分逻辑（消费冻结七轴）

## Blocks
v0.2-F Intent Patch UX

## Blocked by
无（可与 benchmark 并行）
"@
    }
    @{
        Title = "v0.2-B: RegenerationScope Schema"
        Labels = @("v0.2", "P0")
        Body = @"
## Summary
定义局部重生成作用域 schema，替代隐式整层重跑。

## Deliverables
- [ ] ``packages/schema/regeneration.py`` - ``RegenerationScope`` model
- [ ] API schema 扩展（``GenerateRequest`` / ``RegenerateRequest``）
- [ ] 文档：与 ``LayoutLocks`` 的关系

```python
RegenerationScope(
    mutable_rooms=[...],
    locked_rooms=[...],
    affected_neighbors=[...],
    preserve_topology=True,
    preserve_floor_assignment=True,
)
```

## Acceptance
- Schema 有 pydantic 校验与单元测试
- 与现有 ``LayoutLocks`` 向后兼容

## Blocks
#6 Partial Regen API, #7 Partial Regen UX

## Blocked by
#2 Benchmark harness（建议有 ab_rate 基线后实现）
"@
    }
    @{
        Title = "v0.2-B: Partial Regeneration API & Solver Entry"
        Labels = @("v0.2", "P0")
        Body = @"
## Summary
实现区域级局部重生成 solver 入口与 API。

## Deliverables
- [ ] Solver: ``GuillotineGenerator.generate_partial(scope)`` 或等价入口
- [ ] ``affected_neighbors`` 自动推导
- [ ] ``POST /generate`` 或 ``POST /regenerate/partial`` API
- [ ] 确定性：相同 scope + seed → 相同结果

## Acceptance
- Lock 房间几何不变
- mutable 房间重排，neighbors 可受影响
- ``preserve_topology=true`` 时不破坏 TopologyPlan 硬约束

## Blocks
#7 UX

## Blocked by
#5 RegenerationScope Schema
"@
    }
    @{
        Title = "v0.2-B: Partial Regeneration UX - Room Selection & Lock/Regen"
        Labels = @("v0.2", "P0", "product")
        Body = @"
## Summary
建筑师点选房间 → Lock / Resize preference / Regenerate surrounding。

## Deliverables
- [ ] 房间选中上下文菜单：Lock · Regenerate surrounding · More south · Closer to X
- [ ] 与 ``RegenerationScope`` 映射
- [ ] Revision 记录（mutation type: partial_regen）

## Acceptance
- 从 B 级方案出发，partial regen 后 ab_rate 可测量提升
- 不重生成整栋住宅

## Blocks
v0.2-E Revision Tree（记录 regen 节点）

## Blocked by
#6 Partial Regen API
"@
    }
    @{
        Title = "v0.2-C: Topology Workbench - Schema & API"
        Labels = @("v0.2", "P1")
        Body = @"
## Summary
用户可编辑 ``RoomGraph`` / adjacency / zone，持久化到 ``ProjectSpec``。

## Deliverables
- [ ] API: topology CRUD（nodes, edges, must-connect, avoid, zones）
- [ ] ``TopologyPlan`` 从用户 graph 重建（非仅 derive）
- [ ] Lock topology → regen geometry 工作流

## Acceptance
- 编辑 adjacency 后 regenerate 反映新拓扑
- 确定性：相同 graph + seed → 相同结果

## Blocks
#9 Topology UI

## Blocked by
#7 Partial Regen UX（建议先验证 lock+regen 循环）
"@
    }
    @{
        Title = "v0.2-C: Topology Workbench - Bubble Diagram UI"
        Labels = @("v0.2", "P1", "product")
        Body = @"
## Summary
Bubble / topology graph 可视化编辑面板。

## Deliverables
- [ ] 节点 = 房间/zone；边 = adjacency / must-connect / avoid
- [ ] Public / Private / Service zone 着色
- [ ] 楼层切换与锁定

## Acceptance
- 建筑师可完成 B14（开放餐厨）拓扑编辑并 regen
- 不直接拖房间坐标（那是 mutation 层）

## Blocked by
#8 Topology API
"@
    }
    @{
        Title = "v0.2-D: Site Editor 2.0 - Polygon Draw & Edit"
        Labels = @("v0.2", "P1", "product")
        Body = @"
## Summary
场地编辑器：矩形 / 多边形 / L shape / 拖点编辑。

## Deliverables
- [ ] Site Editor 组件（Desktop）
- [ ] 预设：矩形 · L · 阶梯形
- [ ] ``site_polygon`` 持久化到 ProjectSpec
- [ ] buildable polygon 实时预览

## Acceptance
- B09 L 型场地可通过 UI 创建并 generate
- 复用 8.4.1 Shapely pipeline（experimental flag）

## Blocked by
无（backend 已有）
"@
    }
    @{
        Title = "v0.2-D: Site Editor 2.0 - Setbacks, North, Road, Entrance"
        Labels = @("v0.2", "P1", "product")
        Body = @"
## Summary
场地语义编辑：退界 · 北向 · 道路方向 · 入口位置 · 景观/噪声方向。

## Deliverables
- [ ] Setback 四向输入 + buildable 预览
- [ ] North angle 指示器
- [ ] Road edges / entrance edge 选择
- [ ] Site relationship 评分在 Inspector 展示

## Acceptance
- B12 高退界 case 可通过 UI 配置
- B10 转角地块道路双面临街可配置

## Blocked by
#10 Polygon Editor（可部分并行）
"@
    }
    @{
        Title = "v0.2-E: Revision Tree - Data Model"
        Labels = @("v0.2", "P1")
        Body = @"
## Summary
统一 variant lineage + edit revision 为树形 ``DesignRevision`` 模型。

## Deliverables
- [ ] ``DesignRevision`` schema: parent, mutation, locks, solver_identity, evaluation, timestamp
- [ ] SQLite 持久化树结构
- [ ] 与 flat ``variant_parent_id`` 迁移/兼容

## Acceptance
- A → A1 → A1a 分支可存储与查询
- 每节点保留 lock snapshot + provenance

## Blocks
#12 Revision Tree UI

## Blocked by
#7 Partial Regen UX（产生 revision 节点）
"@
    }
    @{
        Title = "v0.2-E: Revision Tree - UI Panel"
        Labels = @("v0.2", "P1", "product")
        Body = @"
## Summary
方案谱系树形导航：选择 · 比较 · 分支。

## Deliverables
- [ ] Revision Tree 面板（替代/补充 flat CandidateStrip）
- [ ] 节点预览 + 跳转到 compare
- [ ] 分支命名（A, A1, A1a）

## Acceptance
- 完整走通：Generate → Modify → Partial Regen → 新分支 → Compare

## Blocked by
#11 Revision Data Model
"@
    }
    @{
        Title = "v0.2-F: DesignIntentPatch Schema"
        Labels = @("v0.2", "P2")
        Body = @"
## Summary
结构化设计意图补丁 schema - AI 与用户的共同输出格式。

## Deliverables
- [ ] ``DesignIntentPatch`` pydantic model
- [ ] 映射到 ``Constraint`` / objective weight 增量
- [ ] 文档与示例（privacy, adjacency, zone compactness）

```json
{
  "privacy": {"master": "increase"},
  "adjacency": [{"a": "kitchen", "b": "garden", "preference": "visual_connection"}],
  "zone": {"bedrooms": "more_compact"}
}
```

## Acceptance
- Patch 可 apply 到现有 DesignProgram 不重写全文
- 确定性 apply + validate

## Blocks
#14 Intent Pipeline, #15 Copilot

## Blocked by
#8 Topology API, #6 Partial Regen API
"@
    }
    @{
        Title = "v0.2-F: Intent Patch -> Constraint/Objective Pipeline"
        Labels = @("v0.2", "P2")
        Body = @"
## Summary
``DesignIntentPatch`` 到 solver 可执行约束/目标的确定性管线。

## Deliverables
- [ ] ``apply_intent_patch(program, patch) -> DesignProgram``
- [ ] source/source_key 追踪
- [ ] Gate: patch 不得破坏已有 hard constraints

## Acceptance
- 示例 patch 触发 partial regen 后 privacy score 可测量变化
- 无 LLM 依赖（可用 fixture patch 测试）

## Blocked by
#13 DesignIntentPatch Schema
"@
    }
    @{
        Title = "v0.2-G: Local AI Design Copilot"
        Labels = @("v0.2", "P2", "product")
        Body = @"
## Summary
本地 LLM 设计助手：自然语言 → ``DesignIntentPatch`` → Solver。

## Non-goals
- 不直接输出坐标
- 不重写完整 RequirementSpec（Parser 已冻结）

## Deliverables
- [ ] Copilot panel（Desktop）
- [ ] NL → IntentPatch（Local LLM）
- [ ] 与 Partial Regen / Topology 联动

## Acceptance
- 「主卧更私密，厨房看庭院」→ patch → regen → 可比较
- 使用现有 Hybrid Parser 基础设施，不新开 parser phase

## Blocked by
#14 Intent Pipeline, #7 Partial Regen UX
"@
    }
    @{
        Title = "v0.2-H: CAD / DXF Interoperability"
        Labels = @("v0.2", "P2", "product")
        Body = @"
## Summary
DXF/CAD 导入导出，进入建筑师现有工作流。

## Deliverables
- [ ] DXF export（房间轮廓 + 标注）
- [ ] Site boundary import（DXF/JSON）
- [ ] 文档：坐标系与精度约定

## Acceptance
- 导出 DXF 可在 AutoCAD / LibreCAD 打开
- Site import 可驱动 B09–B12 benchmark cases

## Blocked by
#10 Site Editor, #12 Revision Tree（导出特定 revision）

## Note
优先级 P2；不阻塞 v0.2 核心循环
"@
    }
    @{
        Title = "v0.2: Update Roadmap & Close Post-v0.1 Planning"
        Labels = @("v0.2", "P0")
        Body = @"
## Summary
将 v0.2 里程碑写入主路线图，关闭 Post-v0.1 观察窗口。

## Deliverables
- [x] ``docs/v0.2-architect-workflow.md``
- [x] ``docs/design-benchmark-v2.md``
- [x] ``docs/roadmap.md`` 更新当前阶段
- [ ] README Next 段落更新

## Acceptance
- Roadmap 当前阶段 = v0.2 Architect Workflow
- GitHub milestone + issues 可追踪

## Blocked by
无
"@
    }
)

foreach ($issue in $issues) {
    New-Issue -Title $issue.Title -Body $issue.Body -Labels $issue.Labels -MilestoneNumber $milestoneNum
}

Write-Host ""
Write-Host "=== Done ===" -ForegroundColor Cyan
Write-Host "View issues: gh issue list --milestone `"$MilestoneTitle`""
