# Step 1 helper: launch PlanSeed Desktop and poll engine health (Gate B1)
# Usage:
#   powershell -File scripts/desktop_b1_watch.ps1
#   powershell -File scripts/desktop_b1_watch.ps1 -ExePath "C:\path\app.exe"
#
# NSIS silent install to custom /D= often yields app.exe (not PlanSeed.exe).

param(
    [string]$ExePath = "",
    [int]$Port = 8796,
    [int[]]$Ports = @(),
    [switch]$StrictPort,
    [int]$WaitSeconds = 120
)

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\_release_path.ps1"

if ($StrictPort) {
    $Ports = @($Port)
} elseif ($Ports.Count -eq 0) {
    $Ports = @($Port, 8787, 8788, 8789, 8790, 8791)
}
$env:PLANSEED_HOST = "127.0.0.1"
$env:PLANSEED_PORT = "$Port"

function Find-DesktopExe {
    param([string]$RootSearch = "")
    $names = @("PlanSeed.exe", "app.exe")
    $roots = @(
        "$env:LOCALAPPDATA\Programs\PlanSeed",
        "$env:LOCALAPPDATA\Programs\com.planseed.app",
        (Join-Path $PSScriptRoot "..\desktop\src-tauri\target\release"),
        $RootSearch
    ) | Where-Object { $_ -and (Test-Path $_) }

    foreach ($root in $roots) {
        foreach ($name in $names) {
            $p = Join-Path $root $name
            if (Test-Path $p) { return (Resolve-Path $p).Path }
        }
        $hit = Get-ChildItem -Path $root -Recurse -Include $names -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($hit) { return $hit.FullName }
    }
    $found = Get-ChildItem -Path "$env:LOCALAPPDATA\Programs" -Recurse -Include $names -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($found) { return $found.FullName }
    return $null
}

if ($ExePath) {
    if (-not (Test-Path $ExePath)) { throw "Desktop exe not found: $ExePath" }
    $exe = (Resolve-Path $ExePath).Path
} else {
    $exe = Find-DesktopExe
    if (-not $exe) {
        throw "Desktop exe not found. Install NSIS setup first or pass -ExePath."
    }
}

Write-Host "== Desktop B1 watch =="
Write-Host "Exe: $exe"
Write-Host "Polling ports: $($Ports -join ', ') for up to ${WaitSeconds}s"
Write-Host ""

$proc = Start-Process -FilePath $exe -PassThru
$deadline = (Get-Date).AddSeconds($WaitSeconds)
$hitPort = $null
$health = $null

while ((Get-Date) -lt $deadline) {
    foreach ($port in $Ports) {
        try {
            $h = Invoke-RestMethod -Uri "http://127.0.0.1:$port/api/health" -Method Get -TimeoutSec 2
            if ($h.ok -eq $true -and $h.service -eq "planseed") {
                $hitPort = $port
                $health = $h
                break
            }
        } catch { }
    }
    if ($hitPort) { break }
    if ($proc.HasExited) {
        throw "Desktop exe exited early (exit $($proc.ExitCode))"
    }
    Start-Sleep -Seconds 2
}

if (-not $hitPort) {
    Write-Host "FAIL: no planseed health on ports $($Ports -join ', ') within ${WaitSeconds}s"
    Write-Host "Check Desktop left panel engine status and Tauri app_log_dir engine.log"
    exit 1
}

Write-Host "OK: engine health on port $hitPort"
Write-Host "  service=$($health.service) engine_version=$($health.engine_version)"
Write-Host "  api_version=$($health.api_version)"
Write-Host ""
Write-Host "Manual B1 checks still required in Desktop UI:"
Write-Host "  [ ] Left panel shows engine READY (no STARTING->ERROR->READY flicker)"
Write-Host "  [ ] Retry Engine -> back to READY"
Write-Host ""
Write-Host "Desktop PID: $($proc.Id) (leave running for Print / .planseed steps)"
Write-Host "Engine base URL: http://127.0.0.1:$hitPort"
$env:PLANSEED_PORT = "$hitPort"
exit 0
