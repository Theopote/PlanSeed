# Alpha v0.1 — NSIS 静默安装 + 装包 sidecar 引擎 smoke（Gate B 半自动）
# B1（Desktop 窗口自启引擎）仍须手测；本脚本覆盖 B3 装包引擎路径。
#
# Usage:
#   powershell -File scripts/installer_release_smoke.ps1
#   powershell -File scripts/installer_release_smoke.ps1 -RebuildInstaller

param(
    [switch]$RebuildInstaller,
    [string]$InstallDir = "",
    [int]$Port = 8798
)

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\_release_path.ps1"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$Setup = Join-Path $Root "desktop\src-tauri\target\release\bundle\nsis\PlanSeed_0.1.0_x64-setup.exe"

if ($RebuildInstaller) {
    & "$PSScriptRoot\build_installer.ps1"
}

if (-not (Test-Path $Setup)) {
    throw "NSIS setup missing: $Setup`nRun: powershell -File scripts/build_installer.ps1"
}

if (-not $InstallDir) {
    $InstallDir = Join-Path $env:TEMP "PlanSeedReleaseSmoke-$([Guid]::NewGuid().ToString('N').Substring(0,8))"
}

if (Test-Path $InstallDir) {
    Remove-Item -Recurse -Force $InstallDir
}
New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null

Write-Host "== Installer release smoke =="
Write-Host "Setup: $Setup"
Write-Host "InstallDir: $InstallDir"

$setupArgs = "/S", "/D=$InstallDir"
$p = Start-Process -FilePath $Setup -ArgumentList $setupArgs -Wait -PassThru -NoNewWindow
if ($p.ExitCode -ne 0) {
    throw "NSIS setup failed with exit $($p.ExitCode)"
}

$backendExe = Get-ChildItem -Path $InstallDir -Recurse -Filter "planseed-backend.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $backendExe) {
    throw "planseed-backend.exe not found under $InstallDir"
}
Write-Host "OK: installed backend $($backendExe.FullName)"

$env:PLANSEED_HOST = "127.0.0.1"
$env:PLANSEED_PORT = "$Port"

$proc = Start-Process -FilePath $backendExe.FullName -WorkingDirectory $backendExe.DirectoryName -PassThru -WindowStyle Hidden
try {
    $deadline = (Get-Date).AddSeconds(60)
    $ready = $false
    while ((Get-Date) -lt $deadline) {
        try {
            $health = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/health" -Method Get -TimeoutSec 3
            if ($health.ok -eq $true -and $health.service -eq "planseed") {
                $ready = $true
                break
            }
        } catch {
            Start-Sleep -Milliseconds 500
        }
    }
    if (-not $ready) {
        throw "Installed backend not ready on port $Port within 60s"
    }
    Write-Host "OK: installed backend health on port $Port"

    uv run python scripts/alpha_release_engine_smoke.py
    if ($LASTEXITCODE -ne 0) {
        throw "alpha_release_engine_smoke.py failed"
    }
}
finally {
    if ($null -ne $proc -and -not $proc.HasExited) {
        Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
    }
    Remove-Item Env:PLANSEED_PORT -ErrorAction SilentlyContinue
    if (Test-Path $InstallDir) {
        Remove-Item -Recurse -Force $InstallDir -ErrorAction SilentlyContinue
    }
}

Write-Host "== installer release smoke passed =="
Write-Host "Manual still required:"
Write-Host "  B1) Desktop app window -> engine READY"
Write-Host "  A)  WebView2 Print"
Write-Host "  C)  Desktop .planseed file picker roundtrip"
