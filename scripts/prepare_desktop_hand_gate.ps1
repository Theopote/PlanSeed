# Desktop Release Gate 手测准备（样本包 + 打开安装器/Print 素材）
# Usage: powershell -File scripts/prepare_desktop_hand_gate.ps1

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\_release_path.ps1"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "== Prepare Desktop Hand Gate assets =="

uv run python scripts/prepare_desktop_hand_gate.py
if ($LASTEXITCODE -ne 0) { throw "prepare_desktop_hand_gate.py failed" }

Write-Host "-- seed Print hand-test projects (P02 + P06) --"
uv run python scripts/generate_print_smoke_reports.py --seed-desktop
if ($LASTEXITCODE -ne 0) { throw "generate_print_smoke_reports --seed-desktop failed" }

$pkg = Join-Path $Root "debug\desktop-hand-gate\alpha-v0.1-hand-gate.planseed"
$setup = Join-Path $Root "desktop\src-tauri\target\release\bundle\nsis\PlanSeed_0.1.0_x64-setup.exe"
$printIdx = Join-Path $Root "debug\print-smoke\index.html"

Write-Host ""
Write-Host "Assets:"
Write-Host "  .planseed: $pkg"
if (Test-Path $setup) {
    Write-Host "  installer: $setup"
} else {
    Write-Host "  installer: MISSING (run build_installer.ps1)"
}
if (Test-Path $printIdx) {
    Write-Host "  print-smoke: $printIdx"
} else {
    Write-Host "  print-smoke: run generate_print_smoke_reports.py"
}

Write-Host ""
Write-Host "Next: docs/alpha-v0.1-desktop-hand-gate.md"
