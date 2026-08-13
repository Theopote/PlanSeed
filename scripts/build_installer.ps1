# Alpha v0.1 — Windows 安装包构建（NSIS）
# 前置：Rust toolchain · pnpm · Node.js · uv
#
# Usage:
#   pwsh scripts/build_installer.ps1
#   pwsh scripts/build_installer.ps1 -SkipSidecar

param(
    [switch]$SkipSidecar
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Require-Command([string]$name, [string]$hint) {
    $cmd = Get-Command $name -ErrorAction SilentlyContinue
    if (-not $cmd) {
        throw "Missing $name. $hint"
    }
    return $cmd.Source
}

Write-Host "== PlanSeed Windows installer build =="

Require-Command "uv" "Install uv: https://docs.astral.sh/uv/"
Require-Command "node" "Install Node.js LTS"
$pnpm = Get-Command "pnpm" -ErrorAction SilentlyContinue
if (-not $pnpm) {
    $corepack = Get-Command "corepack" -ErrorAction SilentlyContinue
    if ($corepack) {
        Write-Host "[installer] enabling pnpm via corepack..."
        & corepack enable
        & corepack prepare pnpm@latest --activate
    } else {
        throw "Missing pnpm. Run: npm install -g pnpm  (or enable corepack)"
    }
}
Require-Command "cargo" "Install Rust: https://rustup.rs/"
Require-Command "pnpm" "Install pnpm"

if (-not $SkipSidecar) {
    & "$PSScriptRoot\build_backend_sidecar.ps1"
}

$sidecar = Join-Path $Root "desktop\src-tauri\resources\planseed-backend\planseed-backend.exe"
if (-not (Test-Path $sidecar)) {
    throw "Sidecar missing after build: $sidecar"
}

Write-Host "[installer] pnpm install (desktop)..."
Push-Location (Join-Path $Root "desktop")
try {
    pnpm install --frozen-lockfile
    Write-Host "[installer] tauri build (NSIS)..."
    pnpm tauri:build
}
finally {
    Pop-Location
}

$nsis = Get-ChildItem -Path (Join-Path $Root "desktop\src-tauri\target\release\bundle\nsis") -Filter "*-setup.exe" -ErrorAction SilentlyContinue
if (-not $nsis) {
    throw "NSIS setup.exe not found under desktop/src-tauri/target/release/bundle/nsis/"
}

Write-Host ""
Write-Host "== installer built =="
Write-Host $nsis.FullName
Write-Host ""
Write-Host "Next (Release Gate B):"
Write-Host "  1) Install setup.exe"
Write-Host "  2) pwsh scripts/windows_alpha_smoke.ps1"
Write-Host "  3) pwsh scripts/sidecar_release_smoke.ps1   # optional if using dev uv engine only"
