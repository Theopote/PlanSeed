# PlanSeed Windows Alpha smoke — health + generate + compare
# 需本机已有 PlanSeed 引擎在听（桌面端已启动，或手动 uv run）。
# Usage: pwsh scripts/windows_alpha_smoke.ps1

$ErrorActionPreference = "Stop"
$hostName = if ($env:PLANSEED_HOST) { $env:PLANSEED_HOST } else { "127.0.0.1" }
$port = if ($env:PLANSEED_PORT) { $env:PLANSEED_PORT } else { "8787" }
$base = "http://${hostName}:${port}"

Write-Host "== PlanSeed smoke @ $base =="

function Assert-True([bool]$cond, [string]$msg) {
    if (-not $cond) { throw "FAIL: $msg" }
    Write-Host "OK: $msg"
}

$health = Invoke-RestMethod -Uri "$base/api/health" -Method Get
Assert-True ($health.ok -eq $true) "health.ok"
Assert-True ($health.service -eq "planseed") "health.service=planseed"
Assert-True ($health.api_version -eq "1") "health.api_version=1"
Assert-True ([string]::IsNullOrEmpty($health.engine_version) -eq $false) "health.engine_version"

$genBody = @{
    use_benchmark = $true
    candidate_count = 8
    return_top_k = 2
} | ConvertTo-Json
$gen = Invoke-RestMethod -Uri "$base/api/generate" -Method Post -ContentType "application/json" -Body $genBody
Assert-True ($gen.candidates.Count -ge 2) "generate returned >=2 candidates"
Assert-True ($null -ne $gen.candidates[0].design_score) "candidate A has design_score"
Assert-True ($null -ne $gen.candidates[0].provenance) "candidate A has provenance"

$cmpBody = @{
    evaluation_a = $gen.candidates[0].design_score
    evaluation_b = $gen.candidates[1].design_score
    label_a = $gen.candidates[0].label
    label_b = $gen.candidates[1].label
} | ConvertTo-Json -Depth 12
$cmp = Invoke-RestMethod -Uri "$base/api/compare" -Method Post -ContentType "application/json" -Body $cmpBody
Assert-True ($cmp.rows.Count -ge 8) "compare rows"
Assert-True ($cmp.label_a -eq $gen.candidates[0].label) "compare label_a"

Write-Host "== smoke passed =="
