# Alpha v0.1 — 对已打包 PyInstaller sidecar 做 engine smoke（无需 NSIS / Tauri）
# 验证装包引擎路径：resvg PNG · SVG · report · .planseed
#
# Usage:
#   pwsh scripts/sidecar_release_smoke.ps1
#   pwsh scripts/sidecar_release_smoke.ps1 -RebuildSidecar
#
# 前置：desktop/src-tauri/resources/planseed-backend/planseed-backend.exe
#       （pwsh scripts/build_backend_sidecar.ps1）

param(
    [switch]$RebuildSidecar,
    [int]$Port = 8799
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$SidecarExe = Join-Path $Root "desktop\src-tauri\resources\planseed-backend\planseed-backend.exe"
if ($RebuildSidecar) {
    & "$PSScriptRoot\build_backend_sidecar.ps1"
}

if (-not (Test-Path $SidecarExe)) {
    throw "Sidecar missing: $SidecarExe`nRun: pwsh scripts/build_backend_sidecar.ps1"
}

Write-Host "== Sidecar release smoke (port $Port) =="

$env:PLANSEED_HOST = "127.0.0.1"
$env:PLANSEED_PORT = "$Port"

$proc = Start-Process -FilePath $SidecarExe -WorkingDirectory (Split-Path $SidecarExe) -PassThru -WindowStyle Hidden
try {
    $deadline = (Get-Date).AddSeconds(45)
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
        throw "Sidecar did not become ready on port $Port within 45s"
    }
    Write-Host "OK: sidecar health on port $Port"

    uv run python scripts/alpha_release_engine_smoke.py
    if ($LASTEXITCODE -ne 0) {
        throw "alpha_release_engine_smoke.py failed against sidecar"
    }
}
finally {
    if ($null -ne $proc -and -not $proc.HasExited) {
        Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 1
    }
    Remove-Item Env:PLANSEED_PORT -ErrorAction SilentlyContinue
}

Write-Host "== sidecar release smoke passed =="
