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
