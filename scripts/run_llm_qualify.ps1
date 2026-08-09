# Phase 6.7 — 真模型 Qualification（Windows）
# 前置：本机已装 Ollama，且已显式安装模型（不会自动 pull）
#
#   ollama pull qwen2.5:7b
#   .\scripts\run_llm_qualify.ps1
#   .\scripts\run_llm_qualify.ps1 -Gate
#   .\scripts\run_llm_qualify.ps1 -Models "qwen2.5:7b,qwen2.5:14b"

param(
    [string]$Model = "qwen2.5:7b",
    [string]$Models = "",
    [int]$Limit = 0,
    [switch]$Gate,
    [string]$BaseUrl = "http://127.0.0.1:11434"
)

$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

Write-Host "PlanSeed LLM Qualify" -ForegroundColor Cyan
Write-Host "  base_url=$BaseUrl"

try {
    $tags = Invoke-RestMethod -Uri "$BaseUrl/api/tags" -TimeoutSec 5
} catch {
    Write-Host "FAIL: 无法连接 Ollama（$BaseUrl）。请先启动 Ollama。" -ForegroundColor Red
    exit 2
}

$installed = @($tags.models | ForEach-Object { $_.name })
Write-Host ("  installed=[{0}]" -f ($installed -join ", "))

$targets = if ($Models) {
    @($Models.Split(",") | ForEach-Object { $_.Trim() } | Where-Object { $_ })
} else {
    @($Model)
}

foreach ($m in $targets) {
    $hit = $installed | Where-Object {
        $_ -eq $m -or ($_ -eq "$m`:latest") -or ($m -notmatch ":" -and $_ -like "$m`:*")
    }
    if (-not $hit) {
        Write-Host "FAIL: 未检测到 $m。请先执行: ollama pull $m" -ForegroundColor Red
        Write-Host "（PlanSeed 不会自动下载模型。）" -ForegroundColor Yellow
        exit 3
    }
}

$env:PLANSEED_LLM_PROVIDER = "ollama"
$env:PLANSEED_OLLAMA_BASE_URL = $BaseUrl
if (-not $Models) {
    $env:PLANSEED_OLLAMA_MODEL = $Model
}

$args = @("-m", "packages.llm.benchmark.qualify")
if ($Models) { $args += @("--models", $Models) }
elseif ($Model) { $args += @("--model", $Model) }
if ($Limit -gt 0) { $args += @("--limit", "$Limit") }
if ($Gate) { $args += "--gate" }

Write-Host ("  uv run python {0}" -f ($args -join " "))
uv run python @args
exit $LASTEXITCODE
