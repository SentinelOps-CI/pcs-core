# PF-Core release-grade local verification (Windows native). Run from repository root.
# No git operations. Requires native `lake` on PATH when Lean steps are enabled.
$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $PSScriptRoot
$py = Join-Path $root "python"
$trace = Join-Path $root "examples\pf-core-valid\tool_use_trace_compiled\pfcore_trace.json"
$failed = @()

function Step($name, [scriptblock]$block) {
    Write-Host ""
    Write-Host "=== $name ===" -ForegroundColor Cyan
    try {
        & $block
        if ($LASTEXITCODE -ne 0 -and $null -ne $LASTEXITCODE) { throw "exit $LASTEXITCODE" }
        Write-Host "OK $name" -ForegroundColor Green
    } catch {
        Write-Host "FAIL $name : $_" -ForegroundColor Red
        $script:failed += $name
    }
}

function Test-LakeAvailable {
    return $null -ne (Get-Command lake -ErrorAction SilentlyContinue)
}

Set-Location $py
pip install -e ".[dev]" -q | Out-Null

Step "pf-core cross-language pytest" { pytest -q tests/test_pf_core_cross_language.py }
Step "pf-core tier1 pytest" { pytest -q tests/test_pf_core_tier1.py }
Step "pf-core compositional pytest" { pytest -q tests/test_pf_core_compositional.py }
Step "pf-core research pytest" { pytest -q tests/test_pf_core_research.py tests/test_pf_core_research_grade.py }
Step "pf-core observational pytest" { pytest -q tests/test_pf_core_observational.py }
Step "pf-core phase F pytest" { pytest -q tests/test_pf_core_phase_f.py }
Step "pf-core conformance release-grade" { pcs conformance run --suite pf-core --release-grade }
Step "pf-core cross-language conformance" { pcs conformance run --suite pf-core-cross-language }

$certFile = Join-Path $env:TEMP "pfcore-release-grade-cert.json"
$bundleDir = Join-Path $env:TEMP "pfcore-release-grade-bundle"

Write-Host ""
Write-Host "=== PF-Core LeanKernelChecked path (when native lake available) ===" -ForegroundColor Cyan
if (Test-LakeAvailable) {
    Step "lake build PFCore" {
        Push-Location (Join-Path $root "lean")
        lake build PFCore
        Pop-Location
    }
    Step "pf-core lean-check full" {
        pcs pf-core lean-check --trace $trace --out $certFile
    }
    if (Test-Path $certFile) {
        Step "pf-core verify-proof-binding" {
            pcs pf-core verify-proof-binding --certificate $certFile --trace $trace
        }
        Step "pf-core bundle-release" {
            pcs pf-core bundle-release --trace $trace --cert $certFile --out $bundleDir
        }
        Step "pf-core validate-bundle" {
            pcs pf-core validate-bundle $bundleDir
        }
    } else {
        Write-Host "FAIL pf-core verify-proof-binding (certificate missing)" -ForegroundColor Red
        $failed += "pf-core verify-proof-binding"
    }
} else {
    Write-Host "SKIP Lean path: lake not on PATH (install elan/lake or see docs/pf-core/windows-lean.md)" -ForegroundColor Yellow
    $failed += "PF-Core Lean path (lake unavailable)"
}

Set-Location (Join-Path $root "rust")
Step "rust pf_core tests" { cargo test pf_core -q }

Write-Host ""
Write-Host "=== CertifyEdge release-gate dry-run (mock) ===" -ForegroundColor Cyan
try {
    & (Join-Path $root "scripts\pf-core-certifyedge-dry-run.ps1")
    Write-Host "OK CertifyEdge dry-run" -ForegroundColor Green
} catch {
    Write-Host "FAIL CertifyEdge dry-run : $_" -ForegroundColor Red
    $failed += "CertifyEdge dry-run"
}

Write-Host ""
Write-Host "=== Summary ===" -ForegroundColor Cyan
if ($failed.Count -eq 0) {
    Write-Host "All PF-Core release-grade local steps passed." -ForegroundColor Green
    exit 0
}
Write-Host "Failed: $($failed -join ', ')" -ForegroundColor Red
exit 1
