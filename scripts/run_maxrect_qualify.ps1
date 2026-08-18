# MaxRect Layout Benchmark Suite v1 — qualification 跑法
# 用法:
#   .\scripts\run_maxrect_qualify.ps1
#   .\scripts\run_maxrect_qualify.ps1 -Count 64
#   .\scripts\run_maxrect_qualify.ps1 -QualifyOnly docs\baselines\layout_benchmark_suite_v1_n32.json

param(
    [int] $Count = 32,
    [string] $Out = "docs/baselines/layout_benchmark_suite_v1_n32.json",
    [string] $QualifyOnly = ""
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

if ($QualifyOnly) {
    uv run python -m solver.benchmark --qualify-only $QualifyOnly
    exit $LASTEXITCODE
}

uv run python -m solver.benchmark --suite v1 --count $Count --qualify --out $Out
exit $LASTEXITCODE
