# 启动 Desktop 手测会话：B1 半自动 + 种子项目 + Print 素材 + Gate C 包校验
# Usage: powershell -File scripts/start_desktop_hand_session.ps1
#
# 结束后 Desktop 保持运行；按 docs/alpha-v0.1-desktop-hand-gate.md 完成 UI 勾选。

param(
    [int]$Port = 8796,
    [string]$InstallDir = ""
)

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\_release_path.ps1"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "== Start Desktop hand-test session =="

$env:PLANSEED_HOST = "127.0.0.1"
$env:PLANSEED_PORT = "$Port"

if ($InstallDir) {
    & "$PSScriptRoot\desktop_shell_smoke.ps1" -Port $Port -InstallDir $InstallDir
} else {
    & "$PSScriptRoot\desktop_shell_smoke.ps1" -Port $Port
}
if ($LASTEXITCODE -ne 0) { throw "desktop_shell_smoke failed" }

Write-Host ""
Write-Host "-- prepare hand-gate assets on port $Port --"
uv run python scripts/prepare_desktop_hand_gate.py
if ($LASTEXITCODE -ne 0) { throw "prepare_desktop_hand_gate failed" }

uv run python scripts/generate_print_smoke_reports.py --seed-desktop
if ($LASTEXITCODE -ne 0) { throw "seed-desktop failed" }

uv run python scripts/validate_hand_gate_fixture.py
if ($LASTEXITCODE -ne 0) { throw "validate_hand_gate_fixture failed" }

$portFile = Join-Path $Root "debug\desktop-hand-gate\engine_port.txt"
Set-Content -Path $portFile -Value $Port -Encoding ascii

Write-Host ""
Write-Host "== session ready (engine http://127.0.0.1:$Port) =="
Write-Host ""
Write-Host "UI checklist (docs/alpha-v0.1-desktop-hand-gate.md):"
Write-Host "  B1) Left panel READY + Retry Engine"
Write-Host "  A)  Open... -> PrintHand-P02 / P06 -> Export -> Report Preview -> Print to PDF"
Write-Host "  C)  Import package -> debug/desktop-hand-gate/alpha-v0.1-hand-gate.planseed"
Write-Host "      -> verify provenance -> Export report/PNG/SVG"
Write-Host ""
Write-Host "Edge reference (optional):"
powershell -File scripts/open_print_smoke.ps1
