# Gate B-Desktop semi-auto: NSIS silent install -> launch app.exe -> health poll
# Does NOT replace UI checks (READY label, Retry Engine).
#
# Usage:
#   powershell -File scripts/desktop_shell_smoke.ps1

param(
    [switch]$RebuildInstaller,
    [string]$InstallDir = "",
    [int]$Port = 8796,
    [int]$WaitSeconds = 120
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
    throw "NSIS setup missing: $Setup"
}

if (-not $InstallDir) {
    $InstallDir = Join-Path $env:TEMP "PlanSeedDesktopSmoke-$([Guid]::NewGuid().ToString('N').Substring(0,8))"
}
if (Test-Path $InstallDir) {
    Remove-Item -Recurse -Force $InstallDir
}
New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null

Write-Host "== Desktop shell smoke =="
Write-Host "InstallDir: $InstallDir"

$p = Start-Process -FilePath $Setup -ArgumentList @("/S", "/D=$InstallDir") -Wait -PassThru -NoNewWindow
if ($p.ExitCode -ne 0) {
    throw "NSIS setup failed exit $($p.ExitCode)"
}

$desktopExe = @(
    (Join-Path $InstallDir "PlanSeed.exe"),
    (Join-Path $InstallDir "app.exe")
) | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not $desktopExe) {
    $desktopExe = Get-ChildItem -Path $InstallDir -Recurse -Include "PlanSeed.exe", "app.exe" -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -ne "uninstall.exe" } |
        Select-Object -First 1 -ExpandProperty FullName
}
if (-not $desktopExe) {
    throw "Desktop exe not found under $InstallDir"
}
Write-Host "OK: desktop exe $desktopExe"

& "$PSScriptRoot\desktop_b1_watch.ps1" -ExePath $desktopExe -Port $Port -WaitSeconds $WaitSeconds
if ($LASTEXITCODE -ne 0) {
    throw "desktop_b1_watch failed"
}

Write-Host ""
Write-Host "== desktop shell smoke (health) passed =="
Write-Host "Cleanup: stop Desktop PID manually; remove $InstallDir when done."
