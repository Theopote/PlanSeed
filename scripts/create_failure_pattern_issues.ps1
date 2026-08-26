# Design Benchmark v2 首评 — Failure Pattern Issues
# Usage: .\scripts\create_failure_pattern_issues.ps1

param([switch]$DryRun)

$ErrorActionPreference = "Stop"
$MilestoneTitle = "v0.2 - Architect Workflow"

function Invoke-GhCommand {
    param([string[]]$GhArgs)
    if ($DryRun) {
        Write-Host "[dry-run] gh $($GhArgs -join ' ')" -ForegroundColor DarkGray
        return
    }
    & gh @GhArgs
    if ($LASTEXITCODE -ne 0) { throw "gh failed" }
}

function New-Issue {
    param([string]$Title, [string]$Body, [string[]]$Labels)
    $titles = gh issue list --milestone $MilestoneTitle --state all --json title --jq ".[].title" 2>$null
    if ($titles -contains $Title) {
        Write-Host "Skip: $Title" -ForegroundColor Yellow
        return
    }
    $bodyFile = New-TemporaryFile
    try {
        Set-Content -Path $bodyFile -Value $Body -Encoding UTF8
        $args = @("issue", "create", "--title", $Title, "--body-file", $bodyFile.FullName, "--milestone", $MilestoneTitle)
        foreach ($l in $Labels) { $args += @("--label", $l) }
        Invoke-GhCommand $args
        Write-Host "Created: $Title" -ForegroundColor Green
    } finally {
        Remove-Item -Force $bodyFile -ErrorAction SilentlyContinue
    }
}

$issues = @(
    @{
        Title = "P0: Entry-Foyer-Stair circulation logic (B04 benchmark)"
        Labels = @("v0.2", "P0")
        Body = @"
## Source
Design Benchmark v2 human review (Theopote, 2026-08-26) — B04 ab_rate 3.1%

## Problem
入口未先进门厅再进楼梯；门厅与楼梯/走廊断裂；车库间多余走廊。

## Acceptance
- B04 valid candidate 中 ≥1 达到 B 级（建筑师评审）
- Entry → Foyer → Stair 可达链在 RealizedAccessGraph 可验证

## Related
- #6 Partial Regeneration API
- docs/baselines/design-benchmark-v2.md
"@
    }
    @{
        Title = "P0: Room chaining / no exit (B06, B12 benchmark)"
        Labels = @("v0.2", "P0")
        Body = @"
## Source
Design Benchmark v2 — B06 ab_rate 6.2%, B12 ab_rate 0%

## Problem
次卧无出口；湿区串联（客卫穿主卧/厨房）；楼梯未连接公共走廊。

## Acceptance
- ``private_through`` / ``unreachable_room`` finding 与建筑师 D 级高度相关
- B06 至少 1 个 valid candidate 达 B 级
"@
    }
    @{
        Title = "P0: Guest bath orientation — face public zone not master (B12)"
        Labels = @("v0.2", "P0")
        Body = @"
## Source
Design Benchmark v2 — B12 全部 26 valid 无 A/B

## Problem
客卫门开向主卧/厨房而非客厅公区；厨房未与客厅相连。

## Acceptance
- 公卫 adjacency preference 进入 TopologyPlan / soft constraint
- B12 ab_rate > 0
"@
    }
    @{
        Title = "P1: Interior bathroom — no exterior wall (B01)"
        Labels = @("v0.2", "P1")
        Body = @"
## Source
Design Benchmark v2 — B01 多个 C 级「黑卫生间」

## Problem
卫生间落在平面中部，无外墙，通风采光潜力差。

## Acceptance
- Environment evaluator 对 wet room 无外墙发出 warning
- 生成器倾向将卫生间贴外墙或湿区堆叠
"@
    }
    @{
        Title = "P2: Door swing SVG rendering incorrect (review noise)"
        Labels = @("v0.2", "P2", "product")
        Body = @"
## Source
Design Benchmark v2 notes — B01/B04 多次提及「门图示画错」

## Problem
SVG 门扇方向/位置错误，干扰建筑师评审，可能误判 solver。

## Acceptance
- 卧室门、卫生间门 SVG 与共边/opening 数据一致
- 评审包 REVIEW.md 中标注 renderer 已知问题直至修复
"@
    }
)

if (-not $DryRun) {
    $env:HTTP_PROXY = ''
    $env:HTTPS_PROXY = ''
    $env:ALL_PROXY = ''
}

foreach ($i in $issues) {
    New-Issue -Title $i.Title -Body $i.Body -Labels $i.Labels
}

Write-Host "Done."
