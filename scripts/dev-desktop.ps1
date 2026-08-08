# 一键开发：本地引擎 + Vite（Windows）
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
if (-not $env:PLANSEED_PORT) { $env:PLANSEED_PORT = "8787" }
if (-not $env:PLANSEED_HOST) { $env:PLANSEED_HOST = "127.0.0.1" }
node "$Root\scripts\dev-desktop.mjs"
