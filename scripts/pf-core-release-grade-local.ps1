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

function Assert-NoTrivialCertificateAggregates($proofPath) {
    if (-not (Test-Path $proofPath)) { return }
    $text = Get-Content $proofPath -Raw
    if ($text -match ":\s*True\s*:=\s*trivial") {
        throw "generated proof contains trivial aggregate: $proofPath"
    }
}

Set-Location $py
pip install -e ".[dev]" -q | Out-Null

Step "pf-core all pytest" {
    $pfTests = Get-ChildItem "tests\test_pf_core_*.py" | ForEach-Object { $_.FullName }
    pytest -q @pfTests
}
Step "pf-core certificate-mode codegen pytest" { pytest -q tests/test_pf_core_certificate_mode_codegen.py }
Step "pf-core catalog tool_map pytest" { pytest -q tests/test_pf_core_catalog_tool_map.py }
Step "pf-core conformance release-grade" { pcs conformance run --suite pf-core --release-grade }
Step "pf-core cross-language conformance" { pcs conformance run --suite pf-core-cross-language }

Step "PF-Core catalog drift check" {
    python scripts/gen_pf_core_catalog.py
    git diff --exit-code `
        (Join-Path $root "python\pcs_core\pf_core_catalog.py") `
        (Join-Path $root "lean\PFCore\Catalog.lean") `
        (Join-Path $root "rust\crates\pcs-core\src\pf_core_catalog.rs") `
        (Join-Path $root "typescript\packages\core\src\pfCoreCatalog.ts")
    $action = Join-Path $root "lean\PFCore\Action.lean"
    if (Select-String -Path $action -Pattern '\("cap:file-read", Effect.read\)' -Quiet) {
        throw "hand-maintained knownCapabilityEffectCatalog entries found in Action.lean"
    }
    $codegen = Join-Path $root "python\pcs_core\pf_core_lean_codegen.py"
    if (Select-String -Path $codegen -Pattern 'EFFECT_KIND_TO_LEAN: dict\[str, str\] = \{' -Quiet) {
        throw "manual EFFECT_KIND_TO_LEAN table found in pf_core_lean_codegen.py"
    }
}

Step "pf-core audit-lean-no-sorry" { pcs pf-core audit-lean-no-sorry }

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
    Step "lake build PCS" {
        Push-Location (Join-Path $root "lean")
        lake build PCS
        Pop-Location
    }
    Step "pf-core lean-check full (TraceSafeRCertificate default)" {
        pcs pf-core lean-check --trace $trace --out $certFile --release-grade
    }
    if (Test-Path $certFile) {
        Step "verify TraceSafeRCertificate + substantive proof" {
            $cert = Get-Content $certFile -Raw | ConvertFrom-Json
            if ($cert.certificate_mode -ne "TraceSafeRCertificate") {
                throw "expected TraceSafeRCertificate, got $($cert.certificate_mode)"
            }
            $proofRef = $cert.proof_term_ref
            if (-not $proofRef) { throw "certificate missing proof_term_ref" }
            $proofPath = Join-Path $root ($proofRef -replace "/", "\")
            Assert-NoTrivialCertificateAggregates $proofPath
            $hasTraceSafeR = $false
            foreach ($ob in $cert.obligations) {
                if ($ob.theorem -eq "concrete_trace_safe_r") { $hasTraceSafeR = $true }
            }
            if (-not $hasTraceSafeR) { throw "certificate missing concrete_trace_safe_r obligation" }
        }
        Step "pf-core verify-proof-binding" {
            pcs pf-core verify-proof-binding --certificate $certFile --trace $trace
        }
        Step "pf-core bundle-release" {
            if (Test-Path $bundleDir) { Remove-Item -Recurse -Force $bundleDir }
            pcs pf-core bundle-release --trace $trace --cert $certFile --out $bundleDir
        }
        Step "pf-core validate-bundle (kernel manifest + hashes)" {
            pcs pf-core validate-bundle $bundleDir
            $manifest = Get-Content (Join-Path $bundleDir "manifest.json") -Raw | ConvertFrom-Json
            if ($manifest.certificate_mode -ne "TraceSafeRCertificate") {
                throw "bundle manifest certificate_mode not TraceSafeRCertificate"
            }
            if (-not (Test-Path (Join-Path $bundleDir "kernel_manifest.json"))) {
                throw "bundle missing kernel_manifest.json"
            }
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
Write-Host "=== CertifyEdge release-gate matrix (mock + stub) ===" -ForegroundColor Cyan
try {
    & (Join-Path $root "scripts\pf-core-certifyedge-dry-run.ps1")
    Write-Host "OK CertifyEdge mock dry-run" -ForegroundColor Green
} catch {
    Write-Host "FAIL CertifyEdge mock dry-run : $_" -ForegroundColor Red
    $failed += "CertifyEdge mock dry-run"
}

try {
    & (Join-Path $root "scripts\pf-core-certifyedge-stub-dry-run.ps1")
    Write-Host "OK CertifyEdge stub dry-run" -ForegroundColor Green
} catch {
    Write-Host "FAIL CertifyEdge stub dry-run : $_" -ForegroundColor Red
    $failed += "CertifyEdge stub dry-run"
}

Write-Host ""
Write-Host "=== Summary ===" -ForegroundColor Cyan
if ($failed.Count -eq 0) {
    Write-Host "All PF-Core release-grade local steps passed." -ForegroundColor Green
    exit 0
}
Write-Host "Failed: $($failed -join ', ')" -ForegroundColor Red
exit 1
