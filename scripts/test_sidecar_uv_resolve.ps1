# 回归：单元素 Where-Object 结果不得被 [0] 取成首字符
# 用法：powershell -NoProfile -File scripts/test_sidecar_uv_resolve.ps1
$ErrorActionPreference = "Stop"

function Resolve-UvCandidate([string[]]$paths) {
  $candidates = @(@($paths) | Where-Object { $_ -and $_.Length -gt 0 })
  if ($candidates.Count -lt 1) {
    throw "no candidates"
  }
  $uv = [string]$candidates[0]
  if ($uv.Length -lt 2) {
    throw "scalar/array bug: got single char '$uv'"
  }
  if (-not ($uv -match '(?i)(^|[\\/])uv(\.exe)?$')) {
    throw "not an uv path: $uv"
  }
  return $uv
}

$single = Resolve-UvCandidate @("C:\Users\ci\.local\bin\uv.exe")
if ($single -ne "C:\Users\ci\.local\bin\uv.exe") {
  throw "single-element resolve failed: $single"
}

$multi = Resolve-UvCandidate @(
  "C:\Users\ci\.local\bin\uv.exe",
  "C:\Users\ci\.cargo\bin\uv.exe"
)
if ($multi -ne "C:\Users\ci\.local\bin\uv.exe") {
  throw "multi-element resolve failed: $multi"
}

try {
  Resolve-UvCandidate @("C:\not-uv.exe") | Out-Null
  throw "expected non-uv path to fail"
} catch {
  if ("$_" -notmatch "not an uv path") { throw }
}

Write-Host "[ok] sidecar uv resolve regression passed"
