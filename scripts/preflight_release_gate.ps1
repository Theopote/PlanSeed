# Alpha v0.1 Release Gate 预检 — 工具链 / 产物 / 自动化状态
# Usage: pwsh scripts/preflight_release_gate.ps1

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\_release_path.ps1"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Show-Tool([string]$name) {
    $cmd = Get-Command $name -ErrorAction SilentlyContinue
    if ($cmd) {
        $ver = try { & $name --version 2>$null | Select-Object -First 1 } catch { "ok" }
        Write-Host ("  [OK]   {0,-8} {1}" -f $name, $ver)
        return $true
    }
    Write-Host ("  [MISS] {0}" -f $name)
    return $false
}

function Show-File([string]$label, [string]$path) {
    if (Test-Path $path) {
        $fi = Get-Item $path
        Write-Host ("  [OK]   {0} ({1:N0} bytes, {2})" -f $label, $fi.Length, $fi.LastWriteTime.ToString("yyyy-MM-dd HH:mm"))
        return $true
    }
    Write-Host ("  [MISS] {0}" -f $label)
    return $false
}

Write-Host "== Alpha v0.1 Release Gate Preflight =="
Write-Host ""
Write-Host "-- Toolchain --"
$toolsOk = @(
    (Show-Tool "uv"),
    (Show-Tool "node"),
    (Show-Tool "pnpm"),
    (Show-Tool "cargo")
) -notcontains $false

Write-Host ""
Write-Host "-- Build artifacts --"
$sidecar = Join-Path $Root "desktop\src-tauri\resources\planseed-backend\planseed-backend.exe"
$setup = Join-Path $Root "desktop\src-tauri\target\release\bundle\nsis\PlanSeed_0.1.0_x64-setup.exe"
$printIdx = Join-Path $Root "debug\print-smoke\index.html"
$hasSidecar = Show-File "sidecar exe" $sidecar
$hasSetup = Show-File "NSIS setup" $setup
$hasPrint = Show-File "print-smoke index" $printIdx

if ($hasSetup) {
    $age = (Get-Date) - (Get-Item $setup).LastWriteTime
    if ($age.TotalDays -gt 2) {
        Write-Host "  [WARN] NSIS setup is older than 2 days — rebuild before release: pwsh scripts/build_installer.ps1"
    }
}

Write-Host ""
Write-Host "-- Suggested commands --"
Write-Host "  Automated:  powershell -File scripts/alpha_release_gate_automated.ps1"
Write-Host "  Sidecar:    powershell -File scripts/sidecar_release_smoke.ps1"
Write-Host "  Print prep: powershell -File scripts/open_print_smoke.ps1"
Write-Host "  Desktop:    powershell -File scripts/desktop_shell_smoke.ps1"
Write-Host "  Hand prep:  powershell -File scripts/prepare_desktop_hand_gate.ps1"
if (-not $hasSetup -and $toolsOk) {
    Write-Host "  Build:      powershell -File scripts/build_installer.ps1"
}

Write-Host ""
Write-Host "-- Manual Release Gate (still required) --"
Write-Host "  A) Desktop WebView2 Print (docs/alpha-v0.1-hand-smoke.md §A)"
Write-Host "  B) Install NSIS setup + engine READY smoke"
Write-Host "  C) Desktop .planseed export/import roundtrip"

if (-not $toolsOk -or -not $hasSidecar) {
    exit 1
}
exit 0
