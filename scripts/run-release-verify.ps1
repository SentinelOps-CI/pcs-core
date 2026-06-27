# PCS v0.1 release verification (Windows). Run from repo root.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$py = Join-Path $root "python"
$failed = @()

function Step($name, [scriptblock]$block) {
    Write-Host "`n=== $name ===" -ForegroundColor Cyan
    try {
        & $block
        if ($LASTEXITCODE -ne 0 -and $null -ne $LASTEXITCODE) { throw "exit $LASTEXITCODE" }
        Write-Host "OK $name" -ForegroundColor Green
    } catch {
        Write-Host "FAIL $name : $_" -ForegroundColor Red
        $script:failed += $name
    }
}

Set-Location $py
pip install -e ".[dev]" -q | Out-Null

Step "schema check" { pcs schema check }
Step "examples check" { pcs examples check }
Step "hash vectors" { python -m pcs_core.hash_vectors --verify }
Step "shared hash vectors" { pcs shared-hash-vectors verify }
Step "labtrust release chain" { pcs validate-release-chain ../examples/labtrust-release/ }
Step "tool-use release chain" { pcs validate-release-chain ../examples/tool-use-release/ }
Step "computation release chain" { pcs validate-release-chain ../examples/computation-release/ }
Step "labtrust release manifest" { pcs validate ../examples/labtrust-release/release_manifest.v0.json }
Step "registry validate" { pcs registry validate ../examples/artifact_registry.valid.json }
Step "registry audit" { pcs registry audit }
Step "benchmark validate" { pcs benchmark validate }
Step "benchmark ingest release-grade" { pcs benchmark validate-ingest --release-grade }
Step "validate benchmark ingest script" { python ../scripts/validate_benchmark_ingest_examples.py --release-grade }
Step "conformance benchmark-ingest" { pcs conformance run --suite benchmark-ingest }
Step "conformance benchmark-report" { pcs conformance run --suite benchmark-report }
Step "conformance benchmark" { pcs conformance run --suite benchmark }
Step "conformance computation" { pcs conformance run --suite computation }
Step "conformance multidomain" { pcs conformance run --suite multidomain }
Step "conformance all" { pcs conformance run --suite all }
Step "labtrust conformance pytest" { pytest -q tests/test_labtrust_conformance.py }
Step "multidomain pytest" { pytest -q tests/test_multidomain_workflows.py }
Step "pytest" { pytest -q }
Step "pytest protocol" { pytest -q tests/test_protocol_conformance.py tests/test_benchmark_ingest_contract.py tests/test_release_chain.py }

@(
    "labtrust-qc-release-v0",
    "tool-use-safety-v0",
    "computation-reproducibility-v0",
    "scientific-memory-rendering-v0",
    "formal-trust-kernel-v0",
    "cross-domain-release-chain-v0"
) | ForEach-Object {
    $suite = $_
    Step "benchmark run $suite" { pcs benchmark run --suite $suite }
}

Step "materialize benchmark examples" { python scripts/materialize_benchmark_examples.py }
Step "materialize benchmark ingest" { python scripts/materialize_benchmark_producer_examples.py }

Set-Location (Join-Path $root "rust")
Step "rust test" { cargo test -q }
Step "rust shared hash vectors" { cargo test shared_hash_vectors -q }
Step "rust fmt" { cargo fmt --check }
Step "rust clippy" { cargo clippy --all-targets -- -D warnings }

Set-Location (Join-Path $root "typescript")
Step "typescript test" { npm install --silent 2>$null; npm test --silent }
Step "typescript hash vectors" { npm run test:hash-vectors -w @pcs/core --silent }

Set-Location $py
Step "ruff check" { ruff check pcs_core tests }
Step "ruff format" { ruff format --check pcs_core tests }

$bash = Get-Command bash -ErrorAction SilentlyContinue
if ($bash) {
    Step "pcs schema diff" {
        Push-Location $root
        bash ./scripts/pcs-schema-diff.sh schemas
        Pop-Location
    }
} else {
    Write-Host "SKIP pcs schema diff (bash not available)" -ForegroundColor Yellow
}

Write-Host "`n=== Summary ===" -ForegroundColor Cyan
if ($failed.Count -eq 0) {
    Write-Host "All steps passed." -ForegroundColor Green
    exit 0
}
Write-Host "Failed: $($failed -join ', ')" -ForegroundColor Red
exit 1
