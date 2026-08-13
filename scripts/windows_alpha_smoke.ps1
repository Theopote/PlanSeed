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

function Invoke-PlanSeedJsonPost([string]$Uri, [object]$BodyObj) {
    # PowerShell 默认 JSON 编码易导致 /api/compare 等嵌套体解析失败；强制 UTF-8 + 足够深度。
    $json = $BodyObj | ConvertTo-Json -Depth 25 -Compress
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($json)
    return Invoke-RestMethod -Uri $Uri -Method Post -ContentType "application/json; charset=utf-8" -Body $bytes
}

$health = Invoke-RestMethod -Uri "$base/api/health" -Method Get
Assert-True ($health.ok -eq $true) "health.ok"
Assert-True ($health.service -eq "planseed") "health.service=planseed"
Assert-True ($health.api_version -eq "1") "health.api_version=1"
Assert-True ([string]::IsNullOrEmpty($health.engine_version) -eq $false) "health.engine_version"

$gen = Invoke-PlanSeedJsonPost -Uri "$base/api/generate" -BodyObj @{
    use_benchmark = $true
    candidate_count = 8
    return_top_k = 2
}
Assert-True ($gen.candidates.Count -ge 2) "generate returned >=2 candidates"
Assert-True ($null -ne $gen.candidates[0].design_score) "candidate A has design_score"
Assert-True ($null -ne $gen.candidates[0].provenance) "candidate A has provenance"

$cmp = Invoke-PlanSeedJsonPost -Uri "$base/api/compare" -BodyObj @{
    evaluation_a = $gen.candidates[0].design_score
    evaluation_b = $gen.candidates[1].design_score
    label_a = $gen.candidates[0].label
    label_b = $gen.candidates[1].label
}
Assert-True ($cmp.rows.Count -ge 8) "compare rows"
Assert-True ($cmp.label_a -eq $gen.candidates[0].label) "compare label_a"

Write-Host "== smoke passed =="
