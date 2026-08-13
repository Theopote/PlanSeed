# Open Phase 7.1.1 print smoke HTML (Edge reference; gate closes in Desktop WebView2)
# Usage: powershell -File scripts/open_print_smoke.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Index = Join-Path $Root "debug\print-smoke\index.html"

if (-not (Test-Path $Index)) {
    Write-Host "Generating print-smoke fixtures..."
    Set-Location $Root
    uv run python scripts/generate_print_smoke_reports.py
}

if (-not (Test-Path $Index)) {
    throw "Missing $Index"
}

Write-Host "Opening $Index"
Start-Process $Index

Write-Host ""
Write-Host "Hand-test Release Gate A:"
Write-Host "  1) Edge reference: Print -> Microsoft Print to PDF"
Write-Host "  2) Gate close: Desktop report preview -> Print/PDF (iframe.print)"
Write-Host "  3) At least P02 + P06; record in docs/phase-7.1-print-smoke.md"
