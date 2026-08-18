# Dot-source: 补全 Release Gate 常见工具 PATH（嵌套 PowerShell 常缺失）
$script:ReleasePathCandidates = @(
    (Join-Path $env:USERPROFILE ".cargo\bin"),
    (Join-Path $env:APPDATA "npm"),
    "C:\Program Files\nodejs"
)
foreach ($dir in $script:ReleasePathCandidates) {
    if ((Test-Path $dir) -and ($env:Path -notlike "*$dir*")) {
        $env:Path = "$dir;$env:Path"
    }
}

function Get-PlanSeedNsisSetup([string]$RepoRoot) {
    $nsisDir = Join-Path $RepoRoot "desktop\src-tauri\target\release\bundle\nsis"
    $setup = Get-ChildItem -Path $nsisDir -Filter "*-setup.exe" -ErrorAction SilentlyContinue |
        Sort-Object Name -Descending |
        Select-Object -First 1
    if (-not $setup) {
        throw "NSIS setup missing under $nsisDir`nRun: powershell -File scripts/build_installer.ps1"
    }
    return $setup.FullName
}
